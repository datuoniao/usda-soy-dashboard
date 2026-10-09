# -*- coding: utf-8 -*-
"""USDA NASS《Crop Progress》作物生长报告取数（周度）。

数据源：ESMIS 归档的 Crop Progress 纯文本周报
        https://esmis.nal.usda.gov/publication/crop-progress?date=YYYY-MM

抽取 8 个指标（均取报表中的 "18 States" 全国合计行）：
  ge_pct              优良率 = Good + Excellent（%）
  vp_pct              差劣率 = Very poor + Poor（%）
  planted_pct         播种进度（%）
  emerged_pct         出芽进度（%）
  blooming_pct        开花进度（%）
  setting_pods_pct    结荚进度（%）
  dropping_leaves_pct 落叶进度（%）
  harvested_pct       收获进度（%）

进度表的列序为「去年同期 / 上周 / 本周 / 五年均值」，故本周取第 3 个数值。
优良率表的列序为「Very poor / Poor / Fair / Good / Excellent」。
报表冬季不含大豆相关表，缺失项留空。

用法：
  python scripts/fetch_crop_progress.py          # 增量：只刷新最近若干周并合并
  python scripts/fetch_crop_progress.py --full   # 全量回填（自 START_YEAR 起）
"""
import csv
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
DATA = os.path.join(ROOT, "data")
TXT_DIR = os.path.join(RAW, "crop_progress_txt")
CSV_PATH = os.path.join(DATA, "crop_progress.csv")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE = "https://esmis.nal.usda.gov"
PUB = "crop-progress"

START_YEAR = 2018          # --full 回填起始年
MONTHS = range(4, 12)      # 大豆相关表只出现在 4–11 月的报告里
REFRESH_MONTHS = 6         # 增量模式回看的月数
WORKERS = 8                # ESMIS 单次请求较慢（数秒），必须并发
FIELDS = ["week_ending", "ge_pct", "vp_pct", "planted_pct", "emerged_pct",
          "blooming_pct", "setting_pods_pct", "dropping_leaves_pct",
          "harvested_pct"]

# 各进度指标对应的报表表名（表名 -> 输出列）
PROGRESS_TABLES = (
    ("Soybeans Planted - Selected States", "planted_pct"),
    ("Soybeans Emerged - Selected States", "emerged_pct"),
    ("Soybeans Blooming - Selected States", "blooming_pct"),
    ("Soybeans Setting Pods - Selected States", "setting_pods_pct"),
    ("Soybeans Dropping Leaves - Selected States", "dropping_leaves_pct"),
    ("Soybeans Harvested - Selected States", "harvested_pct"),
)


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def list_month(ym):
    """返回该月的 [(发布日期, txt_url), ...]"""
    html = get(f"{BASE}/publication/{PUB}?date={ym}").decode("utf-8", "ignore")
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        t = re.search(r'<time datetime="([^"]+)"', row)
        h = re.search(r'href="(/sites/default/release-files/[^"]+\.txt)"', row, re.I)
        if t and h and t.group(1)[:7] == ym:
            out.append((t.group(1)[:10], BASE + h.group(1)))
    return out


def _nums(s):
    """把 '4 10 29 46 11' 或 '(NA) 17 25 33' 解析为 [None|float, ...]"""
    vals = []
    for tok in s.replace(":", " ").split():
        vals.append(None if "NA" in tok.upper() else float(tok))
    return vals


def _agg_row(txt, title_prefix, ncols):
    """在 title_prefix 对应的表格内定位 '18 States' 行，返回数值列表。"""
    i = txt.find(title_prefix)
    if i < 0:
        return None
    for line in txt[i:i + 4000].splitlines():
        if line.startswith("18 States"):
            v = _nums(line.split(":")[-1])
            return v if len(v) >= ncols else None
    return None


def parse_report(txt):
    """解析一份周报，返回本行 dict（缺失字段为 None）。"""
    rec = {k: None for k in FIELDS}

    m = re.search(r"Soybean Condition - Selected States:\s*Week Ending\s*"
                  r"([A-Z][a-z]+ \d{1,2}, \d{4})", txt)
    if m:
        import datetime
        d = datetime.datetime.strptime(m.group(1), "%B %d, %Y").date()
        rec["week_ending"] = d.isoformat()
        v = _agg_row(txt, "Soybean Condition - Selected States", 5)
        if v:
            rec["vp_pct"] = (v[0] or 0) + (v[1] or 0)
            rec["ge_pct"] = (v[3] or 0) + (v[4] or 0)

    for pref, key in PROGRESS_TABLES:
        v = _agg_row(txt, pref, 4)
        if v and v[2] is not None:
            rec[key] = v[2]      # 第 3 列 = 本周

    return rec


def week_ending_from_release(release_date):
    """无 Condition 表时（生长季早期报告），取发布日期当天或之前最近的周日。

    NASS 的作物年度周一律以周日结束；发布日通常为周一，遇假期会顺延到周二，
    因此不能用「减一天」简单处理。"""
    import datetime
    d = datetime.date.fromisoformat(release_date)
    return (d - datetime.timedelta(days=(d.weekday() + 1) % 7)).isoformat()


def collect(months):
    """并发抓取：先把各月发布列表拉全，再并行下载缺失的周报。"""
    from concurrent.futures import ThreadPoolExecutor
    os.makedirs(TXT_DIR, exist_ok=True)

    tasks = []
    with ThreadPoolExecutor(WORKERS) as ex:
        for ym, items in zip(months, ex.map(_safe_list, months)):
            tasks.extend(items)
            print(f"  {ym}: 列到 {len(items)} 期", flush=True)
    print(f"合计 {len(tasks)} 期，开始下载（并发 {WORKERS}）", flush=True)
    print(f"合计 {len(tasks)} 期", flush=True)

    def fetch(item):
        date, url = item
        fn = os.path.join(TXT_DIR, f"prog_{date}.txt")
        if os.path.exists(fn) and os.path.getsize(fn) > 2000:
            return date, open(fn, encoding="utf-8", errors="ignore").read(), False
        try:
            txt = get(url).decode("utf-8", "ignore")
        except Exception as e:
            return date, None, f"{type(e).__name__}"
        open(fn, "w", encoding="utf-8").write(txt)
        return date, txt, True

    rows, n_dl, done = {}, 0, 0
    with ThreadPoolExecutor(WORKERS) as ex:
        for date, txt, dl in ex.map(fetch, tasks):
            done += 1
            if dl is True:
                n_dl += 1
            if txt is None:
                print(f"   !! {date} 下载失败: {dl}")
                continue
            if "Soybean" not in txt:
                continue
            rec = parse_report(txt)
            if not rec["week_ending"]:
                if all(rec[k] is None for k in FIELDS if k != "week_ending"):
                    continue
                rec["week_ending"] = week_ending_from_release(date)
            rows[rec["week_ending"]] = rec
            if done % 40 == 0:
                print(f"   已处理 {done}/{len(tasks)}，解析出 {len(rows)} 周", flush=True)
    return rows, n_dl


def _safe_list(ym):
    try:
        return list_month(ym)
    except Exception as e:
        print(f"!! 列表 {ym} 失败: {e}")
        return []


def load_existing():
    """读取已有 CSV；对新增列（老文件里没有的）留空，便于后续版本平滑升级。"""
    if not os.path.exists(CSV_PATH):
        return {}
    out = {}
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            we = r.get("week_ending")
            if not we:
                continue
            rec = {"week_ending": we}
            for k in FIELDS:
                if k == "week_ending":       # 日期列不做数值转换
                    continue
                v = r.get(k)
                rec[k] = float(v) if v not in ("", None) else None
            out[we] = rec
    return out


def save(rows):
    os.makedirs(DATA, exist_ok=True)

    def cell(k, v):
        if v is None or v == "":
            return ""
        if k == "week_ending":          # 日期列不做数值转换
            return v
        f = float(v)
        return int(f) if f.is_integer() else f

    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for k in sorted(rows):
            r = rows[k]
            w.writerow({kk: cell(kk, r.get(kk)) for kk in FIELDS})


def main():
    full = "--full" in sys.argv
    import datetime
    today = datetime.date.today()

    if full:
        months = []
        for y in range(START_YEAR, today.year + 1):
            for m in MONTHS:
                if datetime.date(y, m, 1) > today:
                    break
                months.append(f"{y}-{m:02d}")
        print(f"全量回填：{months[0]} ~ {months[-1]}（{len(months)} 个月）")
        rows = {}
    else:
        months = []
        y, m = today.year, today.month
        for _ in range(REFRESH_MONTHS):
            months.append(f"{y}-{m:02d}")
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        months.reverse()
        print(f"增量刷新：{months[0]} ~ {months[-1]}")
        rows = load_existing()
        print(f"  已有 {len(rows)} 周")

    new, n_dl = collect(months)
    rows.update(new)
    save(rows)

    have_ge = sum(1 for r in rows.values() if r["ge_pct"] is not None)
    print(f"\n下载 {n_dl} 个新文件；crop_progress.csv 共 {len(rows)} 周，"
          f"其中含优良率 {have_ge} 周")
    for k in ("emerged_pct", "blooming_pct", "setting_pods_pct",
              "dropping_leaves_pct"):
        print(f"  含 {k}: {sum(1 for r in rows.values() if r[k] is not None)} 周")
    last = max(rows)
    print(f"最新 {last}: " + ", ".join(
        f"{k}={rows[last][k]}" for k in FIELDS if rows[last][k] is not None))
    return 0


if __name__ == "__main__":
    sys.exit(main())

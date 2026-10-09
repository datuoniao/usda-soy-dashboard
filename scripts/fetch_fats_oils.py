# -*- coding: utf-8 -*-
"""USDA NASS《Fats and Oils: Oilseed Crushings, Production, Consumption and Stocks》
月度报告取数 —— 美国大豆压榨量与油粕产出、库存（全部为实物量，不含价格）。

数据源：ESMIS 归档文本
  https://esmis.nal.usda.gov/publication/
  fats-and-oils-oilseed-crushings-production-consumption-and-stocks?date=YYYY-MM
报表主体表 «Soybean Crushing, Production, Consumption and Stocks - United States»
三列依次为「去年同月 / 上月 / 本月」，本脚本取「本月」。

抽取字段：
  crush_tons        Soybeans crushed（短吨）
  oil_1000lb        Crude oil produced（千磅）
  meal_tons         Cake and meal produced（短吨）
  meal_stock_tons   Cake and meal on hand end of month（短吨）
  oil_stock_1000lb  Crude oil on hand end of month（千磅）

用法：
  python scripts/fetch_fats_oils.py          # 增量：刷新最近若干月并合并
  python scripts/fetch_fats_oils.py --full   # 全量回填（自 START_YEAR 起）
"""
import csv
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
DATA = os.path.join(ROOT, "data")
TXT_DIR = os.path.join(RAW, "fats_oils_txt")
CSV_PATH = os.path.join(DATA, "us_crush_monthly.csv")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE = "https://esmis.nal.usda.gov"
PUB = "fats-and-oils-oilseed-crushings-production-consumption-and-stocks"

START_YEAR = 2019
REFRESH_MONTHS = 12
WORKERS = 8

FIELDS = ["month", "crush_tons", "oil_1000lb", "meal_tons",
          "meal_stock_tons", "oil_stock_1000lb"]

# 行标签 -> 输出列
ROWS = (
    ("Soybeans crushed", "crush_tons"),
    ("Crude oil produced", "oil_1000lb"),
    ("Cake and meal produced", "meal_tons"),
    ("Cake and meal on hand end of month", "meal_stock_tons"),
    ("Crude oil on hand end of month", "oil_stock_1000lb"),
)

MONTHS_EN = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}


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


def _num(tok):
    tok = tok.strip().replace(",", "")
    if not tok or tok.startswith("(") or tok.upper() == "NA":
        return None                     # (D) 为「不予披露」
    try:
        return float(tok)
    except ValueError:
        return None


def parse_report(txt):
    """解析一份月报，返回 dict（缺失字段为 None）。"""
    rec = {k: None for k in FIELDS}

    m = re.search(r"Soybean Crushing, Production, Consumption and Stocks"
                  r"\s*-\s*United States:\s*([A-Z][a-z]+)\s+(\d{4})", txt)
    if not m or m.group(1) not in MONTHS_EN:
        return rec
    rec["month"] = f"{m.group(2)}-{MONTHS_EN[m.group(1)]:02d}"

    # 主体表在标题之后；到「Soybean Crushing - Regional」为止
    body = txt[m.end():]
    cut = body.find("Soybean Crushing - Regional")
    if cut > 0:
        body = body[:cut]

    for line in body.splitlines():
        if ":" not in line or line.lstrip().startswith("-"):
            continue
        label = line.split(":")[0]
        tail = line.split(":")[-1]
        for prefix, col in ROWS:
            if rec[col] is not None:
                continue
            # 行标签与单位连写（如 "...tons:"），故用前缀包含判断
            if label.strip().startswith(prefix):
                vals = [_num(t) for t in tail.split()]
                vals = [v for v in vals]
                if len(vals) >= 3 and vals[2] is not None:
                    rec[col] = vals[2]      # 第 3 列 = 本月
                elif len(vals) == 3 and vals[2] is None:
                    pass                    # 本月被 (D) 屏蔽，留空
    return rec


def collect(months):
    from concurrent.futures import ThreadPoolExecutor
    os.makedirs(TXT_DIR, exist_ok=True)

    tasks = []
    with ThreadPoolExecutor(WORKERS) as ex:
        for items in ex.map(_safe_list, months):
            tasks.extend(items)
    print(f"合计 {len(tasks)} 期，开始下载（并发 {WORKERS}）", flush=True)

    def fetch(item):
        date, url = item
        fn = os.path.join(TXT_DIR, f"cafo_{date}.txt")
        if os.path.exists(fn) and os.path.getsize(fn) > 2000:
            return date, open(fn, encoding="utf-8", errors="ignore").read(), False
        try:
            txt = get(url).decode("utf-8", "ignore")
        except Exception as e:
            return date, None, type(e).__name__
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
            if "Soybean Crushing" not in txt:
                continue
            rec = parse_report(txt)
            if rec["month"]:
                rows[rec["month"]] = rec
            if done % 24 == 0:
                print(f"   已处理 {done}/{len(tasks)}，解析出 {len(rows)} 月",
                      flush=True)
    return rows, n_dl


def _safe_list(ym):
    try:
        return list_month(ym)
    except Exception as e:
        print(f"!! 列表 {ym} 失败: {e}")
        return []


def load_existing():
    if not os.path.exists(CSV_PATH):
        return {}
    out = {}
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            mo = r.get("month")
            if not mo:
                continue
            rec = {"month": mo}
            for k in FIELDS:
                if k == "month":
                    continue
                v = r.get(k)
                rec[k] = float(v) if v not in ("", None) else None
            out[mo] = rec
    return out


def save(rows):
    def cell(k, v):
        if v in (None, ""):
            return ""
        if k == "month":
            return v
        fv = float(v)
        return int(fv) if fv.is_integer() else fv

    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for mo in sorted(rows):
            w.writerow({k: cell(k, rows[mo].get(k)) for k in FIELDS})


def main():
    full = "--full" in sys.argv
    import datetime
    today = datetime.date.today()

    if full:
        months = []
        y, m = START_YEAR, 1
        while (y, m) <= (today.year, today.month):
            months.append(f"{y}-{m:02d}")
            m += 1
            if m == 13:
                y, m = y + 1, 1
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
        print(f"  已有 {len(rows)} 个月")

    new, n_dl = collect(months)
    rows.update(new)
    save(rows)

    have = sum(1 for r in rows.values() if r["crush_tons"] is not None)
    print(f"\n下载 {n_dl} 个新文件；us_crush_monthly.csv 共 {len(rows)} 个月，"
          f"其中含压榨量 {have} 个月")
    last = max(rows)
    print(f"最新 {last}: " + ", ".join(
        f"{k}={rows[last][k]}" for k in FIELDS if rows[last][k] is not None))
    return 0


if __name__ == "__main__":
    sys.exit(main())

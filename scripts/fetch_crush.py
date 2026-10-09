# -*- coding: utf-8 -*-
"""USDA AMS 伊利诺伊中部大豆压榨周报取数。

数据源：
  A) ESMIS《Soybean Crush Report》(GX_GR211) —— 纯文本，覆盖至 2022-07-29
     https://esmis.nal.usda.gov/publication/soybean-crush-report?date=YYYY-MM
  B) 其后并入《National Weekly Grain Co-Products Report》(AMS_3618)，
     由 fetch_crush_ams.py 处理（需浏览器通道）。

解析出的 4 条周度序列（与文章 img06 一致）：
  margin   大豆压榨利润   $/bu  = 油粕总值 - 黄大豆卡车价
  oil      毛豆油车板价   ¢/lb
  meal     48%豆粕批发价  $/ton
  bean     1号黄大豆卡车价 $/bu
"""
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
TXT_DIR = os.path.join(RAW, "crush_txt")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
BASE = "https://esmis.nal.usda.gov"


def get(url, binary=False, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = r.read()
    return d if binary else d.decode("utf-8", "ignore")


def list_month(pub, ym):
    """返回某月该出版物下的 [(date, file_url), ...]"""
    html = get(f"{BASE}/publication/{pub}?date={ym}")
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        t = re.search(r'<time datetime="([^"]+)"', row)
        h = re.search(r'href="(/sites/default/release-files/[^"]+)"', row)
        if t and h:
            out.append((t.group(1)[:10], BASE + h.group(1)))
    return out


NUM = r"([0-9]+(?:\.[0-9]+)?)"


def parse_txt(txt):
    """从 GX_GR211 文本里抽出四条序列（按行的先后顺序定位，避免张冠李戴）。"""
    lines = [l.rstrip() for l in txt.splitlines()]
    res = {}

    def first_num_after(key, start=0):
        """从 start 行起，找到含 key 的行，其后第一处数字（取 This week 列）。
        报表里标签常跨行且夹空行，故窗口放宽到 8 行并跳过空行。"""
        for i in range(start, len(lines)):
            if key in lines[i]:
                for j in range(i, min(i + 8, len(lines))):
                    s = lines[j]
                    if not s.strip():
                        continue
                    if "$" in s:
                        s = s.split("$")[-1]
                    m = re.search(NUM, s)
                    if m:
                        return float(m.group(1)), j
        return None, start

    i_oil = next((i for i, l in enumerate(lines) if l.startswith("Soybean oil")), 0)
    res["oil"], i_oil_v = first_num_after("Central IL.", i_oil)

    res["oil_yield"], _ = first_num_after("Oil yield per", i_oil_v)
    res["oil_value"], i_ov = first_num_after("of soybeans", i_oil_v)

    i_meal = next((i for i, l in enumerate(lines) if "48% Soybean Meal" in l), i_ov)
    res["meal"], i_meal_v = first_num_after("Central IL.", i_meal)

    res["meal_yield"], _ = first_num_after("Meal yield per", i_meal_v)
    res["meal_value"], i_mv = first_num_after("of soybeans", i_meal_v)

    res["total_value"], i_tv = first_num_after("meal from bushel", i_mv)
    res["bean"], i_b = first_num_after("IL. points", i_tv)
    res["margin"], i_mg = first_num_after("Difference between", i_b)
    res["epv"], _ = first_num_after("Estimated Processing", i_mg if res["margin"] is not None else i_b)

    dt = re.search(r"([A-Z][a-z]{2} \d{1,2}, \d{4})", txt)
    res["report_date"] = dt.group(1) if dt else None

    # 一致性校验：油粕总值 ≈ 油价值 + 粕价值；压榨利润 ≈ 油粕总值 - 黄豆价
    if None not in (res.get("oil_value"), res.get("meal_value"), res.get("total_value")):
        if abs(res["oil_value"] + res["meal_value"] - res["total_value"]) > 0.06:
            res["_warn"] = "oil+meal != total"
    if None not in (res.get("total_value"), res.get("bean"), res.get("margin")):
        if abs(res["total_value"] - res["bean"] - res["margin"]) > 0.02:
            res["_warn"] = (res.get("_warn", "") + " margin check failed").strip()
    return res


def main():
    os.makedirs(TXT_DIR, exist_ok=True)
    # 用 dict 按周去重：ESMIS 在「该月无数据」时会兜底返回最新一期，
    # 直接 append 会把同一周重复收录多次。
    records = {}

    # GX_GR211 覆盖期：2020-01 ~ 2022-07
    months = []
    for y in (2020, 2021, 2022):
        for m in range(1, 13):
            if y == 2022 and m > 7:
                break
            months.append(f"{y}-{m:02d}")

    n_dl = 0
    for ym in months:
        try:
            rows = list_month("soybean-crush-report", ym)
        except Exception as e:
            print(f"!! 列表 {ym} 失败: {e}")
            continue
        for date, url in rows:
            # 只接受属于该月且落在覆盖期内的发布，剔除兜底返回的其它周
            if not date.startswith(ym) or not ("2020-01-01" <= date <= "2022-07-31"):
                continue
            fn = os.path.join(TXT_DIR, f"GX_GR211_{date}.txt")
            if os.path.exists(fn) and os.path.getsize(fn) > 100:
                txt = open(fn, encoding="utf-8", errors="ignore").read()
            else:
                try:
                    txt = get(url)
                except Exception as e:
                    print(f"   !! 下载 {date} 失败: {e}")
                    continue
                open(fn, "w", encoding="utf-8").write(txt)
                n_dl += 1
                time.sleep(0.4)
            if "Soybean oil" not in txt:
                continue
            rec = parse_txt(txt)
            rec["week_ending"] = date
            if not rec.get("_warn"):
                records[date] = rec

    ordered = [records[k] for k in sorted(records)]
    out = os.path.join(RAW, "crush_weekly.json")
    json.dump(ordered, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"下载 {n_dl} 个新文件，共解析 {len(ordered)} 周（已按周去重）")
    if ordered:
        print("最早:", ordered[0]["week_ending"], ordered[0])
        print("最新:", ordered[-1]["week_ending"], ordered[-1])
        ok = sum(1 for r in ordered if r["margin"] is not None)
        print(f"含压榨利润的记录: {ok}/{len(ordered)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

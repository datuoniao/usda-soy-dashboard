# -*- coding: utf-8 -*-
"""USDA PSD 各国大豆供需平衡表取数（年度）。

接口：api.fas.usda.gov/api/psd/commodity/2222000/{country|world}/year/{marketYear}
      大豆 PSD 商品码 2222000；marketYear 为「市场年度起始年」（2026 = 2026/27）。

抽取的物理量属性（不含任何价格/金额口径）：
  1   Area Planted      种植面积（千公顷）
  4   Area Harvested    收获面积（千公顷）
  184 Yield             单产（吨/公顷）
  28  Production        产量（千吨）
  7   Crush             压榨量（千吨）
  57  Imports           进口量（千吨）
  88  Exports           出口量（千吨）
  176 Ending Stocks     期末库存（千吨）

输出 data/psd_balance.csv：
  my_code, my_label, country, area_planted, area_harvested, yield_t_ha,
  production, crush, imports, exports, ending_stocks
（面积千公顷、产消千吨，看板侧再换算单位）
"""
import csv
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "psd_balance")
DATA = os.path.join(ROOT, "data")
KEY = os.environ.get("FAS_API_KEY", "DEMO_KEY")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
API = "https://api.fas.usda.gov/api/psd"
SOY = "2222000"

# 国家/地区：countryCode -> 看板用名。00 走 /world/ 路径（PSD 官方全球合计）
COUNTRIES = [("US", "美国"), ("BR", "巴西"), ("AR", "阿根廷"),
             ("CH", "中国"), ("00", "全球")]

ATTRS = {1: "area_planted", 4: "area_harvested", 184: "yield_t_ha",
         28: "production", 7: "crush", 57: "imports", 88: "exports",
         176: "ending_stocks"}

YEARS = list(range(2015, 2028))
FIELDS = (["my_code", "my_label", "country"] + list(ATTRS.values()))


def get(path):
    url = f"{API}{path}{'&' if '?' in path else '?'}api_key={KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_country(cc, my):
    """返回该国家/年度各属性「最新月份口径」的值。"""
    fn = os.path.join(RAW, f"{cc}_{my}.json")
    if os.path.exists(fn) and os.path.getsize(fn) > 100:
        d = json.load(open(fn, encoding="utf-8"))
    else:
        seg = "world" if cc == "00" else f"country/{cc}"
        d = get(f"/commodity/{SOY}/{seg}/year/{my}")
        json.dump(d, open(fn, "w", encoding="utf-8"), ensure_ascii=False)
    out = {}
    for aid in ATTRS:
        rows = [r for r in d if r.get("attributeId") == aid]
        if not rows:
            continue
        # 同一属性在一个年度内会随 WASDE 多次迭代；取日历月最新的一版
        rows.sort(key=lambda r: (str(r.get("calendarYear", "")),
                                 str(r.get("month", ""))))
        out[aid] = rows[-1]["value"]
    return out


def main():
    os.makedirs(RAW, exist_ok=True)
    rows = []
    for cc, name in COUNTRIES:
        got = 0
        for my in YEARS:
            try:
                v = fetch_country(cc, my)
            except Exception as e:
                print(f"  !! {name} MY{my} 失败: {type(e).__name__} {e}")
                continue
            if not v:
                continue
            rec = {"my_code": my, "my_label": f"{my}/{str(my + 1)[2:]}",
                   "country": name}
            for aid, col in ATTRS.items():
                rec[col] = v.get(aid)
            rows.append(rec)
            got += 1
        print(f"{name}: {got} 个年度")

    rows.sort(key=lambda r: (r["country"], r["my_code"]))
    out = os.path.join(DATA, "psd_balance.csv")
    text_cols = ("my_label", "country")       # 文本列不做数值转换

    def cell(k, v):
        if v in (None, ""):
            return ""
        if k in text_cols:
            return v
        fv = float(v)
        return int(fv) if fv.is_integer() else fv

    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: cell(k, r.get(k)) for k in FIELDS})
    print(f"\npsd_balance.csv: {len(rows)} 行 "
          f"（{len(set(r['country'] for r in rows))} 个国家 × "
          f"{len(set(r['my_code'] for r in rows))} 个年度）")

    # 关键锚点自检
    us = [r for r in rows if r["country"] == "美国" and r["my_code"] == 2026]
    if us:
        r = us[0]
        print(f"  美国 MY2026/27: 收获面积 {r['area_harvested']:,.0f} 千公顷 | "
              f"单产 {r['yield_t_ha']:.3f} t/ha | 产量 {r['production']:,.0f} 千吨 | "
              f"出口 {r['exports']:,.0f} | 压榨 {r['crush']:,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

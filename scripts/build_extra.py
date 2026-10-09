# -*- coding: utf-8 -*-
"""生成 data/crush_il.csv（伊利诺伊压榨周度数据）。

crush_il.csv —— USDA AMS《Soybean Crush Report》伊利诺伊中部压榨（周度）
                来源：ESMIS GX_GR211
注：drought.csv 由 fetch_drought.py 直接产出，不在此处生成。
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
DATA = os.path.join(ROOT, "data")


def my_of(date_str):
    """大豆营销年度：9月1日起算。返回 (my_code, label)"""
    y, m, _ = (int(x) for x in date_str.split("-"))
    start = y if m >= 9 else y - 1
    return start + 1, f"{start}/{str(start+1)[2:]}"


def build_crush():
    src = os.path.join(RAW, "crush_weekly.json")
    if not os.path.exists(src):
        print("!! 缺少 crush_weekly.json")
        return
    recs = json.load(open(src, encoding="utf-8"))
    recs = [r for r in recs if r.get("margin") is not None]
    recs.sort(key=lambda r: r["week_ending"])
    by_my = {}
    for r in recs:
        by_my.setdefault(my_of(r["week_ending"])[0], []).append(r)
    out = []
    for my in sorted(by_my):
        for idx, r in enumerate(by_my[my], start=1):
            out.append({
                "my_label": r and my_of(r["week_ending"])[1],
                "my_code": my,
                "week_ending": r["week_ending"],
                "week_index": idx,
                "crush_margin_usd_bu": r.get("margin"),
                "oil_cent_lb": r.get("oil"),
                "meal_usd_ton": r.get("meal"),
                "bean_usd_bu": r.get("bean"),
                "oil_yield_lb": r.get("oil_yield"),
                "meal_yield_lb": r.get("meal_yield"),
            })
    with open(os.path.join(DATA, "crush_il.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"crush_il.csv: {len(out)} 周 {out[0]['week_ending']} ~ {out[-1]['week_ending']} "
          f"（{len(by_my)} 个营销年度）")


if __name__ == "__main__":
    build_crush()

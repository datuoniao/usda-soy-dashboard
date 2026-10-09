# -*- coding: utf-8 -*-
"""把 USDA 原始响应清洗聚合成看板用的 tidy CSV + 内嵌 JSON。

产出（data/ 目录）：
  export_sales.csv  美豆出口销售：当周净销售/累计总销售/当周装船/累计装船/销售进度
  export_china.csv  美豆对华 & 除中国外出口销售
  meal_export.csv   美豆粕出口销售
  drought.csv       美豆干旱率（由 fetch_drought.py 生成）
  crush_il.csv      伊利诺伊压榨利润（由 fetch_crush*.py 生成）
  dashboard.json    看板内嵌数据
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
DATA = os.path.join(ROOT, "data")
CHINA = 5700
UOM_TO_WANDUN = 1e-4  # 公吨 -> 万吨


def load(fn):
    return json.load(open(os.path.join(RAW, fn), encoding="utf-8"))


def agg_weeks(commodity):
    """按周聚合：全国合计 / 中国 / 除中国外。"""
    years = {}
    for my in range(2020, 2028):
        rows = load(f"esr_{commodity}_{my}.json")
        if not rows:
            continue
        by_week = {}
        for r in rows:
            w = r["weekEndingDate"][:10]
            a = by_week.setdefault(w, {"net": 0, "ship": 0, "cum_ship": 0, "commit": 0,
                                       "c_net": 0, "c_ship": 0, "c_cum": 0, "c_commit": 0})
            a["net"] += r["currentMYNetSales"]
            a["ship"] += r["weeklyExports"]
            a["cum_ship"] += r["accumulatedExports"]
            a["commit"] += r["currentMYTotalCommitment"]
            if r["countryCode"] == CHINA:
                a["c_net"] += r["currentMYNetSales"]
                a["c_ship"] += r["weeklyExports"]
                a["c_cum"] += r["accumulatedExports"]
                a["c_commit"] += r["currentMYTotalCommitment"]
        weeks = sorted(by_week)
        recs = []
        for idx, w in enumerate(weeks, start=1):
            a = by_week[w]
            recs.append({
                "my_code": my,
                "my_label": f"{my-1}/{str(my)[2:]}",
                "week_ending": w,
                "week_index": idx,
                "net_sales_kt": round(a["net"] / 1e3, 3),          # 千吨
                "commitment_kt": round(a["commit"] / 1e3, 3),
                "shipment_kt": round(a["ship"] / 1e3, 3),
                "cum_shipment_kt": round(a["cum_ship"] / 1e3, 3),
                "china_net_kt": round(a["c_net"] / 1e3, 3),
                "china_commit_kt": round(a["c_commit"] / 1e3, 3),
                "china_ship_kt": round(a["c_ship"] / 1e3, 3),
                "china_cum_ship_kt": round(a["c_cum"] / 1e3, 3),
                "noncn_net_kt": round((a["net"] - a["c_net"]) / 1e3, 3),
                "noncn_commit_kt": round((a["commit"] - a["c_commit"]) / 1e3, 3),
                "noncn_ship_kt": round((a["ship"] - a["c_ship"]) / 1e3, 3),
                "noncn_cum_ship_kt": round((a["cum_ship"] - a["c_cum"]) / 1e3, 3),
            })
        years[my] = recs
    return years


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    soy = agg_weeks("soybeans")
    meal = agg_weeks("meal")
    psd = json.load(open(os.path.join(RAW, "psd_us_exports.json"), encoding="utf-8"))

    # ---- 1/2. 美豆出口销售（含对华）
    fields = ["my_label", "my_code", "week_index", "week_ending",
              "net_sales_kt", "commitment_kt", "shipment_kt", "cum_shipment_kt",
              "china_net_kt", "china_commit_kt", "china_ship_kt", "china_cum_ship_kt",
              "noncn_net_kt", "noncn_commit_kt", "noncn_ship_kt", "noncn_cum_ship_kt",
              "progress_pct"]

    # 销售进度分母 = USDA PSD 对该年度的全年出口预测（千吨）
    forecast = {}
    for my, v in psd.items():
        forecast[int(my) + 1] = v["value"] / 1e3 * 1e3  # 已是千吨

    flat = []
    for my, recs in sorted(soy.items()):
        fc = psd.get(str(my - 1), {}).get("value")  # PSD marketYear = 起始年 = my-1
        for r in recs:
            r["progress_pct"] = (round(r["commitment_kt"] / fc * 100, 2)
                                 if fc else None)
            flat.append(r)
    write_csv(os.path.join(DATA, "export_sales.csv"), flat, fields)
    print(f"export_sales.csv: {len(flat)} 行, {flat[0]['my_label']} ~ {flat[-1]['my_label']}")

    # ---- 3. 美豆粕出口销售
    mflat = []
    for my, recs in sorted(meal.items()):
        for r in recs:
            mflat.append(r)
    write_csv(os.path.join(DATA, "meal_export.csv"), mflat, fields)
    print(f"meal_export.csv:  {len(mflat)} 行, {mflat[0]['my_label']} ~ {mflat[-1]['my_label']}")

    # ---- 校验：与文章数字对齐（week ending 2026-10-01）
    target = [r for r in flat if r["week_ending"] == "2026-10-01" and r["my_code"] == 2027]
    if target:
        t = target[0]
        print("\n=== 校验 2026-10-01 当周（MY2026/27）vs 文章 ===")
        chk = [
            ("当周净销售 54.94 万吨", t["net_sales_kt"] / 10, 54.94),
            ("累计总销售 2278.52 万吨", t["commitment_kt"] / 10, 2278.52),
            ("对华当周净销售 38.29 万吨", t["china_net_kt"] / 10, 38.29),
            ("对华累计销售 1114.23 万吨", t["china_commit_kt"] / 10, 1114.23),
            ("对华当周装船 82.79 万吨", t["china_ship_kt"] / 10, 82.79),
            ("除中国外净销售 16.65 万吨", t["noncn_net_kt"] / 10, 16.65),
            ("除中国外累计销售 1164.29 万吨", t["noncn_commit_kt"] / 10, 1164.29),
            ("当周装船 137.97 万吨", t["shipment_kt"] / 10, 137.97),
        ]
        for name, got, exp in chk:
            ok = "OK " if abs(got - exp) < 0.06 else "!! "
            print(f"  {ok}{name:<28} 计算 {got:>10.2f} / 文章 {exp:>10.2f}")

    # 干旱与压榨 CSV 分别由 fetch_drought.py / build_extra.py 产出，此处仅做存在性提示
    for extra in ("drought.csv", "crush_il.csv"):
        p = os.path.join(DATA, extra)
        if not os.path.exists(p):
            print(f"  提示：缺少 {extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

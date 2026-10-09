# -*- coding: utf-8 -*-
"""由 data/ 下的清洗数据生成单文件离线 HTML 看板（根目录 index.html）。

所有日期与数值均从数据动态推导，不含任何硬编码的时点，可安全用于定时自动更新。
"""
import csv
import datetime
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "outputs")

# 分年度配色（延续大豆研报的惯例）
COLORS = {
    "2019/20": "#9aa0a6", "2020/21": "#e8710a", "2021/22": "#e0b429",
    "2022/23": "#4a9d5f", "2023/24": "#2f9fa6", "2024/25": "#3f74cf",
    "2025/26": "#8259c9", "2026/27": "#d94a4a", "2027/28": "#b03a6e",
}
DROUGHT_COLORS = {
    "2012": "#8a5a2b", "2016": "#4a9d5f", "2021": "#e0b429", "2022": "#e8710a",
    "2023": "#3f74cf", "2024": "#4b4f55", "2025": "#8259c9", "2026": "#d94a4a",
}


def load_csv(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def fnum(r, k):
    v = r.get(k, "")
    return None if v in ("", None) else float(v)


def build():
    soy = load_csv("export_sales.csv")
    meal = load_csv("meal_export.csv")
    dr = load_csv("drought.csv")
    cr = load_csv("crush_il.csv")
    if not soy:
        raise SystemExit("!! 缺少 data/export_sales.csv，请先运行取数脚本")

    soy_years = sorted({r["my_label"] for r in soy}, key=lambda s: s[:4])
    meal_years = sorted({r["my_label"] for r in meal}, key=lambda s: s[:4])

    def mk(rows, key, xk="week_index", scale=1.0, rnd=2):
        by = {}
        for r in rows:
            v = fnum(r, key)
            if v is None:
                continue
            by.setdefault(r["my_label"], []).append(
                [float(r[xk]), round(v * scale, rnd)])
        return by

    def series(by, order, colors, hl=None):
        out = []
        for y in order:
            if y in by:
                out.append({"label": y, "color": colors.get(y, "#888"),
                            "p": sorted(by[y], key=lambda t: t[0]), "hl": (y == hl)})
        return out

    charts = []

    def add(cid, title, unit, xlab, ser, xmin=1, xmax=53, y0=True, note=""):
        charts.append({"id": cid, "t": title, "u": unit, "x": xlab,
                       "s": ser, "xmin": xmin, "xmax": xmax, "y0": y0, "note": note})

    hl_soy = soy_years[-1]
    hl_meal = meal_years[-1]

    add("c1", "美豆本年度当周出口净销售", "万吨", "营销年度第几周",
        series(mk(soy, "net_sales_kt", scale=0.1), soy_years, COLORS, hl_soy))
    add("c2", "美豆本年度截至当周出口总销售", "万吨", "营销年度第几周",
        series(mk(soy, "commitment_kt", scale=0.1), soy_years, COLORS, hl_soy))
    add("c3", "美豆本年度当周出口装船", "万吨", "营销年度第几周",
        series(mk(soy, "shipment_kt", scale=0.1), soy_years, COLORS, hl_soy))
    add("c4", "美豆本年度截至当周出口销售进度", "%", "营销年度第几周",
        series(mk(soy, "progress_pct"), soy_years, COLORS, hl_soy), y0=False,
        note="进度 = 累计总销售量 ÷ USDA(PSD) 对该年度的全年出口预测值")

    add("c5", "美豆本年度当周出口至中国净销售", "万吨", "营销年度第几周",
        series(mk(soy, "china_net_kt", scale=0.1), soy_years, COLORS, hl_soy))
    add("c6", "美豆本年度截至当周出口至中国总销售", "万吨", "营销年度第几周",
        series(mk(soy, "china_commit_kt", scale=0.1), soy_years, COLORS, hl_soy))
    add("c7", "美豆本年度当周出口净销售（除中国外）", "万吨", "营销年度第几周",
        series(mk(soy, "noncn_net_kt", scale=0.1), soy_years, COLORS, hl_soy))
    add("c8", "美豆本年度截至当周出口总销售（除中国外）", "万吨", "营销年度第几周",
        series(mk(soy, "noncn_commit_kt", scale=0.1), soy_years, COLORS, hl_soy))

    add("c9", "美豆粕本年度当周出口净销售", "万吨", "营销年度第几周",
        series(mk(meal, "net_sales_kt", scale=0.1), meal_years, COLORS, hl_meal))
    add("c10", "美豆粕本年度累计出口总销售", "万吨", "营销年度第几周",
        series(mk(meal, "commitment_kt", scale=0.1), meal_years, COLORS, hl_meal))
    add("c11", "美豆粕本年度当周出口装船", "万吨", "营销年度第几周",
        series(mk(meal, "shipment_kt", scale=0.1), meal_years, COLORS, hl_meal))
    add("c12", "美豆粕本年度累计出口装船", "万吨", "营销年度第几周",
        series(mk(meal, "cum_shipment_kt", scale=0.1), meal_years, COLORS, hl_meal))

    # 干旱：取最近 8 个有数据的年份
    dr_years_all = sorted({r["week_ending"][:4] for r in dr})
    DY = [y for y in ["2012", "2016"] if y in dr_years_all] + dr_years_all[-6:]
    DY = sorted(set(DY))

    def drought_series(key):
        by = {}
        for r in dr:
            y = r["week_ending"][:4]
            if y not in DY:
                continue
            v = fnum(r, key)
            if v is None:
                continue
            m, d = int(r["week_ending"][5:7]), int(r["week_ending"][8:10])
            doy = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334][m - 1] + d
            by.setdefault(y, []).append([doy, v])
        pal = ["#8a5a2b", "#4a9d5f", "#e0b429", "#e8710a", "#3f74cf",
               "#4b4f55", "#8259c9", "#d94a4a", "#b03a6e", "#2f9fa6"]
        cols = {}
        keys = sorted(by)
        for i, y in enumerate(keys):
            cols[y] = DROUGHT_COLORS.get(y, pal[i % len(pal)])
        return series(by, keys, cols, keys[-1]), cols

    s13, _ = drought_series("soy_d1plus")
    s14, _ = drought_series("soy_d3plus")
    add("c13", "美豆干旱率（D1 及以上）", "%", "日历日（1月1日 → 12月31日）",
        s13, xmin=1, xmax=366)
    add("c14", "美豆重度干旱率（D3 及以上）", "%", "日历日（1月1日 → 12月31日）",
        s14, xmin=1, xmax=366)

    cy = sorted({r["my_label"] for r in cr}, key=lambda s: s[:4])
    CCOL = {y: COLORS.get(y, "#5b6470") for y in cy}
    hl_c = cy[-1] if cy else None
    add("c15", "伊利诺伊州油厂压榨毛利", "美元/蒲式耳", "营销年度第几周",
        series(mk(cr, "crush_margin_usd_bu", rnd=3), cy, CCOL, hl_c), y0=False,
        note="毛利 = 单位大豆产出油粕总值 − 1号黄大豆卡车价（USDA AMS 口径）")
    add("c16", "伊利诺伊中部大豆毛油车板价", "美分/磅", "营销年度第几周",
        series(mk(cr, "oil_cent_lb", rnd=2), cy, CCOL, hl_c), y0=False)
    add("c17", "48%豆粕批发价（伊利诺伊中部）", "美元/短吨", "营销年度第几周",
        series(mk(cr, "meal_usd_ton", rnd=2), cy, CCOL, hl_c), y0=False)
    add("c18", "1号黄大豆卡车价（伊利诺伊中部）", "美元/蒲式耳", "营销年度第几周",
        series(mk(cr, "bean_usd_bu", rnd=3), cy, CCOL, hl_c), y0=False)

    # ---------------- 动态时点 ----------------
    latest = max(r["week_ending"] for r in soy)
    cur_my = max(int(r["my_code"]) for r in soy if r["week_ending"] == latest)
    cur = [r for r in soy if r["week_ending"] == latest and int(r["my_code"]) == cur_my][0]
    prev_my_week = [r for r in soy if int(r["my_code"]) == cur_my
                    and r["week_ending"] < latest]
    prev = max(prev_my_week, key=lambda r: r["week_ending"]) if prev_my_week else None
    ly = [r for r in soy if int(r["my_code"]) == cur_my - 1
          and int(r["week_index"]) == int(cur["week_index"])]
    ly = ly[0] if ly else None
    dr_last = dr[-1] if dr else None
    dr_yago = None
    if dr_last:
        # 「去年同期」取 364 天前最近的一期（同一日历周），避免跨周错配
        target = datetime.date.fromisoformat(dr_last["week_ending"]) - datetime.timedelta(days=364)
        cands = [r for r in dr if abs((datetime.date.fromisoformat(r["week_ending"]) - target).days) <= 10]
        if cands:
            dr_yago = min(cands, key=lambda r: abs(
                (datetime.date.fromisoformat(r["week_ending"]) - target).days))
    crush_last = cr[-1] if cr else None

    def w(v):
        return f"{v/10:,.2f}" if v is not None else "—"

    kpi = []
    if cur:
        kpi.append({"v": w(fnum(cur, "net_sales_kt")), "u": "万吨",
                    "l": "当周出口净销售", "d": f'{latest} 当周'})
        kpi.append({"v": w(fnum(cur, "commitment_kt")), "u": "万吨",
                    "l": "累计出口总销售",
                    "d": f'MY{cur["my_label"]} 截至当周'})
        kpi.append({"v": w(fnum(cur, "china_commit_kt")), "u": "万吨",
                    "l": "对华累计销售",
                    "d": f'占累计总销售 {fnum(cur,"china_commit_kt")/fnum(cur,"commitment_kt")*100:.1f}%'})
    if dr_last:
        kpi.append({"v": f'{float(dr_last["soy_d1plus"]):.0f}', "u": "%",
                    "l": "美豆干旱率 D1+", "d": f'{dr_last["week_ending"]}；'
                    + (f'去年同期 {float(dr_yago["soy_d1plus"]):.0f}%' if dr_yago else "—")})
        kpi.append({"v": f'{float(dr_last["soy_d3plus"]):.0f}', "u": "%",
                    "l": "重度干旱率 D3+", "d": dr_last["week_ending"]})
    if crush_last:
        kpi.append({"v": f'{fnum(crush_last,"crush_margin_usd_bu"):.2f}', "u": "美元/蒲",
                    "l": "伊利诺伊压榨毛利", "d": f'{crush_last["week_ending"]}（当期数据止于此）'})

    # ---------------- 最新一期快照（自动更新） ----------------
    snap = []
    if cur:
        def row(label, key, unit, scale=0.1, rnd=2):
            c = fnum(cur, key)
            p = fnum(prev, key) if prev else None
            l = fnum(ly, key) if ly else None
            snap.append({
                "n": label, "u": unit,
                "c": None if c is None else round(c * scale, rnd),
                "p": None if p is None else round(p * scale, rnd),
                "l": None if l is None else round(l * scale, rnd),
                "wow": None if (c is None or not p) else round((c - p) / abs(p) * 100, 1),
                "yoy": None if (c is None or not l) else round((c - l) / abs(l) * 100, 1),
            })
        row("当周出口净销售", "net_sales_kt", "万吨")
        row("累计出口总销售", "commitment_kt", "万吨")
        row("当周出口装船", "shipment_kt", "万吨")
        row("对华当周净销售", "china_net_kt", "万吨")
        row("对华累计销售", "china_commit_kt", "万吨")
        row("除中国外当周净销售", "noncn_net_kt", "万吨")
        row("除中国外累计销售", "noncn_commit_kt", "万吨")
        row("出口销售进度", "progress_pct", "%", scale=1.0, rnd=2)

    payload = {"charts": charts, "kpis": kpi, "snapshot": snap,
               "meta": {
                   "gen": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                   "asof_export": latest,
                   "asof_drought": dr_last["week_ending"] if dr_last else "—",
                   "asof_crush": crush_last["week_ending"] if crush_last else "—",
               }}

    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "dashboard_template.html"), encoding="utf-8").read()
    html = (tpl.replace("/*__DATA__*/", json.dumps(payload, ensure_ascii=False,
                                                   separators=(",", ":")))
               .replace("__ASOF_EXPORT__", payload["meta"]["asof_export"])
               .replace("__ASOF_DROUGHT__", payload["meta"]["asof_drought"])
               .replace("__ASOF_CRUSH__", payload["meta"]["asof_crush"])
               .replace("__GENERATED__", payload["meta"]["gen"]))
    for p in (os.path.join(ROOT, "index.html"),
              os.path.join(OUT, "usda_soy_dashboard.html")):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(html)
    print(f"已生成 index.html ({len(html)/1024:.0f} KB, {len(charts)} 张图)；"
          f"出口销售截至 {latest}，干旱截至 {payload['meta']['asof_drought']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())

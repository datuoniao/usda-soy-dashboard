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

    # 月首/月末的「日序」，用于把横轴对齐到整月
    MS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    ME = [31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]

    def add(cid, title, unit, xlab, ser, xmin=1, xmax=53, y0=True, note="",
            snap=False, xm="week", yrange=None):
        """snap=True 时按数据实际覆盖的月份收缩横轴，避免大片空白。
        xm: 横轴类型 —— week（营销年度第几周）、day（日历日）或 year（年度）。
        yrange: xm='year' 时的数据年份跨度 (min, max)，供全局筛选按年收缩。"""
        if snap and ser:
            xs = [p[0] for s in ser for p in s["p"]]
            if xs:
                lo = datetime.date(2026, 1, 1) + datetime.timedelta(days=int(min(xs)) - 1)
                hi = datetime.date(2026, 1, 1) + datetime.timedelta(days=int(max(xs)) - 1)
                xmin, xmax = MS[lo.month - 1], ME[hi.month - 1]
        charts.append({"id": cid, "t": title, "u": unit, "x": xlab,
                       "s": ser, "xmin": xmin, "xmax": xmax, "y0": y0,
                       "note": note, "xm": xm, "yr": yrange})

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
        s13, xmin=1, xmax=366, xm="day")
    add("c14", "美豆重度干旱率（D3 及以上）", "%", "日历日（1月1日 → 12月31日）",
        s14, xmin=1, xmax=366, xm="day")

    # ---------- 模块五：作物生长报告 / 优良率
    PAL = ["#8a5a2b", "#4a9d5f", "#e0b429", "#e8710a", "#3f74cf",
           "#4b4f55", "#8259c9", "#d94a4a", "#b03a6e", "#2f9fa6"]
    cp = load_csv("crop_progress.csv")
    cp_years = sorted({r["week_ending"][:4] for r in cp})
    CPY = cp_years[-8:]

    def crop_series(col):
        by = {}
        for r in cp:
            y = r["week_ending"][:4]
            if y not in CPY:
                continue
            v = fnum(r, col)
            if v is None:
                continue
            m, d = int(r["week_ending"][5:7]), int(r["week_ending"][8:10])
            doy = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334][m - 1] + d
            by.setdefault(y, []).append([doy, v])
        cols = {y: PAL[i % len(PAL)] for i, y in enumerate(sorted(by))}
        keys = sorted(by)
        return series(by, keys, cols, keys[-1] if keys else None)

    add("c19", "美豆优良率（Good + Excellent）", "%", "日历日",
        crop_series("ge_pct"), snap=True, xm="day",
        note="取自 NASS《Crop Progress》周报「18 States」全国合计行")
    add("c20", "美豆差劣率（Very poor + Poor）", "%", "日历日",
        crop_series("vp_pct"), snap=True, xm="day")
    add("c21", "美豆播种进度", "%", "日历日",
        crop_series("planted_pct"), snap=True, xm="day")
    add("c23", "美豆出芽进度", "%", "日历日",
        crop_series("emerged_pct"), snap=True, xm="day")
    add("c24", "美豆开花进度", "%", "日历日",
        crop_series("blooming_pct"), snap=True, xm="day")
    add("c25", "美豆结荚进度", "%", "日历日",
        crop_series("setting_pods_pct"), snap=True, xm="day")
    add("c26", "美豆落叶进度", "%", "日历日",
        crop_series("dropping_leaves_pct"), snap=True, xm="day")
    add("c22", "美豆收获进度", "%", "日历日",
        crop_series("harvested_pct"), snap=True, xm="day")

    # ---------- 模块六：全球大豆供需平衡（USDA PSD，年度）
    pb = load_csv("psd_balance.csv")
    if pb:
        PCD = {"美国": "#3f74cf", "巴西": "#4a9d5f", "阿根廷": "#e0b429",
               "中国": "#d94a4a", "全球": "#4b4f55"}
        PCN = ["美国", "巴西", "阿根廷", "中国", "全球"]
        PB_YEARS = sorted({int(r["my_code"]) for r in pb})

        def psd_series(col, scale=1.0, rnd=1, only=None):
            by = {}
            for r in pb:
                if only and r["country"] not in only:
                    continue
                v = fnum(r, col)
                if v is None:
                    continue
                by.setdefault(r["country"], []).append(
                    [float(r["my_code"]), round(v * scale, rnd)])
            keys = [c for c in PCN if c in by]
            return [{"label": c, "color": PCD[c], "p": sorted(by[c]),
                     "hl": (c == "全球")} for c in keys]

        PYR = (PB_YEARS[0], PB_YEARS[-1])

        def add_psd(cid, title, unit, col, scale, rnd=1, note="", only=None):
            add(cid, title, unit, "营销年度（起始年）",
                psd_series(col, scale=scale, rnd=rnd, only=only),
                xmin=PYR[0], xmax=PYR[1], y0=False, xm="year", yrange=PYR,
                note=note)

        add_psd("p1", "大豆产量", "百万吨", "production", 0.001)
        add_psd("p2", "大豆收获面积", "百万公顷", "area_harvested", 0.001)
        add_psd("p3", "大豆单产", "吨/公顷", "yield_t_ha", 1.0, rnd=2)
        add_psd("p4", "大豆压榨量", "百万吨", "crush", 0.001)
        add_psd("p5", "大豆出口量", "百万吨", "exports", 0.001)
        add_psd("p6", "大豆进口量", "百万吨", "imports", 0.001)
        add_psd("p7", "大豆期末库存", "百万吨", "ending_stocks", 0.001)

    # ---------- 模块七：巴西大豆（CONAB 官方 × USDA 对照，年度）
    cb = load_csv("conab_soy.csv")
    if cb and pb:
        cb = [r for r in cb if int(r["year"]) >= 2000]

        def br_series(conab_col, cscale, psd_col, pscale, rnd=1):
            out = []
            by = {}
            for r in cb:
                v = fnum(r, conab_col)
                if v is not None:
                    by.setdefault(float(r["year"]), round(v * cscale, rnd))
            if by:
                out.append({"label": "CONAB", "color": "#4a9d5f",
                            "p": sorted(by.items()), "hl": True})
            by2 = {}
            for r in pb:
                if r["country"] != "巴西":
                    continue
                v = fnum(r, psd_col)
                if v is not None:
                    by2.setdefault(float(r["my_code"]), round(v * pscale, rnd))
            if by2:
                out.append({"label": "USDA", "color": "#3f74cf",
                            "p": sorted(by2.items()), "hl": False})
            return out

        BY_RANGE = (2000, max([int(r["year"]) for r in cb]
                              + [int(r["my_code"]) for r in pb
                                 if r["country"] == "巴西"]))
        add("b1", "巴西大豆种植面积：CONAB 与 USDA 对照", "百万公顷",
            "作物年度（起始年）", br_series("area_kha", 0.001,
                                        "area_harvested", 0.001),
            xmin=BY_RANGE[0], xmax=BY_RANGE[1], y0=False, xm="year",
            yrange=BY_RANGE,
            note="CONAB 为播种面积、USDA PSD 为收获面积，两者口径不同故略有差异")
        add("b2", "巴西大豆单产：CONAB 与 USDA 对照", "吨/公顷",
            "作物年度（起始年）", br_series("yield_kg_ha", 0.001,
                                        "yield_t_ha", 1.0, rnd=2),
            xmin=BY_RANGE[0], xmax=BY_RANGE[1], y0=False, xm="year",
            yrange=BY_RANGE)
        add("b3", "巴西大豆产量：CONAB 与 USDA 对照", "百万吨",
            "作物年度（起始年）", br_series("production_kt", 0.001,
                                        "production", 0.001),
            xmin=BY_RANGE[0], xmax=BY_RANGE[1], y0=False, xm="year",
            yrange=BY_RANGE)

    # ---------- 模块八：美国大豆月度压榨（NASS《Fats and Oils》）
    fo = load_csv("us_crush_monthly.csv")
    if fo:
        fo_years = sorted({r["month"][:4] for r in fo})
        FY = fo_years[-6:]

        def fo_series(col, scale, rnd=1):
            by = {}
            for r in fo:
                y = r["month"][:4]
                if y not in FY:
                    continue
                v = fnum(r, col)
                if v is None:
                    continue
                m = int(r["month"][5:7])
                doy = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334][m - 1] + 15
                by.setdefault(y, []).append([doy, round(v * scale, rnd)])
            keys = sorted(by)
            cols = {y: PAL[i % len(PAL)] for i, y in enumerate(keys)}
            return series(by, keys, cols, keys[-1] if keys else None)

        add("f1", "美国大豆月度压榨量", "百万吨", "日历日",
            fo_series("crush_tons", 1e-6, 2), snap=True, xm="day",
            note="NASS《Fats and Oils》月报，取「本月」列")
        add("f2", "美国豆粕月度产量", "万吨", "日历日",
            fo_series("meal_tons", 1e-4, 1), snap=True, xm="day")
        add("f3", "美国豆粕月末库存", "万吨", "日历日",
            fo_series("meal_stock_tons", 1e-4, 1), snap=True, xm="day")
        add("f4", "美国豆油月度产量", "亿磅", "日历日",
            fo_series("oil_1000lb", 1e-5, 2), snap=True, xm="day")

    # ---------- 模块九：气候与航运水位
    oni = load_csv("oni.csv")
    if oni:
        pts = []
        for r in oni:
            y, m = int(r["month"][:4]), int(r["month"][5:7])
            v = fnum(r, "oni")
            if v is not None:
                pts.append([round(y + (m - 0.5) / 12, 3), v])
        pts.sort(key=lambda t: t[0])
        OR_ = (pts[0][0], pts[-1][0])
        add("w1", "厄尔尼诺 / 拉尼娜指数（ONI）", "°C", "年份",
            [{"label": "ONI", "color": "#3f74cf", "p": pts, "hl": True}],
            xmin=OR_[0], xmax=OR_[1], y0=False, xm="year", yrange=OR_,
            note="NOAA PSL，Niño 3.4 区海温距平的 3 个月滑动平均；≥ +0.5 为厄尔尼诺，≤ −0.5 为拉尼娜")

    rs = load_csv("river_stage.csv")
    if rs:
        rs_years = sorted({r["date"][:4] for r in rs})
        RY = rs_years[-8:]
        by = {}
        for r in rs:
            y = r["date"][:4]
            if y not in RY:
                continue
            v = fnum(r, "stage_ft")
            if v is None:
                continue
            m, d = int(r["date"][5:7]), int(r["date"][8:10])
            doy = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334][m - 1] + d
            by.setdefault(y, []).append([doy, round(v, 2)])
        keys = sorted(by)
        cols = {y: PAL[i % len(PAL)] for i, y in enumerate(keys)}
        add("w2", "密西西比河水位（圣路易斯站）", "英尺", "日历日",
            series(by, keys, cols, keys[-1] if keys else None),
            xmin=1, xmax=366, y0=False, xm="day",
            note="USGS NWIS 站点 07010000 日值；水位偏低会限制驳船吃水，影响美湾大豆出口物流")

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

    cp_ge = [r for r in cp if fnum(r, "ge_pct") is not None]
    cp_last = cp_ge[-1] if cp_ge else None
    cp_yago = None
    if cp_last:
        tgt = datetime.date.fromisoformat(cp_last["week_ending"]) - datetime.timedelta(days=364)
        cands = [r for r in cp_ge
                 if abs((datetime.date.fromisoformat(r["week_ending"]) - tgt).days) <= 10]
        if cands:
            cp_yago = min(cands, key=lambda r: abs(
                (datetime.date.fromisoformat(r["week_ending"]) - tgt).days))

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
    if cp_last:
        kpi.append({"v": f'{fnum(cp_last,"ge_pct"):.0f}', "u": "%",
                    "l": "美豆优良率", "d": f'{cp_last["week_ending"]} 当周；'
                    + (f'去年同期 {fnum(cp_yago,"ge_pct"):.0f}%' if cp_yago else '—')})
    if crush_last:
        kpi.append({"v": f'{fnum(crush_last,"crush_margin_usd_bu"):.2f}', "u": "美元/蒲",
                    "l": "伊利诺伊压榨毛利", "d": f'{crush_last["week_ending"]}（当期数据止于此）'})

    # ---- 新增模块的 KPI ----
    psd_meta = {"my": "—", "asof": "—"}
    if pb:
        last_my = max(int(r["my_code"]) for r in pb)
        psd_meta = {"my": f"{last_my}/{str(last_my + 1)[2:]}", "asof": str(last_my)}

        def pv(country, col, last_my=last_my):
            rr = [r for r in pb if r["country"] == country
                  and int(r["my_code"]) == last_my]
            return fnum(rr[0], col) if rr else None

        us_prod = pv("美国", "production")
        if us_prod is not None:
            kpi.append({"v": f'{us_prod/1000:,.1f}', "u": "百万吨",
                        "l": "美国大豆产量", "d": f'USDA PSD · MY{psd_meta["my"]}'})
        gl_stock = pv("全球", "ending_stocks")
        if gl_stock is not None:
            kpi.append({"v": f'{gl_stock/1000:,.1f}', "u": "百万吨",
                        "l": "全球大豆期末库存", "d": f'USDA PSD · MY{psd_meta["my"]}'})
        cn_imp = pv("中国", "imports")
        if cn_imp is not None:
            kpi.append({"v": f'{cn_imp/1000:,.1f}', "u": "百万吨",
                        "l": "中国大豆进口量", "d": f'USDA PSD · MY{psd_meta["my"]}'})

    conab_meta = {"asof": "—"}
    br_prod = None
    if cb:
        conab_meta["asof"] = cb[-1]["safra"]
        br_prod = fnum(cb[-1], "production_kt")
    if br_prod is not None:
        kpi.append({"v": f'{br_prod/1000:,.1f}', "u": "百万吨",
                    "l": "巴西大豆产量", "d": f'CONAB · {cb[-1]["safra"]} 作物年度'})

    fo_meta = {"asof": "—"}
    if fo:
        fo_last = fo[-1]
        fo_meta["asof"] = fo_last["month"]
        cv = fnum(fo_last, "crush_tons")
        if cv is not None:
            kpi.append({"v": f'{cv/1e6:.2f}', "u": "百万吨",
                        "l": "美国月度大豆压榨量", "d": f'NASS · {fo_last["month"]}'})

    oni_meta = {"asof": "—", "v": None}
    if oni:
        oni_last = oni[-1]
        oni_meta = {"asof": oni_last["month"], "v": fnum(oni_last, "oni")}
        if oni_meta["v"] is not None:
            v = oni_meta["v"]
            state = "厄尔尼诺" if v >= 0.5 else ("拉尼娜" if v <= -0.5 else "中性")
            kpi.append({"v": f'{v:+.2f}', "u": "°C",
                        "l": f"ONI（{state}）", "d": f'NOAA · {oni_last["month"]}'})

    river_meta = {"asof": "—", "v": None}
    if rs:
        river_meta = {"asof": rs[-1]["date"], "v": fnum(rs[-1], "stage_ft")}
        if river_meta["v"] is not None:
            kpi.append({"v": f'{river_meta["v"]:.2f}', "u": "英尺",
                        "l": "密西西比河水位",
                        "d": f'USGS 圣路易斯站 · {river_meta["asof"]}'})

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
                   "asof_crop": cp_last["week_ending"] if cp_last else "—",
                   "asof_psd": psd_meta["my"],
                   "asof_conab": conab_meta["asof"],
                   "asof_fo": fo_meta["asof"],
                   "asof_oni": oni_meta["asof"],
                   "asof_river": river_meta["asof"],
               }}

    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "dashboard_template.html"), encoding="utf-8").read()
    html = (tpl.replace("/*__DATA__*/", json.dumps(payload, ensure_ascii=False,
                                                   separators=(",", ":")))
               .replace("__ASOF_EXPORT__", payload["meta"]["asof_export"])
               .replace("__ASOF_DROUGHT__", payload["meta"]["asof_drought"])
               .replace("__ASOF_CRUSH__", payload["meta"]["asof_crush"])
               .replace("__ASOF_PSD__", payload["meta"]["asof_psd"])
               .replace("__ASOF_CONAB__", payload["meta"]["asof_conab"])
               .replace("__ASOF_FO__", payload["meta"]["asof_fo"])
               .replace("__ASOF_ONI__", payload["meta"]["asof_oni"])
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

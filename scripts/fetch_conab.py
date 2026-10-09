# -*- coding: utf-8 -*-
"""CONAB（巴西国家供应公司）大豆历史序列取数（年度）。

数据源：CONAB「Séries Históricas - Grãos - Soja」官方 XLS
  https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/
  safras/series-historicas/graos/soja/sojaseriehist.xls/@@download/file

工作表：Área（千公顷）/ Produtividade（千克每公顷）/ Produção（千吨），
每张表均含「BRASIL」全国合计行，覆盖 1976/77 起全部作物年度。

输出 data/conab_soy.csv：
  safra, year, area_kha, yield_kg_ha, production_kt
  （year 为该作物年度的起始年，便于与 USDA 营销年度对齐）
"""
import csv
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
DATA = os.path.join(ROOT, "data")
XLS = os.path.join(RAW, "conab_soja_seriehist.xls")
CSV_PATH = os.path.join(DATA, "conab_soy.csv")

URL = ("https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
       "safras/series-historicas/graos/soja/sojaseriehist.xls/@@download/file")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

SHEETS = {"Área": "area_kha", "Produtividade": "yield_kg_ha",
          "Produção": "production_kt"}
FIELDS = ["safra", "year", "area_kha", "yield_kg_ha", "production_kt"]


def download():
    os.makedirs(RAW, exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=120) as r:
        blob = r.read()
    if blob[:4] != b"\xd0\xcf\x11\xe0":          # OLE2 头，确认是真正的 .xls
        raise SystemExit(f"!! 下载到的不是 Excel 文件（前 8 字节 {blob[:8]!r}）")
    open(XLS, "wb").write(blob)
    print(f"已下载 {os.path.basename(XLS)}（{len(blob)/1024:.0f} KB）")


def to_num(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s or s.lower() in ("nan", "-", "..."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse():
    """用 xlrd 直接读 .xls（不依赖 pandas），提取各表 BRASIL 合计行。"""
    import xlrd
    book = xlrd.open_workbook(XLS)
    names = {n: i for i, n in enumerate(book.sheet_names())}
    out = {}
    for sheet, col in SHEETS.items():
        if sheet not in names:
            raise SystemExit(f"!! 缺少工作表 {sheet}（实际：{book.sheet_names()}）")
        sh = book.sheet_by_index(names[sheet])
        header = [str(x) for x in sh.row_values(5)]      # 第 6 行为年度表头
        safras = {}
        for j, h in enumerate(header):
            m = re.search(r"(\d{4})\s*/\s*(\d{2})", h)
            if m:
                safras[j] = f"{m.group(1)}/{m.group(2)}"
        row = None
        for i in range(sh.nrows):
            if str(sh.cell_value(i, 0)).strip().upper() == "BRASIL":
                row = sh.row_values(i)
                break
        if row is None:
            raise SystemExit(f"!! 工作表 {sheet} 未找到 BRASIL 合计行")
        for j, safra in safras.items():
            if j >= len(row):
                continue
            v = to_num(row[j])
            if v is None:
                continue
            out.setdefault(safra, {})[col] = v
        print(f"  {sheet}: {len(safras)} 个作物年度")
    return out


def main():
    if not os.path.exists(XLS) or os.path.getsize(XLS) < 10000:
        download()
    else:
        print(f"使用已缓存 {os.path.basename(XLS)}"
              f"（{os.path.getsize(XLS)/1024:.0f} KB）")
    recs = parse()

    rows = []
    for safra in sorted(recs, key=lambda s: int(s[:4])):
        r = recs[safra]
        if r.get("area_kha") is None and r.get("production_kt") is None:
            continue
        rows.append({"safra": safra, "year": int(safra[:4]),
                     "area_kha": r.get("area_kha"),
                     "yield_kg_ha": r.get("yield_kg_ha"),
                     "production_kt": r.get("production_kt")})

    os.makedirs(DATA, exist_ok=True)

    def cell(k, v):
        if v in (None, ""):
            return ""
        if k in ("safra", "year"):
            return v
        fv = float(v)
        return int(fv) if fv.is_integer() else round(fv, 4)

    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: cell(k, r.get(k)) for k in FIELDS})

    print(f"\nconab_soy.csv: {len(rows)} 个作物年度 "
          f"（{rows[0]['safra']} ~ {rows[-1]['safra']}）")
    for r in rows[-3:]:
        print(f"  {r['safra']}: 面积 {r['area_kha']:,.0f} 千公顷 | "
              f"单产 {r['yield_kg_ha']:,.0f} 千克/公顷 | "
              f"产量 {r['production_kt']:,.0f} 千吨")
    return 0


if __name__ == "__main__":
    sys.exit(main())

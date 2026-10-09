# -*- coding: utf-8 -*-
"""USDA 大豆干旱率取数（周度）。

主通道 —— USDA OCE / WAOB《Agriculture in Drought》官方大豆口径
    首页方法：POST/GET https://agindrought.unl.edu/Home.aspx/ReturnCropsTimeSeriesM2020
    必须带完整浏览器请求头（含 Origin / Referer / X-Requested-With / Content-Type），
    否则 ASP.NET 只会回吐整个 HTML 页面而不是 JSON。
    返回字段 D1/D2/D3/D4 均为「该等级及以上」的占比。
    已验证：2026-10-06 → D1+ = 25%、D3+ = 5%（与 USDA 周报公布值一致）。

兜底通道 —— 自建口径：USDM 州级面积占比 × NASS 州级大豆产量权重。
    仅在主通道不可用时启用；口径与官方略有差异（D1 档位偏高），会写入 _source 标记。

产物：data/raw/agindrought_soybeans.json、data/raw/drought_source.json、data/drought.csv
"""
import csv
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
DATA = os.path.join(ROOT, "data")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
AG = "https://agindrought.unl.edu"
ESMIS = "https://esmis.nal.usda.gov"
USDM = "https://usdmdataservices.unl.edu/api/StateStatistics"

STATES = {
    "Alabama": "01", "Arkansas": "05", "Delaware": "10", "Georgia": "13",
    "Illinois": "17", "Indiana": "18", "Iowa": "19", "Kansas": "20",
    "Kentucky": "21", "Louisiana": "22", "Maryland": "24", "Michigan": "26",
    "Minnesota": "27", "Mississippi": "28", "Missouri": "29", "Nebraska": "31",
    "New Jersey": "34", "New York": "36", "North Carolina": "37",
    "North Dakota": "38", "Ohio": "39", "Oklahoma": "40", "Pennsylvania": "42",
    "South Carolina": "45", "South Dakota": "46", "Tennessee": "47",
    "Texas": "48", "Virginia": "51", "Wisconsin": "55",
}


def http(url, headers=None, timeout=90):
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ------------------------------------------------------------------ 主通道
def official_series():
    """返回 [{date, none, d0..d4}, ...]（按日期倒序，与官方一致）。"""
    # 先取一次页面拿会话 Cookie（部分环境需要）
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    opener.addheaders = [("User-Agent", UA)]
    try:
        opener.open(f"{AG}/TimeSeries.aspx", timeout=60).read()
    except Exception:
        pass

    q = ('ctype=%22soybeans%22&ltype=%221%22&loc=%22United%20States%22')
    url = f"{AG}/Home.aspx/ReturnCropsTimeSeriesM2020?{q}"
    raw = opener.open(urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json; charset=utf-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": AG,
        "Referer": f"{AG}/TimeSeries.aspx",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }), timeout=120).read().decode("utf-8", "ignore")

    if not raw.lstrip().startswith("{"):
        raise RuntimeError("接口返回的不是 JSON（可能请求头不完整或页面结构变更）")
    data = json.loads(raw)["d"]
    rows = [{"date": r["Date"], "none": int(r["None"]), "d0": int(r["D0"]),
             "d1": int(r["D1"]), "d2": int(r["D2"]),
             "d3": int(r["D3"]), "d4": int(r["D4"])} for r in data]
    rows.sort(key=lambda x: x["date"])
    return rows


# ------------------------------------------------------------------ 兜底通道
def nass_weights():
    fp = os.path.join(RAW, "nass_soy_production.json")
    if os.path.exists(fp):
        return json.load(open(fp, encoding="utf-8"))
    import pymupdf
    html = http(f"{ESMIS}/publication/crop-production").decode("utf-8", "ignore")
    url = None
    for row in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        t = re.search(r'<time datetime="([^"]+)"', row)
        h = re.search(r'href="(/sites/default/release-files/[^"]+\.pdf)"', row, re.I)
        if t and h:
            url = ESMIS + h.group(1)
            break
    pdf_fp = os.path.join(RAW, "nass_crop_production.pdf")
    if not os.path.exists(pdf_fp):
        open(pdf_fp, "wb").write(http(url))
    doc = pymupdf.open(pdf_fp)
    page = None
    for i in range(doc.page_count):
        t = doc[i].get_text()
        if "Soybeans for Beans Area Harvested, Yield, and Production" in t and "Alabama" in t:
            page = i
            break
    txt = doc[page].get_text()
    names = [n.strip() for n in re.findall(r"([A-Z][A-Za-z ]+?)\s*\.{4,}", txt)]
    names = [n for n in names if n != "Crop Production"]
    body = txt.split("United States")[-1]
    nums = [float(x) for x in re.findall(r"\b\d[\d,]*\.?\d*\b", body.replace(",", ""))]
    n = len(names)
    prod = nums[6 * n:7 * n] if len(nums) >= 7 * n else nums[5 * n:6 * n]
    w = {nm: p for nm, p in zip(names, prod) if nm in STATES}
    total = sum(w.values())
    out = {"source_pdf": url, "total_kbu": total,
           "states": {k: {"production_kbu": v, "weight": v / total} for k, v in w.items()}}
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


def reconstructed():
    w = nass_weights()["states"]
    weights = {k: v["weight"] for k, v in w.items()}
    fp = os.path.join(RAW, "drought_usdm_state.csv")
    if not (os.path.exists(fp) and os.path.getsize(fp) > 5000):
        rows = []
        for name, fips in STATES.items():
            txt = http(f"{USDM}/GetDroughtSeverityStatisticsByAreaPercent"
                       f"?aoi={fips}&startdate=1/1/2011&enddate=12/31/2030&statisticsType=2"
                       ).decode("utf-8", "ignore")
            for l in [x for x in txt.strip().splitlines() if x.strip()][1:]:
                p = l.split(",")
                if len(p) < 8:
                    continue
                rows.append({"map_date": p[0], "state": name, "none": p[2], "d0": p[3],
                             "d1": p[4], "d2": p[5], "d3": p[6], "d4": p[7]})
        with open(fp, "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)

    by = {}
    with open(fp, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            st = r["state"]
            if st not in weights:
                continue
            a = by.setdefault(r["map_date"], {"d1": 0.0, "d3": 0.0, "w": 0.0})
            wt = weights[st]
            a["d1"] += wt * sum(float(r[x]) for x in ("d1", "d2", "d3", "d4"))
            a["d3"] += wt * sum(float(r[x]) for x in ("d3", "d4"))
            a["w"] += wt
    out = []
    for k in sorted(by):
        a = by[k]
        if a["w"] <= 0:
            continue
        out.append({"date": f"{k[:4]}-{k[4:6]}-{k[6:]}", "none": "", "d0": "",
                    "d1": round(a["d1"] / a["w"]), "d2": "",
                    "d3": round(a["d3"] / a["w"]), "d4": ""})
    return out


# ------------------------------------------------------------------ 主流程
def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    src = "official"
    try:
        rows = official_series()
        print(f"[官方口径] AgInDrought 大豆序列 {len(rows)} 周 "
              f"({rows[0]['date']} ~ {rows[-1]['date']})")
    except Exception as e:
        print(f"!! 官方口径获取失败：{e}\n   回退到自建口径（USDM × NASS 权重）")
        rows = reconstructed()
        src = "reconstructed"
        print(f"[自建口径] {len(rows)} 周 ({rows[0]['date']} ~ {rows[-1]['date']})")

    json.dump(rows, open(os.path.join(RAW, "agindrought_soybeans.json"), "w",
                         encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump({"source": src}, open(os.path.join(RAW, "drought_source.json"), "w",
                                    encoding="utf-8"))

    with open(os.path.join(DATA, "drought.csv"), "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["week_ending", "soy_d1plus", "soy_d2plus",
                                          "soy_d3plus"])
        w.writeheader()
        for r in rows:
            d = r["d1"]
            w.writerow({"week_ending": r["date"], "soy_d1plus": d,
                        "soy_d2plus": r["d2"] if r["d2"] != "" else "",
                        "soy_d3plus": r["d3"]})
    last = rows[-1]
    print(f"drought.csv 已更新（口径：{src}）；最新 {last['date']}: "
          f"D1+ = {last['d1']}%  D3+ = {last['d3']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())

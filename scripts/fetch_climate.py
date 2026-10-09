# -*- coding: utf-8 -*-
"""气候与航运水位取数（全部为官方公开数据）。

1) 厄尔尼诺 / 拉尼娜 —— NOAA PSL 的 ONI（Oceanic Niño Index）
   https://psl.noaa.gov/data/correlation/oni.data
   月度，1950 年至今，为 Niño 3.4 区海温异常的 3 个月滑动平均。
   ONI ≥ +0.5 为厄尔尼诺，≤ −0.5 为拉尼娜。

2) 美国内河水位 —— USGS NWIS 日值，密西西比河圣路易斯站（07010000）
   https://waterservices.usgs.gov/nwis/dv/?format=json&sites=07010000&parameterCd=00065
   参数 00065 = 河面高程（gage height, feet）。该站是美湾大豆出口驳船运输的
   关键水位指标：水位过低会限制驳船吃水、推高内河运费。

输出：
  data/oni.csv          month, oni
  data/river_stage.csv  date, stage_ft
"""
import csv
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
DATA = os.path.join(ROOT, "data")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
ONI_URL = "https://psl.noaa.gov/data/correlation/oni.data"
USGS_URL = ("https://waterservices.usgs.gov/nwis/dv/?format=json"
            "&sites={site}&parameterCd=00065&startDT={start}&endDT={end}")
SITE = "07010000"          # Mississippi River at St. Louis, MO
START = "2015-01-01"
# ONI 起始年：与看板其他年度序列保持可比的长度
ONI_FROM = 2000


def get(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------------------------------------------------------------- ONI
def fetch_oni():
    blob = get(ONI_URL).decode("utf-8", "ignore")
    open(os.path.join(RAW, "oni.data"), "w", encoding="utf-8").write(blob)
    rows = []
    for line in blob.splitlines():
        parts = line.split()
        if len(parts) != 13:
            continue
        try:
            year = int(parts[0])
        except ValueError:
            continue                      # 跳过表头「1950  2026」
        if year < ONI_FROM:
            continue
        for i, tok in enumerate(parts[1:], start=1):
            try:
                v = float(tok)
            except ValueError:
                continue
            if v <= -9.9:                 # -9.9 为缺测占位
                continue
            rows.append({"month": f"{year}-{i:02d}", "oni": round(v, 2)})
    rows.sort(key=lambda r: r["month"])
    p = os.path.join(DATA, "oni.csv")
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["month", "oni"])
        w.writeheader()
        w.writerows(rows)
    last = rows[-1]
    print(f"oni.csv: {len(rows)} 个月（{rows[0]['month']} ~ {last['month']}）；"
          f"最新 {last['month']} ONI = {last['oni']:+.2f}"
          + ("（厄尔尼诺）" if last["oni"] >= 0.5 else
             "（拉尼娜）" if last["oni"] <= -0.5 else "（中性）"))
    return rows


# ------------------------------------------------------- 内河水位
def fetch_river():
    import datetime
    end = datetime.date.today().isoformat()
    url = USGS_URL.format(site=SITE, start=START, end=end)
    d = json.loads(get(url).decode("utf-8"))
    ts = d.get("value", {}).get("timeSeries", [])
    if not ts:
        raise SystemExit("!! USGS 未返回水位序列")
    site_name = ts[0]["sourceInfo"]["siteName"]
    raw_vals = ts[0]["values"][0]["value"]
    rows = []
    for v in raw_vals:
        try:
            fv = float(v["value"])
        except (TypeError, ValueError):
            continue
        rows.append({"date": v["dateTime"][:10], "stage_ft": round(fv, 2)})
    rows.sort(key=lambda r: r["date"])
    p = os.path.join(DATA, "river_stage.csv")
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["date", "stage_ft"])
        w.writeheader()
        w.writerows(rows)
    print(f"river_stage.csv: {len(rows)} 天（{rows[0]['date']} ~ {rows[-1]['date']}）"
          f"；站点 {site_name}；最新 {rows[-1]['date']} = {rows[-1]['stage_ft']:.2f} ft")
    return rows


def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    try:
        fetch_oni()
    except Exception as e:
        print(f"!! ONI 取数失败: {type(e).__name__} {e}")
    try:
        fetch_river()
    except Exception as e:
        print(f"!! 内河水位取数失败: {type(e).__name__} {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

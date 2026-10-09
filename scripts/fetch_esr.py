# -*- coding: utf-8 -*-
"""USDA FAS ESR (Export Sales Reporting) 取数 —— 原始响应全量落盘，支持断点续传。

接口: https://api.fas.usda.gov/api/esr/...
Key : DEMO_KEY (约 30 次/小时, 50 次/天)。已存在的缓存文件不会重复请求。
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
API = "https://api.fas.usda.gov/api/esr"
KEY = os.environ.get("FAS_API_KEY", "DEMO_KEY")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 营销年度 -> API marketYear (= MY 起始年 + 1)
# 2019/20 -> 2020 ... 2026/27 -> 2027
MARKET_YEARS = list(range(2020, 2028))
COMMODITIES = {"soybeans": 801, "meal": 901}


def _get(path, params=None):
    url = f"{API}{path}"
    qs = []
    for k, v in (params or {}).items():
        qs.append(f"{k}={v}")
    qs.append(f"api_key={KEY}")
    url = url + "?" + "&".join(qs)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json, text/plain, */*",
        "Origin": "https://apps.fas.usda.gov",
        "Referer": "https://apps.fas.usda.gov/",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:200]
            if e.code in (429, 403) or "API key" in body:
                raise RuntimeError(f"RATE_LIMIT/KEY {e.code}: {body}")
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))


def fetch(path, params, fname):
    """带缓存的取数。"""
    fp = os.path.join(RAW, fname)
    if os.path.exists(fp) and os.path.getsize(fp) > 20:
        with open(fp, encoding="utf-8") as f:
            return json.load(f), True
    data = _get(path, params)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data, False


def main():
    os.makedirs(RAW, exist_ok=True)
    calls = 0

    # 1. 字典表
    for name, path, fn in [
        ("commodities", "/commodities", "esr_commodities.json"),
        ("countries", "/countries", "esr_countries.json"),
        ("uom", "/unitsOfMeasure", "esr_units.json"),
    ]:
        d, cached = fetch(path, {}, fn)
        calls += 0 if cached else 1
        print(f"[dict] {name}: {len(d)} 条 {'(缓存)' if cached else '(新取)'}")

    # 2. 逐年出口销售
    for cname, code in COMMODITIES.items():
        for my in MARKET_YEARS:
            fn = f"esr_{cname}_{my}.json"
            try:
                d, cached = fetch(
                    f"/exports/commodityCode/{code}/allCountries/marketYear/{my}",
                    {}, fn)
                calls += 0 if cached else 1
                weeks = sorted({r["weekEndingDate"][:10] for r in d})
                print(f"[{cname}] MY{my}: {len(d)} 条, {len(weeks)} 周 "
                      f"({weeks[0] if weeks else '-'} ~ {weeks[-1] if weeks else '-'})"
                      f" {'(缓存)' if cached else '(新取)'}")
                if not cached:
                    time.sleep(1.2)
            except RuntimeError as e:
                print(f"!! [{cname}] MY{my} 失败: {e}")
                print("   已触发限速，其余年度请稍后重跑（已取数已缓存，可直接续跑）")
                return 1

    print(f"\n本次实际消耗 API 调用: {calls}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

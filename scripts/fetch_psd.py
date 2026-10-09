# -*- coding: utf-8 -*-
"""USDA PSD 年度出口预测 —— 用于「出口销售进度」的分母。

attributeId 88 = Exports；大豆 PSD 商品码 2222000，国家码 US。
PSD 的 marketYear 采用「市场年度起始年」，故 2026 对应 2026/27。
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
KEY = os.environ.get("FAS_API_KEY", "DEMO_KEY")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
API = "https://api.fas.usda.gov/api/psd"
SOY = "2222000"
ATTR_EXPORTS = 88


def get(path):
    url = f"{API}{path}{'&' if '?' in path else '?'}api_key={KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    out = {}
    for my in range(2019, 2027):
        fn = os.path.join(RAW, f"psd_soy_us_{my}.json")
        if os.path.exists(fn) and os.path.getsize(fn) > 100:
            d = json.load(open(fn, encoding="utf-8"))
        else:
            d = get(f"/commodity/{SOY}/country/US/year/{my}")
            json.dump(d, open(fn, "w", encoding="utf-8"), ensure_ascii=False)
        rows = [r for r in d if r.get("attributeId") == ATTR_EXPORTS and r.get("countryCode") == "US"]
        if not rows:
            print(f"MY{my}: 无 Exports 记录")
            continue
        # 取该年度内最新月份的口径（随 WASDE 迭代更新）
        rows.sort(key=lambda r: (r.get("calendarYear", ""), r.get("month", "")))
        latest = rows[-1]
        out[str(my)] = {
            "value": latest["value"],
            "unitId": latest.get("unitId"),
            "asof": f'{latest.get("calendarYear")}-{latest.get("month")}',
            "series": [{"asof": f'{r.get("calendarYear")}-{r.get("month")}', "value": r["value"]} for r in rows],
        }
        print(f"MY{my}/{str(my+1)[2:]}: 出口预测 {latest['value']:,.0f} (unit {latest.get('unitId')}) 截至 {latest.get('calendarYear')}-{latest.get('month')}")

    json.dump(out, open(os.path.join(RAW, "psd_us_exports.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())

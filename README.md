# USDA 美豆数据看板

单文件、可离线打开的静态数据看板，跟踪美豆基本面最常看的五组 USDA 周度指标：

| 模块 | 指标 | 数据源 |
|---|---|---|
| ① 美豆出口销售 | 当周净销售 / 累计总销售 / 当周装船 / 销售进度 | USDA FAS — Export Sales Reporting |
| ② 对华与除中国外 | 对华净销售、对华累计、除中国外净销售、除中国外累计 | USDA FAS — ESR（国家维度） |
| ③ 美豆粕出口销售 | 净销售 / 累计总销售 / 装船 / 累计装船 | USDA FAS — ESR（Soybean cake & meal） |
| ④ 美豆干旱率 | 干旱率 D1+ / 重度干旱率 D3+ | USDA OCE·WAOB — Agriculture in Drought |
| ⑤ 伊利诺伊压榨 | 压榨毛利 / 毛豆油价 / 48% 豆粕价 / 黄大豆价 | USDA AMS — Soybean Crush Report |

在线查看（GitHub Pages）：`https://<你的用户名>.github.io/<仓库名>/`

## 数据来源与口径

所有数据均由脚本直接调用 USDA 官方公开接口获取，每周自动更新。

- **出口销售**：`api.fas.usda.gov/api/esr/exports/commodityCode/{801|901}/allCountries/marketYear/{MY}?api_key=…`
  - 商品码：`801` 大豆、`901` 豆粕；营销年度码 = 年度结束年（2026/27 → `2027`）
  - 中国在 FAS 国家编码中为 `5700`；「除中国外」= 全部国家合计 − 中国
  - 字段：`currentMYNetSales` 当周净销售、`currentMYTotalCommitment` 累计总销售、
    `weeklyExports` 当周装船、`accumulatedExports` 累计装船（单位公吨，看板换算为万吨）
- **销售进度**：分母取 USDA PSD 对该年度的全年出口预测
  （`api.fas.usda.gov/api/psd/commodity/2222000/country/US/year/{MY}`，属性 `Exports`）。
  采用最新一期预测值，因此历史年度的终值进度未必正好等于 100%。
- **干旱率**：USDA OCE/WAOB《Agriculture in Drought》官方大豆口径，周度序列自 2000 年至今。
  接口为站点首页方法 `Home.aspx/ReturnCropsTimeSeriesM2020`，**必须带完整浏览器请求头**
  （`Origin` / `Referer` / `X-Requested-With` / `Content-Type`），否则只会返回整页 HTML。
  字段 D1/D2/D3/D4 均为「该等级及以上」的占比。
  若该接口不可用，脚本会自动回退到「USDM 州级面积占比 × NASS 州级大豆产量权重」的自建口径，
  并在 `data/raw/drought_source.json` 中标记实际使用的口径。
- **压榨数据**：USDA AMS《Soybean Crush Report》(GX_GR211)，经 ESMIS 归档文本解析。
  毛利 = 每蒲式耳大豆产出的油粕总值 − 1 号黄大豆卡车价。

## 快速开始

```bash
pip install -r requirements.txt

export FAS_API_KEY=<你的 api.data.gov key>   # 免费申请：https://api.data.gov/signup/

python scripts/fetch_esr.py        # 出口销售（大豆 + 豆粕，各 8 个年度）
python scripts/fetch_psd.py        # 年度出口预测（进度分母）
python scripts/fetch_drought.py    # 美豆干旱率
python scripts/fetch_crush.py      # 伊利诺伊压榨周报
python scripts/build_extra.py      # 压榨 CSV
python scripts/build_data.py       # 聚合清洗
python scripts/build_dashboard.py  # 生成 index.html

node scripts/smoke_test.js         # 冒烟测试
```

原始接口响应会缓存到 `data/raw/`，重复运行不会重新请求。

## 自动更新

`.github/workflows/update.yml` 每周五（北京时间）自动运行取数与构建，并把更新后的
`index.html` 与 `data/*.csv` 提交回仓库，GitHub Pages 随即生效。

需要在仓库 **Settings → Secrets and variables → Actions** 中添加：

| Secret | 说明 |
|---|---|
| `FAS_API_KEY` | api.data.gov 的 key，免费申请。用于 FAS 的 ESR / PSD 接口 |

启用 Pages：**Settings → Pages → Source** 选择 `Deploy from a branch`，分支选 `main`、目录选 `/ (root)`。

## 已知限制

**伊利诺伊压榨模块数据不完整。** 该报表 2022-08 起并入 AMS《National Weekly Grain Co-Products
Report》(AMS_3618)，并迁移至 USDA My Market News / MARS 平台。该平台对部分网络出口整体返回
`Access Denied`（Akamai 按 IP 拦截，真实浏览器同样被拒）；ESMIS 镜像虽保留 2022-08～2025-08 的
发布记录，但对应 PDF 文件已 404。因此在受限网络下该模块只能呈现 2020-01 ~ 2022-07 的周度数据。
若运行环境可正常访问 AMS，可自行扩展 `scripts/fetch_crush.py` 补齐。

## 免责声明

本看板为基于 USDA 公开数据的独立整理，非 USDA 官方发布物，不构成任何投资建议。
图表数值以 USDA 原始口径为准。

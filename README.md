# 大豆基本面数据看板

单文件、可离线打开的静态数据看板，跟踪大豆基本面最常看的十组指标。
数据全部来自各国官方公开数据源，**不含任何价格、金额或期货持仓口径**。

| 模块 | 指标 | 数据源 |
|---|---|---|
| ① 美豆出口销售 | 当周净销售 / 累计总销售 / 当周装船 / 销售进度 | USDA FAS — Export Sales Reporting |
| ② 对华与除中国外 | 对华净销售、对华累计、除中国外净销售、除中国外累计 | USDA FAS — ESR（国家维度） |
| ③ 美豆粕出口销售 | 净销售 / 累计总销售 / 装船 / 累计装船 | USDA FAS — ESR（Soybean cake & meal） |
| ④ 美豆干旱率 | 干旱率 D1+ / 重度干旱率 D3+ | USDA OCE·WAOB — Agriculture in Drought |
| ⑤ 作物生长与优良率 | 播种 / 出芽 / 开花 / 结荚 / 落叶 / 收获进度、优良率、差劣率 | USDA NASS — Crop Progress |
| ⑥ 伊利诺伊压榨 ⚠️ | 压榨毛利 / 毛豆油价 / 48% 豆粕价 / 黄大豆价（价格类，覆盖不全） | USDA AMS — Soybean Crush Report |
| ⑦ 全球大豆供需平衡 | 产量 / 收获面积 / 单产 / 压榨 / 出口 / 进口 / 期末库存（美·巴·阿·中·全球） | USDA FAS — PSD |
| ⑧ 巴西大豆产量 | 种植面积 / 单产 / 产量（CONAB 与 USDA 对照） | 巴西 CONAB + USDA PSD |
| ⑨ 美国月度压榨 | 月度压榨量 / 豆粕产量 / 豆粕库存 / 豆油产量 | USDA NASS — Fats and Oils |
| ⑩ 气候与航运水位 | 厄尔尼诺-拉尼娜 ONI / 密西西比河水位 | NOAA PSL + USGS NWIS |

在线查看（GitHub Pages）：`https://<你的用户名>.github.io/<仓库名>/`

## 数据来源与口径

所有数据均由脚本直接调用各机构官方公开接口获取，每周自动更新。
除模块 ⑥ 外，全部为实物量、面积、进度、库存、气候与水位口径；期货持仓、现货价、
期货价差、汇率、运费与压榨利润等金额/价格类指标一律未纳入。

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
- **作物生长与优良率**：USDA NASS《Crop Progress》周报文本（ESMIS 归档），取各表「18 States」全国合计行。
  优良率 = Good + Excellent，差劣率 = Very poor + Poor；进度类表格列序为
  「去年同期 / 上周 / 本周 / 五年均值」，本看板取本周值。出芽 / 开花 / 结荚 / 落叶同理。
  该报告冬季（约 11 月下旬至次年 4 月）不含大豆相关表，曲线为季节性分段。
- **全球供需平衡**：USDA FAS PSD 数据库，商品码 `2222000`，接口
  `api.fas.usda.gov/api/psd/commodity/2222000/{country/US|BR|AR|CH|world}/year/{MY}`。
  属性 ID：`4` 收获面积（千公顷）、`184` 单产（吨/公顷）、`28` 产量、`7` 压榨、
  `88` 出口、`57` 进口、`176` 期末库存（千吨）。
  同一营销年度内会随 WASDE 多次修订，脚本取**最新月份**那一版；「全球」直接调用 PSD 的世界合计端点。
- **巴西大豆序列**：CONAB（巴西国家供应公司）官方「Séries Históricas - Grãos - Soja」XLS，
  含 1976/77 起全部作物年度的面积 / 单产 / 产量，取其中 `BRASIL` 全国合计行。
  USDA 曲线取自 PSD；两者口径不同（CONAB 为播种面积，PSD 为收获面积）。
- **美国月度压榨**：USDA NASS《Fats and Oils: Oilseed Crushings, Production, Consumption
  and Stocks》月报（ESMIS 归档文本），取主体表 «Soybean Crushing… - United States» 的「本月」列。
- **气候与水位**：ONI 取自 NOAA PSL `psl.noaa.gov/data/correlation/oni.data`，
  为 Niño 3.4 区海温距平的 3 个月滑动平均（≥ +0.5 厄尔尼诺，≤ −0.5 拉尼娜）；
  内河水位取自 USGS NWIS 日值，站点 `07010000`（密西西比河圣路易斯站），参数 `00065` 河面高程。

## 快速开始

```bash
pip install -r requirements.txt

export FAS_API_KEY=<你的 api.data.gov key>   # 免费申请：https://api.data.gov/signup/

python scripts/fetch_esr.py            # 出口销售（大豆 + 豆粕，各 8 个年度）
python scripts/fetch_psd.py            # 年度出口预测（进度分母）
python scripts/fetch_drought.py        # 美豆干旱率
python scripts/fetch_crush.py          # 伊利诺伊压榨周报
python scripts/fetch_crop_progress.py  # 作物生长报告（增量；--full 可全量回填）
python scripts/fetch_psd_balance.py    # 各国大豆供需平衡（PSD）
python scripts/fetch_conab.py          # 巴西 CONAB 大豆历史序列
python scripts/fetch_fats_oils.py      # 美国月度压榨（增量；--full 可全量回填）
python scripts/fetch_climate.py        # ENSO 指数 + 密西西比河水位
python scripts/build_extra.py          # 压榨 / 干旱 CSV
python scripts/build_data.py           # 聚合清洗
python scripts/build_dashboard.py      # 生成 index.html

node scripts/smoke_test.js             # 冒烟测试（92 项）
```

原始接口响应会缓存到 `data/raw/`，重复运行不会重新请求。

## 自动更新

`.github/workflows/update.yml` 每周五（北京时间 20:00）自动运行取数与构建，并把更新后的
`index.html` 与 `data/*.csv` 提交回仓库，GitHub Pages 随即生效。数据无变化时不会产生提交。

需要在仓库 **Settings → Secrets and variables → Actions** 中添加：

| Secret | 说明 |
|---|---|
| `FAS_API_KEY` | api.data.gov 的 key，免费申请。用于 FAS 的 ESR / PSD 接口 |

启用 Pages：**Settings → Pages → Source** 选择 `Deploy from a branch`，分支选 `main`、目录选 `/ (root)`。

## 已知限制

1. **伊利诺伊压榨模块（⑥）数据不完整。** 该报表 2022-08 起并入 AMS《National Weekly Grain
   Co-Products Report》(AMS_3618)，并迁移至 USDA My Market News / MARS 平台。该平台对部分网络
   出口整体返回 `Access Denied`（Akamai 按 IP 拦截，真实浏览器同样被拒）；ESMIS 镜像虽保留
   2022-08～2025-08 的发布记录，但对应 PDF 文件已 404。因此该模块目前只能呈现 2020-01 ~ 2022-07。
   该模块属于价格/利润口径，与看板其余板块口径不同，可按需移除。
2. **周度出口检验报告未纳入。** USDA AMS/FGIS 的 Grain Inspections 与被拦截的 AMS 同源，
   无法获取。国际贸易量改用 PSD 的年度出口/进口口径。
3. **巴西月度出口、中国海关月度进口未纳入。** 巴西 SECEX/Comex Stat 与中国海关总署、
   国家统计局站点对本网络出口返回 403/412，改用 PSD 的年度口径。
   国产大豆产量、生猪存栏等中国指标同理未纳入。
4. **NASS QuickStats 需单独的 key**，本看板改用 ESMIS 归档报告文本解析，效果等价。

## 免责声明

本看板为基于各国官方公开数据的独立整理，非任何机构的官方发布物，不构成任何投资建议。
图表数值以原始口径为准。

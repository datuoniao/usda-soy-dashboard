// 看板冒烟测试：语法 + 运行时渲染 + 标签配对 + 数值校验
const fs = require('fs');
const path = require('path');

const fp = path.join(__dirname, '..', 'index.html');
const html = fs.readFileSync(fp, 'utf8');

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log('  PASS ' + name + (extra ? '  ' + extra : '')); }
  else { fail++; console.log('  FAIL ' + name + (extra ? '  ' + extra : '')); }
}

// ---------- 1. 语法检查
const m = html.match(/<script>([\s\S]*?)<\/script>/);
check('提取到 <script> 块', !!m);
const js = m ? m[1] : '';
try { new Function(js); check('JS 语法检查', true); }
catch (e) { check('JS 语法检查', false, e.message); }

// ---------- 2. 运行时渲染
function mkEl(id) {
  const el = {
    id: id, _html: '', style: {}, dataset: {}, _cls: {},
    classList: {
      add() {}, remove() {}, toggle() {}, contains() { return false; }
    },
    addEventListener() {}, setAttribute() {}, getAttribute() { return null; },
    querySelector() { return null; }, querySelectorAll() { return []; }
  };
  Object.defineProperty(el, 'innerHTML', {
    get() { return el._html; },
    set(v) { el._html = String(v); }
  });
  Object.defineProperty(el, 'textContent', {
    get() { return el._html; },
    set(v) { el._html = String(v); }
  });
  return el;
}
const store = {};
const doc = {
  getElementById(id) { return store[id] || (store[id] = mkEl(id)); },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  createElement(t) { return mkEl(t); },
  addEventListener() {}
};
const win = { addEventListener() {} };
const IO = function (cb) { this.observe = function () {}; };
const OUT = {};

try {
  new Function('document', 'window', 'IntersectionObserver', 'OUT',
    js + '\nOUT.boot = boot; OUT.DATA = DATA; OUT.drawChart = drawChart;' +
         '\nOUT.applyPreset = applyPreset; OUT.toggleYear = toggleYear;' +
         '\nOUT.ACTIVE = ACTIVE; OUT.chartById = chartById;'
  )(doc, win, IO, OUT);
  check('脚本在 DOM stub 下执行', true);
} catch (e) {
  check('脚本在 DOM stub 下执行', false, e.message);
}

// ---------- 3. 渲染产物
const charts = OUT.DATA ? OUT.DATA.charts : [];
check('图表数量 = 42', charts.length === 42, '实际 ' + charts.length);
check('KPI 渲染', (store['kpis'] ? store['kpis']._html : '').length > 100);
let svgCount = 0;
charts.forEach(function (c) {
  const h = store[c.id] ? store[c.id]._html : '';
  if (h.indexOf('<svg') === 0) svgCount++;
  const lg = store['lg-' + c.id] ? store['lg-' + c.id]._html : '';
  if (lg.indexOf('<button') < 0) console.log('    注意：legend 未渲染 ' + c.id);
});
check('全部图表均产出 <svg>', svgCount === 42, '实际 ' + svgCount);
check('KPI 数量 ≥ 10', OUT.DATA.kpis.length >= 10, '实际 ' + OUT.DATA.kpis.length);

const chk = store['chk'] ? store['chk']._html : '';
check('快照表渲染', chk.indexOf('<thead>') >= 0);
check('快照表 8 行', (chk.match(/<tr>/g) || []).length === 9, 'tr=' + (chk.match(/<tr>/g) || []).length);

// ---------- 4. 标签配对（静态区，去掉 script/style）
const body = html.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<style[\s\S]*?<\/style>/g, '');
const openDiv = (body.match(/<div[\s>]/g) || []).length;
const closeDiv = (body.match(/<\/div>/g) || []).length;
check('div 开闭配对', openDiv === closeDiv, openDiv + ' / ' + closeDiv);
const openSec = (body.match(/<section[\s>]/g) || []).length;
const closeSec = (body.match(/<\/section>/g) || []).length;
check('section 开闭配对', openSec === closeSec, openSec + ' / ' + closeSec);

// ---------- 5. 快照表数值校验（与 USDA 公布值对照）
const snap = OUT.DATA && OUT.DATA.snapshot ? OUT.DATA.snapshot : [];
check('快照表 8 行', snap.length === 8, '实际 ' + snap.length);
const expect = {
  '当周出口净销售': 54.94, '累计出口总销售': 2278.52, '当周出口装船': 137.97,
  '对华当周净销售': 38.29, '对华累计销售': 1114.23,
  '除中国外当周净销售': 16.65, '除中国外累计销售': 1164.29
};
let numOk = true;
snap.forEach(function (r) {
  if (expect[r.n] === undefined) return;
  const ok = Math.abs(r.c - expect[r.n]) < 0.06;
  if (!ok) numOk = false;
  console.log('    ' + (ok ? 'OK  ' : 'BAD ') + r.n + '  本期=' + r.c + '  USDA公布=' + expect[r.n]);
});
check('关键指标与 USDA 公布值一致', numOk);

// ---------- 5b. 页面不含特定机构字样
['中粮', '武汉', '每日观察', '复刻'].forEach(function (kw) {
  check('页面不含「' + kw + '」', html.indexOf(kw) < 0);
});

// ---------- 5c. 无遗留占位符
['__ASOF_EXPORT__', '__ASOF_DROUGHT__', '__ASOF_CRUSH__', '__GENERATED__',
 '__ASOF_PSD__', '__ASOF_CONAB__', '__ASOF_FO__', '__ASOF_ONI__'].forEach(function (p) {
  check('占位符已替换 ' + p, html.indexOf(p) < 0);
});

// ---------- 5d. 新增模块不含价格 / 金额 / 期货持仓类口径
const s7 = html.indexOf('id="s7"'), s11 = html.indexOf('id="s11"');
const newHtml = (s7 >= 0 && s11 > s7) ? html.slice(s7, s11) : '';
check('截取到新增模块 HTML', newHtml.length > 2000, '长度 ' + newHtml.length);
['均价', '现货价', '期货', '持仓', '汇率', '价差', '利润', '成本',
 '美元', '元/吨', '美分', '蒲式耳'].forEach(function (kw) {
  const cnt = newHtml.split(kw).length - 1;
  check('新增模块不含价格类字样「' + kw + '」', cnt === 0, '出现 ' + cnt + ' 次');
});
const newChartIds = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'b1', 'b2', 'b3',
                     'f1', 'f2', 'f3', 'f4', 'w1', 'w2', 'c23', 'c24', 'c25', 'c26'];
check('新增图表已全部生成', newChartIds.every(function (id) {
  return charts.some(function (c) { return c.id === id; });
}), '缺失 ' + newChartIds.filter(function (id) {
  return !charts.some(function (c) { return c.id === id; });
}).join(','));

// ---------- 6. 干旱与优良率锚点
const d13 = charts.filter(function (x) { return x.id === 'c13'; })[0];
const lastD = d13.s[d13.s.length - 1].p[d13.s[d13.s.length - 1].p.length - 1][1];
check('干旱率最新值 = 25%', lastD === 25, '实际 ' + lastD);
const d14 = charts.filter(function (x) { return x.id === 'c14'; })[0];
const lastD3 = d14.s[d14.s.length - 1].p[d14.s[d14.s.length - 1].p.length - 1][1];
check('重度干旱率最新值 = 5%', lastD3 === 5, '实际 ' + lastD3);

const c19 = charts.filter(function (x) { return x.id === 'c19'; })[0];
check('优良率图有数据', c19 && c19.s.length > 0 && c19.s[c19.s.length - 1].p.length > 0,
  c19 ? c19.s.length + ' 年' : '缺失');
if (c19 && c19.s.length) {
  const lastGe = c19.s[c19.s.length - 1];
  const v = lastGe.p[lastGe.p.length - 1];
  check('优良率最新值在合理区间(0-100)', v[1] >= 0 && v[1] <= 100, '实际 ' + v[1]);
}
['c20', 'c21', 'c22', 'c23', 'c24', 'c25', 'c26'].forEach(function (id) {
  const c = charts.filter(function (x) { return x.id === id; })[0];
  check('图表 ' + id + ' 有数据', !!c && c.s.length > 0 && c.s[0].p.length > 0,
    c ? c.s.length + ' 年' : '缺失');
});

// ---------- 6b. 新增模块数值锚点（对照各官方源公布值）
function lastVal(cid, label) {
  const c = charts.filter(function (x) { return x.id === cid; })[0];
  if (!c) return null;
  const ser = label ? c.s.filter(function (s) { return s.label === label; })[0]
                    : c.s[c.s.length - 1];
  if (!ser || !ser.p.length) return null;
  return ser.p[ser.p.length - 1][1];
}
function near(a, b, tol) { return a !== null && Math.abs(a - b) <= tol; }

check('全球大豆产量最新 = 442.3 百万吨', near(lastVal('p1', '全球'), 442.3, 1.0),
  '实际 ' + lastVal('p1', '全球'));
check('美国大豆产量最新 = 123.4 百万吨', near(lastVal('p1', '美国'), 123.4, 1.0),
  '实际 ' + lastVal('p1', '美国'));
check('巴西大豆产量(USDA)最新 = 186.0 百万吨', near(lastVal('p1', '巴西'), 186.0, 1.0),
  '实际 ' + lastVal('p1', '巴西'));
check('中国大豆进口量最新 = 115.0 百万吨', near(lastVal('p6', '中国'), 115.0, 1.0),
  '实际 ' + lastVal('p6', '中国'));
check('全球大豆期末库存最新 = 124.0 百万吨', near(lastVal('p7', '全球'), 124.0, 1.0),
  '实际 ' + lastVal('p7', '全球'));

check('CONAB 巴西产量最新 = 180.4 百万吨', near(lastVal('b3', 'CONAB'), 180.4, 1.0),
  '实际 ' + lastVal('b3', 'CONAB'));
check('CONAB 与 USDA 巴西产量差异 < 8%',
  (function () {
    const a = lastVal('b3', 'CONAB'), b = lastVal('b3', 'USDA');
    return a && b && Math.abs(a - b) / b < 0.08;
  })(), lastVal('b3', 'CONAB') + ' vs ' + lastVal('b3', 'USDA'));

check('美国月度压榨最新 = 6.29 百万吨', near(lastVal('f1'), 6.29, 0.03),
  '实际 ' + lastVal('f1'));
check('美国豆粕月度产量最新 = 460.5 万吨', near(lastVal('f2'), 460.5, 3),
  '实际 ' + lastVal('f2'));

check('ONI 最新值 ≈ +2.16', near(lastVal('w1'), 2.16, 0.2), '实际 ' + lastVal('w1'));
check('密西西比河水位有数据', lastVal('w2') !== null, '实际 ' + lastVal('w2'));

// 年度类图表的横轴类型与年份跨度
['p1', 'b1', 'w1'].forEach(function (id) {
  const c = charts.filter(function (x) { return x.id === id; })[0];
  check(id + ' 为年度横轴且含年份跨度', !!c && c.xm === 'year' && Array.isArray(c.yr),
    c ? c.xm + ' ' + JSON.stringify(c.yr) : '缺失');
});
check('年度类图表数量 = 11',
  charts.filter(function (c) { return c.xm === 'year'; }).length === 11,
  '实际 ' + charts.filter(function (c) { return c.xm === 'year'; }).length);

// ---------- 7. 横轴收缩
// 生长季类图表（只在部分月份有数据）应收缩横轴、不留大片空白
['c19', 'c20', 'c21', 'c22', 'c23', 'c24', 'c25', 'c26'].forEach(function (id) {
  const c = charts.filter(function (x) { return x.id === id; })[0];
  const span = c ? c.xmax - c.xmin : 0;
  check(id + ' 横轴已按数据收缩', c && span < 300 && c.xmin > 60,
    c ? (c.xmin + '~' + c.xmax) : '缺失');
});
// 月度压榨覆盖全年，横轴应保留 1–12 月
['f1', 'f2', 'f3', 'f4'].forEach(function (id) {
  const c = charts.filter(function (x) { return x.id === id; })[0];
  check(id + ' 为整年日历横轴', !!c && c.xm === 'day' && c.xmin === 1 && c.xmax === 365,
    c ? (c.xmin + '~' + c.xmax) : '缺失');
});
check('干旱模块保持全年横轴',
  (charts.filter(function (x) { return x.id === 'c13'; })[0] || {}).xmax === 366);
check('出口销售保持周序号横轴',
  (charts.filter(function (x) { return x.id === 'c1'; })[0] || {}).xmax === 53);

// ---------- 8. 年份 / 区间筛选交互
function activeCount(cid) {
  const a = OUT.ACTIVE[cid] || {};
  return Object.keys(a).filter(function (k) { return a[k] !== false; }).length;
}
function isYear(c) { return c.xm === 'year'; }
const flowCharts = charts.filter(function (c) { return !isYear(c); });
const yearCharts = charts.filter(isYear);

check('初始状态全部曲线可见', charts.every(function (c) {
  return activeCount(c.id) === c.s.length;
}));

OUT.applyPreset('last');
check('预设「仅最新」：周度/日历图每图只留 1 年', flowCharts.every(function (c) {
  return activeCount(c.id) === 1;
}));
check('预设「仅最新」：年度图保留全部曲线并收缩到最新 1 年', yearCharts.every(function (c) {
  return activeCount(c.id) === c.s.length &&
         c._xmin >= Math.floor(c.yr[1]);
}), yearCharts.map(function (c) { return c.id + ':' + c._xmin; }).join(' '));

const c19c = charts.filter(function (x) { return x.id === 'c19'; })[0];
const lastLbl = c19c.s[c19c.s.length - 1].label;
check('「仅最新」保留的是最后一年', OUT.ACTIVE['c19'][lastLbl] === true);

OUT.toggleYear('c19', lastLbl);
check('单独再关掉一年即为空', activeCount('c19') === 0);
check('全部隐藏时渲染提示文案',
  (store['c19']._html || '').indexOf('chart-empty') >= 0);

OUT.applyPreset('recent3');
check('预设「近 3 年」：周度/日历图每图 3 年', flowCharts.every(function (c) {
  const n = Math.min(3, c.s.length);
  return activeCount(c.id) === n;
}));
check('预设「近 3 年」：年度图横轴收缩到 3 年', yearCharts.every(function (c) {
  return c._xmin === Math.max(c.xmin, Math.floor(c.yr[1]) - 2);
}), yearCharts.map(function (c) { return c.id + ':' + c._xmin; }).join(' '));

OUT.applyPreset('all');
check('预设「全部年份」恢复：曲线全开', charts.every(function (c) {
  return activeCount(c.id) === c.s.length;
}));
check('预设「全部年份」恢复：年度图横轴回到起点', yearCharts.every(function (c) {
  return c._xmin === c.xmin;
}));
check('恢复后图表重新产出 svg', (store['c19']._html || '').indexOf('<svg') === 0);
check('年度图恢复后仍产出 svg', (store['p1']._html || '').indexOf('<svg') === 0);

// ---------- 9. 无外部依赖
check('无外部 CDN 引用',
  !/src\s*=\s*["']https?:/.test(html) && !/href\s*=\s*["']https?:/.test(html));

console.log('\n=== ' + pass + ' passed, ' + fail + ' failed ===');
process.exit(fail ? 1 : 0);

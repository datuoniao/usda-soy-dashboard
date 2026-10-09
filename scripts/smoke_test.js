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
    js + '\nOUT.boot = boot; OUT.DATA = DATA; OUT.drawChart = drawChart;'
  )(doc, win, IO, OUT);
  check('脚本在 DOM stub 下执行', true);
} catch (e) {
  check('脚本在 DOM stub 下执行', false, e.message);
}

// ---------- 3. 渲染产物
const charts = OUT.DATA ? OUT.DATA.charts : [];
check('图表数量 = 18', charts.length === 18, '实际 ' + charts.length);
check('KPI 渲染', (store['kpis'] ? store['kpis']._html : '').length > 100);
let svgCount = 0;
charts.forEach(function (c) {
  const h = store[c.id] ? store[c.id]._html : '';
  if (h.indexOf('<svg') === 0) svgCount++;
  const lg = store['lg-' + c.id] ? store['lg-' + c.id]._html : '';
  if (lg.indexOf('<span>') < 0) console.log('    注意：legend 未渲染 ' + c.id);
});
check('18 张图均产出 <svg>', svgCount === 18, '实际 ' + svgCount);

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
['__ASOF_EXPORT__', '__ASOF_DROUGHT__', '__ASOF_CRUSH__', '__GENERATED__'].forEach(function (p) {
  check('占位符已替换 ' + p, html.indexOf(p) < 0);
});

// ---------- 6. 干旱锚点
const d13 = charts.filter(function (x) { return x.id === 'c13'; })[0];
const lastD = d13.s[d13.s.length - 1].p[d13.s[d13.s.length - 1].p.length - 1][1];
check('干旱率最新值 = 25%', lastD === 25, '实际 ' + lastD);
const d14 = charts.filter(function (x) { return x.id === 'c14'; })[0];
const lastD3 = d14.s[d14.s.length - 1].p[d14.s[d14.s.length - 1].p.length - 1][1];
check('重度干旱率最新值 = 5%', lastD3 === 5, '实际 ' + lastD3);

// ---------- 7. 无外部依赖
check('无外部 CDN 引用', !/src\s*=\s*["']https?:/.test(html) && !/href\s*=\s*["']https?:/.test(html));

console.log('\n=== ' + pass + ' passed, ' + fail + ' failed ===');
process.exit(fail ? 1 : 0);

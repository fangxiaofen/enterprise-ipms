/* 企业知识产权管理系统 - 核心工具、接口封装与通用组件 */
(function (global) {
  'use strict';

  // ---------------- DOM ----------------
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.prototype.slice.call((root || document).querySelectorAll(sel));

  function esc(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function el(tag, cls, html) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html !== undefined) n.innerHTML = html;
    return n;
  }

  // ---------------- 接口 ----------------
  // GET 的查询参数需拼在 URL 上，不能作为 body 传入
  function qs(q) {
    if (!q) return '';
    const pairs = Object.keys(q)
      .filter(k => q[k] !== '' && q[k] !== null && q[k] !== undefined)
      .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(q[k]));
    return pairs.length ? '?' + pairs.join('&') : '';
  }

  async function req(method, path, body) {
    const opt = { method, headers: { 'Content-Type': 'application/json' } };
    if (body !== undefined) opt.body = JSON.stringify(body);
    let res, data;
    try {
      res = await fetch(path, opt);
      data = await res.json();
    } catch (e) {
      throw new Error('无法连接服务端，请确认 server.py 正在运行');
    }
    if (!data.ok) throw new Error(data.error || ('请求失败 ' + res.status));
    return data.data !== undefined ? data.data : data;
  }
  const API = {
    get: (p, q) => req('GET', p + qs(q)),
    post: (p, b) => req('POST', p, b),
    put: (p, b) => req('PUT', p, b),
    del: (p) => req('DELETE', p),
    meta: () => req('GET', '/api/meta'),
    company: () => req('GET', '/api/company'),
    saveCompany: (b) => req('PUT', '/api/company', b),
    assets: (q) => req('GET', '/api/assets' + qs(q)),
    asset: (id) => req('GET', '/api/assets/' + id),
    createAsset: (b) => req('POST', '/api/assets', b),
    updateAsset: (id, b) => req('PUT', '/api/assets/' + id, b),
    deleteAsset: (id) => req('DELETE', '/api/assets/' + id),
    addLog: (id, b) => req('POST', '/api/assets/' + id + '/logs', b),
    delLog: (id) => req('DELETE', '/api/logs/' + id),
    addFee: (id, b) => req('POST', '/api/assets/' + id + '/fees', b),
    updateFee: (id, b) => req('PUT', '/api/fees/' + id, b),
    delFee: (id) => req('DELETE', '/api/fees/' + id),
    strategies: (q) => req('GET', '/api/strategies' + qs(q)),
    createStrategy: (b) => req('POST', '/api/strategies', b),
    updateStrategy: (id, b) => req('PUT', '/api/strategies/' + id, b),
    deleteStrategy: (id) => req('DELETE', '/api/strategies/' + id),
    rebuildStrategy: () => req('POST', '/api/strategy/rebuild', {}),
    statsOverview: () => req('GET', '/api/stats/overview'),
    statsTrend: () => req('GET', '/api/stats/trend'),
    statsExpiry: (days) => req('GET', '/api/stats/expiry' + qs({ days })),
    statsDist: () => req('GET', '/api/stats/distribution'),
    statsAnalysis: () => req('GET', '/api/stats/analysis'),
    statsDeep: () => req('GET', '/api/stats/deep'),
    calendar: (year, month) => req('GET', '/api/calendar' + qs({ year, month })),
    exportCsv: () => req('GET', '/api/export/csv'),
    exportXls: () => req('GET', '/api/export/xls'),
    templateCsv: () => req('GET', '/api/template/csv'),
    importCsv: (csv, mode) => req('POST', '/api/import/csv', { csv, mode }),
    exportData: () => req('GET', '/api/export'),
    importData: (d) => req('POST', '/api/import', { data: d }),
    resetData: (mode) => req('POST', '/api/reset', { mode }),
  };

  // ---------------- 提示 ----------------
  let toastTimer = [];
  function toast(msg, type) {
    const wrap = $('#toast');
    const n = el('div', 'toast ' + (type || ''), esc(msg));
    wrap.appendChild(n);
    const t = setTimeout(() => {
      n.style.transition = 'opacity .25s'; n.style.opacity = '0';
      setTimeout(() => n.remove(), 260);
    }, 2600);
    toastTimer.push(t);
  }

  // ---------------- 弹窗 ----------------
  function modal(opts) {
    const root = $('#modalRoot');
    root.innerHTML = '';
    const mask = el('div', 'mask');
    const box = el('div', 'modal' + (opts.small ? ' sm' : ''));
    box.innerHTML =
      '<div class="modal-h"><h3>' + esc(opts.title || '') + '</h3>' +
      '<span class="close-x" data-close>&times;</span></div>' +
      '<div class="modal-b"></div>' +
      (opts.noFooter ? '' : '<div class="modal-f">' +
        '<button class="btn" data-close>' + esc(opts.cancelText || '取消') + '</button>' +
        '<button class="btn btn-primary" data-ok>' + esc(opts.okText || '保存') + '</button></div>');
    $('.modal-b', box).appendChild(opts.body);
    mask.appendChild(box);
    root.appendChild(mask);

    function close() { root.innerHTML = ''; document.removeEventListener('keydown', onKey); }
    function onKey(e) { if (e.key === 'Escape') close(); }
    mask.addEventListener('click', e => { if (e.target === mask) close(); });
    $$('[data-close]', box).forEach(b => b.addEventListener('click', close));
    const okBtn = $('[data-ok]', box);
    if (okBtn) okBtn.addEventListener('click', async () => {
      okBtn.disabled = true;
      try { await opts.onOk(box, close); } catch (e) { toast(e.message || '操作失败', 'err'); }
      okBtn.disabled = false;
    });
    document.addEventListener('keydown', onKey);
    if (opts.onMount) opts.onMount(box, close);
    return { box, close };
  }

  function confirmBox(title, text, okText) {
    return new Promise(resolve => {
      const body = el('div', '', '<div style="font-size:13.5px;line-height:1.8;color:var(--text-2)">' + esc(text) + '</div>');
      modal({
        title, small: true, okText: okText || '确认', body,
        onOk: async (b, close) => { close(); resolve(true); },
        onMount: (b, close) => { $('.mask').addEventListener('click', () => resolve(false)); }
      });
      // 取消/关闭时返回 false
      const obs = new MutationObserver(() => {
        if (!$('#modalRoot').firstChild) { obs.disconnect(); resolve(false); }
      });
      obs.observe($('#modalRoot'), { childList: true });
    });
  }

  function drawer(opts) {
    const root = $('#drawerRoot');
    root.innerHTML = '';
    const mask = el('div', 'drawer-mask');
    const box = el('div', 'drawer');
    box.innerHTML =
      '<div class="drawer-h"><div style="display:flex;justify-content:space-between;gap:14px;align-items:flex-start">' +
      '<h3>' + esc(opts.title || '') + '</h3>' +
      '<span class="close-x" data-close>&times;</span></div>' +
      (opts.sub ? '<div style="margin-top:8px">' + opts.sub + '</div>' : '') +
      '</div><div class="drawer-b"></div>';
    $('.drawer-b', box).appendChild(opts.body);
    mask.appendChild(box);
    root.appendChild(mask);
    function close() { root.innerHTML = ''; document.removeEventListener('keydown', onKey); }
    function onKey(e) { if (e.key === 'Escape') close(); }
    mask.addEventListener('click', e => { if (e.target === mask) close(); });
    $('[data-close]', box).addEventListener('click', close);
    document.addEventListener('keydown', onKey);
    return { box, close, body: $('.drawer-b', box) };
  }

  // ---------------- 格式化 ----------------
  const STATUS_CLS = {
    '有效': 't-green', '已授权': 't-green', '已登记': 't-green', '已注册': 't-green', '维持中': 't-green',
    '申请中': 't-blue', '审查中': 't-blue',
    '质押': 't-orange', '许可': 't-orange',
    '年费滞纳': 't-red', '撤三风险': 't-red', '诉讼中': 't-red',
    '失效': 't-gray', '终止': 't-gray', '驳回': 't-gray', '撤回': 't-gray',
  };
  function statusTag(s) {
    const c = STATUS_CLS[s] || 't-gray';
    return '<span class="tag ' + c + '">' + esc(s || '—') + '</span>';
  }
  function catTag(c) {
    const map = { '专利': 't-blue', '著作权': 't-purple', '商标': 't-orange', '数据知识产权': 't-green' };
    return '<span class="tag ' + (map[c] || 't-gray') + '">' + esc(c || '—') + '</span>';
  }
  function daysText(d, prefix) {
    if (d === null || d === undefined) return '<span class="mini">—</span>';
    if (d < 0) return '<span class="days-urgent">已逾期 ' + Math.abs(d) + ' 天</span>';
    if (d === 0) return '<span class="days-urgent">今日到期</span>';
    if (d <= 30) return '<span class="days-urgent">' + d + ' 天</span>';
    if (d <= 90) return '<span class="days-soon">' + d + ' 天</span>';
    if (d <= 365) return '<span class="days-ok">' + d + ' 天</span>';
    return '<span class="days-ok">' + (d / 365).toFixed(1) + ' 年</span>';
  }
  function fmtDate(s) { return s ? esc(String(s).slice(0, 10)) : '<span class="mini">—</span>'; }
  function num(n) { return (n === null || n === undefined || n === '') ? '—' : n; }

  // ---------------- 表单助手 ----------------
  function field(label, inputHtml, opts) {
    opts = opts || {};
    return '<div class="fld' + (opts.full ? ' full' : '') + '">' +
      '<label>' + esc(label) + (opts.required ? '<span class="req">*</span>' : '') + '</label>' +
      inputHtml + (opts.hint ? '<div class="hint">' + esc(opts.hint) + '</div>' : '') + '</div>';
  }
  function input(name, value, ph, type) {
    return '<input name="' + name + '" value="' + esc(value === undefined || value === null ? '' : value) +
      '" placeholder="' + esc(ph || '') + '"' + (type ? ' type="' + type + '"' : '') + '>';
  }
  function textarea(name, value, ph, rows) {
    return '<textarea name="' + name + '" rows="' + (rows || 3) + '" placeholder="' + esc(ph || '') + '">' +
      esc(value || '') + '</textarea>';
  }
  function select(name, options, value, allowEmpty) {
    let h = '<select name="' + name + '">';
    if (allowEmpty !== false) h += '<option value="">— 请选择 —</option>';
    (options || []).forEach(o => {
      const v = typeof o === 'object' ? o.v : o;
      const t = typeof o === 'object' ? o.t : o;
      h += '<option value="' + esc(v) + '"' + (String(v) === String(value === null || value === undefined ? '' : value) ? ' selected' : '') + '>' + esc(t) + '</option>';
    });
    return h + '</select>';
  }
  function formValues(root) {
    const o = {};
    $$('[name]', root).forEach(n => {
      if (n.type === 'checkbox') o[n.name] = n.checked ? 1 : 0;
      else o[n.name] = n.value;
    });
    return o;
  }

  // ---------------- ECharts ----------------
  const charts = {};
  function chart(id, option) {
    const node = document.getElementById(id);
    if (!node) return null;
    if (charts[id]) { try { charts[id].dispose(); } catch (e) { } }
    const c = echarts.init(node);
    c.setOption(option);
    charts[id] = c;
    return c;
  }
  function resizeCharts() {
    Object.keys(charts).forEach(k => { try { charts[k].resize(); } catch (e) { } });
  }
  window.addEventListener('resize', () => setTimeout(resizeCharts, 120));

  const PALETTE = ['#2563eb', '#12a150', '#d97706', '#7c3aed', '#0891b2', '#db2777', '#65a30d', '#ea580c'];
  function baseOption() {
    return {
      color: PALETTE,
      textStyle: { fontFamily: 'PingFang SC, Microsoft YaHei, sans-serif' },
      tooltip: { backgroundColor: 'rgba(255,255,255,.97)', borderColor: '#e5e8ef', borderWidth: 1, textStyle: { color: '#1f2937', fontSize: 12 }, extraCssText: 'box-shadow:0 4px 16px rgba(16,24,40,.12)' },
      grid: { left: 12, right: 18, top: 34, bottom: 10, containLabel: true },
    };
  }

  function emptyBlock(text) {
    return '<div class="empty"><div class="big">◍</div>' + esc(text || '暂无数据') + '</div>';
  }

  global.C = {
    $, $$, esc, el, API, toast, modal, drawer, confirmBox,
    statusTag, catTag, daysText, fmtDate, num,
    field, input, textarea, select, formValues,
    chart, resizeCharts, baseOption, PALETTE, emptyBlock,
    charts,
  };
})(window);

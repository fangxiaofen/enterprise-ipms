/* 统计分析：可视化图表、到期提醒、综合分析结论 */
(function (global) {
  'use strict';
  const { $, $$, esc, el, API, toast, chart, baseOption, PALETTE, emptyBlock,
    statusTag, catTag, daysText, fmtDate } = global.C;

  let days = 365;
  let DATA = null;

  function render(root) {
    root.innerHTML = '<div class="loading">加载统计数据…</div>';
    Promise.all([API.statsOverview(), API.statsTrend(), API.statsExpiry(days),
      API.statsDist(), API.statsAnalysis(), API.statsDeep()])
      .then(([ov, tr, ex, dist, ana, deep]) => {
        DATA = { ov, tr, ex, dist, ana, deep };
        draw(root, DATA);
      })
      .catch(e => { root.innerHTML = '<div class="empty">' + esc(e.message) + '</div>'; });
  }

  function card(title, sub, inner, extraClass) {
    return '<div class="card' + (extraClass || '') + '"><div class="card-h"><h3>' + esc(title) +
      (sub ? '<span class="sub">' + esc(sub) + '</span>' : '') + '</h3></div>' +
      '<div class="chart-box">' + inner + '</div></div>';
  }
  function chartDiv(id, tall) {
    return '<div id="' + id + '" class="chart' + (tall ? ' tall' : '') + '"></div>';
  }

  function draw(root, d) {
    const { ov, tr, ex, dist, ana, deep } = d;
    const html =
      // 概览卡片
      '<div class="grid g4" style="margin-bottom:16px">' +
      stat('知识产权总量', ov.total, '件', '有效 ' + ov.valid + ' 件', 'c-blue') +
      stat('权利有效率', ov.valid_rate, '%', '审查/申请中 ' + ov.pending + ' 件', 'c-green') +
      stat('风险预警项', ov.risk, '项', '滞纳/撤三/到期未缴', 'c-red') +
      stat('一年到期', ov.expiring, '件', '含商标续展与登记到期', 'c-orange') +
      '</div>' +

      '<div class="grid g2" style="margin-bottom:16px">' +
      card('各类知识产权数量与占比', '共 ' + ov.total + ' 件', chartDiv('c-cat')) +
      card('法律状态分布', '按当前状态统计', chartDiv('c-status')) +
      '</div>' +

      '<div class="card" style="margin-bottom:16px"><div class="card-h"><h3>按年份的申请与授权趋势</h3>' +
      '<span class="sub">申请日 / 授权日所在年度</span></div>' +
      '<div class="chart-box">' + chartDiv('c-trend', true) + '</div></div>' +

      '<div class="grid g3" style="margin-bottom:16px">' +
      card('专利类型分布', '发明 / 实用新型 / 外观', chartDiv('c-patent')) +
      card('著作权类型分布', '软件著作权 / 作品著作权', chartDiv('c-cr')) +
      card('数据知识产权类型分布', '数据资源 / 数据产品登记', chartDiv('c-data')) +
      '</div>' +

      '<div class="grid g2" style="margin-bottom:16px">' +
      card('商标类别分布', '按尼斯分类', chartDiv('c-tm')) +
      card('技术领域分布', '按主技术领域归并', chartDiv('c-tech', true)) +
      '</div>' +

      '<div class="grid g2" style="margin-bottom:16px">' +
      card('归属部门分布', '按责任部门统计', chartDiv('c-dept')) +
      card('保护地域分布', '国内 / 涉外', chartDiv('c-region')) +
      '</div>' +

      // 到期提醒
      '<div class="card" style="margin-bottom:16px">' +
      '<div class="card-h"><h3>有效期与缴费到期提醒</h3>' +
      '<div class="seg" id="seg-days">' +
      [90, 365, 730, 3650].map(v =>
        '<button data-d="' + v + '" class="' + (v === days ? 'active' : '') + '">' +
        (v === 90 ? '90 天' : v === 365 ? '1 年' : v === 730 ? '2 年' : '全部') + '</button>').join('') +
      '</div></div><div class="card-b" id="expiryBox"></div></div>' +

      // 深度分析
      '<div class="card" style="margin-bottom:16px"><div class="card-h">' +
      '<h3>深度分析<span class="sub">发明人、技术构成、专利年龄与授权转化</span></h3></div>' +
      '<div class="card-b">' +
      '<div class="grid g2">' + chartDiv('d-inventor', true) + chartDiv('d-ipc-sec') + '</div>' +
      '<div class="grid g2" style="margin-top:8px">' + chartDiv('d-ipc-cls') + chartDiv('d-age') + '</div>' +
      '<div class="grid g2" style="margin-top:8px">' + chartDiv('d-rate', true) + chartDiv('d-agency') + '</div>' +
      '<div style="margin-top:8px">' + chartDiv('d-stack', true) + '</div>' +
      '</div></div>' +

      // 综合分析
      '<div class="card"><div class="card-h"><h3>综合分析结论与布局评价</h3>' +
      '<span class="sub">综合得分 ' + (ana.overall || 0) + ' / 100</span></div>' +
      '<div class="card-b" id="anaBox"></div></div>';

    root.innerHTML = html;

    // 图表
    pie('c-cat', ov.by_category, '数量');
    pie('c-status', ov.by_status);
    pie('c-patent', dist.patent_type);
    pie('c-cr', dist.copyright_type);
    pie('c-data', dist.data_type);
    pie('c-region', ov.by_region);
    barH('c-tm', dist.tm_class, '商标类别');
    barH('c-tech', dist.tech_field, '技术领域');
    barV('c-dept', ov.by_department, '部门');
    trendChart('c-trend', tr);

    // 深度分析图表
    barH('d-inventor', deep.inventors, '发明人 / 作者');
    pie('d-ipc-sec', deep.ipc_section);
    barH('d-ipc-cls', deep.ipc_class, '分类号');
    barV('d-age', deep.patent_age, '专利年龄');
    rateChart('d-rate', deep.grant_rate);
    barH('d-agency', deep.agency, '代理机构');
    stackChart('d-stack', deep.stack);

    renderExpiry($('#expiryBox', root));
    renderAnalysis($('#anaBox', root), ana);

    $$('#seg-days button', root).forEach(b => b.addEventListener('click', () => {
      days = +b.getAttribute('data-d');
      $$('#seg-days button', root).forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      API.statsExpiry(days).then(nex => { DATA.ex = nex; renderExpiry($('#expiryBox', root)); })
        .catch(e => toast(e.message, 'err'));
    }));
  }

  function stat(label, value, unit, foot, cls) {
    return '<div class="stat ' + cls + '"><span class="bar"></span>' +
      '<div class="label">' + esc(label) + '</div>' +
      '<div class="value">' + esc(value) + '<span style="font-size:13px;font-weight:400;color:var(--muted);margin-left:3px">' + esc(unit) + '</span></div>' +
      '<div class="foot">' + esc(foot) + '</div></div>';
  }

  function pie(id, data, name) {
    if (!data || !data.length) {
      if ($('#' + id)) $('#' + id).innerHTML = emptyBlock('暂无数据');
      return;
    }
    chart(id, Object.assign(baseOption(), {
      tooltip: Object.assign({ trigger: 'item', formatter: '{b}: {c} ({d}%)' }, baseOption().tooltip),
      legend: { bottom: 0, left: 'center', itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 12, color: '#4b5563' } },
      grid: { top: 10, bottom: 40, left: 10, right: 10 },
      series: [{
        type: 'pie', radius: ['42%', '66%'], center: ['50%', '45%'],
        avoidLabelOverlap: true, itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b}\n{c} ({d}%)', fontSize: 11.5, color: '#4b5563' },
        labelLine: { length: 8, length2: 8 },
        data: data.map((x, i) => ({ name: x.name, value: x.value })),
      }],
    }));
  }

  function barH(id, data, name) {
    if (!data || !data.length) { if ($('#' + id)) $('#' + id).innerHTML = emptyBlock('暂无数据'); return; }
    const d = data.slice().reverse();
    chart(id, Object.assign(baseOption(), {
      tooltip: Object.assign({ trigger: 'axis', axisPointer: { type: 'shadow' } }, baseOption().tooltip),
      grid: { left: 12, right: 40, top: 20, bottom: 10, containLabel: true },
      xAxis: { type: 'value', splitLine: { lineStyle: { color: '#f0f2f7' } }, axisLabel: { color: '#8a94a6', fontSize: 11 } },
      yAxis: { type: 'category', data: d.map(x => x.name), axisLine: { lineStyle: { color: '#e5e8ef' } }, axisLabel: { color: '#4b5563', fontSize: 12 } },
      series: [{
        type: 'bar', data: d.map(x => x.value), barMaxWidth: 18,
        itemStyle: { borderRadius: [0, 4, 4, 0], color: '#2563eb' },
        label: { show: true, position: 'right', color: '#6b7280', fontSize: 11 },
      }],
    }));
  }

  function barV(id, data, name) {
    if (!data || !data.length) { if ($('#' + id)) $('#' + id).innerHTML = emptyBlock('暂无数据'); return; }
    chart(id, Object.assign(baseOption(), {
      tooltip: Object.assign({ trigger: 'axis', axisPointer: { type: 'shadow' } }, baseOption().tooltip),
      xAxis: { type: 'category', data: data.map(x => x.name), axisLabel: { color: '#4b5563', fontSize: 12, interval: 0, rotate: data.length > 6 ? 22 : 0 }, axisLine: { lineStyle: { color: '#e5e8ef' } } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f0f2f7' } }, axisLabel: { color: '#8a94a6', fontSize: 11 } },
      series: [{
        type: 'bar', data: data.map(x => x.value), barMaxWidth: 40,
        itemStyle: { borderRadius: [5, 5, 0, 0], color: '#2563eb' },
        label: { show: true, position: 'top', color: '#6b7280', fontSize: 11 },
      }],
    }));
  }

  function trendChart(id, tr) {
    if (!tr.years || !tr.years.length) { if ($('#' + id)) $('#' + id).innerHTML = emptyBlock('暂无数据'); return; }
    chart(id, Object.assign(baseOption(), {
      tooltip: Object.assign({ trigger: 'axis' }, baseOption().tooltip),
      legend: { top: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 12, color: '#4b5563' } },
      grid: { left: 12, right: 20, top: 40, bottom: 10, containLabel: true },
      xAxis: { type: 'category', data: tr.years, boundaryGap: false, axisLine: { lineStyle: { color: '#e5e8ef' } }, axisLabel: { color: '#4b5563', fontSize: 12 } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f0f2f7' } }, axisLabel: { color: '#8a94a6', fontSize: 11 } },
      series: [
        { name: '申请量', type: 'bar', data: tr.apply, barMaxWidth: 26, itemStyle: { borderRadius: [4, 4, 0, 0], color: '#93b4f7' }, label: { show: true, position: 'top', fontSize: 11, color: '#6b7280' } },
        { name: '授权量', type: 'line', data: tr.grant, smooth: true, symbolSize: 7, lineStyle: { width: 2.5, color: '#12a150' }, itemStyle: { color: '#12a150' }, areaStyle: { color: 'rgba(18,161,80,.08)' } },
      ],
    }));
  }

  function rateChart(id, g) {
    if (!g || !g.years || !g.years.length) {
      if ($('#' + id)) $('#' + id).innerHTML = emptyBlock('暂无数据');
      return;
    }
    chart(id, Object.assign(baseOption(), {
      tooltip: Object.assign({ trigger: 'axis' }, baseOption().tooltip),
      legend: { top: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 12, color: '#4b5563' },
        data: ['申请量', '已授权', '授权率'] },
      grid: { left: 12, right: 40, top: 40, bottom: 10, containLabel: true },
      xAxis: { type: 'category', data: g.years, axisLine: { lineStyle: { color: '#e5e8ef' } }, axisLabel: { color: '#4b5563', fontSize: 12 } },
      yAxis: [
        { type: 'value', name: '件数', nameTextStyle: { color: '#8a94a6', fontSize: 11 }, splitLine: { lineStyle: { color: '#f0f2f7' } }, axisLabel: { color: '#8a94a6', fontSize: 11 } },
        { type: 'value', name: '授权率', nameTextStyle: { color: '#8a94a6', fontSize: 11 }, max: 100, splitLine: { show: false }, axisLabel: { color: '#8a94a6', fontSize: 11, formatter: '{value}%' } },
      ],
      series: [
        { name: '申请量', type: 'bar', data: g.apply, barMaxWidth: 24, itemStyle: { borderRadius: [4, 4, 0, 0], color: '#93b4f7' } },
        { name: '已授权', type: 'bar', data: g.granted, barMaxWidth: 24, itemStyle: { borderRadius: [4, 4, 0, 0], color: '#2563eb' } },
        { name: '授权率', type: 'line', yAxisIndex: 1, data: g.rate, smooth: true, symbolSize: 7, lineStyle: { width: 2.5, color: '#12a150' }, itemStyle: { color: '#12a150' }, label: { show: true, formatter: '{c}%', fontSize: 10, color: '#6b7280' } },
      ],
    }));
  }

  function stackChart(id, s) {
    if (!s || !s.categories || !s.categories.length) {
      if ($('#' + id)) $('#' + id).innerHTML = emptyBlock('暂无数据');
      return;
    }
    const series = [
      { name: '有效', type: 'bar', stack: 't', data: s.valid, itemStyle: { color: '#12a150' } },
      { name: '审查/申请中', type: 'bar', stack: 't', data: s.pending, itemStyle: { color: '#2563eb' } },
      { name: '失效/驳回', type: 'bar', stack: 't', data: s.dead, itemStyle: { color: '#9aa4b8' } },
    ];
    chart(id, Object.assign(baseOption(), {
      tooltip: Object.assign({ trigger: 'axis', axisPointer: { type: 'shadow' } }, baseOption().tooltip),
      legend: { top: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 12, color: '#4b5563' } },
      grid: { left: 12, right: 20, top: 40, bottom: 10, containLabel: true },
      xAxis: { type: 'category', data: s.categories, axisLine: { lineStyle: { color: '#e5e8ef' } }, axisLabel: { color: '#4b5563', fontSize: 12 } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f0f2f7' } }, axisLabel: { color: '#8a94a6', fontSize: 11 } },
      series: series.map((x, i) => i === series.length - 1
        ? Object.assign(x, { itemStyle: Object.assign({}, x.itemStyle, { borderRadius: [4, 4, 0, 0] }), barMaxWidth: 46, label: { show: true, position: 'top', fontSize: 11, color: '#6b7280' } })
        : Object.assign(x, { barMaxWidth: 46 })),
    }));
  }

  function remindRow(item, kind) {
    const d = item.days;
    const cls = d < 0 ? 'days-urgent' : (d <= 30 ? 'days-urgent' : (d <= 90 ? 'days-soon' : 'days-ok'));
    let extra = '';
    if (kind === 'fee') extra = '第 ' + (item.year || '—') + ' 年度年费';
    else if (kind === 'tm') extra = '续展窗口 ' + esc(item.renew_start) + ' 起';
    else if (kind === 'data') extra = '登记有效期';
    else extra = '保护期限届满';
    return '<div class="remind">' +
      '<div class="rd-main"><div class="rd-name">' + esc(item.name) + '　' + catTag(item.category) +
      ' <span class="mini">' + esc(item.sub_type || '') + '</span></div>' +
      '<div class="rd-sub">' + extra + '　·　' + esc(item.no || '') + '　·　' + esc(item.department || '') +
      '　·　截止 ' + esc(item.date) + '</div></div>' +
      '<div class="rd-days ' + cls + '">' + daysText(d) + '</div>' +
      '<button class="btn btn-sm" data-open="' + item.id + '">查看</button></div>';
  }

  function renderExpiry(box) {
    const ex = DATA.ex;
    const groups = [
      ['逾期未缴（已过应缴日）', ex.overdue, 'fee'],
      ['年费 / 续展缴费提醒', ex.fee_due, 'fee'],
      ['商标续展提醒', ex.tm_renew, 'tm'],
      ['数据知识产权续展提醒', ex.data_renew, 'data'],
      ['专利保护期届满提醒', ex.patent_expire, 'patent'],
    ];
    let total = 0;
    let h = '<div class="grid g2">';
    groups.forEach(([title, list, kind]) => {
      total += (list || []).length;
      h += '<div><div style="font-size:12.5px;color:var(--text-2);font-weight:600;margin-bottom:8px">' +
        esc(title) + '（' + (list || []).length + '）</div>';
      if (!list || !list.length) h += '<div class="mini" style="padding:6px 0 14px">无</div>';
      else h += list.map(x => remindRow(x, kind)).join('');
      h += '</div>';
    });
    h += '</div>';
    box.innerHTML = h +
      '<div class="mini" style="margin-top:10px">统计口径：距今天数按服务端基准日计算，已排除失效、终止、驳回、撤回状态的记录。</div>';
    $$('[data-open]', box).forEach(b => b.addEventListener('click', () => {
      global.Views.assets.openDetail(+b.getAttribute('data-open'));
    }));
  }

  function renderAnalysis(box, ana) {
    let h = '<div class="grid g2"><div>';
    h += '<div style="font-size:12.5px;font-weight:600;color:var(--text-2);margin-bottom:10px">综合结论</div>';
    (ana.conclusions || []).forEach(c => { h += '<div class="concl">' + esc(c) + '</div>'; });
    h += '</div><div>';
    h += '<div style="font-size:12.5px;font-weight:600;color:var(--text-2);margin-bottom:10px">布局能力评分</div>';
    Object.entries(ana.scores || {}).forEach(([k, v]) => {
      h += '<div class="score-row"><span class="nm">' + esc(k) + '</span>' +
        '<span class="score-bar"><i style="width:' + v + '%"></i></span>' +
        '<span class="vl">' + v + '</span></div>';
    });
    h += '<div class="divider"></div>';
    h += '<div style="font-size:12.5px;font-weight:600;color:var(--text-2);margin-bottom:8px">改进建议</div>';
    (ana.suggestions || []).forEach(s => { h += '<div class="sugg">' + esc(s) + '</div>'; });
    h += '</div></div>';
    box.innerHTML = h;
  }

  global.Views = global.Views || {};
  global.Views.stats = { render };
})(window);

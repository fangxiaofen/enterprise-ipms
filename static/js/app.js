/* 应用入口：路由、导航、概览、企业信息、系统设置 */
(function (global) {
  'use strict';
  const { $, $$, esc, el, API, toast, modal, confirmBox, chart, baseOption, emptyBlock,
    statusTag, catTag, daysText, fmtDate, field, input, textarea, select, formValues } = global.C;

  const NAV = [
    { id: 'dashboard', ico: '◱', name: '概览', title: '概览', desc: '企业知识产权资产全景' },
    { id: 'company', ico: '🏢', name: '企业信息', title: '企业基本信息', desc: '维护企业主体与知识产权管理信息' },
    { id: 'assets', ico: '📑', name: '知识产权管理', title: '知识产权管理', desc: '台账维护、检索与批量导入导出' },
    { id: 'calendar', ico: '📅', name: '期限日历', title: '期限日历', desc: '年费、续展、到期与提实审期限的月历视图' },
    { id: 'stats', ico: '📊', name: '统计分析', title: '统计分析', desc: '数量结构、趋势、到期与布局评价' },
    { id: 'strategy', ico: '🎯', name: '战略中心', title: '战略中心', desc: '规避设计战略与风险战略' },
    { id: 'report', ico: '🖨', name: '报表打印', title: '台账报表', desc: 'A4 排版台账报表，可打印或另存 PDF' },
    { id: 'settings', ico: '⚙', name: '系统设置', title: '系统设置', desc: '数据备份、恢复与系统信息' },
  ];

  const APP = global.APP = {
    meta: null, company: null, route: 'dashboard',
    reloadAssets: null, reloadStrategy: null, refreshBadges: null,
  };

  // ---------------- 导航 ----------------
  function renderNav() {
    const nav = $('#nav');
    nav.innerHTML = '<div class="nav-group">主导航</div>' +
      NAV.map(n =>
        '<div class="nav-item' + (APP.route === n.id ? ' active' : '') + '" data-r="' + n.id + '">' +
        '<span class="ico">' + n.ico + '</span><span>' + n.name + '</span>' +
        '<span class="badge" data-badge="' + n.id + '" style="display:none"></span></div>').join('') +
      '<div class="nav-group">快捷操作</div>' +
      '<div class="nav-item" data-act="add"><span class="ico">＋</span><span>新增知识产权</span></div>' +
      '<div class="nav-item" data-act="backup"><span class="ico">⇩</span><span>导出数据备份</span></div>';
    $$('.nav-item', nav).forEach(n => n.addEventListener('click', () => {
      const r = n.getAttribute('data-r');
      if (r) return go(r);
      const act = n.getAttribute('data-act');
      if (act === 'add') return global.Views.assets.openForm(null, () => APP.reloadAssets && APP.reloadAssets());
      if (act === 'backup') return doExport();
    }));
    refreshBadges();
  }

  function refreshBadges() {
    API.statsOverview().then(ov => {
      const set = (id, v) => {
        const b = $('[data-badge=' + id + ']');
        if (!b) return;
        if (v) { b.style.display = ''; b.textContent = v; } else b.style.display = 'none';
      };
      set('assets', ov.total);
      set('strategy', ov.risk ? ov.risk : '');
      APP.overview = ov;
    }).catch(() => { });
    API.strategies({}).then(d => {
      const b = $('[data-badge=strategy]');
      if (b) { b.style.display = ''; b.textContent = d.total; }
    }).catch(() => { });
  }
  APP.refreshBadges = refreshBadges;

  function go(route) {
    APP.route = route;
    location.hash = '#/' + route;
    $$('.nav-item').forEach(n => n.classList.toggle('active', n.getAttribute('data-r') === route));
    const n = NAV.find(x => x.id === route) || NAV[0];
    $('#pageTitle').textContent = n.title;
    $('#pageDesc').textContent = n.desc;
    const view = $('#view');
    view.scrollTop = 0;
    global.C.charts && Object.keys(global.C.charts).forEach(k => {
      try { global.C.charts[k].dispose(); delete global.C.charts[k]; } catch (e) { }
    });
    $('.mask') && $('#modalRoot').replaceChildren();
    $('#drawerRoot').replaceChildren();
    if (route === 'dashboard') renderDashboard(view);
    else if (route === 'company') renderCompany(view);
    else if (route === 'assets') global.Views.assets.render(view);
    else if (route === 'calendar') global.Views.calendar.render(view);
    else if (route === 'stats') global.Views.stats.render(view);
    else if (route === 'strategy') global.Views.strategy.render(view);
    else if (route === 'report') global.Views.report.render(view);
    else if (route === 'settings') renderSettings(view);
  }
  global.go = go;

  // ---------------- 概览 ----------------
  function renderDashboard(root) {
    root.innerHTML = '<div class="loading">加载中…</div>';
    Promise.all([API.statsOverview(), API.statsExpiry(365), API.strategies({ risk_level: '高' }),
      API.statsTrend(), API.statsDist()]).then(([ov, ex, st, tr, dist]) => {
        const company = APP.company || {};
        const urgent = [].concat(
          ex.overdue.map(x => Object.assign({ _k: '年费逾期' }, x)),
          ex.fee_due.map(x => Object.assign({ _k: '年费待缴' }, x)),
          ex.data_renew.map(x => Object.assign({ _k: '数据登记续展' }, x)),
          ex.tm_renew.map(x => Object.assign({ _k: '商标续展' }, x)))
          .sort((a, b) => a.days - b.days).slice(0, 8);

        root.innerHTML =
          '<div class="grid g4" style="margin-bottom:16px">' +
          statC('知识产权总量', ov.total, '件', '覆盖 ' + ov.by_category.length + ' 个大类', 'c-blue') +
          statC('有效权利', ov.valid, '件', '有效率 ' + ov.valid_rate + '%', 'c-green') +
          statC('审查/申请中', ov.pending, '件', '在途申请', 'c-purple') +
          statC('风险预警', ov.risk, '项', '需即时处置', 'c-red') +
          '</div>' +

          '<div class="grid g2" style="margin-bottom:16px">' +
          '<div class="card"><div class="card-h"><h3>类型构成</h3><span class="sub">按知识产权大类</span></div>' +
          '<div class="chart-box"><div id="d-cat" class="chart"></div></div></div>' +
          '<div class="card"><div class="card-h"><h3>法律状态分布</h3><span class="sub">按当前状态</span></div>' +
          '<div class="chart-box"><div id="d-st" class="chart"></div></div></div>' +
          '</div>' +

          '<div class="grid g2" style="margin-bottom:16px">' +
          '<div class="card"><div class="card-h"><h3>近期待办与到期提醒</h3>' +
          '<span class="sub">未来 1 年</span></div><div class="card-b">' +
          (urgent.length ? urgent.map(u =>
            '<div class="remind"><div class="rd-main"><div class="rd-name">' + esc(u.name) + '</div>' +
            '<div class="rd-sub">' + esc(u._k) + '　·　截止 ' + esc(u.date) + '　·　' + esc(u.department || '') + '</div></div>' +
            '<div class="rd-days">' + daysText(u.days) + '</div>' +
            '<button class="btn btn-sm" data-goto="' + u.id + '">查看</button></div>').join('')
            : '<div class="mini">未来一年内无到期事项</div>') +
          '</div></div>' +

          '<div class="card"><div class="card-h"><h3>高风险战略事项</h3>' +
          '<span class="sub">TOP ' + Math.min(5, st.items.length) + '</span></div><div class="card-b">' +
          (st.items.length ? st.items.slice(0, 5).map(s =>
            '<div class="remind"><div class="rd-main"><div class="rd-name">' + esc(s.title) + '</div>' +
            '<div class="rd-sub">' + esc(s.category || '') + (s.owner ? '　·　' + esc(s.owner) : '') +
            (s.deadline ? '　·　时限 ' + esc(s.deadline) : '') + '</div></div>' +
            '<span class="tag ' + (s.module === 'risk' ? 't-red' : 't-orange') + '">' +
            (s.module === 'risk' ? '风险' : '规避') + '</span></div>').join('')
            : '<div class="mini">暂无高风险事项</div>') +
          '<div style="margin-top:12px"><button class="btn btn-sm" id="goto-strategy">查看全部战略条目</button></div>' +
          '</div></div></div>' +

          '<div class="card"><div class="card-h"><h3>企业信息</h3>' +
          '<button class="btn btn-sm" id="edit-co">编辑</button></div>' +
          '<div class="card-b"><div class="grid g2" style="gap:10px 24px">' +
          [['企业名称', company.name], ['统一社会信用代码', company.credit_code],
          ['企业类型', company.company_type], ['所属行业', company.industry],
          ['成立日期', company.founded_date], ['注册资本', company.capital ? company.capital + ' 万元' : ''],
          ['联系人', company.contact], ['联系电话', company.phone],
          ['知识产权管理部门', company.ip_dept], ['知识产权负责人', company.ip_manager],
          ['注册地址', company.address], ['企业网址', company.website]]
            .map(([k, v]) => '<div style="display:flex;gap:10px;font-size:13px">' +
              '<span style="color:var(--muted);width:118px;flex:0 0 118px">' + esc(k) + '</span>' +
              '<span>' + esc(v || '—') + '</span></div>').join('') +
          '</div>' + (company.intro ? '<div class="divider"></div><div class="prose">' + esc(company.intro) + '</div>' : '') +
          '</div></div>';

        pieMini('d-cat', ov.by_category);
        pieMini('d-st', ov.by_status);
        $$('[data-goto]', root).forEach(b => b.addEventListener('click', () =>
          global.Views.assets.openDetail(+b.getAttribute('data-goto'))));
        $('#edit-co', root).addEventListener('click', () => go('company'));
        $('#goto-strategy', root).addEventListener('click', () => go('strategy'));
      }).catch(e => { root.innerHTML = '<div class="empty">' + esc(e.message) + '</div>'; });
  }

  function statC(label, value, unit, foot, cls) {
    return '<div class="stat ' + cls + '"><span class="bar"></span>' +
      '<div class="label">' + esc(label) + '</div>' +
      '<div class="value">' + esc(value) + '<span style="font-size:13px;font-weight:400;color:var(--muted);margin-left:3px">' + esc(unit) + '</span></div>' +
      '<div class="foot">' + esc(foot) + '</div></div>';
  }

  function pieMini(id, data) {
    if (!data || !data.length) { if ($('#' + id)) $('#' + id).innerHTML = emptyBlock('暂无数据'); return; }
    chart(id, Object.assign(baseOption(), {
      tooltip: Object.assign({ trigger: 'item', formatter: '{b}: {c} ({d}%)' }, baseOption().tooltip),
      legend: { bottom: 0, left: 'center', itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 12, color: '#4b5563' } },
      grid: { top: 10, bottom: 40, left: 10, right: 10 },
      series: [{
        type: 'pie', radius: ['40%', '64%'], center: ['50%', '44%'],
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b} {c}', fontSize: 11.5, color: '#4b5563' },
        data,
      }],
    }));
  }

  // ---------------- 企业信息 ----------------
  function renderCompany(root) {
    const c = APP.company || {};
    root.innerHTML =
      '<div class="card"><div class="card-h"><h3>企业基本信息</h3>' +
      '<button class="btn btn-primary btn-sm" id="btn-edit">编辑信息</button></div>' +
      '<div class="card-b">' +
      '<div class="grid g3" style="gap:14px 24px">' +
      infoItem('企业名称', c.name) + infoItem('统一社会信用代码', c.credit_code) +
      infoItem('企业类型', c.company_type) + infoItem('所属行业', c.industry) +
      infoItem('成立日期', c.founded_date) +
      infoItem('注册资本', c.capital ? c.capital + ' 万元' : '—') +
      infoItem('法定代表人', c.legal_person) + infoItem('注册地址', c.address) +
      infoItem('联系人', c.contact) + infoItem('联系电话', c.phone) +
      infoItem('电子邮箱', c.email) + infoItem('企业网址', c.website) +
      infoItem('知识产权管理部门', c.ip_dept) + infoItem('知识产权负责人', c.ip_manager) +
      '</div>' +
      '<div class="divider"></div>' +
      '<div style="font-size:12.5px;font-weight:600;color:var(--text-2);margin-bottom:8px">企业简介</div>' +
      '<div class="prose">' + esc(c.intro || '—') + '</div>' +
      '<div class="divider"></div>' +
      '<div class="mini">最近更新：' + esc(c.updated_at || '—') + '</div>' +
      '</div></div>';
    $('#btn-edit', root).addEventListener('click', () => openCompanyForm());
  }

  function infoItem(k, v) {
    return '<div><div class="mini" style="margin-bottom:2px">' + esc(k) + '</div>' +
      '<div style="font-size:13.5px">' + esc(v || '—') + '</div></div>';
  }

  function openCompanyForm() {
    const c = APP.company || {};
    const body = el('div');
    body.innerHTML = '<div class="form-grid" id="cform">' +
      '<div class="sec-title">主体信息</div>' +
      field('企业名称', input('name', c.name), { required: true }) +
      field('统一社会信用代码', input('credit_code', c.credit_code)) +
      field('企业类型', select('company_type', ['国有企业', '民营企业', '外资企业', '合资企业', '事业单位', '其他'], c.company_type)) +
      field('所属行业', input('industry', c.industry)) +
      field('成立日期', input('founded_date', c.founded_date, '', 'date')) +
      field('注册资本（万元）', input('capital', c.capital, '', 'number')) +
      field('法定代表人', input('legal_person', c.legal_person)) +
      field('注册地址', input('address', c.address)) +
      '<div class="sec-title">联系方式</div>' +
      field('联系人', input('contact', c.contact)) +
      field('联系电话', input('phone', c.phone)) +
      field('电子邮箱', input('email', c.email)) +
      field('企业网址', input('website', c.website)) +
      '<div class="sec-title">知识产权管理</div>' +
      field('知识产权管理部门', input('ip_dept', c.ip_dept)) +
      field('知识产权负责人', input('ip_manager', c.ip_manager)) +
      field('企业简介', textarea('intro', c.intro, '', 6), { full: true }) +
      '</div>';
    modal({
      title: '编辑企业信息', body,
      onOk: (box, close) => {
        const v = formValues($('#cform', box));
        if (!v.name.trim()) { toast('请填写企业名称', 'err'); return; }
        return API.saveCompany(v).then(d => {
          APP.company = d; $('#companyChip').textContent = d.name;
          toast('已保存', 'ok'); close(); go('company');
        });
      }
    });
  }

  // ---------------- 系统设置 ----------------
  function renderSettings(root) {
    const meta = APP.meta || {};
    root.innerHTML =
      '<div class="grid g2" style="margin-bottom:16px">' +
      '<div class="card"><div class="card-h"><h3>数据备份与恢复</h3></div><div class="card-b">' +
      '<div style="font-size:13px;line-height:1.9;color:var(--text-2);margin-bottom:14px">' +
      '全部数据保存在服务端 SQLite 数据库 <code>data/ipms.db</code> 中，刷新页面或重启服务后数据依然存在。' +
      '建议定期导出 JSON 备份，迁移或重装时可通过导入恢复。' +
      '</div>' +
      '<div style="display:flex;gap:10px;flex-wrap:wrap">' +
      '<button class="btn btn-primary" id="btn-export">导出数据备份（JSON）</button>' +
      '<button class="btn" id="btn-import">导入备份文件</button>' +
      '<input type="file" id="file-input" accept=".json" style="display:none">' +
      '</div>' +
      '<div class="divider"></div>' +
      '<div style="font-size:12.5px;font-weight:600;color:var(--text-2);margin-bottom:8px">' +
      '台账表格导入导出</div>' +
      '<div style="font-size:13px;line-height:1.9;color:var(--text-2);margin-bottom:12px">' +
      '导出 Excel 或 CSV 台账用于外部核对与汇报；批量导入支持从 Excel 另存的 CSV 文件一次性录入台账，' +
      '以申请号 / 登记申请号为唯一标识，已存在则更新、不存在则新建。' +
      '</div>' +
      '<div style="display:flex;gap:10px;flex-wrap:wrap">' +
      '<button class="btn" id="btn-tpl">下载导入模板</button>' +
      '<button class="btn" id="btn-xls">导出 Excel 台账</button>' +
      '<button class="btn" id="btn-csv">导出 CSV 台账</button>' +
      '<button class="btn" id="btn-csv-import">批量导入 CSV</button>' +
      '</div></div></div>' +

      '<div class="card"><div class="card-h"><h3>数据与建议维护</h3></div><div class="card-b">' +
      '<div style="font-size:13px;line-height:1.9;color:var(--text-2);margin-bottom:14px">' +
      '战略中心的智能建议由系统依据当前台账数据自动推导。数据变更后可重新生成；' +
      '也可一键恢复内置演示数据，或清空全部数据后录入真实数据。' +
      '</div>' +
      '<div style="display:flex;gap:10px;flex-wrap:wrap">' +
      '<button class="btn" id="btn-rebuild">重新生成战略建议</button>' +
      '<button class="btn" id="btn-demo">恢复内置演示数据</button>' +
      '<button class="btn btn-danger" id="btn-clear">清空全部数据</button>' +
      '</div></div></div>' +
      '</div>' +

      '<div class="card" style="margin-bottom:16px"><div class="card-h"><h3>系统信息</h3></div><div class="card-b">' +
      '<dl class="kv" style="grid-template-columns:150px 1fr">' +
      '<dt>系统名称</dt><dd>企业知识产权管理系统 IPMS v1.0</dd>' +
      '<dt>技术架构</dt><dd>Python 3 标准库 HTTP 服务 + SQLite 持久化 + 原生前端 + ECharts 5.5</dd>' +
      '<dt>数据文件</dt><dd><code>data/ipms.db</code></dd>' +
      '<dt>服务端基准日</dt><dd>' + esc(meta.today || '—') + '（用于到期天数计算）</dd>' +
      '<dt>知识产权大类</dt><dd>' + esc(Object.keys(meta.categories || {}).join('、')) + '</dd>' +
      '<dt>子类型</dt><dd>' + esc(Object.values(meta.categories || {}).flat().join('、')) + '</dd>' +
      '<dt>法律状态枚举</dt><dd>' + esc((meta.statuses || []).join('、')) + '</dd>' +
      '</dl></div></div>' +

      '<div class="card"><div class="card-h"><h3>字段与口径说明</h3></div><div class="card-b">' +
      '<div class="prose">' +
      '保护期限口径：发明专利 20 年、实用新型专利 10 年、外观设计专利 15 年（均自申请日起算）；' +
      '软件著作权与作品著作权保护期为 50 年；注册商标专用权 10 年，期满前 12 个月内可续展；' +
      '数据知识产权登记证书有效期 2 年，期满需办理续展。\n\n' +
      '三类信息板块：基本信息（名称、类型、号码、日期、权利人、分类号、技术领域）、' +
      '法律状态（当前状态、状态变更记录、年费缴纳与下一年费截止日、保护期限起止）、' +
      '具体保护范围（权利要求摘要、设计要点、核定商品服务、作品内容、数据范围与地域范围）。\n\n' +
      '风险判定口径：年费逾期或 30 天内到期、商标连续三年未使用、数据登记失效或 30 天内到期、' +
      '审查周期超出常规、保护地域单一，均会自动生成对应风险条目。' +
      '</div></div></div>';

    $('#btn-export', root).addEventListener('click', doExport);
    $('#btn-tpl', root).addEventListener('click', () => global.IO.downloadTemplate());
    $('#btn-xls', root).addEventListener('click', () => global.IO.exportXls());
    $('#btn-csv', root).addEventListener('click', () => global.IO.exportCsv());
    $('#btn-csv-import', root).addEventListener('click', () =>
      global.IO.openImport(() => { }));
    $('#btn-import', root).addEventListener('click', () => $('#file-input', root).click());
    $('#file-input', root).addEventListener('change', e => {
      const f = e.target.files[0];
      if (!f) return;
      const fr = new FileReader();
      fr.onload = () => {
        let data;
        try { data = JSON.parse(fr.result); } catch (err) { return toast('JSON 解析失败', 'err'); }
        confirmBox('导入确认', '导入将覆盖当前全部数据（企业信息、知识产权台账、战略条目），是否继续？', '确认导入')
          .then(yes => {
            if (!yes) return;
            API.importData(data).then(d => {
              toast('已导入 ' + d.assets + ' 条知识产权、' + d.strategies + ' 条战略条目', 'ok');
              setTimeout(() => location.reload(), 800);
            }).catch(err => toast(err.message, 'err'));
          });
      };
      fr.readAsText(f, 'utf-8');
    });
    $('#btn-rebuild', root).addEventListener('click', () => {
      API.rebuildStrategy().then(d => {
        toast('已生成 ' + d.rebuilt + ' 条智能建议', 'ok'); refreshBadges();
      }).catch(e => toast(e.message, 'err'));
    });
    $('#btn-demo', root).addEventListener('click', () => {
      confirmBox('恢复演示数据', '将清空当前全部数据并恢复内置示例企业（含 29 条各类型知识产权）。是否继续？', '确认恢复')
        .then(yes => {
          if (!yes) return;
          API.resetData('demo').then(() => {
            toast('演示数据已恢复', 'ok'); setTimeout(() => location.reload(), 800);
          }).catch(e => toast(e.message, 'err'));
        });
    });
    $('#btn-clear', root).addEventListener('click', () => {
      confirmBox('清空全部数据', '将删除全部知识产权台账、状态记录、年费记录与战略条目（企业信息保留）。此操作不可撤销，建议先导出备份。是否继续？', '确认清空')
        .then(yes => {
          if (!yes) return;
          API.resetData('empty').then(() => {
            toast('已清空', 'ok'); setTimeout(() => location.reload(), 800);
          }).catch(e => toast(e.message, 'err'));
        });
    });
  }

  function doExport() {
    API.exportData().then(data => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'ipms-backup-' + new Date().toISOString().slice(0, 10) + '.json';
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1500);
      toast('备份已导出', 'ok');
    }).catch(e => toast(e.message, 'err'));
  }

  // ---------------- 启动 ----------------
  function boot() {
    Promise.all([API.meta(), API.company()]).then(([meta, company]) => {
      APP.meta = meta; APP.company = company;
      $('#companyChip').textContent = company.name || '未设置企业名称';
      document.title = (company.name || '企业') + ' · 知识产权管理系统';
      renderNav();
      const r = (location.hash || '').replace('#/', '');
      go(NAV.some(n => n.id === r) ? r : 'dashboard');
    }).catch(e => {
      $('#view').innerHTML = '<div class="empty"><div class="big">⚠</div>' +
        esc(e.message) + '<div style="margin-top:12px" class="mini">请确认后端服务已启动： python server.py</div></div>';
    });
    $('#btnQuickAdd').addEventListener('click', () =>
      global.Views.assets.openForm(null, () => APP.reloadAssets && APP.reloadAssets()));
    window.addEventListener('hashchange', () => {
      const r = (location.hash || '').replace('#/', '');
      if (NAV.some(n => n.id === r) && r !== APP.route) go(r);
    });
  }

  document.addEventListener('DOMContentLoaded', boot);
})(window);

/* 打印友好台账报表：A4 排版，含企业抬头、统计汇总与分类明细 */
(function (global) {
  'use strict';
  const { $, $$, esc, el, API, toast, statusTag, fmtDate } = global.C;

  let option = { groupByCategory: true, onlyValid: false };

  function render(root) {
    root.innerHTML = '<div class="loading">生成报表…</div>';
    Promise.all([API.statsOverview(), API.assets({ page_size: 2000 }), API.company()])
      .then(([ov, list]) => {
        draw(root, ov, list.items);
      })
      .catch(e => { root.innerHTML = '<div class="empty">' + esc(e.message) + '</div>'; });
  }

  function draw(root, ov, items) {
    const co = global.APP.company || {};
    const today = global.APP.meta.today;
    let list = items.slice();
    if (option.onlyValid) {
      list = list.filter(a => ['有效', '已授权', '已登记', '已注册', '维持中', '质押', '许可'].indexOf(a.status) >= 0);
    }
    list.sort((a, b) => (a.category || '').localeCompare(b.category || '', 'zh')
      || String(a.app_date || '').localeCompare(String(b.app_date || '')));

    const groups = {};
    list.forEach(a => { (groups[a.category] = groups[a.category] || []).push(a); });

    const statusSummary = ov.by_status.slice().sort((a, b) => b.value - a.value);

    root.innerHTML =
      '<div class="rpt-tip no-print">' +
      '<div class="card"><div class="card-b" style="padding:12px 16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">' +
      '<button class="btn btn-primary" id="rpt-print">打印 / 另存 PDF</button>' +
      '<button class="btn" id="rpt-xls">导出 Excel</button>' +
      '<button class="btn" id="rpt-csv">导出 CSV</button>' +
      '<label style="display:flex;align-items:center;gap:6px;font-size:13px;color:var(--text-2);margin-left:8px">' +
      '<input type="checkbox" id="rpt-only-valid"' + (option.onlyValid ? ' checked' : '') + '> 仅打印有效权利' +
      '</label>' +
      '<span class="mini" style="margin-left:auto">打印时请在对话框中选择 A4 纸张、纵向，并勾选「背景图形」以保留表头底色</span>' +
      '</div></div></div>' +

      '<div class="rpt" id="rpt-body">' +
      '<div class="rpt-h">' +
      '<h2>' + esc(co.name || '企业名称') + '　知识产权台账报表</h2>' +
      '<div class="sub">统计基准日 ' + esc(today) + '　|　共 ' + list.length + ' 件知识产权　|　制表部门：' +
      esc(co.ip_dept || '知识产权部') + '</div>' +
      '</div>' +

      '<div class="rpt-meta">' +
      metaItem('统一社会信用代码', co.credit_code) +
      metaItem('企业类型', co.company_type) +
      metaItem('所属行业', co.industry) +
      metaItem('成立日期', co.founded_date) +
      metaItem('注册资本', co.capital ? co.capital + ' 万元' : '') +
      metaItem('知识产权负责人', co.ip_manager) +
      '</div>' +

      '<div class="rpt-sec"><h4>一、总体情况</h4>' +
      '<table><tbody>' +
      '<tr>' +
      sumCell('知识产权总量', ov.total + ' 件') + sumCell('有效权利', ov.valid + ' 件') +
      sumCell('审查/申请中', ov.pending + ' 件') + sumCell('失效/驳回', ov.dead + ' 件') +
      '</tr><tr>' +
      sumCell('权利有效率', ov.valid_rate + '%') + sumCell('风险预警项', ov.risk + ' 项') +
      sumCell('一年到期', ov.expiring + ' 件') + sumCell('保护地域', (ov.by_region[0] || {}).name || '—') +
      '</tr>' +
      '</tbody></table>' +
      '</div>' +

      '<div class="rpt-sec"><h4>二、类型构成</h4>' +
      '<table><thead><tr><th>知识产权类型</th><th class="c">数量</th><th class="c">占比</th>' +
      '<th class="c">有效</th><th class="c">审查/申请中</th><th class="c">失效/驳回</th></tr></thead><tbody>' +
      ov.by_category.map(c => {
        const g = groups[c.name] || [];
        const v = g.filter(x => ['有效', '已授权', '已登记', '已注册', '维持中', '质押', '许可'].indexOf(x.status) >= 0).length;
        const p = g.filter(x => ['申请中', '审查中'].indexOf(x.status) >= 0).length;
        const d = g.length - v - p;
        return '<tr><td>' + esc(c.name) + '</td><td class="c">' + c.value + '</td><td class="c">' +
          (ov.total ? (c.value / ov.total * 100).toFixed(1) : 0) + '%</td>' +
          '<td class="c">' + v + '</td><td class="c">' + p + '</td><td class="c">' + d + '</td></tr>';
      }).join('') +
      '</tbody></table>' +
      '</div>' +

      '<div class="rpt-sec"><h4>三、法律状态分布</h4>' +
      '<table><thead><tr>' +
      statusSummary.map(s => '<th class="c">' + esc(s.name) + '</th>').join('') +
      '</tr></thead><tbody><tr>' +
      statusSummary.map(s => '<td class="c">' + s.value + '</td>').join('') +
      '</tr></tbody></table>' +
      '</div>' +

      '<div class="rpt-sec"><h4>四、台账明细</h4>' +
      Object.keys(groups).map(cat => {
        const g = groups[cat];
        return '<div style="margin:10px 0 6px;font-weight:600;font-size:12.5px">' +
          esc(cat) + '（' + g.length + ' 件）</div>' +
          '<table><thead><tr>' +
          '<th style="width:24px" class="c">序</th><th>名称</th><th>类型</th>' +
          '<th>申请号/登记号</th><th class="c">申请日</th><th class="c">状态</th>' +
          '<th class="c">下一年费/续展</th><th class="c">保护期至</th><th>权利人</th>' +
          '</tr></thead><tbody>' +
          g.map((a, i) =>
            '<tr><td class="c">' + (i + 1) + '</td>' +
            '<td>' + esc(a.name) + '</td>' +
            '<td>' + esc(a.sub_type || '') + '</td>' +
            '<td>' + esc(a.grant_no || a.app_no || '') + '</td>' +
            '<td class="c">' + esc(String(a.app_date || '').slice(0, 10)) + '</td>' +
            '<td class="c">' + esc(a.status) + '</td>' +
            '<td class="c">' + esc(String(a.next_fee_date || '—')) + '</td>' +
            '<td class="c">' + esc(String(a.protect_end || '—')) + '</td>' +
            '<td>' + esc(a.applicant || '') + '</td></tr>').join('') +
          '</tbody></table>';
      }).join('') +
      '</div>' +

      '<div class="rpt-foot">' +
      '<span>制表人：' + esc(co.contact || '') + '　审核：' + esc(co.ip_manager || '') + '</span>' +
      '<span>第 1 页 / 共 1 页</span>' +
      '</div>' +
      '</div>';

    $('#rpt-print', root).addEventListener('click', () => window.print());
    $('#rpt-xls', root).addEventListener('click', () => global.IO.exportXls());
    $('#rpt-csv', root).addEventListener('click', () => global.IO.exportCsv());
    $('#rpt-only-valid', root).addEventListener('change', e => {
      option.onlyValid = e.target.checked;
      render(root);
    });
  }

  function metaItem(k, v) {
    return '<div><span style="color:var(--muted)">' + esc(k) + '：</span>' + esc(v || '—') + '</div>';
  }
  function sumCell(k, v) {
    return '<td style="width:25%;padding:6px 8px"><span style="color:var(--muted)">' +
      esc(k) + '：</span><b>' + esc(v) + '</b></td>';
  }

  global.Views = global.Views || {};
  global.Views.report = { render };
})(window);

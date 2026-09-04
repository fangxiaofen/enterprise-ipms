/* 年费与期限日历：月历视图集中展示年费、续展、到期与提实审期限 */
(function (global) {
  'use strict';
  const { $, $$, esc, el, API, toast, catTag, statusTag, daysText } = global.C;

  let year = 0, month = 0;
  let DATA = null;

  const LEVEL_LABEL = {
    overdue: '已逾期', high: '30 天内', medium: '90 天内', low: '90 天以上', done: '已缴纳',
  };

  function render(root) {
    const today = new Date(global.APP.meta.today + 'T00:00:00');
    if (!year) { year = today.getFullYear(); month = today.getMonth() + 1; }
    root.innerHTML = '<div class="loading">加载期限数据…</div>';
    load(root);
  }

  function load(root) {
    API.calendar(year, month).then(d => {
      DATA = d;
      draw(root, d);
    }).catch(e => { root.innerHTML = '<div class="empty">' + esc(e.message) + '</div>'; });
  }

  function shift(root, delta) {
    let m = month + delta, y = year;
    while (m < 1) { m += 12; y -= 1; }
    while (m > 12) { m -= 12; y += 1; }
    year = y; month = m;
    load(root);
  }

  function draw(root, d) {
    const todayStr = global.APP.meta.today;
    const first = new Date(year, month - 1, 1);
    const startDow = (first.getDay() + 6) % 7;          // 周一为一周起始
    const daysInMonth = new Date(year, month, 0).getDate();
    const prevDays = new Date(year, month - 1, 0).getDate();

    const cells = [];
    const total = Math.ceil((startDow + daysInMonth) / 7) * 7;   // 5 或 6 行
    for (let i = 0; i < total; i++) {
      const dayNum = i - startDow + 1;
      let dnum, cmonth, cyear, other = false;
      if (dayNum < 1) {
        dnum = prevDays + dayNum;
        cmonth = month === 1 ? 12 : month - 1;
        cyear = month === 1 ? year - 1 : year;
        other = true;
      } else if (dayNum > daysInMonth) {
        dnum = dayNum - daysInMonth;
        cmonth = month === 12 ? 1 : month + 1;
        cyear = month === 12 ? year + 1 : year;
        other = true;
      } else {
        dnum = dayNum; cmonth = month; cyear = year;
      }
      const key = cyear + '-' + String(cmonth).padStart(2, '0') + '-' + String(dnum).padStart(2, '0');
      cells.push({ dnum, key, items: d.days[key] || [], other, today: key === todayStr });
    }

    const overdue = d.overdue || [];
    root.innerHTML =
      '<div class="card" style="margin-bottom:16px"><div class="card-b" style="padding:14px 16px">' +
      '<div class="cal-bar">' +
      '<button class="btn" id="cal-prev">‹ 上月</button>' +
      '<div class="ym">' + year + ' 年 ' + month + ' 月</div>' +
      '<button class="btn" id="cal-next">下月 ›</button>' +
      '<button class="btn" id="cal-today">回到本月</button>' +
      '<div class="cal-legend">' +
      ['overdue', 'high', 'medium', 'low', 'done'].map(k =>
        '<span><i class="lg-' + k + '"></i>' + LEVEL_LABEL[k] + '</span>').join('') +
      '</div></div>' +
      '<div class="mini">本月到期事项 ' + d.summary.total + ' 项' +
      (d.summary.overdue_total ? '，其中已逾期未处置 ' + d.summary.overdue_total + ' 项' : '') +
      '。点击事项可查看详情。' +
      '</div></div></div>' +

      (overdue.length
        ? '<div class="card" style="margin-bottom:16px"><div class="card-h"><h3>已逾期未处置事项' +
        '<span class="sub">共 ' + overdue.length + ' 项</span></h3></div><div class="card-b">' +
        overdue.map(x => remindRow(x)).join('') +
        '</div></div>'
        : '') +

      '<div class="card"><div class="card-b tight">' +
      '<div class="cal-grid">' +
      ['一', '二', '三', '四', '五', '六', '日'].map(x => '<div class="cal-dow">' + x + '</div>').join('') +
      cells.map(c =>
        '<div class="cal-cell' + (c.other ? ' other' : '') + (c.today ? ' today' : '') + '">' +
        '<div class="cal-day">' + c.dnum + '</div>' +
        c.items.map(it =>
          '<div class="cal-item lv-' + it.level + '" data-id="' + it.id + '" title="' +
          esc(it.kind + ' · ' + it.name + ' · ' + it.date) + '">' +
          esc(it.name.slice(0, 18)) + '<span class="ci-kind"> ·' + esc(it.kind) + '</span>' +
          '</div>').join('') +
        '</div>').join('') +
      '</div></div></div>' +

      '<div class="card" style="margin-top:16px"><div class="card-h"><h3>本月事项清单</h3>' +
      '<span class="sub">按日期排序</span></div><div class="card-b tight">' +
      (d.list.length
        ? '<div class="tbl-wrap"><table class="tbl"><thead><tr>' +
        '<th>日期</th><th>事项</th><th>名称</th><th>类型</th><th>状态</th><th>剩余</th><th>部门</th><th></th>' +
        '</tr></thead><tbody>' +
        d.list.map(x =>
          '<tr><td>' + esc(x.date) + '</td><td>' + esc(x.kind) + '</td>' +
          '<td>' + esc(x.name) + '</td><td>' + catTag(x.category) + '</td>' +
          '<td>' + statusTag(x.status) + '</td><td>' + daysText(x.days) + '</td>' +
          '<td class="mini">' + esc(x.department || '—') + '</td>' +
          '<td><button class="btn btn-sm" data-open="' + x.id + '">查看</button></td></tr>').join('') +
        '</tbody></table></div>'
        : '<div class="empty">本月无到期事项</div>') +
      '</div></div>';

    $('#cal-prev', root).addEventListener('click', () => shift(root, -1));
    $('#cal-next', root).addEventListener('click', () => shift(root, 1));
    $('#cal-today', root).addEventListener('click', () => {
      const t = new Date(global.APP.meta.today + 'T00:00:00');
      year = t.getFullYear(); month = t.getMonth() + 1; load(root);
    });
    $$('.cal-item', root).forEach(n => n.addEventListener('click', () =>
      global.Views.assets.openDetail(+n.getAttribute('data-id'))));
    $$('[data-open]', root).forEach(n => n.addEventListener('click', () =>
      global.Views.assets.openDetail(+n.getAttribute('data-open'))));
  }

  function remindRow(x) {
    return '<div class="remind">' +
      '<span class="tag ' + (x.level === 'overdue' ? 't-red' : 't-orange') + '">' + esc(x.kind) + '</span>' +
      '<div class="rd-main"><div class="rd-name">' + esc(x.name) + '　' + catTag(x.category) + '</div>' +
      '<div class="rd-sub">' + esc(x.no || '') + '　·　' + esc(x.department || '') +
      '　·　应办日期 ' + esc(x.date) + '</div></div>' +
      '<div class="rd-days days-urgent">' + daysText(x.days) + '</div>' +
      '<button class="btn btn-sm" data-open="' + x.id + '">查看</button></div>';
  }

  global.Views = global.Views || {};
  global.Views.calendar = { render };
})(window);

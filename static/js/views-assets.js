/* 知识产权管理：列表筛选、表单弹窗、详情抽屉 */
(function (global) {
  'use strict';
  const { $, $$, esc, el, API, toast, modal, drawer, confirmBox, statusTag, catTag,
    daysText, fmtDate, field, input, textarea, select, formValues, emptyBlock } = global.C;

  const state = {
    category: '', sub_type: '', status: '', department: '', keyword: '',
    sort: 'updated_at', order: 'desc', page: 1, total: 0, items: [], loading: false,
  };

  // 字段标签随类型变化
  const LABEL = {
    '专利': { no: '申请号', noG: '授权公告号', d: '申请日', dG: '授权公告日', p: '申请人', c: '发明人/设计人',
      cl: '分类号（IPC/洛迦诺）', tf: '技术领域', s: '保护范围描述（权利要求摘要/设计要点）',
      si: '保护范围要点（每项一行）', ps: '保护期限起始日', pe: '保护期限届满日' },
    '著作权': { no: '登记申请号', noG: '登记号', d: '申请日', dG: '登记日', p: '著作权人', c: '作者/创作人',
      cl: '著作权分类', tf: '作品类别', s: '作品内容描述', si: '登记材料清单（每项一行）',
      ps: '保护期起始日', pe: '保护期届满日' },
    '数据知识产权': { no: '登记申请号', noG: '登记证书号', d: '申请登记日', dG: '登记日', p: '权利人',
      c: '数据处理者', cl: '数据分类', tf: '数据领域', s: '数据范围与登记内容', si: '数据字段与样例（每项一行）',
      ps: '登记有效期起', pe: '登记有效期止' },
    '商标': { no: '申请号', noG: '注册号', d: '申请日', dG: '注册日', p: '注册人', c: '设计人',
      cl: '类别（尼斯分类）', tf: '商品/服务类别', s: '核定使用商品/服务', si: '核定服务项目（每项一行）',
      ps: '专用权起始日', pe: '专用权到期日' },
  };
  const L = cat => LABEL[cat] || LABEL['专利'];

  function render(root) {
    const wrap = el('div');
    wrap.innerHTML =
      '<div class="card" style="margin-bottom:16px"><div class="card-b" style="padding:14px 16px">' +
      '<div class="filters" id="filters">' +
      '<input id="f-kw" class="grow" placeholder="搜索名称 / 申请号 / 登记号 / 权利人 / 分类号 / 代理机构…">' +
      '<select id="f-cat"><option value="">全部类型</option></select>' +
      '<select id="f-sub"><option value="">全部子类型</option></select>' +
      '<select id="f-st"><option value="">全部状态</option></select>' +
      '<select id="f-dept"><option value="">全部部门</option></select>' +
      '<select id="f-sort">' +
      '<option value="updated_at">按更新时间</option><option value="app_date">按申请日期</option>' +
      '<option value="protect_end">按到期日</option><option value="next_fee_date">按年费截止日</option>' +
      '</select>' +
      '<button class="btn" id="f-reset">重置</button>' +
      '</div></div></div>' +
      '<div class="card"><div class="card-h"><h3>知识产权台账<span class="sub" id="cntSub"></span></h3>' +
      '<div style="display:flex;gap:10px;align-items:center">' +
      '<button class="btn btn-primary btn-sm" id="btn-add">+ 新建</button></div></div>' +
      '<div class="card-b tight"><div id="tblBox"><div class="loading">加载中…</div></div></div></div>';

    root.innerHTML = '';
    root.appendChild(wrap);

    // 填充筛选项
    const meta = global.APP.meta;
    const catSel = $('#f-cat', wrap);
    Object.keys(meta.categories).forEach(c => catSel.appendChild(new Option(c, c)));
    meta.statuses.forEach(s => $('#f-st', wrap).appendChild(new Option(s, s)));
    meta.departments.forEach(d => $('#f-dept', wrap).appendChild(new Option(d, d)));

    function fillSub() {
      const sub = $('#f-sub', wrap);
      sub.innerHTML = '<option value="">全部子类型</option>';
      if (state.category && meta.categories[state.category]) {
        meta.categories[state.category].forEach(s => sub.appendChild(new Option(s, s)));
      } else {
        Object.values(meta.categories).flat().forEach(s => sub.appendChild(new Option(s, s)));
      }
      sub.value = state.sub_type || '';
    }
    fillSub();
    $('#f-kw', wrap).value = state.keyword;
    catSel.value = state.category; $('#f-st', wrap).value = state.status;
    $('#f-dept', wrap).value = state.department; $('#f-sort', wrap).value = state.sort;

    let timer;
    $('#f-kw', wrap).addEventListener('input', e => {
      state.keyword = e.target.value; state.page = 1;
      clearTimeout(timer); timer = setTimeout(load, 260);
    });
    catSel.addEventListener('change', e => { state.category = e.target.value; state.sub_type = ''; state.page = 1; fillSub(); load(); });
    $('#f-sub', wrap).addEventListener('change', e => { state.sub_type = e.target.value; state.page = 1; load(); });
    $('#f-st', wrap).addEventListener('change', e => { state.status = e.target.value; state.page = 1; load(); });
    $('#f-dept', wrap).addEventListener('change', e => { state.department = e.target.value; state.page = 1; load(); });
    $('#f-sort', wrap).addEventListener('change', e => { state.sort = e.target.value; load(); });
    $('#f-reset', wrap).addEventListener('click', () => {
      Object.assign(state, { category: '', sub_type: '', status: '', department: '', keyword: '', page: 1 });
      render(root);
    });
    $('#btn-add', wrap).addEventListener('click', () => openForm(null, () => load()));

    load();

    function load() {
      if (state.loading) return;
      state.loading = true;
      API.assets({
        category: state.category, sub_type: state.sub_type, status: state.status,
        department: state.department, keyword: state.keyword, sort: state.sort,
        order: state.order, page: state.page, page_size: 300,
      }).then(d => {
        state.items = d.items; state.total = d.total;
        renderTable($('#tblBox', wrap));
        $('#cntSub', wrap).textContent = '共 ' + d.total + ' 条';
      }).catch(e => toast(e.message, 'err')).finally(() => state.loading = false);
    }
    global.APP.reloadAssets = load;
  }

  function renderTable(box) {
    if (!state.items.length) { box.innerHTML = emptyBlock('没有符合条件的知识产权记录'); return; }
    const h =
      '<table class="tbl"><thead><tr>' +
      '<th style="min-width:230px">名称</th><th>类型</th><th>子类型</th><th>申请号/登记号</th>' +
      '<th>申请日</th><th>法律状态</th><th>年费/续展截止</th><th>保护期至</th><th>部门</th>' +
      '<th style="width:140px">操作</th></tr></thead><tbody>' +
      state.items.map(a =>
        '<tr class="tr-click" data-id="' + a.id + '">' +
        '<td><div class="txt-ell" title="' + esc(a.name) + '">' + esc(a.name) + '</div>' +
        '<div class="mini">' + esc(a.applicant || '') + '</div></td>' +
        '<td>' + catTag(a.category) + '</td>' +
        '<td><span class="mini">' + esc(a.sub_type || '—') + '</span></td>' +
        '<td><span class="mini">' + esc(a.grant_no || a.app_no || '—') + '</span></td>' +
        '<td><span class="mini">' + fmtDate(a.app_date) + '</span></td>' +
        '<td>' + statusTag(a.status) + '</td>' +
        '<td>' + (a.next_fee_date ? '<span class="mini">' + fmtDate(a.next_fee_date) + '</span><br>' + daysText(a.days_to_fee) : '<span class="mini">—</span>') + '</td>' +
        '<td><span class="mini">' + fmtDate(a.protect_end) + '</span></td>' +
        '<td><span class="mini">' + esc(a.department || '—') + '</span></td>' +
        '<td><div class="row-btns">' +
        '<button class="btn btn-sm" data-act="detail" data-id="' + a.id + '">详情</button>' +
        '<button class="btn btn-sm" data-act="edit" data-id="' + a.id + '">编辑</button>' +
        '<button class="btn btn-sm btn-danger" data-act="del" data-id="' + a.id + '">删除</button>' +
        '</div></td></tr>').join('') + '</tbody></table>';
    box.innerHTML = '<div class="tbl-wrap">' + h + '</div>';

    $$('.tr-click', box).forEach(tr => tr.addEventListener('click', e => {
      const act = e.target.getAttribute('data-act');
      const id = +tr.getAttribute('data-id');
      if (act === 'detail') return openDetail(id);
      if (act === 'edit') return openForm(id, () => global.APP.reloadAssets && global.APP.reloadAssets());
      if (act === 'del') return doDelete(id);
      if (!act) openDetail(id);
    }));
  }

  function doDelete(id) {
    const a = state.items.find(x => x.id === id);
    confirmBox('删除确认', '确定删除「' + (a ? a.name : id) + '」吗？该记录的状态变更与年费记录将一并删除，且不可恢复。', '确认删除')
      .then(yes => {
        if (!yes) return;
        API.deleteAsset(id).then(() => {
          toast('已删除', 'ok');
          global.APP.reloadAssets && global.APP.reloadAssets();
          global.APP.refreshBadges && global.APP.refreshBadges();
        }).catch(e => toast(e.message, 'err'));
      });
  }

  // ---------------- 表单 ----------------
  function openForm(id, onDone) {
    const meta = global.APP.meta;
    const editing = !!id;
    let data = { category: '专利', region: '国内', status: '申请中' };

    Promise.resolve(id ? API.asset(id) : data).then(d => {
      data = d;
      const body = el('div');
      body.innerHTML = '<div class="form-grid" id="aform">' +
        '<div class="sec-title">基本信息</div>' +
        field('知识产权类型', select('category', Object.keys(meta.categories), data.category, false), { required: true }) +
        field('子类型', '<select name="sub_type"></select>', { required: true }) +
        field('知识产权名称', input('name', data.name, '例如：一种基于负压反馈的自适应抓取控制方法'), { required: true, full: true }) +
        field('申请号 / 登记申请号', input('app_no', data.app_no, '如 202010356782.1')) +
        field('授权号 / 登记号 / 注册号', input('grant_no', data.grant_no, '如 ZL202010356782.1')) +
        field('申请日 / 登记申请日', input('app_date', data.app_date, '', 'date')) +
        field('授权日 / 登记日 / 注册日', input('grant_date', data.grant_date, '', 'date')) +
        field('申请人 / 权利人', input('applicant', data.applicant, '默认取企业名称')) +
        field('发明人 / 作者 / 设计人', input('creators', data.creators, '多人用分号分隔')) +
        field('代理机构', input('agency', data.agency)) +
        field('分类号', input('class_no', data.class_no, 'IPC / 洛迦诺 / 尼斯 / 著作权分类')) +
        field('技术领域 / 商品类别', input('tech_field', data.tech_field)) +
        field('归属部门', select('department', meta.departments, data.department)) +
        field('保护地域', select('region', meta.regions, data.region, false)) +

        '<div class="sec-title">法律状态</div>' +
        field('当前法律状态', select('status', meta.statuses, data.status, false), { required: true }) +
        field('状态更新日期', input('status_date', data.status_date, '', 'date')) +
        field('当前年费年度 / 续展次数', input('fee_year', data.fee_year || 0, '如 6', 'number')) +
        field('本期是否已缴纳', select('fee_paid', [{ v: 1, t: '已缴纳' }, { v: 0, t: '未缴纳' }], data.fee_paid ? 1 : 0, false)) +
        field('下一年费 / 续展截止日', input('next_fee_date', data.next_fee_date, '', 'date')) +
        field('保护期限起始日', input('protect_start', data.protect_start, '', 'date')) +
        field('保护期限届满日', input('protect_end', data.protect_end, '', 'date'),
          { hint: '发明 20 年 / 实用新型 10 年 / 外观 15 年 / 软件著作权 50 年 / 商标 10 年可续展 / 数据登记 2 年' }) +

        '<div class="sec-title">具体保护范围</div>' +
        field('保护范围描述', textarea('scope_text', data.scope_text,
          '专利填权利要求摘要与设计要点；著作权填作品内容；商标填核定使用商品/服务；数据知识产权填数据范围与登记内容', 5), { full: true }) +
        field('保护范围要点清单', textarea('scope_items', (data.scope_items || []).join('\n'),
          '每行一条，例如：独立权利要求 1 项，从属权利要求 11 项', 4), { full: true, hint: '每行一条，保存为清单' }) +
        field('核心技术方案 / 数据要点', textarea('key_points', data.key_points, '被保护的技术要点或数据要点', 2), { full: true }) +
        field('竞争对手 / 参照专利族', input('rival_ref', data.rival_ref, '用于规避设计分析'), { full: true }) +
        field('备注', textarea('remark', data.remark, '', 2), { full: true }) +
        '</div>';

      const m = modal({
        title: editing ? '编辑知识产权' : '新建知识产权',
        body,
        okText: editing ? '保存修改' : '创建',
        onOk: (box, close) => {
          const v = formValues($('#aform', box));
          if (!v.name.trim()) { toast('请填写知识产权名称', 'err'); return; }
          v.fee_paid = v.fee_paid === '1' || v.fee_paid === 1 ? 1 : 0;
          v.scope_items = (v.scope_items || '').split('\n').map(s => s.trim()).filter(Boolean);
          const p = editing ? API.updateAsset(id, v) : API.createAsset(v);
          return p.then(res => {
            toast(editing ? '已保存' : '已创建', 'ok');
            close(); onDone && onDone(res);
            global.APP.refreshBadges && global.APP.refreshBadges();
          });
        },
      });

      // 子类型联动 + 标签联动
      const box = m.box;
      function syncSub() {
        const cat = $('[name=category]', box).value;
        const sel = $('[name=sub_type]', box);
        sel.innerHTML = '';
        (meta.categories[cat] || []).forEach(s => sel.appendChild(new Option(s, s)));
        if (data.sub_type && meta.categories[cat] && meta.categories[cat].indexOf(data.sub_type) >= 0) {
          sel.value = data.sub_type;
        }
        const lb = L(cat);
        // 更新动态标签
        const map = { '申请号 / 登记申请号': lb.no, '授权号 / 登记号 / 注册号': lb.noG, '申请日 / 登记申请日': lb.d, '授权日 / 登记日 / 注册日': lb.dG, '申请人 / 权利人': lb.p, '发明人 / 作者 / 设计人': lb.c, '分类号': lb.cl, '技术领域 / 商品类别': lb.tf, '保护范围描述': lb.s, '保护范围要点清单': lb.si, '保护期限起始日': lb.ps, '保护期限届满日': lb.pe };
        $$('.fld label', box).forEach(l => {
          const key = l.textContent.replace('*', '').trim();
          if (map[key]) l.innerHTML = esc(map[key]) + (l.querySelector('.req') ? '<span class="req">*</span>' : '');
        });
      }
      $('[name=category]', box).addEventListener('change', syncSub);
      syncSub();
    }).catch(e => toast(e.message, 'err'));
  }

  // ---------------- 详情抽屉 ----------------
  function openDetail(id) {
    API.asset(id).then(a => {
      const lb = L(a.category);
      const body = el('div');
      const items = a.scope_items || [];
      body.innerHTML =
        '<div class="block"><h4>基本信息</h4><dl class="kv">' +
        kv('类型', catTag(a.category) + ' <span class="mini">' + esc(a.sub_type || '') + '</span>') +
        kv(lb.no, a.app_no) + kv(lb.noG, a.grant_no) +
        kv(lb.d, a.app_date) + kv(lb.dG, a.grant_date) +
        kv(lb.p, a.applicant) + kv(lb.c, a.creators) +
        kv('代理机构', a.agency) + kv(lb.cl, a.class_no) +
        kv(lb.tf, a.tech_field) + kv('归属部门', a.department) +
        kv('保护地域', a.region) +
        '</dl></div>' +

        '<div class="block"><h4>法律状态</h4><dl class="kv">' +
        kv('当前状态', statusTag(a.status) + ' <span class="mini">' + esc(a.status_date || '') + '</span>') +
        kv('本期年费', (a.fee_year ? '第 ' + a.fee_year + ' 年度 · ' : '') +
          (a.fee_paid ? '<span class="tag t-green">已缴纳</span>' : '<span class="tag t-red">未缴纳</span>')) +
        kv('下一年费/续展截止', (a.next_fee_date || '—') + (a.days_to_fee !== null ? '　' + daysText(a.days_to_fee) : '')) +
        kv('保护期限', (a.protect_start || '—') + ' 至 ' + (a.protect_end || '—') +
          (a.days_to_end !== null ? '　' + daysText(a.days_to_end) : '')) +
        '</dl></div>' +

        '<div class="block"><h4>具体保护范围</h4>' +
        (a.scope_text ? '<div class="prose" style="margin-bottom:12px">' + esc(a.scope_text) + '</div>'
          : '<div class="mini" style="margin-bottom:12px">未填写</div>') +
        (items.length ? '<div>' + items.map(x => '<div class="ul-item">' + esc(x) + '</div>').join('') + '</div>' : '') +
        (a.key_points ? '<div style="margin-top:12px"><span class="mini">核心要点：</span><div class="prose">' + esc(a.key_points) + '</div></div>' : '') +
        (a.rival_ref ? '<div style="margin-top:10px"><span class="mini">竞争对手/参照专利族：</span><span>' + esc(a.rival_ref) + '</span></div>' : '') +
        '</div>' +

        '<div class="block"><h4>状态变更记录 <button class="btn btn-sm" id="add-log" style="margin-left:auto">+ 添加</button></h4>' +
        (a.logs && a.logs.length ?
          '<table class="tbl"><thead><tr><th>变更日期</th><th>原状态</th><th>新状态</th><th>说明</th><th></th></tr></thead><tbody>' +
          a.logs.map(l => '<tr><td>' + fmtDate(l.change_date) + '</td><td>' + (l.old_status ? statusTag(l.old_status) : '<span class="mini">—</span>') +
            '</td><td>' + statusTag(l.new_status) + '</td><td class="mini">' + esc(l.note || '') + '</td>' +
            '<td><button class="btn btn-sm btn-danger" data-dellog="' + l.id + '">删除</button></td></tr>').join('') +
          '</tbody></table>' : '<div class="mini">暂无状态变更记录</div>') +
        '</div>' +

        '<div class="block"><h4>年费 / 续展缴纳记录 <button class="btn btn-sm" id="add-fee" style="margin-left:auto">+ 添加</button></h4>' +
        (a.fees && a.fees.length ?
          '<table class="tbl"><thead><tr><th>年度</th><th>金额(元)</th><th>应缴日</th><th>实缴日</th><th>状态</th><th>备注</th><th></th></tr></thead><tbody>' +
          a.fees.map(f => '<tr><td>第 ' + esc(f.year) + ' 年</td><td>' + esc(f.amount) + '</td><td>' + fmtDate(f.due_date) +
            '</td><td>' + fmtDate(f.paid_date) + '</td><td>' + (f.paid ? '<span class="tag t-green">已缴</span>' : '<span class="tag t-red">未缴</span>') +
            '</td><td class="mini">' + esc(f.note || '') + '</td>' +
            '<td><button class="btn btn-sm" data-editfee="' + f.id + '">编辑</button> ' +
            '<button class="btn btn-sm btn-danger" data-delfee="' + f.id + '">删除</button></td></tr>').join('') +
          '</tbody></table>' : '<div class="mini">暂无年费记录</div>') +
        '</div>' +

        (a.remark ? '<div class="block"><h4>备注</h4><div class="prose">' + esc(a.remark) + '</div></div>' : '');

      const sub =
        '<div style="display:flex;gap:8px;align-items:center">' +
        catTag(a.category) + '<span class="tag t-gray">' + esc(a.sub_type || '—') + '</span>' + statusTag(a.status) +
        (a.source === 'auto' ? '' : '') +
        '</div>';

      const d = drawer({ title: a.name, sub, body });

      $('#add-log', body).addEventListener('click', () => addLogForm(a, d));
      $('#add-fee', body).addEventListener('click', () => addFeeForm(a, d));
      $$('[data-dellog]', body).forEach(b => b.addEventListener('click', () => {
        API.delLog(+b.getAttribute('data-dellog')).then(() => { toast('已删除', 'ok'); d.close(); openDetail(id); });
      }));
      $$('[data-delfee]', body).forEach(b => b.addEventListener('click', () => {
        API.delFee(+b.getAttribute('data-delfee')).then(() => { toast('已删除', 'ok'); d.close(); openDetail(id); });
      }));
      $$('[data-editfee]', body).forEach(b => b.addEventListener('click', () => {
        const f = a.fees.find(x => x.id === +b.getAttribute('data-editfee'));
        addFeeForm(a, d, f);
      }));
    }).catch(e => toast(e.message, 'err'));
  }

  function kv(k, v) {
    return '<dt>' + esc(k) + '</dt><dd>' + (v === null || v === undefined || v === '' ? '<span class="mini">—</span>' : v) + '</dd>';
  }

  function addLogForm(a, drawerRef) {
    const body = el('div');
    body.innerHTML = '<div class="form-grid">' +
      field('变更日期', input('change_date', global.APP.meta.today, '', 'date'), { required: true }) +
      field('新状态', select('new_status', global.APP.meta.statuses, a.status, false), { required: true }) +
      field('说明', textarea('note', '', '如：授权公告、办理质押登记'), { full: true }) +
      '</div>';
    modal({
      title: '添加状态变更记录', small: true, body,
      onOk: (box, close) => {
        const v = formValues(box);
        return API.addLog(a.id, v).then(() => {
          toast('已添加', 'ok'); close(); drawerRef.close(); openDetail(a.id);
          global.APP.reloadAssets && global.APP.reloadAssets();
          global.APP.refreshBadges && global.APP.refreshBadges();
        });
      }
    });
  }

  function addFeeForm(a, drawerRef, fee) {
    const editing = !!fee;
    const f = fee || { year: (a.fee_year || 0) + 1, amount: '', due_date: a.next_fee_date || '', paid: 0, paid_date: '', note: '' };
    const body = el('div');
    body.innerHTML = '<div class="form-grid">' +
      field('年度', input('year', f.year, '', 'number'), { required: true }) +
      field('金额（元）', input('amount', f.amount, '如 1200', 'number')) +
      field('应缴日期', input('due_date', f.due_date, '', 'date'), { required: true }) +
      field('是否已缴', select('paid', [{ v: 1, t: '已缴' }, { v: 0, t: '未缴' }], f.paid ? 1 : 0, false)) +
      field('实缴日期', input('paid_date', f.paid_date, '', 'date')) +
      field('备注', input('note', f.note, '如：第 6 年年费')) +
      '</div>';
    modal({
      title: editing ? '编辑年费记录' : '添加年费记录', small: true, body,
      onOk: (box, close) => {
        const v = formValues(box);
        v.paid = v.paid === '1' ? 1 : 0;
        const p = editing ? API.updateFee(fee.id, v) : API.addFee(a.id, v);
        return p.then(() => {
          toast(editing ? '已保存' : '已添加', 'ok'); close(); drawerRef.close(); openDetail(a.id);
          global.APP.reloadAssets && global.APP.reloadAssets();
          global.APP.refreshBadges && global.APP.refreshBadges();
        });
      }
    });
  }

  global.Views = global.Views || {};
  global.Views.assets = { render, openForm, openDetail, state };
})(window);

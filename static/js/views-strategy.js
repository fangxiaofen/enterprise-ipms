/* 战略中心：规避设计战略与风险战略 */
(function (global) {
  'use strict';
  const { $, $$, esc, el, API, toast, modal, confirmBox, field, input, textarea, select,
    formValues, emptyBlock } = global.C;

  let module = 'risk';
  let level = '';
  let keyword = '';
  let DATA = [];

  function render(root) {
    root.innerHTML =
      '<div class="card" style="margin-bottom:16px"><div class="card-b" style="padding:14px 16px">' +
      '<div class="filters">' +
      '<div class="seg" id="seg-mod">' +
      '<button data-m="risk" class="' + (module === 'risk' ? 'active' : '') + '">风险战略</button>' +
      '<button data-m="avoid" class="' + (module === 'avoid' ? 'active' : '') + '">规避设计战略</button>' +
      '</div>' +
      '<input id="s-kw" class="grow" placeholder="搜索标题 / 内容 / 建议…">' +
      '<select id="s-lv"><option value="">全部风险等级</option>' +
      '<option value="高">高</option><option value="中">中</option><option value="低">低</option></select>' +
      '<button class="btn" id="s-rebuild" title="依据当前台账数据重新推导战略建议">重新生成智能建议</button>' +
      '<button class="btn btn-primary" id="s-add">+ 新增条目</button>' +
      '</div></div></div>' +
      '<div id="listBox"><div class="loading">加载中…</div></div>';

    $('#s-kw', root).value = keyword;
    $('#s-lv', root).value = level;
    let timer;
    $('#s-kw', root).addEventListener('input', e => {
      keyword = e.target.value; clearTimeout(timer); timer = setTimeout(load, 250);
    });
    $('#s-lv', root).addEventListener('change', e => { level = e.target.value; load(); });
    $$('#seg-mod button', root).forEach(b => b.addEventListener('click', () => {
      module = b.getAttribute('data-m');
      $$('#seg-mod button', root).forEach(x => x.classList.remove('active'));
      b.classList.add('active'); load();
    }));
    $('#s-add', root).addEventListener('click', () => openForm(null));
    $('#s-rebuild', root).addEventListener('click', () => {
      confirmBox('重新生成智能建议',
        '将根据当前知识产权台账数据重新推导战略条目。系统自动生成的条目会被覆盖，您手动新增的条目将保留。是否继续？',
        '重新生成')
        .then(yes => {
          if (!yes) return;
          API.rebuildStrategy().then(d => {
            toast('已生成 ' + d.rebuilt + ' 条智能建议', 'ok');
            load(); global.APP.refreshBadges && global.APP.refreshBadges();
          }).catch(e => toast(e.message, 'err'));
        });
    });
    load();
    global.APP.reloadStrategy = load;
  }

  function load() {
    API.strategies({ module, risk_level: level, keyword }).then(d => {
      DATA = d.items;
      renderList($('#listBox'));
    }).catch(e => toast(e.message, 'err'));
  }

  const LEVEL_CLS = { '高': 't-red', '中': 't-orange', '低': 't-green' };

  function renderList(box) {
    if (!box) return;
    if (!DATA.length) { box.innerHTML = emptyBlock('暂无战略条目，可点击「重新生成智能建议」或手动新增'); return; }
    const high = DATA.filter(x => x.risk_level === '高').length;
    box.innerHTML =
      '<div class="card"><div class="card-h"><h3>' +
      (module === 'risk' ? '风险战略清单' : '规避设计战略清单') +
      '<span class="sub">共 ' + DATA.length + ' 条，其中高风险 ' + high + ' 条</span></h3></div>' +
      '<div class="card-b">' + DATA.map(itemHtml).join('') + '</div></div>';

    $$('[data-toggle]', box).forEach(h => h.addEventListener('click', () => {
      const id = h.getAttribute('data-toggle');
      const b = $('#body-' + id, box);
      b.style.display = b.style.display === 'none' ? 'block' : 'none';
    }));
    $$('[data-edit]', box).forEach(b => b.addEventListener('click', e => {
      e.stopPropagation();
      openForm(+b.getAttribute('data-edit'));
    }));
    $$('[data-del]', box).forEach(b => b.addEventListener('click', e => {
      e.stopPropagation();
      const id = +b.getAttribute('data-del');
      const it = DATA.find(x => x.id === id);
      confirmBox('删除确认', '确定删除「' + (it ? it.title : id) + '」吗？', '确认删除').then(yes => {
        if (!yes) return;
        API.deleteStrategy(id).then(() => {
          toast('已删除', 'ok'); load(); global.APP.refreshBadges && global.APP.refreshBadges();
        }).catch(e => toast(e.message, 'err'));
      });
    }));
    $$('[data-status]', box).forEach(sel => sel.addEventListener('change', e => {
      const id = +sel.getAttribute('data-status');
      API.updateStrategy(id, { status: e.target.value })
        .then(() => { toast('状态已更新', 'ok'); load(); })
        .catch(err => toast(err.message, 'err'));
    }));
  }

  function itemHtml(s) {
    return '<div class="strat" id="strat-' + s.id + '">' +
      '<div class="strat-h" data-toggle="' + s.id + '">' +
      '<span class="tag ' + (LEVEL_CLS[s.risk_level] || 't-gray') + '">' + esc(s.risk_level || '中') + '</span>' +
      '<div class="strat-t"><div class="tt">' + esc(s.title) + '</div>' +
      '<div class="tm"><span>' + esc(s.category || '未分类') + '</span>' +
      (s.owner ? '<span>责任人：' + esc(s.owner) + '</span>' : '') +
      (s.deadline ? '<span>时限：' + esc(s.deadline) + '</span>' : '') +
      '<span class="source-tag' + (s.source === 'auto' ? ' auto' : '') + '">' +
      (s.source === 'auto' ? '系统生成' : '手动新增') + '</span></div></div>' +
      '<select data-status="' + s.id + '" class="btn btn-sm" style="padding:3px 6px">' +
      ['待启动', '进行中', '已完成', '已关闭'].map(v =>
        '<option value="' + v + '"' + (s.status === v ? ' selected' : '') + '>' + v + '</option>').join('') +
      '</select>' +
      '<button class="btn btn-sm" data-edit="' + s.id + '">编辑</button>' +
      '<button class="btn btn-sm btn-danger" data-del="' + s.id + '">删除</button>' +
      '</div>' +
      '<div class="strat-b" id="body-' + s.id + '" style="display:none">' +
      '<div class="lbl">分析内容</div><div class="prose">' + esc(s.content || '—') + '</div>' +
      '<div class="lbl">应对建议</div><div class="prose">' + esc(s.actions || '—') + '</div>' +
      '</div></div>';
  }

  function openForm(id) {
    const editing = !!id;
    const data = editing ? DATA.find(x => x.id === id) : { module, risk_level: '中', status: '待启动' };
    if (!data) return;
    const meta = global.APP.meta;
    const body = el('div');
    const catMap = {
      risk: ['侵权风险（FTO）', '年费维持风险', '商标续展风险', '商标撤三风险', '数据合规风险',
        '诉讼风险', '审查周期风险', '布局结构风险', '商标布局风险', '权利流失风险', '其他'],
      avoid: ['规避设计', '专利布局', '防御性公开', '外围专利布局', '挖掘与申报策略',
        '标准必要专利', '数据资产布局', '其他'],
    };
    body.innerHTML = '<div class="form-grid" id="sform">' +
      field('所属模块', select('module', [{ v: 'risk', t: '风险战略' }, { v: 'avoid', t: '规避设计战略' }], data.module, false), { required: true }) +
      field('风险等级', select('risk_level', meta.levels, data.risk_level, false)) +
      field('标题', input('title', data.title, '一句话概括'), { required: true, full: true }) +
      field('分类', select('category', catMap.risk.concat(catMap.avoid), data.category)) +
      field('责任人 / 部门', input('owner', data.owner, '如：知识产权部 / 方晓汾')) +
      field('完成时限', input('deadline', data.deadline, '', 'date')) +
      field('处置状态', select('status', ['待启动', '进行中', '已完成', '已关闭'], data.status, false)) +
      field('分析内容', textarea('content', data.content, '问题背景、风险成因、影响范围', 5), { full: true }) +
      field('应对建议', textarea('actions', data.actions, '每条建议单独一行', 5), { full: true, hint: '每行一条，界面按行展示' }) +
      '</div>';
    modal({
      title: editing ? '编辑战略条目' : '新增战略条目',
      body,
      onOk: (box, close) => {
        const v = formValues($('#sform', box));
        if (!v.title.trim()) { toast('请填写标题', 'err'); return; }
        const p = editing ? API.updateStrategy(id, v) : API.createStrategy(v);
        return p.then(() => {
          toast(editing ? '已保存' : '已新增', 'ok');
          close(); load(); global.APP.refreshBadges && global.APP.refreshBadges();
        });
      },
      onMount: box => {
        const modSel = $('[name=module]', box);
        const catSel = $('[name=category]', box);
        function sync() {
          const list = catMap[modSel.value] || catMap.risk;
          const cur = catSel.value;
          catSel.innerHTML = '<option value="">— 请选择 —</option>' +
            list.map(c => '<option value="' + esc(c) + '">' + esc(c) + '</option>').join('');
          catSel.value = list.indexOf(cur) >= 0 ? cur : '';
        }
        modSel.addEventListener('change', sync); sync();
      },
    });
  }

  global.Views = global.Views || {};
  global.Views.strategy = { render };
})(window);

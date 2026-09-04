/* 导入导出与下载：Excel / CSV / 模板 / 批量导入 */
(function (global) {
  'use strict';
  const { $, $$, esc, el, API, toast, modal, select, field } = global.C;

  function download(text, filename, mime) {
    // 文本类文件统一加 BOM，保证 Excel 打开 CSV 不乱码
    const body = /^(\.csv|text\/csv)/i.test(filename) || /csv/.test(mime || '')
      ? '\ufeff' + text : text;
    const blob = new Blob([body], { type: mime || 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
  }

  function exportCsv() {
    API.exportCsv().then(d => {
      download(d.csv, d.filename, 'text/csv;charset=utf-8');
      toast('已导出 ' + d.count + ' 条台账（CSV）', 'ok');
    }).catch(e => toast(e.message, 'err'));
  }

  function exportXls() {
    API.exportXls().then(d => {
      download(d.xml, d.filename, 'application/vnd.ms-excel;charset=utf-8');
      toast('已导出 ' + d.count + ' 条台账（Excel）', 'ok');
    }).catch(e => toast(e.message, 'err'));
  }

  function downloadTemplate() {
    API.templateCsv().then(d => {
      download(d.csv, d.filename, 'text/csv;charset=utf-8');
      toast('模板已下载，请按说明填写', 'ok');
    }).catch(e => toast(e.message, 'err'));
  }

  // 浏览器端读取文件，自动识别 UTF-8 / GBK
  function readText(file) {
    return new Promise((resolve, reject) => {
      const fr = new FileReader();
      fr.onerror = () => reject(new Error('文件读取失败'));
      fr.onload = () => {
        const buf = fr.result;
        let text = '';
        try {
          text = new TextDecoder('utf-8', { fatal: false }).decode(buf);
        } catch (e) {
          text = '';
        }
        // 出现大量替换字符说明不是 UTF-8，改用 GBK 重新解码
        if ((text.match(/\ufffd/g) || []).length > 2) {
          try {
            text = new TextDecoder('gbk').decode(buf);
          } catch (e) { /* 浏览器不支持 gbk 时沿用 utf-8 结果 */ }
        }
        resolve(text);
      };
      fr.readAsArrayBuffer(file);
    });
  }

  function openImport(onDone) {
    const body = el('div');
    body.innerHTML =
      '<div style="font-size:13px;line-height:1.9;color:var(--text-2);margin-bottom:14px">' +
      '支持从 Excel 另存的 CSV 文件批量导入台账（自动识别 UTF-8 与 GBK 编码）。<br>' +
      '以「申请号/登记申请号」为唯一标识：已存在则更新该条，不存在则新建。<br>' +
      '请先下载模板，按模板表头填写后导入。' +
      '</div>' +
      '<div class="form-grid">' +
      field('选择 CSV 文件', '<input type="file" id="imp-file" accept=".csv,.txt">', { full: true }) +
      field('导入方式', select('mode', [{ v: 'append', t: '追加 / 更新（保留现有数据）' },
        { v: 'replace', t: '覆盖导入（清空现有台账后导入）' }], 'append', false), { full: true }) +
      '</div>' +
      '<div id="imp-preview" style="margin-top:14px"></div>' +
      '<div style="margin-top:10px"><span class="link" id="imp-tpl">下载导入模板</span></div>';

    let csvText = '';
    const m = modal({
      title: '批量导入知识产权台账', body, okText: '开始导入',
      onOk: (box, close) => {
        if (!csvText.trim()) { toast('请先选择 CSV 文件', 'err'); return; }
        const mode = $('[name=mode]', box).value;
        if (mode === 'replace' && !window.confirm('覆盖导入将清空现有全部台账数据，确定继续吗？')) return;
        return API.importCsv(csvText, mode).then(r => {
          close();
          showResult(r, mode);
          onDone && onDone(r);
          global.APP.refreshBadges && global.APP.refreshBadges();
        });
      },
      onMount: box => {
        $('#imp-tpl', box).addEventListener('click', downloadTemplate);
        $('#imp-file', box).addEventListener('change', e => {
          const f = e.target.files[0];
          if (!f) return;
          readText(f).then(t => {
            csvText = t;
            const lines = t.split(/\r?\n/).filter(s => s.trim());
            const head = lines[0] || '';
            const okHeader = head.indexOf('名称') >= 0;
            $('#imp-preview', box).innerHTML =
              '<div class="card" style="background:#fafbfd"><div class="card-b" style="padding:12px 14px">' +
              '<div class="mini">文件：' + esc(f.name) + '　共 ' + Math.max(lines.length - 1, 0) + ' 行数据</div>' +
              '<div class="mini" style="margin-top:4px">表头：' +
              (okHeader
                ? '<span class="tag t-green">识别正常</span>'
                : '<span class="tag t-red">未识别到「名称」列，请使用系统模板</span>') +
              '</div>' +
              '<div class="mini" style="margin-top:6px;word-break:break-all;opacity:.85">' +
              esc(head.slice(0, 150)) + '</div>' +
              '</div></div>';
          }).catch(err => toast(err.message, 'err'));
        });
      },
    });
    return m;
  }

  function showResult(r, mode) {
    const body = el('div');
    const errs = r.errors || [];
    body.innerHTML =
      '<div class="grid g4" style="gap:10px;margin-bottom:16px">' +
      miniStat('新建', r.created, 'c-green') + miniStat('更新', r.updated, 'c-blue') +
      miniStat('跳过', r.skipped, 'c-orange') + miniStat('错误', r.error_total || 0, 'c-red') +
      '</div>' +
      (errs.length
        ? '<div style="font-size:12.5px;font-weight:600;color:var(--text-2);margin-bottom:8px">' +
        '问题明细（最多显示 30 条）</div>' +
        '<div class="tbl-wrap" style="max-height:260px"><table class="tbl"><thead><tr>' +
        '<th style="width:70px">行号</th><th>名称</th><th>原因</th></tr></thead><tbody>' +
        errs.map(e => '<tr><td>' + esc(e.row) + '</td><td>' + esc(e.name || '—') + '</td>' +
          '<td class="mini">' + esc(e.msg) + '</td></tr>').join('') +
        '</tbody></table></div>'
        : '<div class="empty" style="padding:20px">全部数据导入成功</div>');
    modal({
      title: '导入结果', body, okText: '知道了', noFooter: false, small: false,
      onOk: (b, close) => close(),
      onMount: box => {
        const cancel = $$('.modal-f .btn', box).find(x => x.textContent === '取消');
        if (cancel) cancel.style.display = 'none';
      },
    });
  }

  function miniStat(label, value, cls) {
    return '<div class="stat ' + cls + '" style="padding:12px 14px"><span class="bar"></span>' +
      '<div class="label">' + esc(label) + '</div>' +
      '<div class="value" style="font-size:20px">' + esc(value) + '</div></div>';
  }

  global.C.download = download;
  global.IO = { exportCsv, exportXls, downloadTemplate, openImport, readText };
})(window);

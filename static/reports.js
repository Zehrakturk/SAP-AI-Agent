/* static/reports.js
   4 Power BI benzeri rapor formatı + interaktif rapor oluşturucu.
   Reports.open(data) ile çağrılır.
   data = { question, summary, rows, count, chart_type, chart_data, sql, tables_used, kpis, highlights }

   Akış:
     open(data) → _showBuilder(data)  (format + kolon + grafik + satır seçimi)
       → "Raporu Oluştur" → _renderReport(data, fmt, config)
*/

const Reports = (() => {

  const COLORS = [
    '#1a56db','#10b981','#f59e0b','#ef4444',
    '#8b5cf6','#ec4899','#06b6d4','#f97316',
  ];

  const FORMATS = [
    { fmt:'executive',  icon:'📊', title:'Yönetici Panosu',
      desc:'Büyük KPI sayıları, grafik ve özet. Üst yönetim için.' },
    { fmt:'analytical', icon:'📈', title:'Analiz Raporu',
      desc:'Grafik + detay tablo. Operasyonel analizler için.' },
    { fmt:'table',      icon:'🗂️', title:'Veri Tablosu',
      desc:'Tam tablo, kolon toplam/ortalamaları. Detaylı liste.' },
    { fmt:'trend',      icon:'📉', title:'Trend Raporu',
      desc:'Zaman serisi + top-N liste. Dönem analizleri için.' },
  ];

  /* ── Giriş noktası ────────────────────────────────────────────────────── */
  function open(data) {
    _showBuilder(data);
  }

  /* ── İnteraktif rapor oluşturucu ──────────────────────────────────────── */
  function _showBuilder(data) {
    _removeExisting('rpt-picker');

    const rows = data.rows || [];
    const keys = rows.length
      ? Object.keys(rows[0]).filter(k => !['id','fetched_at'].includes(k))
      : [];
    const numericCols = keys.filter(k =>
      rows.length && rows.every(r => r[k] === null || r[k] === '' || !isNaN(Number(r[k]))));
    const stringCols  = keys.filter(k => !numericCols.includes(k));
    const defLabel = stringCols[0] || keys[0] || '';
    const defValue = numericCols[0] || '';
    const defType  = (data.chart_type || 'BAR').toUpperCase();

    const overlay = document.createElement('div');
    overlay.id = 'rpt-picker';
    overlay.dataset.fmt = 'executive';
    overlay.style.cssText = `
      position:fixed;inset:0;background:rgba(17,24,39,.6);z-index:1000;
      display:flex;align-items:center;justify-content:center;
      backdrop-filter:blur(4px);padding:16px;font-family:'Inter',system-ui,sans-serif;
    `;

    const formatCards = FORMATS.map(f => _formatCard(f, f.fmt === 'executive')).join('');

    const colChecks = keys.length
      ? keys.map(k => `
          <label class="rpt-colchk" style="display:flex;align-items:center;gap:7px;padding:6px 9px;
                 border:1px solid #e5e7eb;border-radius:7px;font-size:12px;color:#374151;cursor:pointer;background:#fff">
            <input type="checkbox" data-col="${_esc(k)}" checked style="accent-color:#1a56db">
            <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${_esc(k)}</span>
          </label>`).join('')
      : `<div style="color:#9ca3af;font-size:12px;padding:8px">Bu sorguda kolon yok.</div>`;

    const labelOpts = keys.map(k =>
      `<option value="${_esc(k)}" ${k===defLabel?'selected':''}>${_esc(k)}</option>`).join('');
    const valueOpts = (numericCols.length ? numericCols : keys).map(k =>
      `<option value="${_esc(k)}" ${k===defValue?'selected':''}>${_esc(k)}</option>`).join('');
    const typeOpts = ['BAR','LINE','PIE'].map(t =>
      `<option value="${t}" ${t===defType?'selected':''}>${t}</option>`).join('');

    overlay.innerHTML = `
      <div style="background:#fff;border-radius:16px;box-shadow:0 24px 64px rgba(0,0,0,.18);
                  width:880px;max-width:100%;max-height:92vh;display:flex;flex-direction:column;overflow:hidden">

        <!-- Header -->
        <div style="padding:20px 26px 16px;border-bottom:1px solid #e5e7eb;
                    display:flex;align-items:center;justify-content:space-between;flex-shrink:0">
          <div>
            <div style="font-size:17px;font-weight:700;color:#111827">Rapor Oluştur</div>
            <div style="font-size:12px;color:#9ca3af;margin-top:2px">
              ${data.count ?? rows.length} kayıt • ${(data.tables_used||[]).join(', ') || '—'}
            </div>
          </div>
          <button onclick="document.getElementById('rpt-picker').remove()"
            style="width:32px;height:32px;border:1px solid #e5e7eb;border-radius:8px;background:#f9fafb;
                   color:#6b7280;font-size:18px;cursor:pointer;display:flex;align-items:center;justify-content:center">✕</button>
        </div>

        <!-- Body (scroll) -->
        <div style="overflow-y:auto;padding:20px 26px;display:flex;flex-direction:column;gap:22px">

          <!-- 1 · Format -->
          <section>
            <div style="font-size:13px;font-weight:700;color:#374151;margin-bottom:10px">1 · Rapor Formatı</div>
            <div id="rpt-formats" style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
              ${formatCards}
            </div>
          </section>

          <!-- 2 · Kolonlar -->
          <section>
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
              <span style="font-size:13px;font-weight:700;color:#374151">2 · Rapora Dahil Edilecek Kolonlar</span>
              <span style="display:flex;gap:6px">
                <button id="rpt-col-all"  style="font-size:11px;padding:4px 10px;border:1px solid #e5e7eb;border-radius:6px;background:#f9fafb;color:#374151;cursor:pointer">Tümü</button>
                <button id="rpt-col-none" style="font-size:11px;padding:4px 10px;border:1px solid #e5e7eb;border-radius:6px;background:#f9fafb;color:#374151;cursor:pointer">Temizle</button>
              </span>
            </div>
            <div id="rpt-cols" style="display:grid;grid-template-columns:repeat(3,1fr);gap:7px;
                        max-height:170px;overflow-y:auto;padding:2px">
              ${colChecks}
            </div>
          </section>

          <!-- 3 · Grafik + 4 · Satır -->
          <section>
            <div style="font-size:13px;font-weight:700;color:#374151;margin-bottom:10px">3 · Grafik & Tablo Ayarları</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px">
              <div>
                <label style="font-size:11px;color:#6b7280;display:block;margin-bottom:4px">Etiket (X ekseni)</label>
                <select id="rpt-chart-label" class="rpt-sel">${labelOpts}</select>
              </div>
              <div>
                <label style="font-size:11px;color:#6b7280;display:block;margin-bottom:4px">Değer (Y ekseni)</label>
                <select id="rpt-chart-value" class="rpt-sel">${valueOpts}</select>
              </div>
              <div>
                <label style="font-size:11px;color:#6b7280;display:block;margin-bottom:4px">Grafik tipi</label>
                <select id="rpt-chart-type" class="rpt-sel">${typeOpts}</select>
              </div>
              <div>
                <label style="font-size:11px;color:#6b7280;display:block;margin-bottom:4px">Tablo satır limiti</label>
                <input id="rpt-maxrows" type="number" min="1" max="500" value="25" class="rpt-sel">
              </div>
            </div>
            <div style="font-size:11px;color:#9ca3af;margin-top:8px">
              İpucu: Etiket + Değer seçilince grafik bu kolonlardan yeniden hesaplanır
              (aynı etiketler toplanır). Boş bırakırsan AI'nın önerdiği grafik kullanılır.
            </div>
          </section>
        </div>

        <!-- Footer -->
        <div style="padding:16px 26px;border-top:1px solid #e5e7eb;display:flex;
                    justify-content:flex-end;gap:10px;flex-shrink:0;background:#fafafa">
          <button id="rpt-cancel"
            style="padding:9px 18px;border:1px solid #e5e7eb;border-radius:8px;background:#fff;
                   color:#374151;font-size:13px;font-weight:600;cursor:pointer">İptal</button>
          <button id="rpt-generate"
            style="padding:9px 22px;border:none;border-radius:8px;background:#1a56db;
                   color:#fff;font-size:13px;font-weight:600;cursor:pointer">Raporu Oluştur →</button>
        </div>
      </div>

      <style>
        #rpt-picker .rpt-sel{width:100%;padding:7px 10px;border:1px solid #e5e7eb;border-radius:7px;
                             font-size:12px;font-family:inherit;color:#111827;outline:none;background:#fff}
        #rpt-picker .rpt-colchk:hover{border-color:#bfdbfe;background:#f8faff}
        #rpt-picker .rpt-fmt[data-selected="1"]{border-color:#1a56db !important;
                             box-shadow:0 0 0 3px rgba(26,86,219,.12)}
      </style>
    `;

    document.body.appendChild(overlay);
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });

    // Format seçimi (radio davranışı)
    overlay.querySelectorAll('.rpt-fmt').forEach(card => {
      card.addEventListener('click', () => {
        overlay.dataset.fmt = card.dataset.fmt;
        overlay.querySelectorAll('.rpt-fmt').forEach(c =>
          c.dataset.selected = (c === card) ? '1' : '0');
      });
    });

    // Kolon tümü / temizle
    overlay.querySelector('#rpt-col-all') ?.addEventListener('click', () =>
      overlay.querySelectorAll('#rpt-cols input[type=checkbox]').forEach(c => c.checked = true));
    overlay.querySelector('#rpt-col-none')?.addEventListener('click', () =>
      overlay.querySelectorAll('#rpt-cols input[type=checkbox]').forEach(c => c.checked = false));

    // İptal
    overlay.querySelector('#rpt-cancel')?.addEventListener('click', () => overlay.remove());

    // Oluştur
    overlay.querySelector('#rpt-generate')?.addEventListener('click', () => {
      const cols = [...overlay.querySelectorAll('#rpt-cols input[type=checkbox]:checked')]
        .map(c => c.dataset.col);
      const config = {
        columns   : cols,
        chartLabel: overlay.querySelector('#rpt-chart-label')?.value || '',
        chartValue: overlay.querySelector('#rpt-chart-value')?.value || '',
        chartType : overlay.querySelector('#rpt-chart-type')?.value  || '',
        maxRows   : Math.max(1, parseInt(overlay.querySelector('#rpt-maxrows')?.value) || 25),
      };
      const fmt = overlay.dataset.fmt || 'executive';
      overlay.remove();
      _renderReport(data, fmt, config);
    });
  }

  function _formatCard(f, selected) {
    return `
      <div class="rpt-fmt" data-fmt="${f.fmt}" data-selected="${selected ? '1' : '0'}"
        style="border:2px solid #e5e7eb;border-radius:12px;padding:14px 16px;cursor:pointer;
               transition:all .15s;background:#fff;display:flex;gap:12px;align-items:flex-start">
        <div style="font-size:24px;line-height:1">${f.icon}</div>
        <div>
          <div style="font-size:14px;font-weight:700;color:#111827;margin-bottom:3px">${f.title}</div>
          <div style="font-size:11px;color:#6b7280;line-height:1.5">${f.desc}</div>
        </div>
      </div>`;
  }

  /* ── Konfigürasyonu uygula (kolon süz + grafik yeniden hesapla + özet) ─── */
  function _applyConfig(data, config) {
    if (!config) return data;
    const allRows = data.rows || [];
    const allKeys = allRows.length ? Object.keys(allRows[0]) : [];
    const cols    = (config.columns && config.columns.length)
      ? config.columns
      : allKeys.filter(k => !['id','fetched_at'].includes(k));

    // Seçili kolonlara indir (sıra korunur)
    const rows = allRows.map(r => {
      const o = {};
      cols.forEach(c => { o[c] = r[c]; });
      return o;
    });

    // Grafik — etiket+değer seçildiyse yeniden hesapla
    let chart_data = data.chart_data;
    let chart_type = data.chart_type;
    if (config.chartLabel && config.chartValue) {
      chart_data = _aggregateChart(allRows, config.chartLabel, config.chartValue);
      chart_type = config.chartType || data.chart_type;
    } else if (config.chartType) {
      chart_type = config.chartType;
    }

    // Özet — boş / "analiz edilemedi" ise istemci tarafı özet üret
    let summary = data.summary;
    if (!summary || /analiz edilemedi/i.test(summary)) {
      summary = _fallbackSummary(data, cols);
    }

    return { ...data, rows, chart_data, chart_type, summary, _maxRows: config.maxRows };
  }

  function _aggregateChart(rows, labelCol, valueCol) {
    if (!rows.length) return { labels: [], datasets: [] };
    const map = new Map();
    rows.forEach(r => {
      const k = (r[labelCol] ?? '—').toString();
      const v = Number(r[valueCol]) || 0;
      map.set(k, (map.get(k) || 0) + v);
    });
    const entries = [...map.entries()].sort((a,b) => b[1]-a[1]).slice(0, 15);
    return {
      labels  : entries.map(e => e[0]),
      datasets: [{ label: valueCol, data: entries.map(e => Math.round(e[1]*100)/100) }],
    };
  }

  function _fallbackSummary(data, cols) {
    const rows = data.rows || [];
    if (!rows.length) return 'Bu sorgu için gösterilecek veri bulunamadı.';
    const keys = cols && cols.length ? cols : Object.keys(rows[0]);
    const numCols = keys.filter(k =>
      rows.every(r => r[k] === null || r[k] === '' || !isNaN(Number(r[k]))));
    let s = `${data.question ? `"${data.question}" sorgusu için ` : ''}toplam ${rows.length} kayıt bulundu.`;
    if (numCols.length) {
      const k = numCols[0];
      const sum = rows.reduce((a,r) => a + (Number(r[k]) || 0), 0);
      s += ` ${k} toplamı: ${sum.toLocaleString('tr-TR')}.`;
      if (numCols[1]) {
        const k2 = numCols[1];
        const avg = rows.reduce((a,r) => a + (Number(r[k2]) || 0), 0) / rows.length;
        s += ` ${k2} ortalaması: ${(Math.round(avg*100)/100).toLocaleString('tr-TR')}.`;
      }
    }
    return s;
  }

  /* ── Rapor render ────────────────────────────────────────────────────── */
  async function _renderReport(data, fmt, config) {
    const tplFn = {
      executive : _tplExecutive,
      analytical: _tplAnalytical,
      table     : _tplTable,
      trend     : _tplTrend,
    }[fmt];
    if (!tplFn) return;

    // ÖNEMLİ: pencereyi kullanıcı hareketi içinde HEMEN aç (popup engellemesini önler)
    const win = window.open('', '_blank', 'width=1200,height=800,scrollbars=yes');
    if (!win) {
      alert('Rapor penceresi açılamadı. Lütfen tarayıcının popup engelleyicisini bu site için kapatın.');
      return;
    }
    win.document.write(`<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
      <title>Rapor hazırlanıyor…</title></head>
      <body style="font-family:system-ui,sans-serif;display:flex;align-items:center;
                   justify-content:center;height:100vh;margin:0;color:#6b7280;background:#f3f4f6">
        <div style="text-align:center">
          <div style="font-size:28px;margin-bottom:10px">⏳</div>
          <div style="font-size:14px">Rapor hazırlanıyor…</div>
        </div>
      </body></html>`);

    // Konfigürasyonu uygula (kolon/ grafik/ özet)
    const prepared = _applyConfig(data, config);

    // Gemini HTML bölümünü çek (opsiyonel — başarısızsa atlanır)
    let geminiHtml = '';
    try {
      const res = await fetch('/api/v1/enhance/report', {
        method : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body   : JSON.stringify({
          question   : prepared.question   || '',
          rows       : (prepared.rows || []).slice(0, 50),
          summary    : prepared.summary    || '',
          kpis       : prepared.kpis       || [],
          highlights : prepared.highlights || [],
        }),
      });
      if (res.ok) {
        const r = await res.json();
        geminiHtml = r.html || '';
      }
    } catch {}

    const html = tplFn({ ...prepared, _geminiHtml: geminiHtml });
    try {
      win.document.open();
      win.document.write(html);
      win.document.close();
    } catch (e) {
      console.error('Rapor yazılamadı:', e);
    }
  }

  /* ── Ortak yardımcılar ───────────────────────────────────────────────── */
  function _esc(s) {
    return String(s ?? '').replace(/[&<>"]/g, c =>
      ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));
  }

  function _baseStyle() {
    return `
      <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{font-family:'Inter',system-ui,sans-serif;font-size:14px;color:#111827;background:#f3f4f6;-webkit-print-color-adjust:exact;print-color-adjust:exact}
        .rpt-page{max-width:1140px;margin:0 auto;padding:24px 20px}
        .rpt-header{background:#fff;border-radius:12px;padding:22px 26px;margin-bottom:16px;border:1px solid #e5e7eb;box-shadow:0 1px 4px rgba(0,0,0,.05)}
        .rpt-logo{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;background:#1a56db;border-radius:8px;color:#fff;font-weight:800;font-size:14px;margin-right:10px;vertical-align:middle}
        .rpt-title{font-size:20px;font-weight:700;color:#111827;margin-top:10px;letter-spacing:-.01em}
        .rpt-sub{font-size:13px;color:#6b7280;margin-top:4px}
        .rpt-meta{font-size:11px;color:#9ca3af;margin-top:6px}
        .card{background:#fff;border-radius:12px;border:1px solid #e5e7eb;box-shadow:0 1px 4px rgba(0,0,0,.04);overflow:hidden}
        .card-header{padding:14px 18px;border-bottom:1px solid #f3f4f6;font-size:13px;font-weight:700;color:#374151;display:flex;align-items:center;gap:8px}
        .card-body{padding:18px}
        .kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:16px}
        .kpi{background:#fff;border-radius:10px;border:1px solid #e5e7eb;padding:16px 18px;position:relative;overflow:hidden}
        .kpi::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
        .kpi.blue::before{background:#1a56db}
        .kpi.green::before{background:#10b981}
        .kpi.amber::before{background:#f59e0b}
        .kpi.red::before{background:#ef4444}
        .kpi-label{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:#9ca3af}
        .kpi-value{font-size:28px;font-weight:700;color:#111827;margin:6px 0 2px;letter-spacing:-.02em}
        .kpi-desc{font-size:11px;color:#6b7280}
        table{width:100%;border-collapse:collapse;font-size:12px}
        th{padding:8px 12px;text-align:left;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#9ca3af;background:#f9fafb;border-bottom:1px solid #e5e7eb}
        td{padding:9px 12px;border-bottom:1px solid #f3f4f6;color:#374151;vertical-align:middle}
        tr:last-child td{border-bottom:none}
        tr:hover td{background:#f9fafb}
        .tfoot td{background:#eff6ff;font-weight:700;color:#1d4ed8;border-top:2px solid #bfdbfe}
        .badge{display:inline-flex;align-items:center;padding:2px 8px;border-radius:999px;font-size:10px;font-weight:700}
        .badge-blue{background:#dbeafe;color:#1d4ed8}
        .badge-green{background:#d1fae5;color:#065f46}
        .badge-amber{background:#fef3c7;color:#92400e}
        .badge-red{background:#fee2e2;color:#991b1b}
        .summary-box{background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:16px 18px;font-size:13px;color:#1e40af;line-height:1.7}
        .print-btn{position:fixed;bottom:24px;right:24px;background:#1a56db;color:#fff;border:none;border-radius:10px;padding:10px 20px;font-size:13px;font-weight:600;cursor:pointer;box-shadow:0 4px 14px rgba(26,86,219,.3);font-family:inherit}
        .print-btn:hover{background:#1543a5}
        @media print{.print-btn{display:none}body{background:#fff}.rpt-page{max-width:100%;padding:16px}}
        canvas{max-height:260px}
      </style>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"><\/script>
    `;
  }

  function _headerHtml(data, subtitle) {
    const now = new Date().toLocaleDateString('tr-TR', {day:'2-digit',month:'long',year:'numeric',hour:'2-digit',minute:'2-digit'});
    return `
      <div class="rpt-header">
        <div style="display:flex;align-items:flex-start;justify-content:space-between">
          <div>
            <div><span class="rpt-logo">AI</span>
              <span style="font-size:13px;font-weight:600;color:#6b7280;vertical-align:middle">SAP AI Copilot</span>
            </div>
            <div class="rpt-title">${data.question || 'SAP Veri Raporu'}</div>
            <div class="rpt-sub">${subtitle}</div>
            <div class="rpt-meta">Oluşturma: ${now} &nbsp;·&nbsp; ${data.count ?? (data.rows||[]).length} kayıt &nbsp;·&nbsp; ${(data.tables_used||[]).join(', ')}</div>
          </div>
          <div style="text-align:right">
            <div style="font-size:11px;color:#9ca3af;margin-bottom:4px">Kaynak Tablo</div>
            ${(data.tables_used||['—']).map(t => `<span class="badge badge-blue" style="margin-left:4px">${t}</span>`).join('')}
          </div>
        </div>
      </div>
    `;
  }

  function _kpiCards(rows) {
    if (!rows.length) return '';
    const numericCols = Object.keys(rows[0]).filter(k => {
      const v = rows[0][k];
      return v !== null && v !== '' && !isNaN(Number(v));
    }).slice(0, 4);
    if (!numericCols.length) return '';

    const colors = ['blue','green','amber','red'];
    const icons  = ['📦','✅','⚡','📊'];

    return `<div class="kpi-grid">` + numericCols.map((col, i) => {
      const vals = rows.map(r => Number(r[col]) || 0);
      const sum  = vals.reduce((a,b) => a+b, 0);
      const avg  = sum / vals.length;
      const fmt  = (n) => n >= 1000 ? (n/1000).toFixed(1)+'K' : n.toFixed(Number.isInteger(n) ? 0 : 1);
      return `
        <div class="kpi ${colors[i]}">
          <div class="kpi-label">${icons[i]} ${col}</div>
          <div class="kpi-value">${fmt(sum)}</div>
          <div class="kpi-desc">Ort: ${fmt(avg)} &nbsp;·&nbsp; ${vals.length} kayıt</div>
        </div>`;
    }).join('') + `</div>`;
  }

  function _tableHtml(rows, maxRows = 9999, showTotals = false) {
    if (!rows.length) return '<p style="color:#9ca3af;padding:16px">Veri bulunamadı.</p>';
    const displayRows = rows.slice(0, maxRows);
    const keys = Object.keys(rows[0]).filter(k => !['id','fetched_at'].includes(k));
    if (!keys.length) return '<p style="color:#9ca3af;padding:16px">Gösterilecek kolon seçilmedi.</p>';
    const numericCols = keys.filter(k => displayRows.every(r => r[k] === null || r[k] === '' || !isNaN(Number(r[k]))));

    let totalsRow = '';
    if (showTotals && numericCols.length) {
      totalsRow = `<tr class="tfoot">` + keys.map(k => {
        if (numericCols.includes(k)) {
          const sum = displayRows.reduce((a,r) => a + (Number(r[k]) || 0), 0);
          return `<td>${sum >= 1000 ? (sum/1000).toFixed(1)+'K' : sum.toFixed(1)}</td>`;
        }
        return k === keys[0] ? `<td style="color:#1d4ed8;font-weight:700">TOPLAM</td>` : `<td></td>`;
      }).join('') + `</tr>`;
    }

    return `
      <div style="overflow-x:auto">
        <table>
          <thead><tr>${keys.map(k => `<th>${_esc(k)}</th>`).join('')}</tr></thead>
          <tbody>
            ${displayRows.map(r => `<tr>${keys.map(k => `<td>${_esc(r[k] ?? '—')}</td>`).join('')}</tr>`).join('')}
            ${totalsRow}
          </tbody>
        </table>
      </div>
      ${rows.length > maxRows ? `<div style="font-size:11px;color:#9ca3af;padding:10px 12px">+ ${rows.length - maxRows} kayıt daha gösterilmiyor</div>` : ''}
    `;
  }

  function _chartScript(canvasId, type, chartData, options = {}) {
    if (!chartData?.labels?.length) return '';
    const dsJson = JSON.stringify((chartData.datasets||[]).map((ds, i) => ({
      label: ds.label || '',
      data : ds.data  || [],
      backgroundColor: type === 'pie'
        ? COLORS.map(c => c + 'cc')
        : COLORS[i % COLORS.length] + 'cc',
      borderColor: COLORS[i % COLORS.length],
      borderWidth: 2,
      borderRadius: type === 'bar' ? 4 : 0,
      tension: type === 'line' ? 0.4 : 0,
      fill: type === 'line' ? true : false,
    })));

    const scalesJson = type !== 'pie' ? `scales:{y:{beginAtZero:true,grid:{color:'rgba(0,0,0,.04)'}},x:{grid:{display:false}}}` : '';

    return `
      <script>
        new Chart(document.getElementById('${canvasId}'), {
          type: '${type}',
          data: { labels: ${JSON.stringify(chartData.labels)}, datasets: ${dsJson} },
          options: {
            responsive:true, maintainAspectRatio:false,
            plugins:{ legend:{ position:'${type==='pie'?'right':'top'}' } },
            ${scalesJson}
          }
        });
      <\/script>
    `;
  }

  function _resolveChartType(raw) {
    const t = (raw||'BAR').toUpperCase();
    if (t === 'LINE') return 'line';
    if (t === 'PIE')  return 'pie';
    return 'bar';
  }

  /* ══════════════════════════════════════════════════════════════════════
     FORMAT 1 — YÖNETİCİ PANOSU
     ══════════════════════════════════════════════════════════════════════ */
  function _tplExecutive(data) {
    const rows      = data.rows || [];
    const chartType = _resolveChartType(data.chart_type);
    const cid       = 'exec-chart';

    return `<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
      <title>Yönetici Panosu</title>${_baseStyle()}</head><body>
      <div class="rpt-page">
        ${_headerHtml(data, 'Yönetici Panosu')}

        <!-- KPI Satırı -->
        ${_kpiCards(rows)}

        <!-- Grafik + Özet -->
        <div style="display:grid;grid-template-columns:1fr 340px;gap:14px;margin-bottom:16px">
          <div class="card">
            <div class="card-header">
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
              Veri Görselleştirme
            </div>
            <div class="card-body" style="height:280px;position:relative">
              <canvas id="${cid}"></canvas>
            </div>
          </div>

          <div style="display:flex;flex-direction:column;gap:14px">
            <div class="card" style="flex:1">
              <div class="card-header">
                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
                AI Analizi
              </div>
              <div class="card-body">
                <div class="summary-box">${data.summary || 'Analiz mevcut değil.'}</div>
              </div>
            </div>
            <div class="card">
              <div class="card-header">📋 Rapor Özeti</div>
              <div class="card-body" style="font-size:12px;color:#6b7280;display:flex;flex-direction:column;gap:8px">
                <div style="display:flex;justify-content:space-between">
                  <span>Toplam Kayıt</span><strong style="color:#111827">${data.count ?? rows.length}</strong>
                </div>
                <div style="display:flex;justify-content:space-between">
                  <span>Tablo</span><strong style="color:#111827">${(data.tables_used||[]).join(', ')}</strong>
                </div>
                <div style="display:flex;justify-content:space-between">
                  <span>Grafik Tipi</span><strong style="color:#111827">${data.chart_type||'—'}</strong>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Gemini Analizi -->
        ${data._geminiHtml ? `
        <div style="margin-bottom:16px">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;padding:0 4px">
            <span style="font-size:18px">✨</span>
            <span style="font-size:13px;font-weight:700;color:#374151">Gemini Analizi</span>
            <span style="background:linear-gradient(90deg,#4285f4,#34a853,#fbbc05,#ea4335);
                         -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                         font-size:11px;font-weight:700">Powered by Gemini</span>
          </div>
          ${data._geminiHtml}
        </div>` : ''}

        <!-- Üst kayıtlar -->
        <div class="card">
          <div class="card-header">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
            İlk ${data._maxRows ?? 10} Kayıt
          </div>
          <div>${_tableHtml(rows, data._maxRows ?? 10)}</div>
        </div>
      </div>

      <button class="print-btn" onclick="window.print()">🖨 Yazdır / PDF</button>
      ${_chartScript(cid, chartType, data.chart_data)}
    </body></html>`;
  }

  /* ══════════════════════════════════════════════════════════════════════
     FORMAT 2 — ANALİZ RAPORU
     ══════════════════════════════════════════════════════════════════════ */
  function _tplAnalytical(data) {
    const rows      = data.rows || [];
    const chartType = _resolveChartType(data.chart_type);
    const cid       = 'anal-chart';

    return `<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
      <title>Analiz Raporu</title>${_baseStyle()}</head><body>
      <div class="rpt-page">
        ${_headerHtml(data, 'Analiz Raporu')}

        <!-- Özet + Grafik yan yana -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px">
          <div class="card">
            <div class="card-header">
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/></svg>
              AI Analiz Özeti
            </div>
            <div class="card-body">
              <div class="summary-box" style="margin-bottom:14px">${data.summary || '—'}</div>
              ${_kpiCards(rows.slice(0,3))}
            </div>
          </div>

          <div class="card">
            <div class="card-header">
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
              Veri Dağılımı
            </div>
            <div class="card-body" style="height:240px;position:relative">
              <canvas id="${cid}"></canvas>
            </div>
          </div>
        </div>

        <!-- Detay tablo -->
        <div class="card">
          <div class="card-header">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/></svg>
            Detay Veri — ${rows.length} kayıt
          </div>
          ${_tableHtml(rows, data._maxRows ?? 25, true)}
        </div>
      </div>

      <button class="print-btn" onclick="window.print()">🖨 Yazdır / PDF</button>
      ${_chartScript(cid, chartType, data.chart_data)}
    </body></html>`;
  }

  /* ══════════════════════════════════════════════════════════════════════
     FORMAT 3 — VERİ TABLOSU
     ══════════════════════════════════════════════════════════════════════ */
  function _tplTable(data) {
    const rows = data.rows || [];
    const keys = rows.length ? Object.keys(rows[0]).filter(k => !['id','fetched_at'].includes(k)) : [];
    const numericCols = keys.filter(k => rows.every(r => r[k] === null || r[k] === '' || !isNaN(Number(r[k]))));

    // Kolon istatistikleri
    const stats = numericCols.slice(0,4).map(k => {
      const vals = rows.map(r => Number(r[k])||0).filter(v => v !== 0);
      const sum  = vals.reduce((a,b)=>a+b,0);
      const max  = vals.length ? Math.max(...vals) : 0;
      const min  = vals.length ? Math.min(...vals) : 0;
      const avg  = sum / (vals.length || 1);
      const fmt  = n => n >= 1000 ? (n/1000).toFixed(1)+'K' : n.toFixed(1);
      return `
        <div class="kpi blue">
          <div class="kpi-label">∑ ${k}</div>
          <div class="kpi-value" style="font-size:22px">${fmt(sum)}</div>
          <div class="kpi-desc">Min ${fmt(min)} · Ort ${fmt(avg)} · Max ${fmt(max)}</div>
        </div>`;
    }).join('');

    return `<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
      <title>Veri Tablosu</title>${_baseStyle()}
      <style>
        td{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .search-bar{display:flex;align-items:center;gap:10px;padding:12px 16px;background:#f9fafb;border-bottom:1px solid #e5e7eb}
        .search-bar input{padding:7px 12px;border:1px solid #e5e7eb;border-radius:8px;font-size:12px;font-family:inherit;outline:none;width:260px}
        .count-badge{background:#dbeafe;color:#1d4ed8;padding:4px 10px;border-radius:6px;font-size:12px;font-weight:700}
      </style>
      </head><body>
      <div class="rpt-page">
        ${_headerHtml(data, 'Veri Tablosu Raporu')}

        ${numericCols.length ? `<div class="kpi-grid" style="margin-bottom:16px">${stats}</div>` : ''}

        <div class="card">
          <div class="card-header">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
            Tam Veri Listesi
            <span class="count-badge" style="margin-left:auto">${rows.length} kayıt</span>
          </div>
          <div class="search-bar">
            <input type="text" placeholder="Tabloda ara..." id="tbl-search" oninput="filterTable(this.value)">
            <span style="font-size:12px;color:#9ca3af">Kolon sayısı: ${keys.length}</span>
          </div>
          <div id="tbl-wrap">${_tableHtml(rows, data._maxRows ?? 9999, true)}</div>
        </div>

        ${data.sql ? `
        <div class="card" style="margin-top:14px">
          <div class="card-header">⚙ SQL Sorgusu</div>
          <div class="card-body">
            <pre style="font-size:12px;background:#0f172a;color:#7dd3fc;padding:14px;border-radius:8px;overflow-x:auto;white-space:pre-wrap">${_esc(data.sql)}</pre>
          </div>
        </div>` : ''}
      </div>

      <button class="print-btn" onclick="window.print()">🖨 Yazdır / PDF</button>

      <script>
        function filterTable(q) {
          const rows = document.querySelectorAll('#tbl-wrap tbody tr');
          q = q.toLowerCase();
          rows.forEach(r => {
            r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
          });
        }
      <\/script>
    </body></html>`;
  }

  /* ══════════════════════════════════════════════════════════════════════
     FORMAT 4 — TREND RAPORU
     ══════════════════════════════════════════════════════════════════════ */
  function _tplTrend(data) {
    const rows      = data.rows || [];
    const chartType = _resolveChartType(data.chart_type);
    const cidMain   = 'trend-main';
    const cidSec    = 'trend-sec';

    // İkinci grafik için bar data
    const barData = data.chart_data?.labels?.length ? {
      labels  : data.chart_data.labels.slice(0, 8),
      datasets: [{
        label: 'Miktar',
        data : (data.chart_data.datasets?.[0]?.data || []).slice(0, 8),
      }]
    } : null;

    // Top N liste (ilk numeric kolona göre sırala)
    let topList = '';
    if (rows.length) {
      const keys = Object.keys(rows[0]).filter(k => !['id','fetched_at'].includes(k));
      const numKey = keys.find(k => rows.every(r => r[k]===null || !isNaN(Number(r[k]))));
      const labelKey = keys.find(k => k !== numKey && typeof rows[0][k] === 'string') || keys[0];

      if (numKey) {
        const sorted = [...rows].sort((a,b) => (Number(b[numKey])||0) - (Number(a[numKey])||0)).slice(0,7);
        const maxVal = Number(sorted[0]?.[numKey]) || 1;
        const colors = ['#1a56db','#3b82f6','#60a5fa','#93c5fd','#bfdbfe','#dbeafe','#eff6ff'];
        topList = `
          <div class="card">
            <div class="card-header">🏆 En Yüksek ${numKey}</div>
            <div class="card-body" style="display:flex;flex-direction:column;gap:10px">
              ${sorted.map((r,i) => {
                const v = Number(r[numKey])||0;
                const pct = (v/maxVal*100).toFixed(0);
                return `
                  <div>
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:12px">
                      <span style="font-weight:600;color:#374151">${i+1}. ${_esc(r[labelKey] ?? '—')}</span>
                      <span style="color:#1d4ed8;font-weight:700">${v >= 1000 ? (v/1000).toFixed(1)+'K' : v}</span>
                    </div>
                    <div style="height:8px;background:#f3f4f6;border-radius:999px;overflow:hidden">
                      <div style="height:100%;width:${pct}%;background:${colors[i]};border-radius:999px;transition:width .3s"></div>
                    </div>
                  </div>`;
              }).join('')}
            </div>
          </div>`;
      }
    }

    return `<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
      <title>Trend Raporu</title>${_baseStyle()}</head><body>
      <div class="rpt-page">
        ${_headerHtml(data, 'Trend & Dönem Analizi')}

        <!-- Özet -->
        <div class="card" style="margin-bottom:14px">
          <div class="card-header">📝 AI Yorumu</div>
          <div class="card-body">
            <div class="summary-box">${data.summary || '—'}</div>
          </div>
        </div>

        <!-- Ana trend grafiği (geniş) -->
        <div class="card" style="margin-bottom:14px">
          <div class="card-header">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
            Zaman Trendi
          </div>
          <div class="card-body" style="height:260px;position:relative">
            <canvas id="${cidMain}"></canvas>
          </div>
        </div>

        <!-- Bar + Top N -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px">
          ${barData ? `
          <div class="card">
            <div class="card-header">📊 Karşılaştırmalı</div>
            <div class="card-body" style="height:220px;position:relative">
              <canvas id="${cidSec}"></canvas>
            </div>
          </div>` : '<div></div>'}
          ${topList}
        </div>

        <!-- Detay tablo -->
        <div class="card">
          <div class="card-header">📋 İlk ${data._maxRows ?? 15} Kayıt</div>
          ${_tableHtml(rows, data._maxRows ?? 15)}
        </div>
      </div>

      <button class="print-btn" onclick="window.print()">🖨 Yazdır / PDF</button>
      ${_chartScript(cidMain, 'line', data.chart_data)}
      ${barData ? _chartScript(cidSec, 'bar', barData) : ''}
    </body></html>`;
  }

  /* ── Temizlik ─────────────────────────────────────────────────────────── */
  function _removeExisting(id) {
    document.getElementById(id)?.remove();
  }

  return { open };
})();

window.Reports = Reports;

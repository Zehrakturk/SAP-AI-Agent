/* static/logs.js — AI Logs Page */

const LogsPage = (() => {

  let _allLogs  = [];
  let _filtered = [];
  let _table    = null;
  let _statusFilter = 'all';
  let _modelFilter  = '';
  let _searchQuery  = '';

  // ── Render ───────────────────────────────────────────────────────────────────
  function render() {
    return `
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px" id="logs-summary">
      ${_summaryCard('Toplam Log',      '…', 'badge-blue')}
      ${_summaryCard('Başarılı',        '…', 'badge-green')}
      ${_summaryCard('Hata',            '…', 'badge-red')}
      ${_summaryCard('Ort. Token',      '…', 'badge-amber')}
    </div>

    <div class="card">
      <div class="filter-bar">
        <div class="search-input-wrap" style="width:260px">
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input class="input" placeholder="Soru, kullanıcı veya ID ara…" oninput="LogsPage.onSearch(this.value)">
        </div>
        <button class="filter-chip active" data-filter="all"     onclick="LogsPage.filterStatus('all',this)">Tümü</button>
        <button class="filter-chip"        data-filter="success" onclick="LogsPage.filterStatus('success',this)">Başarılı</button>
        <button class="filter-chip"        data-filter="error"   onclick="LogsPage.filterStatus('error',this)">Hata</button>
        <select class="select-input" style="width:180px;margin-left:auto" onchange="LogsPage.filterModel(this.value)">
          <option value="">Tüm Modeller</option>
          <option value="gpt-4o">GPT-4o</option>
          <option value="claude-sonnet-4-6">Claude Sonnet 4.6</option>
          <option value="claude-opus-4-6">Claude Opus 4.6</option>
          <option value="claude-haiku-4-5">Claude Haiku 4.5</option>
        </select>
        <button class="btn btn-ghost btn-sm" onclick="LogsPage.exportLogs()">
          <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          CSV İndir
        </button>
      </div>
      <div id="logs-table-host"></div>
    </div>`;
  }

  function _summaryCard(label, value, cls) {
    return `
      <div class="card" style="padding:14px 18px;display:flex;align-items:center;justify-content:space-between">
        <span style="font-size:12px;color:var(--gray-500);text-transform:uppercase;letter-spacing:0.6px">${label}</span>
        <span class="badge ${cls}" style="font-size:13px;font-weight:700" id="sumval-${label.replace(/\s/g,'').toLowerCase()}">${value}</span>
      </div>`;
  }

  // ── Init ─────────────────────────────────────────────────────────────────────
  async function init() {
    try {
      const [logsResp, summary] = await Promise.all([
        API.Logs.list({ limit: 200 }),
        API.Logs.summary(),
      ]);

      _allLogs  = logsResp.items || [];
      _filtered = [..._allLogs];

      // Summary kartları
      const cards = document.getElementById('logs-summary');
      if (cards && summary) {
        document.getElementById('sumval-toplamlog').textContent  = summary.total    ?? _allLogs.length;
        document.getElementById('sumval-başarılı').textContent   = summary.success  ?? '—';
        document.getElementById('sumval-hata').textContent       = summary.errors   ?? '—';
        document.getElementById('sumval-ort.token').textContent  = summary.avg_tokens ? Math.round(summary.avg_tokens).toLocaleString() : '—';
      }
    } catch (e) {
      console.error('[Logs] API hatası:', e);
      _allLogs  = [];
      _filtered = [];
    }

    _table = Tables.create('logs-table-host',
      [
        { key: 'id',        label: 'Log ID',  bold: true,     width: '130px' },
        { key: 'user_id',   label: 'Kullanıcı', width: '110px',
          render: v => `<code style="font-size:12px;background:var(--gray-100);padding:2px 6px;border-radius:4px">${v}</code>` },
        { key: 'question',  label: 'Soru', sortable: false,
          render: v => `<div style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${v}">${v}</div>` },
        { key: 'model',     label: 'Model',   render: _modelCell },
        { key: 'tokens',    label: 'Token',   render: _tokCell  },
        { key: 'latency',   label: 'Gecikme', render: _latCell  },
        { key: 'status',    label: 'Durum',   render: _statusCell },
        { key: 'timestamp', label: 'Zaman',   sortable: false   },
      ],
      _filtered,
      { pageSize: 15 }
    );
  }

  // ── Cell Renderers ───────────────────────────────────────────────────────────
  function _statusCell(v) {
    return v === 'success'
      ? `<span class="badge badge-green">✓ Başarılı</span>`
      : `<span class="badge badge-red">✗ Hata</span>`;
  }

  function _modelCell(v) {
    const short = (v || '').replace('claude-','').replace(/-4-[56]/g,'');
    const cls   = v?.includes('opus') ? 'badge-purple' : v?.includes('haiku') ? 'badge-amber' : 'badge-blue';
    return `<span class="badge ${cls}" style="font-size:10px">${short || v}</span>`;
  }

  function _tokCell(v) {
    const n   = Number(v) || 0;
    const pct = Math.min(100, Math.round(n / 4800 * 100));
    return `<div>${n.toLocaleString()}</div>
      <div class="token-bar-wrap" style="width:80px">
        <div class="token-bar" style="width:${pct}%"></div>
      </div>`;
  }

  function _latCell(v) {
    const n   = Number(v) || 0;
    const pct = Math.min(100, n / 2200 * 100).toFixed(0);
    const cls = n > 1800 ? 'red' : '';
    return `<div class="token-bar-wrap" style="width:80px;margin-bottom:4px">
        <div class="token-bar ${cls}" style="width:${pct}%"></div>
      </div>
      <div style="font-size:11px">${n}ms</div>`;
  }

  // ── Filters ──────────────────────────────────────────────────────────────────
  function _applyFilters() {
    _filtered = _allLogs.filter(l => {
      if (_statusFilter !== 'all' && l.status !== _statusFilter) return false;
      if (_modelFilter  && l.model !== _modelFilter)             return false;
      if (_searchQuery) {
        const q = _searchQuery.toLowerCase();
        if (!( (l.question||'').toLowerCase().includes(q) ||
               (l.user_id ||'').toLowerCase().includes(q) ||
               (l.id      ||'').toLowerCase().includes(q) )) return false;
      }
      return true;
    });
    if (_table) _table.updateRows(_filtered);
  }

  function filterStatus(s, el) {
    _statusFilter = s;
    document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
    el.classList.add('active');
    _applyFilters();
  }

  function filterModel(m)  { _modelFilter  = m; _applyFilters(); }
  function onSearch(q)     { _searchQuery  = q; _applyFilters(); }

  function exportLogs() {
    const header = 'ID,User,Question,Model,Tokens,Latency,Status,Timestamp\n';
    const rows   = _filtered.map(l =>
      `"${l.id}","${l.user_id}","${(l.question||'').replace(/"/g,'""')}","${l.model}",${l.tokens},${l.latency}ms,${l.status},"${l.timestamp}"`
    ).join('\n');
    const a      = document.createElement('a');
    a.href       = URL.createObjectURL(new Blob([header + rows], { type: 'text/csv' }));
    a.download   = `ai_logs_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
  }

  return { render, init, filterStatus, filterModel, onSearch, exportLogs };
})();

/* static/metrics.js — "Metrikler" (Semantic Layer) admin sayfası */

const MetricsPage = (() => {

  function _token() { return localStorage.getItem('sap_ai_token') || ''; }
  let _editing = null;   // düzenlenen metrik id'si (null = yeni)

  function render() {
    return `
      <div style="max-width:1000px;margin:0 auto">
        <div class="card" style="margin-bottom:16px">
          <div class="card-header"><h3 class="card-title" style="margin:0">📐 Metrik Sözlüğü (Semantic Layer)</h3></div>
          <div class="card-body">
            <p style="font-size:13px;color:var(--text-muted,#6b7280);margin-bottom:8px">
              İş terimlerinin SQL karşılığını burada tanımlarsınız. AI, sorularda bu terimleri
              gördüğünde tahmin yürütmek yerine tanımlı ifadeyi <b>aynen</b> kullanır → tutarlı, doğru KPI.
              <b>measure</b> = SELECT/aggregate, <b>filter</b> = WHERE koşulu, <b>dimension</b> = GROUP BY.
            </p>
            <button onclick="MetricsPage.newMetric()" class="btn btn-primary"
              style="background:#1a56db;color:#fff;border:none;border-radius:8px;padding:9px 16px;
                     font-size:13px;font-weight:600;cursor:pointer">+ Yeni Metrik</button>
          </div>
        </div>

        <div id="metric-form-wrap"></div>

        <div class="card">
          <div class="card-header"><h3 class="card-title" style="margin:0">Tanımlı Metrikler</h3></div>
          <div id="metric-list" style="padding:4px 0"><div style="padding:16px;color:#9ca3af">Yükleniyor…</div></div>
        </div>
      </div>
    `;
  }

  function init() { _load(); }

  async function _load() {
    const el = document.getElementById('metric-list');
    try {
      const res = await fetch('/api/v1/metrics/', { headers: { 'Authorization': `Bearer ${_token()}` } });
      if (res.status === 403) { el.innerHTML = '<div style="padding:16px;color:#dc2626">Bu sayfa yalnız admin içindir.</div>'; return; }
      const data = await res.json();
      _renderList(data.items || []);
    } catch { el.innerHTML = '<div style="padding:16px;color:#dc2626">Liste yüklenemedi.</div>'; }
  }

  function _esc(s) { return String(s ?? '').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  function _renderList(items) {
    const el = document.getElementById('metric-list');
    if (!items.length) { el.innerHTML = '<div style="padding:16px;color:#9ca3af">Henüz metrik yok. "Yeni Metrik" ile ekleyin.</div>'; return; }
    const typeColor = { measure: '#1a56db', filter: '#b45309', dimension: '#0e7490' };
    el.innerHTML = `
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead><tr style="text-align:left;color:#6b7280;font-size:11px;text-transform:uppercase">
          <th style="padding:8px 12px">Anahtar / Etiket</th>
          <th style="padding:8px 12px">Tip</th>
          <th style="padding:8px 12px">İfade</th>
          <th style="padding:8px 12px">Kapsam</th>
          <th style="padding:8px 12px">Durum</th>
          <th style="padding:8px 12px"></th>
        </tr></thead>
        <tbody>
        ${items.map(m => `
          <tr style="border-top:1px solid #f1f5f9">
            <td style="padding:8px 12px"><b>${_esc(m.metric_key)}</b><div style="color:#9ca3af;font-size:11px">${_esc(m.label||'')}</div></td>
            <td style="padding:8px 12px"><span style="font-size:11px;font-weight:600;color:${typeColor[m.metric_type]||'#374151'}">${_esc(m.metric_type)}</span></td>
            <td style="padding:8px 12px"><code style="font-size:11px;background:#f3f4f6;padding:2px 6px;border-radius:4px">${_esc(m.expression)}</code></td>
            <td style="padding:8px 12px;font-size:11px;color:#6b7280">${_esc(m.table_name||'—')}${m.company?` · ${_esc(m.company)}`:''}${m.integration_id?` · int#${m.integration_id}`:''}</td>
            <td style="padding:8px 12px">
              <span onclick="MetricsPage.toggle(${m.id}, ${m.is_active?0:1})" title="Tıkla: durumu değiştir"
                style="cursor:pointer;font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px;
                       background:${m.is_active?'#dcfce7':'#fef3c7'};color:${m.is_active?'#15803d':'#b45309'}">
                ${m.is_active ? '● Aktif' : '○ Taslak'}</span>
            </td>
            <td style="padding:8px 12px;white-space:nowrap">
              <button onclick='MetricsPage.edit(${JSON.stringify(m)})' style="border:none;background:none;cursor:pointer;color:#1a56db;font-size:12px">Düzenle</button>
              <button onclick="MetricsPage.remove(${m.id})" style="border:none;background:none;cursor:pointer;color:#dc2626;font-size:12px">Sil</button>
            </td>
          </tr>`).join('')}
        </tbody>
      </table>`;
  }

  function _formHtml(m) {
    m = m || {};
    const f = (id, label, val, ph='') => `
      <div style="margin-bottom:10px">
        <label style="display:block;font-size:11px;font-weight:600;color:#4b5563;margin-bottom:3px">${label}</label>
        <input id="mf-${id}" value="${_esc(val||'')}" placeholder="${ph}"
          style="width:100%;padding:8px 10px;border:1px solid #e5e7eb;border-radius:7px;font-size:13px;font-family:inherit;box-sizing:border-box"></div>`;
    return `
      <div class="card" style="margin-bottom:16px;border:2px solid #1a56db">
        <div class="card-header"><h3 class="card-title" style="margin:0">${m.id?'Metrik Düzenle':'Yeni Metrik'}</h3></div>
        <div class="card-body">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            ${f('metric_key','Anahtar (zorunlu)', m.metric_key, 'gecikme')}
            ${f('label','Etiket', m.label, 'Gecikmeli Sevkiyat')}
          </div>
          <div style="margin-bottom:10px">
            <label style="display:block;font-size:11px;font-weight:600;color:#4b5563;margin-bottom:3px">Tip</label>
            <select id="mf-metric_type" style="width:100%;padding:8px 10px;border:1px solid #e5e7eb;border-radius:7px;font-size:13px">
              <option value="measure" ${m.metric_type==='measure'?'selected':''}>measure (SELECT/aggregate)</option>
              <option value="filter" ${m.metric_type==='filter'?'selected':''}>filter (WHERE koşulu)</option>
              <option value="dimension" ${m.metric_type==='dimension'?'selected':''}>dimension (GROUP BY)</option>
            </select>
          </div>
          ${f('expression','SQL İfadesi (zorunlu)', m.expression, "COUNT(DISTINCT TKNUM)")}
          ${f('description','Açıklama', m.description)}
          ${f('synonyms','Eş anlamlılar (virgülle)', m.synonyms, 'geciken,gecikmeli,geç')}
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">
            ${f('table_name','Tablo', m.table_name, 'shipments')}
            ${f('company','Firma (boş=global)', m.company, 'Beycelik')}
            ${f('integration_id','Entegrasyon id (boş=global)', m.integration_id, '1')}
          </div>
          <label style="display:flex;align-items:center;gap:6px;font-size:13px;margin:8px 0">
            <input type="checkbox" id="mf-is_active" ${m.id===undefined||m.is_active?'checked':''}> Aktif (işaretsiz=taslak, prompt'a girmez)
          </label>
          <div style="display:flex;gap:8px;margin-top:8px">
            <button onclick="MetricsPage.save()" style="background:#1a56db;color:#fff;border:none;border-radius:7px;padding:9px 18px;font-size:13px;font-weight:600;cursor:pointer">Kaydet</button>
            <button onclick="MetricsPage.cancel()" style="background:#fff;color:#374151;border:1px solid #e5e7eb;border-radius:7px;padding:9px 18px;font-size:13px;cursor:pointer">İptal</button>
          </div>
        </div>
      </div>`;
  }

  function newMetric() { _editing = null; document.getElementById('metric-form-wrap').innerHTML = _formHtml({}); }
  function edit(m)     { _editing = m.id; document.getElementById('metric-form-wrap').innerHTML = _formHtml(m);
                         document.getElementById('metric-form-wrap').scrollIntoView({ behavior:'smooth' }); }
  function cancel()    { _editing = null; document.getElementById('metric-form-wrap').innerHTML = ''; }

  function _val(id) { const e = document.getElementById('mf-'+id); return e ? e.value.trim() : ''; }

  async function save() {
    const body = {
      metric_key: _val('metric_key'), label: _val('label'),
      metric_type: document.getElementById('mf-metric_type').value,
      expression: _val('expression'), description: _val('description'),
      synonyms: _val('synonyms'), table_name: _val('table_name') || null,
      company: _val('company') || null,
      integration_id: _val('integration_id') ? parseInt(_val('integration_id')) : null,
      is_active: document.getElementById('mf-is_active').checked,
    };
    if (!body.metric_key || !body.expression) { alert('Anahtar ve SQL ifadesi zorunlu.'); return; }
    const url = _editing ? `/api/v1/metrics/${_editing}` : '/api/v1/metrics/';
    const method = _editing ? 'PUT' : 'POST';
    const res = await fetch(url, { method, headers: { 'Content-Type':'application/json', 'Authorization':`Bearer ${_token()}` }, body: JSON.stringify(body) });
    if (!res.ok) { const e = await res.json().catch(()=>({})); alert(e.error || 'Kaydedilemedi'); return; }
    cancel(); _load();
  }

  async function toggle(id, active) {
    await fetch(`/api/v1/metrics/${id}`, { method:'PUT', headers:{ 'Content-Type':'application/json', 'Authorization':`Bearer ${_token()}` }, body: JSON.stringify({ is_active: !!active }) });
    _load();
  }

  async function remove(id) {
    if (!confirm('Bu metrik silinsin mi?')) return;
    await fetch(`/api/v1/metrics/${id}`, { method:'DELETE', headers:{ 'Authorization':`Bearer ${_token()}` } });
    _load();
  }

  return { render, init, newMetric, edit, cancel, save, toggle, remove };
})();

window.MetricsPage = MetricsPage;

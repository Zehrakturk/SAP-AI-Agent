/* static/integrations.js — Integrations Management Page */

const IntegrationsPage = (() => {
  let _list         = [];
  let _selectedId   = null;
  let _schemaText   = '';

  // ── Render ───────────────────────────────────────────────────────────────────
  function render() {
    return `
<div class="page-content active" id="page-integrations">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px">
    <div>
      <h2 style="margin:0;font-size:20px;font-weight:700;color:var(--gray-900)">Entegrasyonlar</h2>
      <p style="margin:4px 0 0;color:var(--gray-500);font-size:13px">SAP bağlantıları ve Qdrant indexleme yönetimi</p>
    </div>
    <div style="display:flex;gap:10px">
      <button class="btn btn-ghost" id="btn-index-all">Tümünü İndeksle</button>
      <button class="btn btn-primary" id="btn-add-int">+ Yeni Entegrasyon</button>
    </div>
  </div>

  <div style="display:grid;grid-template-columns:340px 1fr;gap:20px;align-items:start">

    <!-- Sol: Liste -->
    <div class="card">
      <div class="card-header"><h3 class="card-title">Entegrasyon Listesi</h3></div>
      <div id="int-list" style="min-height:60px"></div>
    </div>

    <!-- Sağ: Detay paneli -->
    <div id="int-detail-panel">
      <div class="card" style="padding:40px;text-align:center;color:var(--gray-400)">
        <div style="font-size:32px;margin-bottom:8px">🔌</div>
        <div style="font-size:14px">Bir entegrasyon seçin</div>
      </div>
    </div>

  </div>
</div>

<!-- Yeni / Düzenle Modal -->
<div class="modal-overlay" id="int-modal-overlay" style="display:none">
  <div class="modal" style="width:480px">
    <div class="modal-header">
      <h3 class="modal-title" id="int-modal-title">Yeni Entegrasyon</h3>
      <button class="btn btn-ghost" id="btn-close-int-modal" style="padding:4px 8px">✕</button>
    </div>
    <div class="modal-body" style="display:flex;flex-direction:column;gap:14px">
      <input type="hidden" id="int-edit-id">
      <div id="int-template-row">
        <label class="form-label">Hazır Şablon</label>
        <select id="int-template" class="input" style="width:100%">
          <option value="">— Şablon Seç (opsiyonel) —</option>
        </select>
        <div id="int-template-desc" style="font-size:11px;color:var(--gray-400);margin-top:4px"></div>
      </div>
      <div><label class="form-label">Ad <span style="color:red">*</span></label>
        <input id="int-name" class="input" style="width:100%" placeholder="Sevkiyat Servisi"></div>
      <div><label class="form-label">Açıklama</label>
        <input id="int-desc" class="input" style="width:100%" placeholder="Kısa açıklama"></div>
      <div><label class="form-label">WSDL URL</label>
        <input id="int-wsdl" class="input" style="width:100%" placeholder="http://..."></div>
      <div><label class="form-label">Servis Metodu</label>
        <input id="int-method" class="input" style="width:100%" placeholder="ZWHSD_FG001_009_WS"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div><label class="form-label">Kullanıcı Adı</label>
          <input id="int-user" class="input" style="width:100%"></div>
        <div><label class="form-label">Şifre</label>
          <input id="int-pass" class="input" type="password" style="width:100%"></div>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" id="btn-cancel-int-modal">İptal</button>
      <button class="btn btn-primary" id="btn-save-int">Kaydet</button>
    </div>
  </div>
</div>`;
  }

  // ── Init ─────────────────────────────────────────────────────────────────────
  async function init() {
    await _loadList();
    _bindGlobal();
  }

  // ── Load List ─────────────────────────────────────────────────────────────────
  async function _loadList() {
    try {
      const data = await _apiFetch('/api/v1/integrations/');
      _list = Array.isArray(data) ? data : [];
    } catch { _list = []; }
    _renderList();
  }

  function _renderList() {
    const container = document.getElementById('int-list');
    if (!container) return;

    if (_list.length === 0) {
      container.innerHTML = `<div style="padding:20px;text-align:center;color:var(--gray-400);font-size:13px">Henüz entegrasyon yok</div>`;
      return;
    }

    container.innerHTML = _list.map(item => {
      const active  = item.is_active;
      const vectors = item.vector_count || 0;
      const isSelected = _selectedId === item.id;
      return `
        <div class="int-item ${isSelected ? 'int-item--active' : ''}"
             data-id="${item.id}"
             style="padding:14px 16px;cursor:pointer;border-bottom:1px solid var(--gray-100);
                    background:${isSelected ? 'var(--blue-50)' : 'white'};
                    transition:background 0.15s">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
            <span style="font-size:14px;font-weight:600;color:var(--gray-800)">${item.name}</span>
            <span class="badge ${active ? 'badge-green' : 'badge-gray'}" style="font-size:11px">
              ${active ? 'Aktif' : 'Pasif'}
            </span>
          </div>
          <div style="font-size:12px;color:var(--gray-400);display:flex;gap:12px">
            <span>${item.service_method || '—'}</span>
            <span style="color:${vectors > 0 ? 'var(--blue-600)' : 'var(--gray-300)'}">
              ${vectors > 0 ? `✓ ${vectors} vektör` : '○ İndekslenmedi'}
            </span>
          </div>
        </div>`;
    }).join('');

    container.querySelectorAll('.int-item').forEach(el => {
      el.addEventListener('click', () => _selectIntegration(parseInt(el.dataset.id)));
    });
  }

  // ── Select Integration ───────────────────────────────────────────────────────
  async function _selectIntegration(id) {
    _selectedId = id;
    _renderList();

    const panel = document.getElementById('int-detail-panel');
    panel.innerHTML = `<div class="card" style="padding:30px;text-align:center;color:var(--gray-400)">
      <div style="font-size:13px">Yükleniyor...</div></div>`;

    try {
      const detail = await _apiFetch(`/api/v1/integrations/${id}`);
      _renderDetail(detail);
    } catch (e) {
      panel.innerHTML = `<div class="card" style="padding:20px;color:var(--red-600)">Yüklenemedi: ${e.message}</div>`;
    }
  }

  function _renderDetail(d) {
    const schema = (d.schemas || [])[0] || {};
    _schemaText  = schema.schema_text || '';

    const vectors = d.vector_count || 0;
    const panel   = document.getElementById('int-detail-panel');

    panel.innerHTML = `
      <div class="card">
        <div class="card-header" style="display:flex;align-items:center;justify-content:space-between">
          <h3 class="card-title" style="margin:0">${d.name}</h3>
          <div style="display:flex;gap:8px">
            <button class="btn btn-ghost" id="btn-edit-int" data-id="${d.id}" style="font-size:12px">Düzenle</button>
            <button class="btn ${d.is_active ? 'btn-ghost' : 'btn-primary'}" id="btn-toggle-active"
                    data-id="${d.id}" data-active="${d.is_active}" style="font-size:12px">
              ${d.is_active ? 'Pasife Al' : 'Aktife Al'}
            </button>
          </div>
        </div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:20px">

          <!-- Bağlantı Bilgileri -->
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:13px">
            <div><span style="color:var(--gray-400)">WSDL URL</span><br>
              <code style="font-size:11px;color:var(--blue-700);word-break:break-all">${d.wsdl_url || '—'}</code></div>
            <div><span style="color:var(--gray-400)">Metod</span><br>
              <code style="font-size:12px">${d.service_method || '—'}</code></div>
            <div><span style="color:var(--gray-400)">Kullanıcı</span><br>
              <code style="font-size:12px">${d.username || '—'}</code></div>
            <div><span style="color:var(--gray-400)">Qdrant Vektörler</span><br>
              <span style="font-weight:600;color:${vectors > 0 ? 'var(--blue-600)' : 'var(--gray-400)'}">
                ${vectors > 0 ? `${vectors} chunk` : 'İndekslenmedi'}
              </span></div>
          </div>

          <!-- Şema Düzenleyici -->
          <div>
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
              <label class="form-label" style="margin:0">Tablo Şeması (LLM'e verilecek açıklama)</label>
              <div style="display:flex;gap:8px">
                <input id="int-target-table" class="input" style="width:120px;font-size:12px"
                       placeholder="tablo adı" value="${schema.target_table || 'shipments'}">
                <button class="btn btn-ghost" id="btn-save-schema" data-id="${d.id}" style="font-size:12px">
                  Şemayı Kaydet
                </button>
              </div>
            </div>
            <textarea id="int-schema-text" class="input" rows="12"
                      style="width:100%;resize:vertical;font-size:12px;font-family:monospace"
                      placeholder="Kolon açıklamalarını buraya yazın...">${_schemaText}</textarea>
          </div>

          <!-- Qdrant İndeksleme -->
          <div style="display:flex;align-items:center;gap:12px;padding:14px;
                      background:var(--blue-50);border-radius:8px;border:1px solid var(--blue-100)">
            <div style="flex:1;font-size:13px">
              <strong>Qdrant İndeksleme</strong><br>
              <span style="color:var(--gray-500);font-size:12px">
                Şemayı kaydettikten sonra Qdrant'a indexleyin.
              </span>
            </div>
            <button class="btn btn-primary" id="btn-index-one" data-id="${d.id}" style="white-space:nowrap">
              Bu Entegrasyonu İndeksle
            </button>
          </div>

          <!-- On-Demand SAP Çekimi -->
          ${d.wsdl_url ? `
          <div style="padding:14px;background:#f0fdf4;border-radius:8px;border:1px solid #bbf7d0">
            <div style="font-size:13px;font-weight:600;color:#166534;margin-bottom:10px">
              🔄 Manuel SAP Çekimi
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr auto;gap:8px;align-items:end">
              <div>
                <label style="font-size:11px;color:#6b7280;display:block;margin-bottom:4px">Başlangıç Tarihi</label>
                <input type="date" id="fetch-start-${d.id}" class="input" style="font-size:12px">
              </div>
              <div>
                <label style="font-size:11px;color:#6b7280;display:block;margin-bottom:4px">Bitiş Tarihi</label>
                <input type="date" id="fetch-end-${d.id}" class="input" style="font-size:12px">
              </div>
              <button class="btn btn-primary" id="btn-fetch-${d.id}" style="font-size:12px;white-space:nowrap">
                SAP'tan Çek
              </button>
            </div>
            <div id="fetch-result-${d.id}" style="display:none;margin-top:10px;font-size:12px;
                 padding:8px 12px;border-radius:6px;background:#fff;border:1px solid #e5e7eb"></div>
          </div>` : ''}

          <!-- Parametreler -->
          ${_renderParams(d.params || [], d.id)}

        </div>
      </div>`;

    _bindDetailEvents(d);
  }

  function _renderParams(params, intId) {
    const rows = params.map(p => `
      <tr>
        <td><code style="font-size:12px">${p.param_name}</code></td>
        <td>${p.param_type || '—'}</td>
        <td>${p.is_required ? '<span class="badge badge-red">Zorunlu</span>' : '<span class="badge badge-gray">Opsiyonel</span>'}</td>
        <td style="font-size:12px;color:var(--gray-400)">${p.description || '—'}</td>
      </tr>`).join('');

    return `
      <div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
          <label class="form-label" style="margin:0">Parametreler</label>
          <button class="btn btn-ghost" id="btn-add-param" data-id="${intId}" style="font-size:12px">+ Parametre Ekle</button>
        </div>
        ${params.length ? `
          <table class="table" style="font-size:13px">
            <thead><tr><th>Ad</th><th>Tip</th><th>Zorunluluk</th><th>Açıklama</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>` : `<p style="font-size:13px;color:var(--gray-400)">Parametre eklenmemiş.</p>`}
      </div>`;
  }

  // ── Detail Event Binding ──────────────────────────────────────────────────────
  function _bindDetailEvents(d) {
    const panel = document.getElementById('int-detail-panel');

    panel.querySelector('#btn-edit-int').addEventListener('click', () => _openModal(d));

    panel.querySelector('#btn-toggle-active').addEventListener('click', async e => {
      const btn       = e.currentTarget;
      const newActive = d.is_active ? 0 : 1;
      try {
        await _apiFetch(`/api/v1/integrations/${d.id}`, 'PUT', { is_active: newActive });
        await _loadList();
        await _selectIntegration(d.id);
      } catch { alert('Güncellenemedi'); }
    });

    panel.querySelector('#btn-save-schema').addEventListener('click', async e => {
      const btn        = e.currentTarget;
      const schemaText = document.getElementById('int-schema-text').value.trim();
      const targetTbl  = document.getElementById('int-target-table').value.trim() || 'shipments';
      if (!schemaText) { alert('Şema metni boş olamaz.'); return; }
      btn.textContent = 'Kaydediliyor...'; btn.disabled = true;
      try {
        await _apiFetch(`/api/v1/integrations/${d.id}/schema`, 'POST', {
          target_table: targetTbl,
          schema_text : schemaText,
        });
        btn.textContent = '✓ Kaydedildi';
        setTimeout(() => { btn.textContent = 'Şemayı Kaydet'; btn.disabled = false; }, 1500);
      } catch {
        btn.textContent = 'Hata!'; btn.disabled = false;
      }
    });

    panel.querySelector('#btn-index-one').addEventListener('click', async e => {
      const btn = e.currentTarget;
      btn.textContent = 'İndeksleniyor...'; btn.disabled = true;
      try {
        const res = await _apiFetch(`/api/v1/integrations/${d.id}/index`, 'POST');
        btn.textContent = `✓ ${res.count || 0} chunk indexlendi`;
        await _loadList();
        await _selectIntegration(d.id);
      } catch (err) {
        btn.textContent = `Hata: ${err.message}`;
        btn.disabled = false;
      }
    });

    // Manuel SAP fetch butonu
    const fetchBtn = panel.querySelector(`#btn-fetch-${d.id}`);
    if (fetchBtn) {
      fetchBtn.addEventListener('click', async () => {
        const start     = document.getElementById(`fetch-start-${d.id}`)?.value;
        const end       = document.getElementById(`fetch-end-${d.id}`)?.value;
        const resultEl  = document.getElementById(`fetch-result-${d.id}`);
        if (!start || !end) { alert('Lütfen başlangıç ve bitiş tarihi seçin.'); return; }

        fetchBtn.textContent = 'Çekiliyor...'; fetchBtn.disabled = true;
        resultEl.style.display = 'none';

        try {
          const res = await _apiFetch(`/api/v1/integrations/${d.id}/fetch`, 'POST', {
            start_date: start, end_date: end, force: false,
          });
          const icon  = res.status === 'fetched' ? '✅' : res.status === 'cached' ? '📦' : '❌';
          const color = res.status === 'error'   ? '#dc2626' : '#166534';

          let html = `<div style="color:${color};font-weight:600">${icon} ${res.message || 'OK'}</div>`;

          // Hata varsa debug detayını göster — hangi parametreler gönderildi
          if (res.status === 'error') {
            const attempted = res.attempted_params || {};
            const extracted = res.extracted_params || {};
            const attemptedHtml = Object.keys(attempted).length
              ? Object.entries(attempted).map(([k,v]) =>
                  `<code style="background:#fff;padding:1px 5px;border-radius:3px;font-size:11px">${k}=${v}</code>`
                ).join(' ')
              : '<em style="color:#9ca3af">SAP\'a gönderilen parametre yok — integration_params kontrol edin</em>';
            html += `
              <details style="margin-top:8px">
                <summary style="cursor:pointer;font-size:11px;color:#9ca3af">🔍 Debug detayı</summary>
                <div style="margin-top:6px;padding:8px;background:#fafafa;border-radius:4px;font-size:11px;line-height:1.6">
                  <div><strong>Kullanıcı girdisi:</strong> start=${extracted.start_date || '∅'}, end=${extracted.end_date || '∅'}</div>
                  <div style="margin-top:4px"><strong>SAP'a giden:</strong> ${attemptedHtml}</div>
                  <div style="margin-top:6px;color:#6b7280">
                    💡 Provider-side hata: SAP servisi parametreyi anlamadı veya yetki sorunu var.
                    integration_params tablosunda doğru param adı (örn. <code>I_BEGDA</code> vs <code>ISTART_DATE</code>) tanımlı mı kontrol edin.
                  </div>
                </div>
              </details>`;
          }

          resultEl.innerHTML = html;
          resultEl.style.display = 'block';

          if (res.rows_written > 0) {
            setTimeout(() => _selectIntegration(d.id), 800);
          }
        } catch (e) {
          resultEl.innerHTML = `<span style="color:#dc2626">❌ ${e.message}</span>`;
          resultEl.style.display = 'block';
        }
        fetchBtn.textContent = 'SAP\'tan Çek'; fetchBtn.disabled = false;
      });
    }

    const addParamBtn = panel.querySelector('#btn-add-param');
    if (addParamBtn) {
      addParamBtn.addEventListener('click', async () => {
        const name = prompt('Parametre adı (örn: ISTART_DATE):');
        if (!name) return;
        const type = prompt('Tip (string / date / int):', 'string') || 'string';
        const req  = confirm('Zorunlu mu?');
        const desc = prompt('Açıklama:', '') || '';
        try {
          await _apiFetch(`/api/v1/integrations/${d.id}/params`, 'POST', {
            param_name: name, param_type: type, is_required: req, description: desc,
          });
          await _selectIntegration(d.id);
        } catch { alert('Eklenemedi'); }
      });
    }
  }

  // ── Modal ─────────────────────────────────────────────────────────────────────
  let _templates = [];

  async function _loadTemplatesOnce() {
    if (_templates.length) return _templates;
    try {
      _templates = await _apiFetch('/api/v1/integrations/templates');
    } catch { _templates = []; }
    return _templates;
  }

  function _applyTemplate(tpl) {
    if (!tpl) {
      document.getElementById('int-template-desc').textContent = '';
      return;
    }
    document.getElementById('int-template-desc').textContent = tpl.description || '';
    const f = tpl.fields || {};
    if (f.wsdl_url)       document.getElementById('int-wsdl').value   = f.wsdl_url;
    if (f.service_method) document.getElementById('int-method').value = f.service_method;
    if (f.username)       document.getElementById('int-user').value   = f.username;
    if (!document.getElementById('int-name').value) {
      document.getElementById('int-name').value = tpl.name;
    }
    if (!document.getElementById('int-desc').value) {
      document.getElementById('int-desc').value = tpl.description || '';
    }
    // Şablonun kalan kısmı (service_type, auth_type, extra_config, params) backend'e
    // ayrı endpoint'lerle gönderilir — burada UI dataset'e koyuyoruz.
    document.getElementById('int-modal-overlay').dataset.tplKey = tpl.key;
  }

  async function _openModal(existing = null) {
    document.getElementById('int-modal-title').textContent = existing ? 'Entegrasyonu Düzenle' : 'Yeni Entegrasyon';
    document.getElementById('int-edit-id').value   = existing?.id   || '';
    document.getElementById('int-name').value      = existing?.name           || '';
    document.getElementById('int-desc').value      = existing?.description    || '';
    document.getElementById('int-wsdl').value      = existing?.wsdl_url       || '';
    document.getElementById('int-method').value    = existing?.service_method || '';
    document.getElementById('int-user').value      = existing?.username       || '';
    document.getElementById('int-pass').value      = '';

    // Şablon dropdown'ı sadece YENİ kayıtta görünsün
    const tplRow = document.getElementById('int-template-row');
    if (existing) {
      tplRow.style.display = 'none';
    } else {
      tplRow.style.display = '';
      const sel = document.getElementById('int-template');
      const tpls = await _loadTemplatesOnce();
      sel.innerHTML = '<option value="">— Şablon Seç (opsiyonel) —</option>' +
        tpls.map(t => `<option value="${t.key}">${t.icon || ''} ${t.name}</option>`).join('');
      sel.value = '';
      document.getElementById('int-template-desc').textContent = '';
      document.getElementById('int-modal-overlay').dataset.tplKey = '';
    }

    document.getElementById('int-modal-overlay').style.display = 'flex';
  }

  function _closeModal() {
    document.getElementById('int-modal-overlay').style.display = 'none';
  }

  // ── Global Event Binding ─────────────────────────────────────────────────────
  function _bindGlobal() {
    document.getElementById('btn-add-int').addEventListener('click', () => _openModal());

    document.getElementById('btn-index-all').addEventListener('click', async () => {
      const btn = document.getElementById('btn-index-all');
      btn.textContent = 'İndeksleniyor...'; btn.disabled = true;
      try {
        const res = await _apiFetch('/api/v1/integrations/index-all', 'POST');
        const ok  = Object.values(res).filter(v => v.status === 'ok').length;
        btn.textContent = `✓ ${ok} entegrasyon indexlendi`;
        setTimeout(() => { btn.textContent = 'Tümünü İndeksle'; btn.disabled = false; }, 2000);
        await _loadList();
      } catch (err) {
        btn.textContent = `Hata: ${err.message}`; btn.disabled = false;
      }
    });

    document.getElementById('int-template').addEventListener('change', (e) => {
      const key = e.target.value;
      const tpl = _templates.find(t => t.key === key);
      _applyTemplate(tpl || null);
    });

    document.getElementById('btn-close-int-modal').addEventListener('click', _closeModal);
    document.getElementById('btn-cancel-int-modal').addEventListener('click', _closeModal);
    document.getElementById('int-modal-overlay').addEventListener('click', e => {
      if (e.target === document.getElementById('int-modal-overlay')) _closeModal();
    });

    document.getElementById('btn-save-int').addEventListener('click', async () => {
      const id     = document.getElementById('int-edit-id').value;
      const name   = document.getElementById('int-name').value.trim();
      if (!name) { alert('Ad zorunlu.'); return; }

      const payload = {
        name          : name,
        description   : document.getElementById('int-desc').value.trim(),
        wsdl_url      : document.getElementById('int-wsdl').value.trim(),
        service_method: document.getElementById('int-method').value.trim(),
        username      : document.getElementById('int-user').value.trim(),
      };
      const pass = document.getElementById('int-pass').value;
      if (pass) payload.password = pass;

      // Şablon seçildiyse type/auth/extra_config ve params payload'a katılır
      const tplKey = document.getElementById('int-modal-overlay').dataset.tplKey || '';
      const tpl    = tplKey ? _templates.find(t => t.key === tplKey) : null;
      if (tpl && !id) {
        const f = tpl.fields || {};
        if (f.service_type) payload.service_type = f.service_type;
        if (f.auth_type)    payload.auth_type    = f.auth_type;
        if (f.extra_config) payload.extra_config = f.extra_config;
      }

      try {
        let newId;
        if (id) {
          await _apiFetch(`/api/v1/integrations/${id}`, 'PUT', payload);
          newId = parseInt(id);
        } else {
          const res = await _apiFetch('/api/v1/integrations/', 'POST', payload);
          _selectedId = res.id;
          newId       = res.id;

          // Şablon parametrelerini ekle (yalnızca yeni kayıtta)
          if (tpl && tpl.params?.length) {
            for (const p of tpl.params) {
              try { await _apiFetch(`/api/v1/integrations/${newId}/params`, 'POST', p); }
              catch (e) { console.warn('Param eklenemedi:', p.param_name, e); }
            }
          }
        }
        _closeModal();
        await _loadList();
        if (_selectedId) await _selectIntegration(_selectedId);
      } catch (e) { alert(`Kaydedilemedi: ${e.message}`); }
    });
  }

  // ── Fetch Helper ──────────────────────────────────────────────────────────────
  async function _apiFetch(url, method = 'GET', body = null) {
    const token = localStorage.getItem('sap_ai_token') || '';
    const opts  = {
      method,
      headers: {
        'Content-Type' : 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${res.status}`);
    }
    return res.json();
  }

  return { render, init };
})();

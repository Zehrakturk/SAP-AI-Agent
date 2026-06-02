/* static/settings.js — Settings Page */

const SettingsPage = (() => {
  let _settings = {};
  let _models   = [];

  // ── Render ──────────────────────────────────────────────────────────────────
  function render() {
    return `
<div class="page-content active" id="page-settings">
  <div class="page-header" style="margin-bottom:24px">
    <h2 style="margin:0;font-size:20px;font-weight:700;color:var(--gray-900)">Sistem Ayarları</h2>
    <p style="margin:4px 0 0;color:var(--gray-500);font-size:13px">Model, güvenlik ve loglama yapılandırması</p>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;max-width:1100px">

    <!-- Model Ayarları -->
    <div class="card">
      <div class="card-header"><h3 class="card-title">Model Ayarları</h3></div>
      <div class="card-body" style="display:flex;flex-direction:column;gap:16px">
        <div>
          <label class="form-label">Model</label>
          <select id="s-model" class="select-input" style="width:100%"></select>
        </div>
        <div>
          <label class="form-label">Temperature &nbsp;<span id="s-temp-val" style="color:var(--blue-600);font-weight:600">0.2</span></label>
          <input id="s-temperature" type="range" min="0" max="1" step="0.05" style="width:100%;accent-color:var(--blue-600)">
        </div>
        <div>
          <label class="form-label">Max Tokens &nbsp;<span id="s-tokens-val" style="color:var(--blue-600);font-weight:600">1024</span></label>
          <input id="s-max-tokens" type="range" min="256" max="4096" step="128" style="width:100%;accent-color:var(--blue-600)">
        </div>
        <div>
          <label class="form-label">Günlük Token Bütçesi</label>
          <input id="s-budget" type="number" class="input" placeholder="50000" style="width:100%">
        </div>
        <div>
          <label class="form-label">Sistem Prompt'u</label>
          <textarea id="s-system-prompt" class="input" rows="4" style="width:100%;resize:vertical;font-size:12px"></textarea>
        </div>
        <button class="btn btn-primary" id="btn-save-model" style="align-self:flex-start">Kaydet</button>
      </div>
    </div>

    <!-- Güvenlik Toggleları -->
    <div class="card">
      <div class="card-header"><h3 class="card-title">Güvenlik</h3></div>
      <div class="card-body" style="display:flex;flex-direction:column;gap:14px" id="security-toggles"></div>
    </div>

    <!-- Loglama -->
    <div class="card">
      <div class="card-header"><h3 class="card-title">Loglama</h3></div>
      <div class="card-body" style="display:flex;flex-direction:column;gap:14px" id="logging-toggles">
        <div>
          <label class="form-label">Log Seviyesi</label>
          <select id="s-log-level" class="select-input" style="width:100%">
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
        </div>
        <div>
          <label class="form-label">Saklama Süresi (gün)</label>
          <input id="s-retention" type="number" class="input" style="width:100%">
        </div>
      </div>
    </div>

    <!-- Bağlantı Testi -->
    <div class="card">
      <div class="card-header"><h3 class="card-title">Bağlantı Testi</h3></div>
      <div class="card-body" style="display:flex;flex-direction:column;gap:16px">
        <p style="font-size:13px;color:var(--gray-500);margin:0">Backend servisinin yanıt verip vermediğini test edin.</p>
        <button class="btn btn-primary" id="btn-test-conn" style="align-self:flex-start">Bağlantıyı Test Et</button>
        <div id="conn-result" style="display:none"></div>
      </div>
    </div>

  </div>

  <!-- SAP Konnektörler -->
  <div class="card" style="max-width:1100px;margin-top:20px">
    <div class="card-header"><h3 class="card-title">SAP Konnektörleri</h3></div>
    <div class="card-body" style="padding:0">
      <table class="table" style="margin:0">
        <thead><tr>
          <th>Konnektör Adı</th><th>Tip</th><th>Durum</th><th>Son Kontrol</th>
        </tr></thead>
        <tbody id="connectors-tbody"></tbody>
      </table>
    </div>
  </div>
</div>`;
  }

  // ── Init ────────────────────────────────────────────────────────────────────
  async function init() {
    try {
      [_settings, _models] = await Promise.all([
        API.Settings.get(),
        API.Settings.models(),
      ]);
    } catch (e) {
      console.error('Settings yüklenemedi', e);
      return;
    }
    _fillModelDropdown();
    _fillModelFields();
    _fillSecurityToggles();
    _fillLoggingToggles();
    _loadConnectors();
    _bindEvents();
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────
  function _fillModelDropdown() {
    const sel = document.getElementById('s-model');
    sel.innerHTML = _models.map(m =>
      `<option value="${m.id}" ${m.id === _settings.model ? 'selected' : ''}>${m.name} (${m.tier})</option>`
    ).join('');
  }

  function _fillModelFields() {
    const temp = document.getElementById('s-temperature');
    temp.value = _settings.temperature ?? 0.2;
    document.getElementById('s-temp-val').textContent = temp.value;

    const tok = document.getElementById('s-max-tokens');
    tok.value = _settings.max_tokens ?? 1024;
    document.getElementById('s-tokens-val').textContent = tok.value;

    document.getElementById('s-budget').value        = _settings.daily_budget ?? 50000;
    document.getElementById('s-system-prompt').value = _settings.system_prompt ?? '';
  }

  const SECURITY_LABELS = {
    prompt_injection_protection: 'Prompt Enjeksiyon Koruması',
    rbac                       : 'Rol Tabanlı Erişim (RBAC)',
    sensitive_data_filtering   : 'Hassas Veri Filtreleme',
    rate_limiting              : 'Hız Sınırlama',
    audit_logging              : 'Denetim Loglama',
    session_expiry             : 'Oturum Zaman Aşımı',
  };

  function _fillSecurityToggles() {
    const container = document.getElementById('security-toggles');
    container.innerHTML = Object.entries(_settings.security || {}).map(([key, val]) => `
      <div style="display:flex;align-items:center;justify-content:space-between">
        <span style="font-size:13px;color:var(--gray-700)">${SECURITY_LABELS[key] || key}</span>
        <label class="toggle">
          <input type="checkbox" data-sec="${key}" ${val ? 'checked' : ''}>
          <span class="toggle-slider"></span>
        </label>
      </div>`).join('') +
      `<button class="btn btn-primary" id="btn-save-security" style="align-self:flex-start;margin-top:4px">Kaydet</button>`;
  }

  const LOG_LABELS = {
    log_questions    : 'Soruları Logla',
    log_responses    : 'Yanıtları Logla',
    log_tokens       : 'Token Kullanımını Logla',
    log_tool_calls   : 'Araç Çağrılarını Logla',
    log_auth_failures: 'Kimlik Doğrulama Hatalarını Logla',
  };

  function _fillLoggingToggles() {
    const container = document.getElementById('logging-toggles');
    const togglesHtml = Object.entries(_settings.logging || {})
      .filter(([k]) => k in LOG_LABELS)
      .map(([key, val]) => `
        <div style="display:flex;align-items:center;justify-content:space-between">
          <span style="font-size:13px;color:var(--gray-700)">${LOG_LABELS[key]}</span>
          <label class="toggle">
            <input type="checkbox" data-log="${key}" ${val ? 'checked' : ''}>
            <span class="toggle-slider"></span>
          </label>
        </div>`).join('');

    container.innerHTML = togglesHtml + container.innerHTML;

    document.getElementById('s-log-level').value = _settings.logging?.log_level    ?? 'INFO';
    document.getElementById('s-retention').value = _settings.logging?.retention_days ?? 90;

    container.innerHTML += `<button class="btn btn-primary" id="btn-save-logging" style="align-self:flex-start;margin-top:4px">Kaydet</button>`;
  }

  async function _loadConnectors() {
    let connectors = [];
    try { connectors = await API.Settings.connectors(); } catch {}
    const badge = s =>
      s === 'online'  ? `<span class="badge badge-green">● Online</span>` :
      s === 'warning' ? `<span class="badge badge-amber">● Uyarı</span>`  :
                        `<span class="badge badge-red">● Offline</span>`;
    document.getElementById('connectors-tbody').innerHTML = connectors.map(c => `
      <tr>
        <td><code style="font-size:12px">${c.name}</code></td>
        <td>${c.type}</td>
        <td>${badge(c.status)}</td>
        <td style="color:var(--gray-400);font-size:12px">${c.last_ping}</td>
      </tr>`).join('');
  }

  function _bindEvents() {
    document.getElementById('s-temperature').addEventListener('input', e =>
      document.getElementById('s-temp-val').textContent = e.target.value);

    document.getElementById('s-max-tokens').addEventListener('input', e =>
      document.getElementById('s-tokens-val').textContent = e.target.value);

    document.getElementById('btn-save-model').addEventListener('click', async () => {
      const btn = document.getElementById('btn-save-model');
      btn.textContent = 'Kaydediliyor...'; btn.disabled = true;
      try {
        await API.Settings.update({
          model        : document.getElementById('s-model').value,
          temperature  : parseFloat(document.getElementById('s-temperature').value),
          max_tokens   : parseInt(document.getElementById('s-max-tokens').value),
          daily_budget : parseInt(document.getElementById('s-budget').value),
          system_prompt: document.getElementById('s-system-prompt').value,
        });
        btn.textContent = '✓ Kaydedildi';
        setTimeout(() => { btn.textContent = 'Kaydet'; btn.disabled = false; }, 1500);
      } catch { btn.textContent = 'Hata!'; btn.disabled = false; }
    });

    document.getElementById('page-settings').addEventListener('click', async e => {
      if (e.target.id === 'btn-save-security') {
        const sec = {};
        document.querySelectorAll('[data-sec]').forEach(c => { sec[c.dataset.sec] = c.checked; });
        try {
          await API.Settings.update({ security: sec });
          e.target.textContent = '✓ Kaydedildi';
          setTimeout(() => { e.target.textContent = 'Kaydet'; }, 1500);
        } catch { e.target.textContent = 'Hata!'; }
      }

      if (e.target.id === 'btn-save-logging') {
        const log = {};
        document.querySelectorAll('[data-log]').forEach(c => { log[c.dataset.log] = c.checked; });
        log.log_level      = document.getElementById('s-log-level').value;
        log.retention_days = parseInt(document.getElementById('s-retention').value);
        try {
          await API.Settings.update({ logging: log });
          e.target.textContent = '✓ Kaydedildi';
          setTimeout(() => { e.target.textContent = 'Kaydet'; }, 1500);
        } catch { e.target.textContent = 'Hata!'; }
      }

      if (e.target.id === 'btn-test-conn') {
        const btn = document.getElementById('btn-test-conn');
        const res = document.getElementById('conn-result');
        btn.textContent = 'Test ediliyor...'; btn.disabled = true;
        res.style.display = 'none';
        try {
          const data = await API.Settings.testConnection();
          res.innerHTML = `<div class="badge badge-green" style="padding:8px 12px;font-size:13px">✓ ${data.message} (${data.latency})</div>`;
        } catch {
          res.innerHTML = `<div class="badge badge-red" style="padding:8px 12px;font-size:13px">✗ Bağlantı başarısız</div>`;
        }
        res.style.display = 'block';
        btn.textContent = 'Bağlantıyı Test Et'; btn.disabled = false;
      }
    });
  }

  return { render, init };
})();

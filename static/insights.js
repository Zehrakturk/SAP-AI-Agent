/* static/insights.js — Bugünün İçgörüleri paneli
 *
 * Dashboard sayfasının en üstüne render edilir.
 * Kart tıklama → chat sayfasına yönlendir + drill question önceden yazılı.
 */

const InsightsPanel = (() => {

  const SEVERITY_COLORS = {
    critical: { bg: '#fef2f2', border: '#fca5a5', text: '#991b1b' },
    warning : { bg: '#fefce8', border: '#fde68a', text: '#92400e' },
    info    : { bg: '#eff6ff', border: '#bfdbfe', text: '#1e40af' },
  };

  const COLOR_MAP = {
    red:    SEVERITY_COLORS.critical,
    amber:  SEVERITY_COLORS.warning,
    green:  { bg: '#f0fdf4', border: '#bbf7d0', text: '#166534' },
    blue:   SEVERITY_COLORS.info,
  };

  /* ── Public: panel HTML oluştur ────────────────────────────────────── */
  function render() {
    return `
      <div id="insights-panel" style="margin-bottom:24px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
          <div style="display:flex;align-items:center;gap:8px">
            <span style="font-size:20px">✨</span>
            <h3 style="margin:0;font-size:16px;font-weight:700;color:#111827">Bugünün İçgörüleri</h3>
            <span id="insights-count" style="background:#dbeafe;color:#1d4ed8;font-size:11px;
                  font-weight:700;padding:2px 8px;border-radius:999px"></span>
          </div>
          <div style="display:flex;gap:8px">
            <button id="insights-refresh" onclick="InsightsPanel.refresh()"
              style="background:#fff;border:1px solid #e5e7eb;border-radius:6px;
                     padding:5px 10px;font-size:12px;cursor:pointer;color:#6b7280">
              ↻ Yenile
            </button>
            <button id="insights-run" onclick="InsightsPanel.runDetectors()"
              style="background:#1a56db;border:none;border-radius:6px;
                     padding:5px 12px;font-size:12px;cursor:pointer;color:#fff;font-weight:600">
              🔄 Yeni İçgörü Üret
            </button>
          </div>
        </div>
        <div id="insights-cards" style="display:grid;
             grid-template-columns:repeat(auto-fill, minmax(260px, 1fr));gap:12px"></div>
      </div>
    `;
  }

  /* ── Public: init — load + render ──────────────────────────────────── */
  async function init() {
    await refresh();
  }

  async function refresh() {
    const container = document.getElementById('insights-cards');
    const count     = document.getElementById('insights-count');
    if (!container) return;

    container.innerHTML = `<div style="padding:20px;color:#9ca3af;font-size:12px">Yükleniyor...</div>`;

    try {
      const tok  = localStorage.getItem('sap_ai_token') || '';
      const res  = await fetch('/api/v1/insights/?limit=12', {
        headers: { 'Authorization': `Bearer ${tok}` },
      });
      const data = await res.json();

      const items = data.items || [];
      if (count) count.textContent = items.length ? `${items.length} aktif` : '';

      if (!items.length) {
        container.innerHTML = _emptyState();
        return;
      }

      container.innerHTML = items.map(_cardHtml).join('');
    } catch (e) {
      console.error('[Insights] yükleme hatası:', e);
      container.innerHTML = `<div style="padding:20px;color:#dc2626;font-size:12px">İçgörüler yüklenemedi.</div>`;
    }
  }

  async function runDetectors() {
    const btn = document.getElementById('insights-run');
    if (btn) { btn.textContent = '⏳ Çalışıyor...'; btn.disabled = true; }
    try {
      const tok = localStorage.getItem('sap_ai_token') || '';
      const res = await fetch('/api/v1/insights/run', {
        method: 'POST',
        headers: { 'Content-Type':'application/json', 'Authorization': `Bearer ${tok}` },
        body: JSON.stringify({})
      });
      const summary = await res.json();
      console.log('[Insights] üretildi:', summary);
      if (btn) btn.textContent = `✓ ${summary.total || 0} yeni içgörü`;
      setTimeout(() => {
        if (btn) { btn.textContent = '🔄 Yeni İçgörü Üret'; btn.disabled = false; }
      }, 2000);
      await refresh();
    } catch (e) {
      if (btn) { btn.textContent = 'Hata!'; btn.disabled = false; }
      console.error(e);
    }
  }

  async function dismiss(id, ev) {
    ev?.stopPropagation();
    const tok = localStorage.getItem('sap_ai_token') || '';
    await fetch(`/api/v1/insights/${id}/dismiss`, {
      method: 'POST', headers: { 'Authorization': `Bearer ${tok}` }
    });
    // Kartı fade out yap
    const card = document.querySelector(`[data-insight-id="${id}"]`);
    if (card) {
      card.style.transition = 'opacity 0.25s, transform 0.25s';
      card.style.opacity = '0';
      card.style.transform = 'scale(0.95)';
      setTimeout(() => card.remove(), 250);
    }
  }

  async function open(id, drillQuestion) {
    // Görüldü olarak işaretle
    const tok = localStorage.getItem('sap_ai_token') || '';
    fetch(`/api/v1/insights/${id}/view`, {
      method: 'POST', headers: { 'Authorization': `Bearer ${tok}` }
    });

    // Chat sayfasına git ve drill question'ı koy
    if (drillQuestion && window.App) {
      // Soru'yu localStorage'a koy, chat sayfası init'te alacak
      sessionStorage.setItem('insights_pending_question', drillQuestion);
      window.App.navigate('chats');
    }
  }

  /* ── Private: kart HTML ────────────────────────────────────────────── */
  function _cardHtml(item) {
    const palette = COLOR_MAP[item.color] || SEVERITY_COLORS[item.severity] || SEVERITY_COLORS.info;
    const payload = item.payload || {};
    const hypotheses = payload.hypotheses || [];
    const icon = item.icon || payload.icon || '💡';
    const drillQ = (item.drill_action || payload.drill_down_question || '').replace(/"/g, '&quot;');

    const deltaBadge = item.delta_pct
      ? `<span style="font-size:11px;font-weight:700;color:${item.delta_pct < 0 ? '#dc2626' : '#16a34a'}">
           ${item.delta_pct < 0 ? '▼' : '▲'} ${Math.abs(item.delta_pct).toFixed(0)}%
         </span>`
      : '';

    const hypList = hypotheses.slice(0, 2).map(h => `
      <div style="font-size:11px;color:#4b5563;line-height:1.5;padding:4px 0">
        🔸 ${_escape(h.text || '')}
      </div>`).join('');

    return `
      <div data-insight-id="${item.id}"
        onclick="InsightsPanel.open(${item.id}, '${drillQ}')"
        style="background:${palette.bg};border:1px solid ${palette.border};
               border-radius:12px;padding:14px;cursor:pointer;
               transition:transform .15s, box-shadow .15s;
               display:flex;flex-direction:column;gap:8px;position:relative"
        onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 6px 18px rgba(0,0,0,0.08)'"
        onmouseout="this.style.transform='none';this.style.boxShadow='none'">

        <button onclick="InsightsPanel.dismiss(${item.id}, event)"
          style="position:absolute;top:8px;right:8px;background:rgba(255,255,255,0.7);
                 border:none;width:22px;height:22px;border-radius:50%;cursor:pointer;
                 font-size:14px;color:#6b7280;line-height:1"
          title="Kapat">✕</button>

        <div style="display:flex;align-items:center;gap:8px;padding-right:24px">
          <span style="font-size:20px">${icon}</span>
          ${deltaBadge}
        </div>

        <div style="font-size:13px;font-weight:700;color:${palette.text};line-height:1.4">
          ${_escape(item.title || '')}
        </div>

        ${item.summary ? `
          <div style="font-size:11px;color:#6b7280;line-height:1.5">
            ${_escape(item.summary).slice(0, 140)}${item.summary.length > 140 ? '…' : ''}
          </div>` : ''}

        ${hypList ? `<div style="margin-top:4px;padding-top:8px;
            border-top:1px dashed ${palette.border}">${hypList}</div>` : ''}

        <div style="margin-top:auto;padding-top:8px;font-size:11px;color:${palette.text};
             font-weight:600;display:flex;align-items:center;gap:4px">
          İncele →
        </div>
      </div>
    `;
  }

  function _emptyState() {
    return `
      <div style="grid-column:1/-1;padding:28px 20px;text-align:center;
                  background:#f9fafb;border:1px dashed #d1d5db;border-radius:12px">
        <div style="font-size:32px;margin-bottom:8px">💤</div>
        <div style="font-size:13px;color:#6b7280;margin-bottom:4px;font-weight:600">
          Aktif içgörü yok
        </div>
        <div style="font-size:11px;color:#9ca3af">
          "Yeni İçgörü Üret" butonuna basarak veri analizi başlatın.
        </div>
      </div>`;
  }

  function _escape(s) {
    return String(s || '').replace(/[<>&"]/g, c => ({
      '<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'
    }[c]));
  }

  return { render, init, refresh, runDetectors, dismiss, open };
})();

window.InsightsPanel = InsightsPanel;

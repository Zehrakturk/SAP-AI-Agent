/**
 * pages/chats.js
 * SAP AI Copilot — Gerçek soru-cevap arayüzü
 */

const ChatsPage = (() => {

  let chatHistory    = [];
  let isLoading      = false;
  let _currentSid    = null;   // aktif oturum ID
  const _reportStore = {};     // msgId → rapor verisi

  // -------------------------------------------------------
  // Render
  // -------------------------------------------------------
  function render() {
    return `
    <div class="chat-layout" style="height:calc(100vh - 84px)">

      <!-- Sol panel -->
      <div class="chat-sidebar" style="display:flex;flex-direction:column">

        <!-- Yeni Sohbet — en üstte -->
        <div style="padding:12px;border-bottom:1px solid var(--border);flex-shrink:0">
          <button class="btn btn-primary" style="width:100%;font-size:13px;gap:6px"
                  onclick="ChatsPage.newChat()">
            <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            Yeni Sohbet
          </button>
        </div>

        <!-- Geçmiş sohbetler -->
        <div style="flex:1;overflow-y:auto;min-height:0">
          <div style="padding:10px 14px 6px;position:sticky;top:0;background:var(--card);z-index:1">
            <span style="font-size:10px;font-weight:700;text-transform:uppercase;
                         letter-spacing:.08em;color:var(--text-muted)">Geçmiş</span>
            <input type="text" id="session-search" placeholder="Sohbetlerde ara (başlık / etiket)..."
                   oninput="ChatsPage.searchSessions(this.value)"
                   style="width:100%;margin-top:6px;font-size:12px;padding:6px 9px;
                          border:1px solid var(--border);border-radius:6px;outline:none">
          </div>
          <div id="session-list"></div>
        </div>

        <!-- Filtreler (daraltılabilir) -->
        <div style="border-top:1px solid var(--border);flex-shrink:0">
          <button onclick="ChatsPage.toggleFilters()" id="filter-toggle-btn"
            style="width:100%;padding:9px 14px;background:none;border:none;
                   display:flex;align-items:center;justify-content:space-between;
                   font-size:12px;font-weight:600;color:var(--text-secondary);cursor:pointer">
            <span>🔍 Veri Filtreleri</span>
            <svg id="filter-chevron" width="12" height="12" fill="none" viewBox="0 0 24 24"
                 stroke="currentColor" stroke-width="2.5" style="transition:transform .2s">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
          <div id="filter-panel" style="display:none;padding:0 14px 14px">
            <div style="display:flex;flex-direction:column;gap:8px;padding-top:8px">
              <div>
                <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">Başlangıç Tarihi</label>
                <input type="date" id="filter-start" class="input" style="width:100%;font-size:12px">
              </div>
              <div>
                <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">Bitiş Tarihi</label>
                <input type="date" id="filter-end" class="input" style="width:100%;font-size:12px">
              </div>
              <div>
                <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">Müşteri Adı</label>
                <input type="text" id="filter-musteri" class="input" placeholder="Müşteri ara..." style="width:100%;font-size:12px">
              </div>
              <div>
                <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">Şehir</label>
                <input type="text" id="filter-city" class="input" placeholder="Şehir ara..." style="width:100%;font-size:12px">
              </div>
              <div>
                <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:3px">Transfer Durumu</label>
                <select id="filter-tdurum" class="select-input" style="width:100%;font-size:12px">
                  <option value="">Tümü</option>
                  <option value="01">01 - Oluşturuldu</option>
                  <option value="02">02 - Planlandı</option>
                  <option value="03">03 - Yüklendi</option>
                  <option value="04">04 - Mal Çıkışı</option>
                  <option value="05">05 - Teslim Edildi</option>
                </select>
              </div>
              <button class="btn btn-primary" style="width:100%;font-size:12px" onclick="ChatsPage.runFilter()">
                Filtrele
              </button>
              <div id="active-filter-badge" style="display:none;padding:6px 10px;
                   background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;
                   font-size:11px;color:#1d4ed8;font-weight:600;text-align:center"></div>
            </div>
          </div><!-- /filter-panel -->
        </div><!-- /filtre dış container -->
      </div><!-- /chat-sidebar -->

      <!-- Sağ panel: chat alanı -->
      <div class="chat-main" style="display:flex;flex-direction:column;height:100%;overflow:hidden">

        <!-- Header -->
        <div class="chat-thread-header">
          <div class="msg-avatar" style="width:34px;height:34px;background:#1a56db;color:white;display:flex;align-items:center;justify-content:center;border-radius:8px;font-weight:700;font-size:13px">AI</div>
          <div>
            <div style="font-size:14px;font-weight:600;color:var(--text)" id="chat-session-title">SAP AI Sorgu Asistanı</div>
            <div style="font-size:12px;color:var(--text-muted)">Türkçe soru sorun — SAP verilerinden yanıt alın</div>
          </div>
          <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
            <div class="status-indicator">
              <div class="status-dot"></div>
              Bağlı
            </div>
          </div>
        </div>

        <!-- Mesajlar -->
        <div class="chat-messages" id="chat-messages" style="flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:16px">
          <div id="empty-state" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:12px;color:var(--gray-400)">
            <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            <div style="font-size:14px;font-weight:500">SAP verilerinizi sorgulayın</div>
            <div style="font-size:12px;text-align:center">Sol taraftaki örnek sorulardan birini seçin<br>veya aşağıya kendi sorunuzu yazın</div>
          </div>
        </div>

        <!-- Input alanı -->
        <div style="padding:16px;border-top:1px solid var(--gray-100);background:white">
          <div style="display:flex;gap:10px;align-items:flex-end">
            <textarea
              id="chat-input"
              class="input"
              placeholder="SAP verileriniz hakkında Türkçe soru sorun... (Enter ile gönder)"
              style="flex:1;min-height:44px;max-height:120px;resize:none;font-size:13px;line-height:1.5;padding:10px 14px"
              onkeydown="ChatsPage.onKeyDown(event)"
              oninput="this.style.height='44px';this.style.height=Math.min(this.scrollHeight,120)+'px'"
            ></textarea>
            <button id="send-btn" class="btn btn-primary" style="height:44px;padding:0 18px;white-space:nowrap" onclick="ChatsPage.sendMessage()">
              <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"/>
                <polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </button>
          </div>
          <div style="font-size:11px;color:var(--gray-400);margin-top:6px;padding-left:2px">
            Sorular Türkçe yazılabilir • Veriler SAP'tan alınmıştır
          </div>
        </div>
      </div>
    </div>
    `;
  }

  // -------------------------------------------------------
  // Mesaj gönder
  // -------------------------------------------------------
  function _collectFilters() {
    const f = {};
    const start  = document.getElementById('filter-start')?.value;
    const end    = document.getElementById('filter-end')?.value;
    const mus    = document.getElementById('filter-musteri')?.value?.trim();
    const city   = document.getElementById('filter-city')?.value?.trim();
    const tdurum = document.getElementById('filter-tdurum')?.value;
    if (start)  f.start_date = start;
    if (end)    f.end_date   = end;
    if (mus)    f.musteri    = mus;
    if (city)   f.city       = city;
    if (tdurum) f.tdurum     = tdurum;
    return f;
  }

  function _activeFilterBadges(filters) {
    if (!Object.keys(filters).length) return '';
    const labels = {
      start_date: 'Başlangıç', end_date: 'Bitiş',
      musteri: 'Müşteri', city: 'Şehir', tdurum: 'Durum',
    };
    return Object.entries(filters).map(([k, v]) =>
      `<span style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:4px;
                    padding:2px 7px;font-size:10px;font-weight:600;color:#1d4ed8">
        ${labels[k] || k}: ${v}
      </span>`
    ).join(' ');
  }

  async function sendMessage() {
    const input = document.getElementById('chat-input');
    const question = input.value.trim();
    if (!question || isLoading) return;
    if (input) input.dataset.lastQ = question;

    const activeFilters = _collectFilters();

    input.value = '';
    input.style.height = '44px';
    hideEmptyState();
    isLoading = true;

    // Kullanıcı balonu — aktif filtreler varsa göster
    const filterBadges = _activeFilterBadges(activeFilters);
    appendMessage('user', question, filterBadges);

    // Yükleniyor balonu
    const loadingId = appendLoading();

    try {
      // Aktif oturum yoksa yeni oluştur
      if (!_currentSid) await newChat();

      const res = await fetch(`${window.API_BASE_URL}/query/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('sap_ai_token') || ''}`,
        },
        body: JSON.stringify({ question, filters: activeFilters, session_id: _currentSid })
      });
      const data = await res.json();
      removeLoading(loadingId);

      if (data.error) {
        appendMessage('error', `Hata: ${data.error}`);
      } else if (data.status === 'confirmation_needed') {
        _appendConfirmation(data, question, activeFilters);
        _loadSessions();
      } else if (data.status === 'pending_approval') {
        _appendPendingApproval(data);
        _loadSessions();
      } else {
        appendAIMessage(data);
        // İlk mesajsa oturum başlığını güncelle
        if (chatHistory.filter(m => m.role === 'user').length === 1 && _currentSid) {
          const shortTitle = question.length > 60 ? question.slice(0, 57) + '…' : question;
          const tok = localStorage.getItem('sap_ai_token') || '';
          fetch(`/api/v1/chats/sessions/${_currentSid}/title`, {
            method : 'PATCH',
            headers: { 'Content-Type':'application/json', 'Authorization':`Bearer ${tok}` },
            body   : JSON.stringify({ title: shortTitle }),
          }).then(() => _loadSessions());
          const titleEl = document.getElementById('chat-session-title');
          if (titleEl) titleEl.textContent = shortTitle;
        } else {
          _loadSessions();
        }
      }
    } catch (e) {
      removeLoading(loadingId);
      appendMessage('error', 'Sunucuya bağlanılamadı. Lütfen tekrar deneyin.');
    }

    isLoading = false;
  }

  // -------------------------------------------------------
  // Filtre çalıştır
  // -------------------------------------------------------
  async function runFilter() {
    const payload = {
      start_date: document.getElementById('filter-start').value  || undefined,
      end_date:   document.getElementById('filter-end').value    || undefined,
      musteri:    document.getElementById('filter-musteri').value || undefined,
      city:       document.getElementById('filter-city').value   || undefined,
      tdurum:     document.getElementById('filter-tdurum').value || undefined,
    };

    // Boş değerleri temizle
    Object.keys(payload).forEach(k => payload[k] === undefined && delete payload[k]);

    if (!Object.keys(payload).length) {
      alert('En az bir filtre seçin.');
      return;
    }

    hideEmptyState();
    isLoading = true;
    const loadingId = appendLoading();

    // Kullanıcı mesajı olarak filtre özetini göster
    const summary = Object.entries(payload)
      .map(([k, v]) => `${k}: ${v}`).join(' • ');
    appendMessage('user', `🔍 Filtre: ${summary}`);

    try {
      const res = await fetch(`${window.API_BASE_URL}/query/filter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      removeLoading(loadingId);
      appendAIMessage({ ...data, summary: `${data.count} kayıt bulundu.` });
    } catch (e) {
      removeLoading(loadingId);
      appendMessage('error', 'Filtre sorgusu başarısız.');
    }

    isLoading = false;
  }

  // -------------------------------------------------------
  // DOM helpers
  // -------------------------------------------------------
  function hideEmptyState() {
    const es = document.getElementById('empty-state');
    if (es) es.remove();
  }

  function appendMessage(role, text, filterBadgesHtml = '') {
    const msgs   = document.getElementById('chat-messages');
    const div    = document.createElement('div');
    const isUser = role === 'user';
    const isError= role === 'error';

    // Kullanıcı → sağa yasla, AI → sola yasla
    div.style.cssText = `display:flex;gap:10px;align-items:flex-start;
      ${isUser ? 'flex-direction:row-reverse' : 'flex-direction:row'}`;

    const avatarBg = isUser  ? '#e2e8f0'
                   : isError ? '#fee2e2'
                   :           '#1a56db';
    const avatarColor = isUser ? '#374151' : '#fff';
    const avatarText  = isUser ? (window._currentUser?.charAt(0) || 'U') : 'AI';

    const bubbleStyle = isUser
      ? 'background:#1a56db;color:#fff;border:none'
      : isError
        ? 'background:#fee2e2;border:1px solid #fca5a5;color:#dc2626'
        : 'background:#f1f5f9;border:1px solid #e2e8f0;color:#1e293b';

    const timeAlign = isUser ? 'text-align:right' : '';

    div.innerHTML = `
      <div style="width:32px;height:32px;border-radius:${isUser?'50%':'8px'};
                  background:${avatarBg};color:${avatarColor};
                  display:flex;align-items:center;justify-content:center;
                  font-size:${isUser?'13px':'11px'};font-weight:700;flex-shrink:0;margin-top:2px">
        ${avatarText}
      </div>
      <div style="max-width:72%;${isUser?'align-items:flex-end':'align-items:flex-start'};display:flex;flex-direction:column">
        <div style="padding:10px 14px;border-radius:${isUser?'16px 4px 16px 16px':'4px 16px 16px 16px'};
                    font-size:13px;line-height:1.6;${bubbleStyle}">
          ${text.replace(/\n/g, '<br>')}
          ${filterBadgesHtml ? `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,.3)">${filterBadgesHtml}</div>` : ''}
        </div>
        <div style="font-size:11px;color:#9ca3af;margin-top:4px;${timeAlign}">
          ${new Date().toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit'})}
        </div>
      </div>
    `;

    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    chatHistory.push({ role, text });
  }

  const CHART_COLORS = [
    '#1a56db','#10b981','#f59e0b','#ef4444',
    '#8b5cf6','#ec4899','#06b6d4','#f97316',
  ];
  const CHART_COLORS_SOFT = CHART_COLORS.map(c => c + '33');

  function _makeDatasets(chartType, rawDatasets) {
    return (rawDatasets || []).map((ds, i) => {
      const base = {
        label          : ds.label || '',
        data           : ds.data  || [],
        borderWidth    : 2,
        borderRadius   : chartType === 'bar' ? 5 : 0,
        tension        : chartType === 'line' ? 0.4 : 0,
      };
      if (chartType === 'pie' || chartType === 'doughnut') {
        base.backgroundColor = CHART_COLORS.map(c => c + 'cc');
        base.borderColor     = '#fff';
        base.borderWidth     = 2;
      } else if (chartType === 'line') {
        base.borderColor     = CHART_COLORS[i % CHART_COLORS.length];
        base.backgroundColor = CHART_COLORS[i % CHART_COLORS.length] + '22';
        base.pointBackgroundColor = CHART_COLORS[i % CHART_COLORS.length];
        base.pointRadius     = 4;
        base.fill            = true;
      } else {
        base.backgroundColor = CHART_COLORS[i % CHART_COLORS.length] + 'cc';
        base.borderColor     = CHART_COLORS[i % CHART_COLORS.length];
      }
      return base;
    });
  }

  function _chartOptions(chartType, title) {
    const isCategory = chartType !== 'pie' && chartType !== 'doughnut';
    return {
      responsive         : true,
      maintainAspectRatio: false,
      animation          : { duration: 600 },
      plugins: {
        legend : { position: (chartType === 'pie' || chartType === 'doughnut') ? 'right' : 'top', labels: { boxWidth: 12, font: { size: 11 } } },
        title  : title ? { display: true, text: title, font: { size: 12, weight: '600' }, color: '#374151' } : { display: false },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor      : '#f1f5f9',
          bodyColor       : '#cbd5e1',
          cornerRadius    : 8,
          padding         : 10,
        },
      },
      scales: isCategory ? {
        y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,.04)' }, ticks: { font: { size: 11 }, color: '#9ca3af' } },
        x: { grid: { display: false },                              ticks: { font: { size: 11 }, color: '#9ca3af' } },
      } : {},
    };
  }

  function _resolveChartJsType(raw) {
    const t = (raw || 'BAR').toUpperCase();
    if (t === 'LINE') return 'line';
    if (t === 'PIE')  return 'pie';
    return 'bar';
  }

  function appendAIMessage(data) {
    const msgs = document.getElementById('chat-messages');
    const div  = document.createElement('div');
    // AI → sola yasla
    div.style.cssText = 'display:flex;flex-direction:row;gap:10px;align-items:flex-start';

    const rows         = data.rows           || [];
    const kpis         = data.kpis           || [];
    const highlights   = data.highlights     || [];
    const chartType    = (data.chart_type    || 'NONE').toUpperCase();
    const chartData    = data.chart_data     || {};
    const secondaryChart = data.secondary_chart || null;

    const chartId  = 'c1-' + Date.now();
    const chart2Id = 'c2-' + Date.now();

    const showPrimary   = ['BAR','LINE','PIE'].includes(chartType) && chartData.labels?.length;
    const showSecondary = secondaryChart?.data?.labels?.length;
    const showTable     = rows.length > 0 && (chartType === 'TABLE' || !showPrimary);

    // ── KPI satırı ───────────────────────────────────────────────────────
    const kpiColors = { blue:'#1a56db', green:'#10b981', amber:'#f59e0b', red:'#ef4444', purple:'#8b5cf6' };
    const kpiHtml = kpis.length ? `
      <div style="display:grid;grid-template-columns:repeat(${Math.min(kpis.length,4)},1fr);gap:8px;margin-bottom:14px">
        ${kpis.map(k => {
          const col = kpiColors[k.color] || '#1a56db';
          const trendHtml = k.trend
            ? `<span style="font-size:10px;color:${k.trend==='up'?'#10b981':'#ef4444'}">${k.trend==='up'?'▲':'▼'} ${k.change||''}</span>`
            : '';
          return `
            <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px 12px;
                        border-top:3px solid ${col}">
              <div style="font-size:10px;font-weight:600;color:#9ca3af;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">${k.label}</div>
              <div style="font-size:20px;font-weight:700;color:#111827;letter-spacing:-.02em;line-height:1">${k.value}</div>
              <div style="margin-top:4px">${trendHtml}</div>
            </div>`;
        }).join('')}
      </div>` : '';

    // ── Highlights ───────────────────────────────────────────────────────
    const highlightsHtml = highlights.length ? `
      <div style="background:#f8faff;border:1px solid #dbeafe;border-radius:8px;padding:10px 14px;
                  margin-bottom:14px;display:flex;flex-direction:column;gap:5px">
        ${highlights.map(h => `<div style="font-size:12px;color:#1e40af;line-height:1.5">${h}</div>`).join('')}
      </div>` : '';

    // ── Kaynaklar (PDF-RAG / knowledge yanıtı) ────────────────────────────
    const sources = data.sources || [];
    const sourcesHtml = sources.length ? `
      <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:10px 14px;
                  margin-bottom:14px">
        <div style="font-size:11px;font-weight:700;color:#15803d;margin-bottom:6px">📄 Kaynaklar</div>
        ${sources.map(s => `
          <div style="font-size:12px;color:#166534;line-height:1.5;margin-bottom:4px">
            <b>${s.filename || ''}</b>${s.snippet ? ` — <span style="color:#4b5563">${(s.snippet||'').replace(/</g,'&lt;')}…</span>` : ''}
          </div>`).join('')}
      </div>` : '';

    // ── Kullanılan metrikler (Semantic Layer) ─────────────────────────────
    const metricsUsed = (data.metrics_used || []).filter(Boolean);
    const metricsUsedHtml = metricsUsed.length ? `
      <div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center">
        <span style="font-size:11px;color:#9ca3af;font-weight:600">📐 Kullanılan metrikler:</span>
        ${metricsUsed.map(m => `<span title="${(m.key||'').replace(/"/g,'&quot;')}"
            style="font-size:11px;color:#6d28d9;background:#f5f3ff;border:1px solid #ddd6fe;
                   border-radius:10px;padding:2px 9px">${(m.label||m.key||'').replace(/</g,'&lt;')}</span>`).join('')}
      </div>` : '';

    // ── Takip soruları (follow-up çipleri) ───────────────────────────────
    const followUps = (data.follow_ups || []).filter(Boolean).slice(0, 3);
    const followUpsHtml = followUps.length ? `
      <div style="margin-top:12px;display:flex;flex-wrap:wrap;gap:6px;align-items:center">
        <span style="font-size:11px;color:#9ca3af;font-weight:600">💡 Devam:</span>
        ${followUps.map(q => {
          const safe = (q || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
          const label = (q || '').replace(/</g, '&lt;');
          return `<button onclick="ChatsPage.askFollowUp('${safe}')"
            style="font-size:12px;color:#1a56db;background:#eff6ff;border:1px solid #bfdbfe;
                   border-radius:14px;padding:5px 12px;cursor:pointer;font-family:inherit;
                   transition:all .15s"
            onmouseover="this.style.background='#dbeafe';this.style.borderColor='#1a56db'"
            onmouseout="this.style.background='#eff6ff';this.style.borderColor='#bfdbfe'"
          >${label}</button>`;
        }).join('')}
      </div>` : '';

    // ── Ana grafik ────────────────────────────────────────────────────────
    const primaryChartHtml = showPrimary ? `
      <div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:14px;
                  margin-bottom:${showSecondary||showTable?'10px':'0'}">
        <div style="height:260px;position:relative">
          <canvas id="${chartId}"></canvas>
        </div>
      </div>` : '';

    // ── İkincil grafik ────────────────────────────────────────────────────
    const secondaryChartHtml = showSecondary ? `
      <div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:14px;
                  margin-bottom:${showTable?'10px':'0'}">
        <div style="font-size:11px;font-weight:600;color:#6b7280;margin-bottom:8px;text-transform:uppercase;letter-spacing:.05em">
          ${secondaryChart.title || 'Detay Görünüm'}
        </div>
        <div style="height:180px;position:relative">
          <canvas id="${chart2Id}"></canvas>
        </div>
      </div>` : '';

    // ── Veri tablosu ──────────────────────────────────────────────────────
    const tableHtml = showTable
      ? `<div style="margin-top:4px">${buildTable(rows.slice(0,20))}</div>
         ${rows.length > 20 ? `<div style="font-size:11px;color:#9ca3af;padding:6px 10px">+ ${rows.length-20} kayıt daha...</div>` : ''}`
      : '';

    // ── Canlı sorgu rozeti (SQL'e yazılmayan anlık SAP sorgusu) ───────────
    const liveBadgeHtml = data.mode === 'live' ? `
      <div style="margin-bottom:8px;display:inline-flex;align-items:center;gap:5px;
                  font-size:10px;font-weight:700;padding:3px 9px;border-radius:10px;
                  background:${data.live_success===false?'#fef2f2':'#fff7ed'};
                  color:${data.live_success===false?'#dc2626':'#c2410c'};
                  border:1px solid ${data.live_success===false?'#fecaca':'#fed7aa'}">
        <span style="font-size:8px">●</span> CANLI SAP SORGUSU${data.live_success===false?' · HATA':''}
      </div><br>` : '';

    div.innerHTML = `
      <!-- AI avatar — sol -->
      <div style="width:34px;height:34px;background:#1a56db;color:#fff;border-radius:8px;
                  font-size:11px;font-weight:700;display:flex;align-items:center;
                  justify-content:center;flex-shrink:0;margin-top:2px">AI</div>

      <!-- AI içerik — sol hizalı, geniş (rapor tek ekrana sığsın) -->
      <div style="flex:1;min-width:0;max-width:94%">
        <div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:4px 16px 16px 16px;
                    padding:14px 16px">

          ${liveBadgeHtml}
          <div style="font-size:13px;color:#1e293b;line-height:1.65;white-space:pre-wrap;
                      margin-bottom:${kpis.length||highlights.length||showPrimary?'14px':'0'}">
            ${data.summary || ''}
          </div>

          ${kpiHtml}
          ${highlightsHtml}
          ${sourcesHtml}
          ${metricsUsedHtml}
          ${primaryChartHtml}
          ${secondaryChartHtml}
          ${tableHtml}

          ${data.sql ? `
          <details style="margin-top:10px">
            <summary style="font-size:11px;color:#9ca3af;cursor:pointer;user-select:none">
              ⚙ SQL sorgusunu görüntüle
            </summary>
            <pre style="font-size:11px;background:#0f172a;color:#7dd3fc;padding:10px 12px;
                        border-radius:6px;margin-top:6px;overflow-x:auto;white-space:pre-wrap">${data.sql}</pre>
          </details>` : ''}

          ${followUpsHtml}
        </div>

        <div style="display:flex;align-items:center;gap:10px;margin-top:4px">
          <div class="msg-time" style="font-size:11px;color:#9ca3af">
            ${new Date().toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit'})} · SAP AI · ${data.count ?? rows.length} kayıt
          </div>
        </div>
      </div>
    `;

    // ── Rapor Yap butonu ──────────────────────────────────────────────────
    if (rows.length) {
      const msgId = 'msg-' + Date.now();
      div.dataset.msgId = msgId;
      _reportStore[msgId] = {
        question       : document.getElementById('chat-input')?.dataset?.lastQ || '',
        summary        : data.summary    || '',
        rows           : rows.slice(0, 500),
        count          : data.count      ?? rows.length,
        chart_type     : data.chart_type || 'BAR',
        chart_data     : data.chart_data || {},
        kpis           : data.kpis       || [],
        highlights     : data.highlights || [],
        secondary_chart: data.secondary_chart || null,
        tables_used    : data.tables_used || [],
        sql            : data.sql        || '',
      };
      const timeRow = div.querySelector('.msg-time')?.parentElement;
      if (timeRow) {
        const btn = document.createElement('button');
        btn.style.cssText = `display:inline-flex;align-items:center;gap:5px;padding:4px 10px;
          background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;
          color:#1d4ed8;font-size:11px;font-weight:600;cursor:pointer;font-family:inherit;transition:background .15s`;
        btn.innerHTML = `<svg width="11" height="11" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/>
          </svg> Rapor Yap`;
        btn.addEventListener('mouseover', () => btn.style.background = '#dbeafe');
        btn.addEventListener('mouseout',  () => btn.style.background = '#eff6ff');
        btn.addEventListener('click', () => {
          const d = _reportStore[msgId];
          if (d) Reports.open(d);
        });
        timeRow.appendChild(btn);

        // ── E-posta gönder butonu (Sprint 2.2) ─────────────────────────
        const mailBtn = document.createElement('button');
        mailBtn.style.cssText = `display:inline-flex;align-items:center;gap:5px;padding:4px 10px;
          background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;
          color:#15803d;font-size:11px;font-weight:600;cursor:pointer;font-family:inherit;transition:background .15s`;
        mailBtn.innerHTML = `✉ E-posta`;
        mailBtn.addEventListener('mouseover', () => mailBtn.style.background = '#dcfce7');
        mailBtn.addEventListener('mouseout',  () => mailBtn.style.background = '#f0fdf4');
        mailBtn.addEventListener('click', () => _emailReport(_reportStore[msgId], mailBtn));
        timeRow.appendChild(mailBtn);
      }
    }

    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;

    // ── Görselleştirme seçici: grafik yoksa ama veri varsa ────────────────
    if (!showPrimary && !showSecondary && rows.length > 1) {
      _appendVizPicker(rows, msgs);
    }

    // ── Chart.js oluştur ──────────────────────────────────────────────────
    if (showPrimary) {
      const ctx  = document.getElementById(chartId);
      const type = _resolveChartJsType(data.chart_type);
      if (ctx) {
        const opts = _chartOptions(type);
        opts.onClick = (evt, els, chart) => _drillDown(chart, els, data);
        ctx.style.cursor = 'pointer';
        ctx._chartInst = new Chart(ctx, {
          type,
          data   : { labels: chartData.labels || [], datasets: _makeDatasets(type, chartData.datasets) },
          options: opts,
        });
      }
    }

    if (showSecondary) {
      const ctx2  = document.getElementById(chart2Id);
      const type2 = _resolveChartJsType(secondaryChart.type || 'BAR');
      if (ctx2) {
        const opts2 = _chartOptions(type2, secondaryChart.title);
        opts2.onClick = (evt, els, chart) => _drillDown(chart, els, data);
        ctx2.style.cursor = 'pointer';
        new Chart(ctx2, {
          type   : type2,
          data   : { labels: secondaryChart.data.labels || [], datasets: _makeDatasets(type2, secondaryChart.data.datasets) },
          options: opts2,
        });
      }
    }

    // ── Gemini zenginleştirme (arka planda, non-blocking) ─────────────────
    if (rows.length && showPrimary) {
      _geminiEnhanceChat(data, chartId, div);
    }

    // Karşılaştırma sorgusuysa "Olası Sebepler" kutusu yükle
    if (_isComparisonQuery(data) && rows.length) {
      _loadHypotheses(data, div);
    }
  }

  /* ── Human-in-the-loop onay süreci ────────────────────────────────────── */

  function _appendConfirmation(data, question, filters) {
    const msgs = document.getElementById('chat-messages');
    const div  = document.createElement('div');
    div.style.cssText = 'display:flex;flex-direction:row;gap:10px;align-items:flex-start';
    const cid  = 'confirm-' + Date.now();
    const name = data.gap?.integration_name || 'Bu veri kaynağı';

    div.innerHTML = `
      <div style="width:34px;height:34px;background:#3b82f6;color:#fff;border-radius:8px;
                  font-size:15px;display:flex;align-items:center;justify-content:center;
                  flex-shrink:0;margin-top:2px">❓</div>
      <div style="flex:1;min-width:0;max-width:85%">
        <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:4px 16px 16px 16px;padding:14px 16px">
          <div style="font-size:13px;font-weight:700;color:#1e40af;margin-bottom:6px">
            Veri sistemde bulunamadı
          </div>
          <div style="font-size:13px;color:#1e3a8a;line-height:1.6;margin-bottom:12px">
            ${data.reason || ''}<br><br>
            <b>${name}</b> için entegrasyon çalıştırılsın mı?
            <span style="color:#64748b">(Onay admin'e gönderilecek.)</span>
          </div>
          <div id="${cid}-btns" style="display:flex;gap:8px">
            <button id="${cid}-yes" style="padding:7px 16px;border:none;border-radius:7px;
                    background:#1a56db;color:#fff;font-size:12px;font-weight:600;cursor:pointer">
              Evet, onaya gönder</button>
            <button id="${cid}-no" style="padding:7px 16px;border:1px solid #cbd5e1;border-radius:7px;
                    background:#fff;color:#475569;font-size:12px;font-weight:600;cursor:pointer">
              Hayır</button>
          </div>
          <div id="${cid}-msg" style="font-size:12px;color:#64748b;margin-top:8px;display:none"></div>
        </div>
      </div>`;

    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;

    const hideBtns = () => { const b = document.getElementById(`${cid}-btns`); if (b) b.style.display='none'; };
    const showMsg  = (t) => { const m = document.getElementById(`${cid}-msg`); if (m){ m.style.display='block'; m.textContent=t; } };

    document.getElementById(`${cid}-no`).addEventListener('click', () => {
      hideBtns(); showMsg('İşlem iptal edildi.');
    });

    document.getElementById(`${cid}-yes`).addEventListener('click', async () => {
      hideBtns(); showMsg('Onaya gönderiliyor...');
      try {
        const tok = localStorage.getItem('sap_ai_token') || '';
        const res = await fetch(`${window.API_BASE_URL}/approvals/request`, {
          method : 'POST',
          headers: { 'Content-Type':'application/json', 'Authorization':`Bearer ${tok}` },
          body   : JSON.stringify({ gap: data.gap, question, filters, session_id: _currentSid }),
        });
        const r = await res.json();
        if (!res.ok) throw new Error(r.error || `HTTP ${res.status}`);
        showMsg(r.deduped ? 'Bu talep zaten onay sürecinde.' : 'Admin onayına gönderildi.');
        _appendPendingApproval({
          approval_external_id: r.approval_external_id,
          approval_id         : r.approval_id,
          reason              : data.reason,
        });
      } catch (e) {
        showMsg('Gönderilemedi: ' + e.message);
      }
    });
  }

  function _appendPendingApproval(data) {
    const msgs = document.getElementById('chat-messages');
    const div  = document.createElement('div');
    div.style.cssText = 'display:flex;flex-direction:row;gap:10px;align-items:flex-start';
    const ext = data.approval_external_id;

    div.innerHTML = `
      <div style="width:34px;height:34px;background:#f59e0b;color:#fff;border-radius:8px;
                  font-size:15px;display:flex;align-items:center;justify-content:center;
                  flex-shrink:0;margin-top:2px">⏳</div>
      <div style="flex:1;min-width:0;max-width:85%">
        <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:4px 16px 16px 16px;padding:14px 16px">
          <div style="font-size:13px;font-weight:700;color:#92400e;margin-bottom:6px">
            Veri sistemde yok — admin onayına gönderildi
          </div>
          <div style="font-size:13px;color:#78350f;line-height:1.6;margin-bottom:10px">
            ${data.reason || data.summary || ''}
          </div>
          <div id="appr-pill-${ext}" style="display:inline-flex;align-items:center;gap:6px;
                font-size:11px;font-weight:600;color:#92400e;background:#fef3c7;
                border:1px solid #fde68a;border-radius:999px;padding:4px 11px">
            <span style="width:7px;height:7px;border-radius:50%;background:#f59e0b;
                  display:inline-block;animation:apprPulse 1.2s infinite"></span>
            Onay bekleniyor (#${data.approval_id})
          </div>
        </div>
      </div>`;

    if (!document.getElementById('appr-pulse-style')) {
      const st = document.createElement('style');
      st.id = 'appr-pulse-style';
      st.textContent = '@keyframes apprPulse{0%,100%{opacity:1}50%{opacity:.3}}';
      document.head.appendChild(st);
    }

    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;

    if (ext) _pollApproval(ext, div);
  }

  function _pollApproval(externalId, container, tries = 0) {
    // ~5 dk boyunca 4 sn'de bir yokla (75 deneme)
    if (tries > 75) {
      _setApprPill(externalId, '⌛ Zaman aşımı — sayfayı yenileyip durumu kontrol edin', '#9ca3af');
      return;
    }
    const tok = localStorage.getItem('sap_ai_token') || '';
    fetch(`${window.API_BASE_URL}/approvals/status/${externalId}`, {
      headers: { 'Authorization': `Bearer ${tok}` },
    })
    .then(r => r.json())
    .then(s => {
      if (s.error) { _setApprPill(externalId, 'Durum alınamadı', '#ef4444'); return; }

      if (s.status === 'REJECTED') {
        _setApprPill(externalId, '❌ Talep reddedildi', '#ef4444');
        return;
      }
      if (s.status === 'EXPIRED') {
        _setApprPill(externalId, '⌛ Talep süresi doldu', '#9ca3af');
        return;
      }

      const jobStatus = s.job?.status;
      if (jobStatus === 'COMPLETED') {
        _setApprPill(externalId, '✅ Onaylandı — veri çekildi', '#10b981');
        if (s.result && !s.result.error) {
          appendAIMessage(s.result);   // sonucu otomatik render et
        } else {
          appendMessage('error', 'Veri çekildi ancak sonuç oluşturulamadı.');
        }
        return;
      }
      if (jobStatus === 'FAILED') {
        _setApprPill(externalId, `❌ Veri çekme başarısız${s.job?.error_message ? ': '+s.job.error_message.slice(0,80) : ''}`, '#ef4444');
        return;
      }

      // Durum etiketini canlı güncelle
      const labels = {
        PENDING  : `Onay bekleniyor`,
        APPROVED : jobStatus ? `İşleniyor: ${_jobLabel(jobStatus)}` : 'Onaylandı, kuyruğa alındı',
      };
      _setApprPill(externalId, '⏳ ' + (labels[s.status] || s.status), '#92400e', true);

      setTimeout(() => _pollApproval(externalId, container, tries + 1), 4000);
    })
    .catch(() => setTimeout(() => _pollApproval(externalId, container, tries + 1), 4000));
  }

  function _jobLabel(st) {
    return ({ QUEUED:'kuyrukta', RUNNING:'başlatılıyor', FETCHING:'SAP\'tan çekiliyor',
              INDEXING:'indeksleniyor', RERUNNING:'sorgu çalıştırılıyor' })[st] || st;
  }

  function _setApprPill(externalId, text, color, pulsing = false) {
    const pill = document.getElementById(`appr-pill-${externalId}`);
    if (!pill) return;
    pill.style.color       = color;
    pill.style.background   = color === '#10b981' ? '#ecfdf5'
                            : color === '#ef4444' ? '#fef2f2' : '#fef3c7';
    pill.style.borderColor  = color === '#10b981' ? '#a7f3d0'
                            : color === '#ef4444' ? '#fecaca' : '#fde68a';
    const dot = pulsing
      ? `<span style="width:7px;height:7px;border-radius:50%;background:${color};display:inline-block;animation:apprPulse 1.2s infinite"></span>`
      : '';
    pill.innerHTML = dot + text;
  }

  /* ── E-posta paylaşımı (Sprint 2.2) ───────────────────────────────────── */

  async function _emailReport(payload, btn) {
    if (!payload) return;
    const to = window.prompt(
      'Rapor hangi e-posta adres(ler)ine gönderilsin?\n(Virgülle ayırabilirsiniz)',
      ''
    );
    if (!to) return;
    const recipients = to.split(',').map(s => s.trim()).filter(Boolean);
    if (!recipients.length) return;

    const original = btn?.innerHTML;
    if (btn) { btn.innerHTML = 'Gönderiliyor...'; btn.disabled = true; }

    try {
      const res = await fetch(`${window.API_BASE_URL}/reports/email`, {
        method : 'POST',
        headers: {
          'Content-Type' : 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('sap_ai_token') || ''}`,
        },
        body: JSON.stringify({
          to     : recipients,
          subject: `SAP-AI Rapor — ${(payload.question || '').slice(0, 60)}`,
          report : payload,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      if (btn) btn.innerHTML = '✓ Gönderildi';
      setTimeout(() => { if (btn) { btn.innerHTML = original; btn.disabled = false; } }, 2500);
    } catch (e) {
      alert(`E-posta gönderilemedi: ${e.message}`);
      if (btn) { btn.innerHTML = original; btn.disabled = false; }
    }
  }

  /* ── Drill-down (Sprint 2.3) ──────────────────────────────────────────── */

  function _drillDown(chart, elements, sourceData) {
    if (!elements || !elements.length) return;
    const el        = elements[0];
    const label     = chart.data.labels?.[el.index];
    const dsLabel   = chart.data.datasets?.[el.datasetIndex]?.label;
    const chartType = (chart.config?.type || '').toLowerCase();
    if (label == null) return;

    // Önceki sorudan tablo/bağlam çıkar
    const lastQ  = document.getElementById('chat-input')?.dataset?.lastQ
                 || sourceData?._question
                 || '';
    const tables = (sourceData?.tables_used || []).join(', ');

    // Soru üret — chart tipine göre
    let question;
    if (chartType === 'pie' || chartType === 'doughnut') {
      question = `"${label}" için detayları göster${tables ? ` (${tables})` : ''}.`;
    } else if (chartType === 'line') {
      question = `${label} dönemini daha detaylı göster${dsLabel ? ` — ${dsLabel}` : ''}.`;
    } else { // bar / grouped bar
      if (dsLabel && dsLabel !== 'Veri') {
        question = `${label} içinde ${dsLabel} için detay kır.`;
      } else {
        question = `${label} için detaylı dağılım göster.`;
      }
    }
    if (lastQ) question += ` (Önceki soru: "${lastQ}")`;

    // Input'u doldur ve gönder
    const input = document.getElementById('chat-input');
    if (input) {
      input.value = question;
      input.dataset.lastQ = question;
    }
    // sendMessage IIFE closure'ı içinde — doğrudan çağrılabilir
    sendMessage();
  }

  /* ── Olası Sebepler (Hypothesis Engine) ───────────────────────────────── */

  function _isComparisonQuery(data) {
    // SQL veya summary'de CASE WHEN ... BETWEEN ... var mı?
    const sql = (data.sql || '').toUpperCase();
    if (sql.includes('CASE') && sql.includes('BETWEEN')) return true;
    // ChartData'da iki dataset varsa veya 2 dönem etiketi varsa
    const labels = (data.chart_data?.labels || []).map(l => String(l).toLowerCase());
    const compareWords = ['hafta','dönem','ay','sezon','geçen','önceki','vs','karşı'];
    return labels.length === 2 &&
           labels.some(l => compareWords.some(w => l.includes(w)));
  }

  async function _loadHypotheses(data, msgDiv) {
    // SQL'den iki tarih aralığını çıkarmaya çalış
    const periods = _extractPeriodsFromSQL(data.sql || '');
    const table   = (data.tables_used || [])[0];
    if (!periods || !table) return;

    const bubble = msgDiv.querySelector('.msg-bubble') || msgDiv.querySelector('[style*="border-radius:4px 16px"]');
    if (!bubble) return;

    // Placeholder ekle
    const box = document.createElement('div');
    box.style.cssText = `
      margin-top:12px;padding:12px 14px;
      background:linear-gradient(135deg,#fff7ed,#fef3c7);
      border:1px solid #fde68a;border-radius:8px;
      font-size:12px;color:#92400e
    `;
    box.innerHTML = `
      <div style="font-weight:700;margin-bottom:6px;display:flex;align-items:center;gap:6px">
        💡 Olası Sebepler <span style="font-size:10px;color:#a16207">AI hipotezi yükleniyor...</span>
      </div>
      <div id="hyp-list-loading" style="color:#9a8552">
        Veriler analiz ediliyor...
      </div>
    `;
    bubble.appendChild(box);

    try {
      const res = await fetch('/api/v1/insights/explain', {
        method : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body   : JSON.stringify({
          table_name        : table,
          integration_name  : (data.integration_names || ['Veri'])[0],
          cur_start         : periods.cur_start,
          cur_end           : periods.cur_end,
          prev_start        : periods.prev_start,
          prev_end          : periods.prev_end,
          max               : 3,
        }),
      });
      const result = await res.json();
      const hyps = result.hypotheses || [];

      if (!hyps.length) {
        box.querySelector('#hyp-list-loading').textContent = 'Bu karşılaştırma için belirgin bir kök-sebep bulunamadı.';
        return;
      }

      box.innerHTML = `
        <div style="font-weight:700;margin-bottom:8px;display:flex;align-items:center;gap:6px;color:#78350f">
          💡 Olası Sebepler
        </div>
        ${hyps.map(h => `
          <div style="font-size:12px;line-height:1.6;padding:4px 0;color:#451a03">
            🔸 ${_escapeHtml(h.text || '')}
            ${h.confidence ? `<span style="font-size:10px;color:#9a8552;margin-left:4px">
              (güven: %${Math.round((h.confidence || 0.5) * 100)})</span>` : ''}
          </div>`).join('')}
      `;
    } catch (e) {
      console.warn('[Hypotheses] yüklenemedi:', e);
      box.remove();
    }
  }

  function _extractPeriodsFromSQL(sql) {
    // BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD' kalıbından iki dönemi çıkar
    const re = /BETWEEN\s+'(\d{4}-\d{2}-\d{2})'\s+AND\s+'(\d{4}-\d{2}-\d{2})'/gi;
    const matches = [...sql.matchAll(re)];
    if (matches.length < 2) return null;
    // İlk match WHERE (toplam aralık) olabilir → CASE WHEN içindekiler 2 ve 3. sıralarda
    const periods = matches.slice(-2);  // son ikisi (CASE WHEN'ler)
    return {
      prev_start: periods[0][1], prev_end: periods[0][2],
      cur_start : periods[1][1], cur_end : periods[1][2],
    };
  }

  function _escapeHtml(s) {
    return String(s || '').replace(/[<>&"]/g, c => ({
      '<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'
    }[c]));
  }

  async function _geminiEnhanceChat(data, chartId, msgDiv) {
    try {
      const res = await fetch('/api/v1/enhance/visualization', {
        method : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body   : JSON.stringify({
          question   : document.getElementById('chat-input')?.dataset?.lastQ || '',
          rows       : (data.rows || []).slice(0, 50),
          summary    : data.summary    || '',
          chart_type : data.chart_type || 'BAR',
          chart_data : data.chart_data || {},
        }),
      });
      if (!res.ok) return;
      const enh = await res.json();
      if (enh.error || !Object.keys(enh).length) return;

      // Grafik başlığı + alt başlık ekle
      const chartWrap = document.getElementById(chartId)?.parentElement;
      if (chartWrap && (enh.chart_title || enh.chart_subtitle)) {
        const titleEl = document.createElement('div');
        titleEl.style.cssText = 'margin-bottom:8px';
        titleEl.innerHTML = `
          ${enh.chart_title ? `<div style="font-size:13px;font-weight:700;color:#111827">${enh.chart_title}</div>` : ''}
          ${enh.chart_subtitle ? `<div style="font-size:11px;color:#9ca3af;margin-top:2px">${enh.chart_subtitle}</div>` : ''}
        `;
        chartWrap.insertBefore(titleEl, chartWrap.firstChild);
      }

      // Renk paletini uygula
      if (enh.palette?.length && chartId) {
        const canvas = document.getElementById(chartId);
        if (canvas?._chartInst) {
          const chart = canvas._chartInst;
          chart.data.datasets.forEach((ds, i) => {
            const col = enh.palette[i % enh.palette.length];
            if (chart.config.type === 'pie' || chart.config.type === 'doughnut') {
              ds.backgroundColor = enh.palette.map(c => c + 'cc');
            } else if (chart.config.type === 'line') {
              ds.borderColor     = col;
              ds.backgroundColor = col + '22';
            } else {
              ds.backgroundColor = col + 'cc';
              ds.borderColor     = col;
            }
          });
          chart.update('none');
        }
      }

      // Badge satırı ekle
      if (enh.badge_html) {
        const timeRow = msgDiv.querySelector('.msg-time')?.parentElement;
        if (timeRow) {
          const badgeWrap = document.createElement('div');
          badgeWrap.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;align-items:center';
          badgeWrap.innerHTML = `
            <span style="font-size:10px;color:#9ca3af;font-weight:600">✨ Gemini:</span>
            ${enh.badge_html}`;
          timeRow.insertAdjacentElement('afterend', badgeWrap);
        }
      }

      // Insights ekle
      if (enh.insights?.length) {
        const bubble = msgDiv.querySelector('.msg-bubble');
        if (bubble) {
          const insightBox = document.createElement('div');
          insightBox.style.cssText = `
            background:linear-gradient(135deg,#f0fdf4,#eff6ff);
            border:1px solid #bbf7d0;border-radius:8px;
            padding:10px 14px;margin-top:10px;
            display:flex;flex-direction:column;gap:4px`;
          insightBox.innerHTML = `
            <div style="font-size:10px;font-weight:700;color:#15803d;text-transform:uppercase;
                        letter-spacing:.05em;margin-bottom:2px">✨ Gemini Insights</div>
            ${enh.insights.map(ins =>
              `<div style="font-size:12px;color:#374151;line-height:1.5">${ins}</div>`
            ).join('')}
          `;
          bubble.appendChild(insightBox);
        }
      }

    } catch (e) {
      // Gemini hatası sessizce geç — ana içerik etkilenmesin
      console.debug('[Gemini enhance]', e.message);
    }
  }
  
  // ── Görselleştirme seçici ─────────────────────────────────────────────
  function _appendVizPicker(rows, container) {
    if (!rows?.length) return;

    const keys       = Object.keys(rows[0]).filter(k => !['id','fetched_at'].includes(k));
    const numericKeys = keys.filter(k => rows.every(r => r[k] === null || r[k] === '' || !isNaN(Number(r[k]))));
    const labelKeys   = keys.filter(k => !numericKeys.includes(k));

    // Sadece tek bir sayısal değer varsa zaten anlamsız, çıkma
    if (numericKeys.length === 0) return;

    const pickerId = 'vp-' + Date.now();

    const wrap = document.createElement('div');
    wrap.id    = pickerId;
    wrap.style.cssText = `
      display:flex;align-items:flex-start;gap:10px;margin-top:8px;
      animation:page-fade .3s ease;
    `;

    wrap.innerHTML = `
      <div style="width:30px;height:30px;background:#f59e0b;border-radius:8px;
                  display:flex;align-items:center;justify-content:center;
                  font-size:14px;flex-shrink:0;margin-top:2px">📊</div>
      <div style="flex:1;min-width:0">
        <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:14px 16px;
                    box-shadow:0 1px 4px rgba(0,0,0,.05)">

          <div style="font-size:13px;font-weight:600;color:#374151;margin-bottom:4px">
            Bu veriyi görselleştirelim mi?
          </div>
          <div style="font-size:12px;color:#9ca3af;margin-bottom:14px">
            Hangi kolonu eksen olarak kullanmamı istiyorsun?
          </div>

          <!-- Etiket (X) ekseni -->
          <div style="margin-bottom:12px">
            <div style="font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;
                        letter-spacing:.05em;margin-bottom:6px">Etiket (X ekseni)</div>
            <div style="display:flex;flex-wrap:wrap;gap:6px" id="${pickerId}-labels">
              ${[...labelKeys, ...numericKeys].map(k => `
                <button data-col="${k}" data-role="label"
                  onclick="_vizPickSelect(this, '${pickerId}')"
                  style="padding:5px 12px;border:1.5px solid #e5e7eb;border-radius:6px;
                         background:#f9fafb;color:#374151;font-size:12px;font-weight:500;
                         cursor:pointer;transition:all .15s;font-family:inherit">
                  ${k}
                </button>`).join('')}
            </div>
          </div>

          <!-- Değer (Y) ekseni -->
          <div style="margin-bottom:14px">
            <div style="font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;
                        letter-spacing:.05em;margin-bottom:6px">Değer (Y ekseni)</div>
            <div style="display:flex;flex-wrap:wrap;gap:6px" id="${pickerId}-values">
              ${numericKeys.map(k => `
                <button data-col="${k}" data-role="value"
                  onclick="_vizPickSelect(this, '${pickerId}')"
                  style="padding:5px 12px;border:1.5px solid #e5e7eb;border-radius:6px;
                         background:#f9fafb;color:#374151;font-size:12px;font-weight:500;
                         cursor:pointer;transition:all .15s;font-family:inherit">
                  ${k}
                </button>`).join('')}
            </div>
          </div>

          <!-- Grafik tipi -->
          <div style="margin-bottom:14px">
            <div style="font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;
                        letter-spacing:.05em;margin-bottom:6px">Grafik Tipi</div>
            <div style="display:flex;gap:6px">
              ${[
                {t:'bar',  icon:'📊', label:'Sütun'},
                {t:'line', icon:'📈', label:'Çizgi'},
                {t:'pie',  icon:'🥧', label:'Pasta'},
              ].map(g => `
                <button data-type="${g.t}" data-role="type"
                  onclick="_vizPickSelect(this, '${pickerId}')"
                  style="padding:5px 14px;border:1.5px solid ${g.t==='bar'?'#1a56db':'#e5e7eb'};
                         border-radius:6px;background:${g.t==='bar'?'#eff6ff':'#f9fafb'};
                         color:${g.t==='bar'?'#1d4ed8':'#374151'};font-size:12px;font-weight:500;
                         cursor:pointer;transition:all .15s;font-family:inherit">
                  ${g.icon} ${g.label}
                </button>`).join('')}
            </div>
          </div>

          <!-- Grafik çizme butonu -->
          <button id="${pickerId}-drawbtn"
            style="background:#1a56db;color:#fff;border:none;border-radius:8px;padding:8px 18px;
                   font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;
                   transition:background .15s"
            onmouseover="this.style.background='#1543a5'"
            onmouseout="this.style.background='#1a56db'">
            Grafiği Çiz
          </button>
        </div>

        <!-- Grafik alanı -->
        <div id="${pickerId}-chart" style="display:none;margin-top:10px;background:#fff;
             border:1px solid #e5e7eb;border-radius:12px;padding:16px">
          <div style="height:280px;position:relative">
            <canvas id="${pickerId}-canvas"></canvas>
          </div>
        </div>
      </div>
    `;

    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;

    // Butona rows verisini güvenli şekilde bağla
    if (!window._vizRows) window._vizRows = {};
    window._vizRows[pickerId] = rows.slice(0, 200);

    const drawBtn = document.getElementById(pickerId + '-drawbtn');
    if (drawBtn) {
      drawBtn.addEventListener('click', () => _vizPickDraw(pickerId));
    }
  }

  // Global: seçim state'i
  window._vizState = {};

  window._vizPickSelect = function(btn, pickerId) {
    const role = btn.dataset.role;
    if (!window._vizState[pickerId]) window._vizState[pickerId] = { type: 'bar' };

    const section = btn.parentElement;
    section.querySelectorAll('button').forEach(b => {
      b.style.borderColor = '#e5e7eb';
      b.style.background  = '#f9fafb';
      b.style.color       = '#374151';
    });
    btn.style.borderColor = '#1a56db';
    btn.style.background  = '#eff6ff';
    btn.style.color       = '#1d4ed8';

    if (role === 'label') window._vizState[pickerId].label = btn.dataset.col;
    if (role === 'value') window._vizState[pickerId].value = btn.dataset.col;
    if (role === 'type')  window._vizState[pickerId].type  = btn.dataset.type;
  };

  window._vizPickDraw = function(pickerId) {
    const state = window._vizState[pickerId] || {};
    const rows  = (window._vizRows || {})[pickerId] || [];

    const labelCol = state.label;
    const valueCol = state.value;
    const chartType = state.type || 'bar';

    if (!labelCol || !valueCol) {
      alert('Lütfen önce X ekseni ve Y ekseni seçin.');
      return;
    }

    // Gruplama: aynı etiket varsa topla
    const grouped = {};
    rows.forEach(r => {
      const lbl = String(r[labelCol] ?? '—');
      const val = Number(r[valueCol]) || 0;
      grouped[lbl] = (grouped[lbl] || 0) + val;
    });

    const labels   = Object.keys(grouped).slice(0, 30);
    const values   = labels.map(l => grouped[l]);
    const COLORS   = ['#1a56db','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#06b6d4','#f97316'];

    const chartArea = document.getElementById(pickerId + '-chart');
    const canvas    = document.getElementById(pickerId + '-canvas');
    if (!chartArea || !canvas) return;

    chartArea.style.display = 'block';

    // Eski chart'ı yok et
    if (canvas._chartInstance) canvas._chartInstance.destroy();

    const ds = {
      label          : valueCol,
      data           : values,
      borderWidth    : 2,
      borderRadius   : chartType === 'bar' ? 5 : 0,
      tension        : 0.4,
      fill           : chartType === 'line',
    };

    if (chartType === 'pie') {
      ds.backgroundColor = COLORS.map(c => c + 'cc');
      ds.borderColor     = '#fff';
    } else {
      ds.backgroundColor = chartType === 'line'
        ? '#1a56db22'
        : labels.map((_, i) => COLORS[i % COLORS.length] + 'cc');
      ds.borderColor = chartType === 'line'
        ? '#1a56db'
        : labels.map((_, i) => COLORS[i % COLORS.length]);
    }

    canvas._chartInstance = new Chart(canvas, {
      type: chartType,
      data: { labels, datasets: [ds] },
      options: {
        responsive          : true,
        maintainAspectRatio : false,
        animation           : { duration: 500 },
        plugins: {
          legend : { position: chartType === 'pie' ? 'right' : 'top', labels: { font: { size: 11 } } },
          tooltip: { backgroundColor: '#1e293b', cornerRadius: 8, padding: 10,
                     titleColor: '#f1f5f9', bodyColor: '#cbd5e1' },
        },
        scales: chartType !== 'pie' ? {
          y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,.04)' },
               ticks: { font: { size: 11 }, color: '#9ca3af' } },
          x: { grid: { display: false },
               ticks: { font: { size: 11 }, color: '#9ca3af',
                        maxRotation: labels.length > 8 ? 45 : 0 } },
        } : {},
      },
    });

    // Picker'ı daralt
    const pickerCard = document.querySelector(`#${pickerId} > div:last-child > div:first-child`);
    if (pickerCard) {
      pickerCard.style.display = 'none';
    }
    document.getElementById(pickerId + '-chart').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  function buildTable(rows) {
    if (!rows.length) return '';
    const keys = Object.keys(rows[0]).filter(k => k !== 'id' && k !== 'fetched_at');
    return `
      <div style="overflow-x:auto;margin-top:4px">
        <table style="width:100%;border-collapse:collapse;font-size:11px;min-width:500px">
          <thead>
            <tr style="background:var(--gray-50)">
              ${keys.map(k => `<th style="padding:6px 10px;text-align:left;border-bottom:1px solid var(--gray-200);color:var(--gray-600);font-weight:600;white-space:nowrap">${k}</th>`).join('')}
            </tr>
          </thead>
          <tbody>
            ${rows.map((r, i) => `
              <tr style="background:${i % 2 === 0 ? 'white' : 'var(--gray-50)'}">
                ${keys.map(k => `<td style="padding:5px 10px;border-bottom:1px solid var(--gray-100);color:var(--gray-700);white-space:nowrap;max-width:200px;overflow:hidden;text-overflow:ellipsis" title="${r[k] ?? ''}">${r[k] ?? '—'}</td>`).join('')}
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  function appendLoading() {
    const msgs = document.getElementById('chat-messages');
    const id   = 'loading-' + Date.now();
    const div  = document.createElement('div');
    div.id = id;
    div.style.cssText = 'display:flex;flex-direction:row;gap:10px;align-items:flex-start';
    div.innerHTML = `
      <div style="width:34px;height:34px;background:#1a56db;color:#fff;border-radius:8px;
                  font-size:11px;font-weight:700;display:flex;align-items:center;
                  justify-content:center;flex-shrink:0;margin-top:2px">AI</div>
      <div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:4px 16px 16px 16px;
                  padding:12px 16px;display:flex;align-items:center;gap:8px">
        <div style="display:flex;gap:4px">
          <span style="width:7px;height:7px;background:var(--gray-400);border-radius:50%;animation:bounce .8s infinite 0s"></span>
          <span style="width:7px;height:7px;background:var(--gray-400);border-radius:50%;animation:bounce .8s infinite .15s"></span>
          <span style="width:7px;height:7px;background:var(--gray-400);border-radius:50%;animation:bounce .8s infinite .3s"></span>
        </div>
        <span style="font-size:12px;color:var(--gray-500)" id="loading-status">SAP verileri sorgulanıyor...</span>
      </div>
    `;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;

    // Bounce animasyonu yoksa ekle
    if (!document.getElementById('bounce-style')) {
      const s = document.createElement('style');
      s.id = 'bounce-style';
      s.textContent = `@keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-6px)} }`;
      document.head.appendChild(s);
    }

    return id;
  }

  function removeLoading(id) {
    document.getElementById(id)?.remove();
  }

  // -------------------------------------------------------
  // Diğer
  // -------------------------------------------------------
  function useQuestion(q) {
    const input = document.getElementById('chat-input');
    if (input) {
      input.value = q;
      input.focus();
    }
  }

  // Takip sorusu çipi tıklandığında: input'u doldur ve hemen gönder
  function askFollowUp(q) {
    if (isLoading) return;
    const input = document.getElementById('chat-input');
    if (input) input.value = q;
    sendMessage();
  }

  function clearHistory() {
    chatHistory = [];
    const msgs = document.getElementById('chat-messages');
    if (msgs) {
      msgs.innerHTML = `
        <div id="empty-state" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:12px;color:var(--gray-400)">
          <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          <div style="font-size:14px;font-weight:500">Geçmiş temizlendi</div>
          <div style="font-size:12px;text-align:center">Yeni bir soru sormaya hazırsınız</div>
        </div>`;
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function _updateFilterBadge() {
    const f    = _collectFilters();
    const badge = document.getElementById('active-filter-badge');
    if (badge) {
      const count = Object.keys(f).length;
      badge.style.display = count > 0 ? 'block' : 'none';
      badge.textContent   = count > 0 ? `🔵 ${count} filtre aktif` : '';
    }
  }

  function toggleFilters() {
    const panel   = document.getElementById('filter-panel');
    const chevron = document.getElementById('filter-chevron');
    if (!panel) return;
    const open = panel.style.display === 'none';
    panel.style.display   = open ? 'block' : 'none';
    if (chevron) chevron.style.transform = open ? 'rotate(180deg)' : '';
  }

  // ── Oturum yönetimi ───────────────────────────────────────────────────────

  let _sessionSearch = '';

  async function _loadSessions() {
    const token = localStorage.getItem('sap_ai_token') || '';
    const qs    = _sessionSearch ? `?q=${encodeURIComponent(_sessionSearch)}` : '';
    try {
      const res  = await fetch(`/api/v1/chats/sessions${qs}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const list = await res.json();
      _renderSessionList(list);
    } catch { _renderSessionList([]); }
  }

  let _searchTimer = null;
  function searchSessions(value) {
    _sessionSearch = (value || '').trim().toLowerCase();
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(_loadSessions, 250);
  }

  function _renderSessionList(sessions) {
    const el = document.getElementById('session-list');
    if (!el) return;
    if (!sessions.length) {
      el.innerHTML = `<div style="padding:12px 14px;font-size:12px;color:var(--text-muted)">
        ${_sessionSearch ? 'Eşleşen sohbet yok' : 'Henüz sohbet yok'}</div>`;
      return;
    }
    el.innerHTML = sessions.map(s => {
      const isActive = s.id === _currentSid;
      const tags = (s.tags || []).map(t =>
        `<span style="display:inline-block;font-size:9px;padding:1px 6px;border-radius:8px;
                      background:rgba(26,86,219,.08);color:var(--primary);margin-right:3px">${t}</span>`
      ).join('');
      const pin = s.pinned ? '📌 ' : '';
      return `
        <div data-sid="${s.id}"
          style="padding:10px 14px;cursor:pointer;border-left:2px solid ${isActive ? 'var(--primary)' : 'transparent'};
                 background:${isActive ? 'rgba(26,86,219,.06)' : 'transparent'};transition:all .15s"
          onmouseover="if('${s.id}'!='${_currentSid}')this.style.background='var(--bg-soft)'"
          onmouseout="if('${s.id}'!='${_currentSid}')this.style.background='transparent'">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:6px">
            <div onclick="ChatsPage.loadSession('${s.id}')"
                 style="flex:1;min-width:0;font-size:13px;font-weight:${isActive?'600':'500'};color:var(--text);
                        white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
              ${pin}${s.title || 'Yeni Sohbet'}
            </div>
            <div style="position:relative;flex-shrink:0">
              <button onclick="event.stopPropagation();ChatsPage.toggleMenu('${s.id}',event)"
                      title="Seçenekler"
                      style="background:none;border:none;cursor:pointer;font-size:17px;line-height:1;
                             color:var(--text-muted);padding:2px 5px;border-radius:5px"
                      onmouseover="this.style.background='var(--bg-soft)'"
                      onmouseout="this.style.background='none'">⋮</button>
              <div id="menu-${s.id}" style="display:none;position:absolute;right:0;top:calc(100% + 2px);z-index:50;
                   background:var(--card);border:1px solid var(--border);border-radius:8px;
                   box-shadow:0 6px 18px rgba(0,0,0,.14);min-width:170px;padding:4px">
                <button onclick="event.stopPropagation();ChatsPage.togglePin('${s.id}',${s.pinned?0:1})"
                        style="width:100%;text-align:left;background:none;border:none;cursor:pointer;
                               font-size:13px;color:var(--text);padding:8px 10px;border-radius:6px;font-family:inherit"
                        onmouseover="this.style.background='var(--bg-soft)'"
                        onmouseout="this.style.background='none'">${s.pinned ? '📌 Sabitlemeyi kaldır' : '📌 Sabitle'}</button>
                <button onclick="event.stopPropagation();ChatsPage.deleteSession('${s.id}',event)"
                        style="width:100%;text-align:left;background:none;border:none;cursor:pointer;
                               font-size:13px;color:#dc2626;padding:8px 10px;border-radius:6px;font-family:inherit"
                        onmouseover="this.style.background='#fef2f2'"
                        onmouseout="this.style.background='none'">🗑 Sil</button>
              </div>
            </div>
          </div>
          ${tags ? `<div style="margin-top:4px">${tags}</div>` : ''}
          <div onclick="ChatsPage.loadSession('${s.id}')"
               style="font-size:11px;color:var(--text-muted);margin-top:3px;display:flex;justify-content:space-between">
            <span>${s.updated_at || s.created_at || ''}</span>
            <span>${s.message_count || 0} mesaj</span>
          </div>
        </div>`;
    }).join('');
  }

  async function togglePin(sid, pinned) {
    const token = localStorage.getItem('sap_ai_token') || '';
    try {
      await fetch(`/api/v1/chats/sessions/${sid}/pin`, {
        method : 'PATCH',
        headers: { 'Content-Type':'application/json', 'Authorization':`Bearer ${token}` },
        body   : JSON.stringify({ pinned: !!pinned }),
      });
      await _loadSessions();
    } catch (e) { console.warn('Pin hatası:', e); }
  }

  async function newChat() {
    const token = localStorage.getItem('sap_ai_token') || '';
    try {
      const res  = await fetch('/api/v1/chats/sessions', {
        method : 'POST',
        headers: { 'Content-Type':'application/json', 'Authorization':`Bearer ${token}` },
        body   : JSON.stringify({ title: 'Yeni Sohbet' }),
      });
      const data = await res.json();
      _currentSid = data.id;
    } catch { _currentSid = null; }

    // Ekranı sıfırla
    chatHistory = [];
    const msgs  = document.getElementById('chat-messages');
    if (msgs) msgs.innerHTML = `
      <div id="empty-state" style="display:flex;flex-direction:column;align-items:center;
           justify-content:center;height:100%;gap:12px;color:var(--text-muted)">
        <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <div style="font-size:14px;font-weight:500">Yeni bir sohbet başlatıldı</div>
        <div style="font-size:12px;text-align:center">Aşağıya sorunuzu yazın</div>
      </div>`;

    const title = document.getElementById('chat-session-title');
    if (title) title.textContent = 'SAP AI Sorgu Asistanı';

    await _loadSessions();
  }

  async function loadSession(sid) {
    _currentSid = sid;
    await _loadSessions();  // aktif vurguyu güncelle

    const token = localStorage.getItem('sap_ai_token') || '';
    const msgs  = document.getElementById('chat-messages');
    msgs.innerHTML = '';
    chatHistory    = [];

    try {
      // Oturum başlığını header'a yaz
      const sRes    = await fetch(`/api/v1/chats/sessions/${sid}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const session = await sRes.json();
      const title   = document.getElementById('chat-session-title');
      if (title) title.textContent = session.title || 'Sohbet';

      // Mesajları çek ve göster
      const mRes  = await fetch(`/api/v1/chats/sessions/${sid}/messages`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const messages = await mRes.json();
      messages.forEach(m => {
        if (m.role === 'user') {
          appendMessage('user', m.content || '');
        } else if (m.role === 'assistant') {
          // data_json varsa tam AI yanıtı olarak göster, yoksa sadece metin
          if (m.data && Object.keys(m.data).length) {
            appendAIMessage({
              summary    : m.content,
              rows       : [],
              count      : m.data.count || 0,
              sql        : m.data.sql || '',
              chart_type : m.data.chart_type || 'NONE',
              chart_data : m.data.chart_data || {},
              kpis       : m.data.kpis || [],
              highlights : m.data.highlights || [],
              follow_ups : m.data.follow_ups || [],
              sources    : m.data.sources || [],
              metrics_used: m.data.metrics_used || [],
              tables_used: m.data.tables_used || [],
              mode       : m.data.mode,
              live_success: m.data.live_success,
              live_message: m.data.live_message,
            });
          } else {
            appendMessage('assistant', m.content || '');
          }
        }
      });

      // Bu sohbete ait onay taleplerinin durum kartlarını yeniden çiz
      await _renderSessionApprovals(sid);

      msgs.scrollTop = msgs.scrollHeight;
    } catch (e) {
      console.error('[loadSession]', e);
    }
  }

  async function _renderSessionApprovals(sid) {
    const tok = localStorage.getItem('sap_ai_token') || '';
    let items = [];
    try {
      const res  = await fetch(`${window.API_BASE_URL}/approvals/by-session/${sid}`, {
        headers: { 'Authorization': `Bearer ${tok}` },
      });
      const data = await res.json();
      items = data.items || [];
    } catch { return; }

    items.forEach(a => {
      const jobStatus = a.job && a.job.status;
      if (a.status === 'REJECTED') {
        _appendApprovalNote('❌ Veri çekme talebi reddedildi', a.reason);
      } else if (a.status === 'EXPIRED') {
        _appendApprovalNote('⌛ Onay talebinin süresi doldu', a.reason);
      } else if (jobStatus === 'COMPLETED') {
        if (a.result && !a.result.error) {
          appendAIMessage(a.result);          // çözülen sonucu yeniden göster
        } else {
          _appendApprovalNote('✅ Veri çekildi (sonuç oluşturulamadı)', a.reason);
        }
      } else {
        // PENDING / APPROVED+işleniyor → canlı kart + polling devam
        _appendPendingApproval({
          approval_external_id: a.external_id,
          approval_id         : a.approval_id,
          reason              : a.reason,
        });
      }
    });
  }

  function _appendApprovalNote(title, reason) {
    const msgs = document.getElementById('chat-messages');
    const div  = document.createElement('div');
    div.style.cssText = 'display:flex;flex-direction:row;gap:10px;align-items:flex-start';
    div.innerHTML = `
      <div style="width:34px;height:34px;background:#94a3b8;color:#fff;border-radius:8px;
                  font-size:15px;display:flex;align-items:center;justify-content:center;
                  flex-shrink:0;margin-top:2px">i</div>
      <div style="flex:1;min-width:0;max-width:85%">
        <div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:4px 16px 16px 16px;padding:12px 16px">
          <div style="font-size:13px;font-weight:600;color:#475569">${title}</div>
          ${reason ? `<div style="font-size:12px;color:#64748b;margin-top:4px">${reason}</div>` : ''}
        </div>
      </div>`;
    msgs.appendChild(div);
  }

  function _closeAllMenus(exceptSid) {
    document.querySelectorAll('#session-list [id^="menu-"]').forEach(m => {
      if (m.id !== `menu-${exceptSid}`) m.style.display = 'none';
    });
  }

  function toggleMenu(sid, e) {
    e?.stopPropagation();
    const m = document.getElementById(`menu-${sid}`);
    if (!m) return;
    const willShow = m.style.display === 'none';
    _closeAllMenus(sid);
    m.style.display = willShow ? 'block' : 'none';
    if (!willShow) return;
    // Kaydırılabilir liste içinde alta sığmıyorsa yukarı aç (son sohbetlerde kırpılmasın)
    const listEl = document.getElementById('session-list');
    const mr = m.getBoundingClientRect();
    const lr = (listEl?.parentElement || listEl)?.getBoundingClientRect();
    if (lr && mr.bottom > lr.bottom) {
      m.style.top = 'auto';
      m.style.bottom = 'calc(100% + 2px)';
    } else {
      m.style.bottom = 'auto';
      m.style.top = 'calc(100% + 2px)';
    }
  }

  async function deleteSession(sid, e) {
    e?.stopPropagation();
    _closeAllMenus();
    if (!confirm('Bu sohbeti silmek istiyor musunuz?')) return;
    const token = localStorage.getItem('sap_ai_token') || '';
    await fetch(`/api/v1/chats/sessions/${sid}`, {
      method : 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (sid === _currentSid) await newChat();
    else await _loadSessions();
  }

  function init() {
    try {
      const u = JSON.parse(localStorage.getItem('sap_user') || '{}');
      window._currentUser = u.name || 'U';
    } catch {}

    // Sohbet menüsü (⋮) — dışarı tıklayınca kapansın (bir kez bağla)
    if (!window._chatMenuOutsideBound) {
      document.addEventListener('click', () => _closeAllMenus());
      window._chatMenuOutsideBound = true;
    }

    // Filtre değişimini izle
    ['filter-start','filter-end','filter-musteri','filter-city','filter-tdurum'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('change', _updateFilterBadge);
      if (el) el.addEventListener('input',  _updateFilterBadge);
    });

    // Oturumları yükle — varsa son oturumu aç, yoksa yenisini başlat
    _loadSessions().then(() => {
      const firstItem = document.querySelector('#session-list [data-sid]');
      if (firstItem) loadSession(firstItem.dataset.sid);
      else newChat();

      // Insights panelinden gelen pending question varsa input'a koy + odakla
      const pending = sessionStorage.getItem('insights_pending_question');
      if (pending) {
        sessionStorage.removeItem('insights_pending_question');
        setTimeout(() => {
          const input = document.getElementById('chat-input');
          if (input) {
            input.value = pending;
            input.dispatchEvent(new Event('input'));
            input.focus();
          }
        }, 300);
      }
    });
  }

  return { render, init, sendMessage, runFilter, onKeyDown, useQuestion, askFollowUp,
           clearHistory, newChat, loadSession, deleteSession, toggleFilters,
           searchSessions, togglePin, toggleMenu };
})();

window.ChatsPage = ChatsPage;
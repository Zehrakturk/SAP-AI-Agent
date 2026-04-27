/**
 * pages/chats.js
 * SAP AI Copilot — Gerçek soru-cevap arayüzü
 */

const ChatsPage = (() => {

  // Gerçek mesaj geçmişi (session bazlı, memory'de tutulur)
  let chatHistory = [];
  let isLoading   = false;

  // -------------------------------------------------------
  // Render
  // -------------------------------------------------------
  function render() {
    return `
    <div class="chat-layout" style="height:calc(100vh - 120px)">

      <!-- Sol panel: filtre + ipuçları -->
      <div class="chat-sidebar" style="display:flex;flex-direction:column;gap:0">

        <div class="chat-sidebar-header">
          <div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:var(--gray-500)">
            SAP Veri Sorgu
          </div>
        </div>

        <!-- Hızlı Filtre -->
        <div style="padding:14px;border-bottom:1px solid var(--gray-100)">
          <div style="font-size:11px;font-weight:600;color:var(--gray-500);text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px">
            Hızlı Filtre
          </div>

          <div style="display:flex;flex-direction:column;gap:8px">
            <div>
              <label style="font-size:11px;color:var(--gray-500);display:block;margin-bottom:3px">Başlangıç Tarihi</label>
              <input type="date" id="filter-start" class="input" style="width:100%;font-size:12px">
            </div>
            <div>
              <label style="font-size:11px;color:var(--gray-500);display:block;margin-bottom:3px">Bitiş Tarihi</label>
              <input type="date" id="filter-end" class="input" style="width:100%;font-size:12px">
            </div>
            <div>
              <label style="font-size:11px;color:var(--gray-500);display:block;margin-bottom:3px">Müşteri Adı</label>
              <input type="text" id="filter-musteri" class="input" placeholder="Müşteri ara..." style="width:100%;font-size:12px">
            </div>
            <div>
              <label style="font-size:11px;color:var(--gray-500);display:block;margin-bottom:3px">Şehir</label>
              <input type="text" id="filter-city" class="input" placeholder="Şehir ara..." style="width:100%;font-size:12px">
            </div>
            <div>
              <label style="font-size:11px;color:var(--gray-500);display:block;margin-bottom:3px">Transfer Durumu</label>
              <select id="filter-tdurum" class="select-input" style="width:100%;font-size:12px">
                <option value="">Tümü</option>
                <option value="01">01 - Oluşturuldu</option>
                <option value="02">02 - Planlandı</option>
                <option value="03">03 - Yüklendi</option>
                <option value="04">04 - Mal Çıkışı</option>
                <option value="05">05 - Teslim Edildi</option>
              </select>
            </div>
            <button class="btn btn-primary" style="width:100%;font-size:12px;margin-top:4px" onclick="ChatsPage.runFilter()">
              Filtrele
            </button>
          </div>
        </div>

        <!-- Örnek sorular -->
        <div style="padding:14px;flex:1;overflow-y:auto">
          <div style="font-size:11px;font-weight:600;color:var(--gray-500);text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px">
            Örnek Sorular
          </div>
          <div style="display:flex;flex-direction:column;gap:6px">
            ${[
              'Ocak 2024\'te kaç sevkiyat yapıldı?',
              'En çok sevkiyat yapılan şehir hangisi?',
              'MAL ÇIKIŞI YAPILDI durumundaki sevkiyatlar',
              'BATUHAN SARI müşterisinin siparişleri',
              'Deniz yolu ile yapılan sevkiyatlar',
              'Bu ay oluşturulan sevkiyat sayısı',
            ].map(q => `
              <button class="suggestion-btn" onclick="ChatsPage.useQuestion(this.textContent.trim())"
                style="text-align:left;background:var(--gray-50);border:1px solid var(--gray-200);border-radius:8px;padding:8px 10px;font-size:11px;color:var(--gray-700);cursor:pointer;transition:all .15s;line-height:1.4"
                onmouseover="this.style.background='var(--red-50)';this.style.borderColor='var(--red-200)'"
                onmouseout="this.style.background='var(--gray-50)';this.style.borderColor='var(--gray-200)'">
                ${q}
              </button>`).join('')}
          </div>
        </div>

        <!-- Geçmişi temizle -->
        <div style="padding:12px;border-top:1px solid var(--gray-100)">
          <button class="btn btn-ghost" style="width:100%;font-size:12px" onclick="ChatsPage.clearHistory()">
            Geçmişi Temizle
          </button>
        </div>
      </div>

      <!-- Sağ panel: chat alanı -->
      <div class="chat-main" style="display:flex;flex-direction:column;height:100%;overflow:hidden">

        <!-- Header -->
        <div class="chat-thread-header">
          <div class="msg-avatar" style="width:34px;height:34px;background:var(--red-600);color:white;display:flex;align-items:center;justify-content:center;border-radius:8px;font-weight:700;font-size:13px">AI</div>
          <div>
            <div style="font-size:14px;font-weight:600;color:var(--gray-900)">SAP AI Sorgu Asistanı</div>
            <div style="font-size:12px;color:var(--gray-500)">Türkçe soru sorun — SAP verilerinden yanıt alın</div>
          </div>
          <div style="margin-left:auto">
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
  async function sendMessage() {
    const input = document.getElementById('chat-input');
    const question = input.value.trim();
    if (!question || isLoading) return;

    input.value = '';
    input.style.height = '44px';
    hideEmptyState();
    isLoading = true;

    // Kullanıcı balonu
    appendMessage('user', question);

    // Yükleniyor balonu
    const loadingId = appendLoading();

    try {
      const res = await fetch(`${window.API_BASE_URL}/query/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
      });
      const data = await res.json();
      removeLoading(loadingId);

      if (data.error) {
        appendMessage('error', `Hata: ${data.error}`);
      } else {
        appendAIMessage(data);
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

  function appendMessage(role, text) {
    const msgs = document.getElementById('chat-messages');
    const div  = document.createElement('div');
    div.className = `message-row ${role}`;

    const isUser  = role === 'user';
    const isError = role === 'error';

    div.innerHTML = `
      <div class="msg-avatar ${isUser ? 'user' : 'assistant'}"
        style="${isUser ? '' : 'background:var(--red-600);color:white;border-radius:8px;font-size:11px;font-weight:700'}">
        ${isUser ? (window._currentUser?.charAt(0) || 'U') : 'AI'}
      </div>
      <div>
        <div class="msg-bubble ${isError ? 'error-bubble' : ''}"
          style="${isError ? 'background:var(--red-50);border:1px solid var(--red-200);color:var(--red-700)' : ''}">
          ${text.replace(/\n/g, '<br>')}
        </div>
        <div class="msg-time">${new Date().toLocaleTimeString('tr-TR', {hour:'2-digit',minute:'2-digit'})}</div>
      </div>
    `;

    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    chatHistory.push({ role, text });
  }

  function appendAIMessage(data) {
    const msgs = document.getElementById('chat-messages');
    const div  = document.createElement('div');
    div.className = 'message-row assistant';

    const rows = data.rows || [];
    const tableHtml = rows.length > 0 ? buildTable(rows.slice(0, 20)) : '';
    const moreText  = rows.length > 20 ? `<div style="font-size:11px;color:var(--gray-500);margin-top:6px">+ ${rows.length - 20} kayıt daha...</div>` : '';

    div.innerHTML = `
      <div class="msg-avatar assistant"
        style="background:var(--red-600);color:white;border-radius:8px;font-size:11px;font-weight:700">
        AI
      </div>
      <div style="flex:1;min-width:0">
        <div class="msg-bubble" style="max-width:100%">
          <div style="margin-bottom:${tableHtml ? '12px' : '0'}">${data.summary || ''}</div>
          ${tableHtml}
          ${moreText}
          ${data.sql ? `
          <details style="margin-top:10px">
            <summary style="font-size:11px;color:var(--gray-400);cursor:pointer">SQL sorgusunu görüntüle</summary>
            <pre style="font-size:11px;background:var(--gray-900);color:#7dd3fc;padding:10px;border-radius:6px;margin-top:6px;overflow-x:auto;white-space:pre-wrap">${data.sql}</pre>
          </details>` : ''}
        </div>
        <div class="msg-time">${new Date().toLocaleTimeString('tr-TR', {hour:'2-digit',minute:'2-digit'})} · SAP AI Copilot · ${data.count ?? rows.length} kayıt</div>
      </div>
    `;

    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }

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
    div.className = 'message-row assistant';
    div.innerHTML = `
      <div class="msg-avatar assistant" style="background:var(--red-600);color:white;border-radius:8px;font-size:11px;font-weight:700">AI</div>
      <div class="msg-bubble" style="display:flex;align-items:center;gap:8px">
        <div style="display:flex;gap:4px">
          <span style="width:7px;height:7px;background:var(--gray-400);border-radius:50%;animation:bounce .8s infinite 0s"></span>
          <span style="width:7px;height:7px;background:var(--gray-400);border-radius:50%;animation:bounce .8s infinite .15s"></span>
          <span style="width:7px;height:7px;background:var(--gray-400);border-radius:50%;animation:bounce .8s infinite .3s"></span>
        </div>
        <span style="font-size:12px;color:var(--gray-500)">SAP verileri sorgulanıyor...</span>
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

  function init() {
    // Mevcut kullanıcıyı al (varsa)
    try {
      const u = JSON.parse(localStorage.getItem('sap_user') || '{}');
      window._currentUser = u.name || 'U';
    } catch {}
  }

  return { render, init, sendMessage, runFilter, onKeyDown, useQuestion, clearHistory };
})();

window.ChatsPage = ChatsPage;
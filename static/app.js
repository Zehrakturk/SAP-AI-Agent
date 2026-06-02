/**
 * app.js
 * Main application: router, sidebar navigation, header management.
 */

const App = (() => {

  const ROUTES = [
    { id: 'dashboard',    label: 'Dashboard',       icon: dashIcon(),         page: () => DashboardPage    },
    { id: 'users',        label: 'Users',           icon: usersIcon(),        page: () => UsersPage        },
    { id: 'chats',        label: 'Chat Sessions',   icon: chatIcon(),         page: () => ChatsPage        },
    { id: 'logs',         label: 'AI Logs',         icon: logsIcon(),         page: () => LogsPage         },
    { id: 'integrations', label: 'Entegrasyonlar',  icon: integrationsIcon(), page: () => IntegrationsPage },
    { id: 'settings',     label: 'Settings',        icon: settingsIcon(),     page: () => SettingsPage     },
  ];

  const PAGE_META = {
    dashboard   : { title: 'Dashboard',          crumb: 'Overview' },
    users       : { title: 'User Management',    crumb: 'Users' },
    chats       : { title: 'Chat Sessions',      crumb: 'Chat Logs' },
    logs        : { title: 'AI Logs',            crumb: 'Activity Logs' },
    integrations: { title: 'Entegrasyonlar',     crumb: 'Integrations' },
    settings    : { title: 'Settings',           crumb: 'Configuration' },
  };

  let current = 'dashboard';
  let user    = null;

  // -------------------------------------------------------
  // Bootstrap
  // -------------------------------------------------------
  function boot() {
    Auth.guard((u) => {
      user = u;
      renderShell();
      navigate('dashboard');
      _startApprovalNotifier();
    });
  }

  // -------------------------------------------------------
  // Admin onay bildirimleri (Human-in-the-loop)
  // -------------------------------------------------------
  let _approvals  = [];
  let _notifTimer = null;

  function _isAdmin() { return user && String(user.role).toUpperCase() === 'ADMIN'; }

  function _startApprovalNotifier() {
    if (!_isAdmin()) return;
    _pollApprovals();
    if (_notifTimer) clearInterval(_notifTimer);
    _notifTimer = setInterval(_pollApprovals, 12000);  // 12 sn'de bir
  }

  async function _pollApprovals() {
    const tok = localStorage.getItem('sap_ai_token') || '';
    try {
      const res = await fetch('/api/v1/approvals/?status=PENDING&limit=50', {
        headers: { 'Authorization': `Bearer ${tok}` },
      });
      if (!res.ok) return;
      const data = await res.json();
      _approvals = data.items || [];
    } catch { return; }
    _updateNotifBadge();
    const panel = document.getElementById('notif-panel');
    if (panel && panel.style.display === 'block') _renderNotifPanel();
  }

  function _updateNotifBadge() {
    const n   = _approvals.length;
    const dot = document.getElementById('notif-dot');
    const cnt = document.getElementById('notif-count');
    if (cnt) { cnt.textContent = n; cnt.style.display = n ? 'flex' : 'none'; }
    if (dot) dot.style.display = n ? 'block' : 'none';
  }

  function toggleNotif() {
    const panel = document.getElementById('notif-panel');
    if (!panel) return;
    const open = panel.style.display !== 'block';
    panel.style.display = open ? 'block' : 'none';
    if (open) _renderNotifPanel();
  }

  function _renderNotifPanel() {
    const panel = document.getElementById('notif-panel');
    if (!panel) return;
    if (!_isAdmin()) {
      panel.innerHTML = '<div style="padding:16px;font-size:13px;color:#9ca3af">Onay yetkisi yok.</div>';
      return;
    }
    if (!_approvals.length) {
      panel.innerHTML = '<div style="padding:22px;text-align:center;font-size:13px;color:#9ca3af">Bekleyen onay yok ✅</div>';
      return;
    }
    panel.innerHTML =
      `<div style="padding:12px 16px;border-bottom:1px solid #f1f5f9;font-size:13px;font-weight:700;color:#111827">
         Bekleyen Onaylar (${_approvals.length})
       </div>` +
      _approvals.map(a => {
        const p = a.requested_params || {};
        const range = (p.start_date && p.end_date) ? `${p.start_date} → ${p.end_date}` : '';
        return `
        <div style="padding:12px 16px;border-bottom:1px solid #f5f5f5">
          <div style="font-size:12px;color:#374151;line-height:1.5;margin-bottom:8px">
            <b>#${a.id}</b> · ${a.reason || ''}
            ${range ? `<div style="color:#6b7280;margin-top:2px">📅 ${range}</div>` : ''}
            <div style="color:#9ca3af;margin-top:2px">Talep eden: ${a.user_id || '—'}</div>
          </div>
          <div style="display:flex;gap:8px">
            <button onclick="App.approveReq(${a.id})"
              style="flex:1;padding:6px;border:none;border-radius:6px;background:#16a34a;color:#fff;
                     font-size:12px;font-weight:600;cursor:pointer">Onayla</button>
            <button onclick="App.rejectReq(${a.id})"
              style="flex:1;padding:6px;border:1px solid #e5e7eb;border-radius:6px;background:#fff;
                     color:#dc2626;font-size:12px;font-weight:600;cursor:pointer">Reddet</button>
          </div>
        </div>`;
      }).join('');
  }

  async function approveReq(id) { await _decide(id, 'approve'); }
  async function rejectReq(id)  {
    const note = prompt('Reddetme nedeni (opsiyonel):') || '';
    await _decide(id, 'reject', note);
  }

  async function _decide(id, action, note) {
    const tok = localStorage.getItem('sap_ai_token') || '';
    try {
      const res = await fetch(`/api/v1/approvals/${id}/${action}`, {
        method : 'POST',
        headers: { 'Content-Type':'application/json', 'Authorization':`Bearer ${tok}` },
        body   : JSON.stringify({ note: note || '' }),
      });
      const r = await res.json();
      if (!res.ok) { alert(r.error || 'İşlem başarısız'); return; }
    } catch { alert('Bağlantı hatası'); return; }
    await _pollApprovals();
    _renderNotifPanel();
  }

  // -------------------------------------------------------
  // Shell (sidebar + header + content area)
  // -------------------------------------------------------
  function renderShell() {
    document.body.innerHTML = `
    <div class="app-shell">
      <!-- Sidebar -->
      <aside class="sidebar">
        <div class="sidebar-logo">
          <div class="logo-icon">AI</div>
          <div>
            <div class="logo-text">SAP AI Copilot</div>
            <div class="logo-sub">Admin Portal</div>
          </div>
        </div>

        <div class="sidebar-section-label">Navigation</div>
        <nav class="sidebar-nav" id="sidebar-nav">
          ${renderNav()}
        </nav>

        <div class="sidebar-user">
          <div class="user-avatar">${user.name.charAt(0)}</div>
          <div class="user-info">
            <div class="user-name">${user.name}</div>
            <div class="user-role">${user.role}</div>
          </div>
          <button onclick="App.logout()" title="Sign out" style="margin-left:auto;background:none;border:none;color:var(--gray-500);cursor:pointer;padding:4px;border-radius:4px;transition:color .2s" onmouseover="this.style.color='var(--red-400)'" onmouseout="this.style.color='var(--gray-500)'">
            <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
          </button>
        </div>
      </aside>

      <!-- Main -->
      <div class="main">
        <!-- Header -->
        <header class="header">
          <div class="header-left">
            <div class="page-title" id="page-title">Dashboard</div>
            <div class="page-breadcrumb" id="page-crumb">Portal / Overview</div>
          </div>
          <div class="header-right">
            <div class="status-indicator">
              <div class="status-dot"></div>
              System Online
            </div>
            <div style="position:relative">
              <button class="header-btn" title="Onaylar" id="notif-bell" onclick="App.toggleNotif()" style="position:relative">
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                  <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                <div class="notif-dot" id="notif-dot" style="display:none"></div>
                <span id="notif-count" style="display:none;position:absolute;top:-4px;right:-4px;min-width:16px;height:16px;
                      padding:0 4px;background:#ef4444;color:#fff;font-size:10px;font-weight:700;border-radius:9px;
                      align-items:center;justify-content:center"></span>
              </button>
              <div id="notif-panel" style="display:none;position:absolute;right:0;top:44px;width:360px;
                   max-height:460px;overflow-y:auto;background:#fff;border:1px solid #e5e7eb;border-radius:12px;
                   box-shadow:0 12px 32px rgba(0,0,0,.16);z-index:1000"></div>
            </div>
            <button class="header-btn" title="Refresh" onclick="App.refresh()">
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <polyline points="23 4 23 10 17 10"/>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
            </button>
          </div>
        </header>

        <!-- Page content areas -->
        ${ROUTES.map(r => `<div class="page-content" id="page-${r.id}"></div>`).join('')}
      </div>
    </div>
    `;
  }

  function renderNav() {
    return ROUTES.map(r => `
      <button class="nav-item ${r.id===current?'active':''}" id="nav-${r.id}" onclick="App.navigate('${r.id}')">
        <span class="nav-icon">${r.icon}</span>
        ${r.label}
        ${r.badge ? `<span class="nav-badge">${r.badge}</span>` : ''}
      </button>`).join('');
  }

  // -------------------------------------------------------
  // Navigate
  // -------------------------------------------------------
  function navigate(id) {
    if (current === id && document.getElementById(`page-${id}`)?.innerHTML) return;

    current = id;

    // Update header
    const meta = PAGE_META[id];
    document.getElementById('page-title').textContent = meta.title;
    document.getElementById('page-crumb').textContent = `Portal / ${meta.crumb}`;

    // Update nav
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.getElementById(`nav-${id}`)?.classList.add('active');

    // Hide all pages
    document.querySelectorAll('.page-content').forEach(el => el.classList.remove('active'));

    // Render & show
    const pageEl  = document.getElementById(`page-${id}`);
    const route   = ROUTES.find(r => r.id === id);
    const pageObj = route.page();

    pageEl.innerHTML = pageObj.render();
    pageEl.classList.add('active');
    pageObj.init();

    // Update URL hash
    window.location.hash = id;
  }

  function refresh() {
    const pageEl  = document.getElementById(`page-${current}`);
    const route   = ROUTES.find(r => r.id === current);
    const pageObj = route.page();
    pageEl.innerHTML = pageObj.render();
    pageObj.init();
  }

  function logout() {
    if (confirm('Sign out of the portal?')) {
      Auth.logout(() => { window.location.reload(); });
    }
  }

  return { boot, navigate, refresh, logout, toggleNotif, approveReq, rejectReq };

  // ---- SVG icon helpers ----
  function dashIcon() { return `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>`; }
  function usersIcon() { return `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`; }
  function chatIcon() { return `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`; }
  function logsIcon() { return `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`; }
  function settingsIcon() { return `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`; }
  function integrationsIcon() { return `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>`; }
})();

window.App = App;

// Boot on DOM ready
document.addEventListener('DOMContentLoaded', () => App.boot());
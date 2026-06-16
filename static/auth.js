/**
 * components/auth.js
 * Login screen and session guard for the AI Admin Portal.
 */

const Auth = (() => {

  const DEMO_USERS = [
    { username: 'admin',    password: 'admin123', name: 'System Admin',   role: 'ADMIN', company: 'ALL',      dept: 'IT' },
    { username: 'warmhaus', password: 'warm123',  name: 'Warmhaus User',  role: 'USER',  company: 'Warmhaus', dept: 'Lojistik' },
    { username: 'beycelik', password: 'bey123',   name: 'Beyçelik User',  role: 'USER',  company: 'Beycelik', dept: 'Üretim' },
    { username: 'demo',     password: 'demo123',  name: 'Demo Kullanıcı', role: 'USER',  company: 'Demo',     dept: 'Demo' },
  ];

  let currentUser = JSON.parse(sessionStorage.getItem('sap_ai_user') || 'null');

  // -------------------------------------------------------
  // Render login overlay
  // -------------------------------------------------------
  function showLogin(onSuccess) {
    // Remove existing
    document.getElementById('login-overlay')?.remove();

    const overlay = document.createElement('div');
    overlay.id = 'login-overlay';
    overlay.style.cssText = `
      position:fixed;inset:0;
      background:radial-gradient(ellipse at top left,rgba(26,86,219,0.12) 0%,transparent 60%),
                 radial-gradient(ellipse at bottom right,rgba(139,92,246,0.08) 0%,transparent 60%),
                 #f3f4f6;
      display:flex;align-items:center;justify-content:center;z-index:9999;
      font-family:'Inter',system-ui,sans-serif;
    `;

    overlay.innerHTML = `
      <div style="width:420px;max-width:calc(100vw - 32px)">

        <!-- Card -->
        <div style="background:#fff;border:1px solid #e5e7eb;border-radius:16px;
                    box-shadow:0 8px 24px rgba(0,0,0,0.08);overflow:hidden;">

          <!-- Top accent bar -->
          <div style="height:4px;background:linear-gradient(90deg,#1543a5,#1a56db,#60a5fa);"></div>

          <div style="padding:36px 36px 32px;">

            <!-- Logo -->
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:32px">
              <div style="width:44px;height:44px;background:#1a56db;border-radius:10px;
                          display:flex;align-items:center;justify-content:center;
                          font-size:16px;font-weight:800;color:white;
                          box-shadow:0 4px 14px rgba(26,86,219,0.35)">AI</div>
              <div>
                <div style="font-size:18px;font-weight:700;color:#111827;letter-spacing:-0.01em">SAP AI Copilot</div>
                <div style="font-size:11px;color:#9ca3af;letter-spacing:0.10em;text-transform:uppercase">Admin Portal</div>
              </div>
            </div>

            <!-- Canlı / Test sekmeleri -->
            <div style="display:flex;gap:4px;background:#f3f4f6;border-radius:10px;padding:4px;margin-bottom:22px">
              <button type="button" id="tab-live" class="login-tab" data-mode="live"
                style="flex:1;padding:9px 0;border:none;border-radius:7px;background:#fff;cursor:pointer;
                       font-family:inherit;font-size:13px;font-weight:700;color:#111827;
                       box-shadow:0 1px 3px rgba(0,0,0,0.10);transition:all .15s">Canlı</button>
              <button type="button" id="tab-test" class="login-tab" data-mode="test"
                style="flex:1;padding:9px 0;border:none;border-radius:7px;background:transparent;cursor:pointer;
                       font-family:inherit;font-size:13px;font-weight:600;color:#6b7280;
                       box-shadow:none;transition:all .15s">Test</button>
            </div>

            <h2 style="font-size:22px;font-weight:700;color:#111827;margin-bottom:4px;letter-spacing:-0.02em">Giriş Yap</h2>
            <p id="login-subtitle" style="font-size:13px;color:#6b7280;margin-bottom:18px">Firmanızı seçin ve bilgilerinizle giriş yapın.</p>

            <!-- Firma seçici -->
            <label style="display:block;font-size:12px;font-weight:600;color:#4b5563;margin-bottom:8px">Firma</label>

            <!-- CANLI grubu -->
            <div id="group-live" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:20px">
              <button type="button" class="login-company" data-company="Warmhaus" data-user="warmhaus"
                style="padding:12px 6px;border:2px solid #e5e7eb;border-radius:10px;background:#fff;cursor:pointer;
                       font-family:inherit;text-align:center;transition:all .15s">
                <div style="font-size:20px;line-height:1;margin-bottom:5px">🔥</div>
                <div style="font-size:12px;font-weight:700;color:#111827">Warmhaus</div>
              </button>
              <button type="button" class="login-company" data-company="Beycelik" data-user="beycelik"
                style="padding:12px 6px;border:2px solid #e5e7eb;border-radius:10px;background:#fff;cursor:pointer;
                       font-family:inherit;text-align:center;transition:all .15s">
                <div style="font-size:20px;line-height:1;margin-bottom:5px">⚙️</div>
                <div style="font-size:12px;font-weight:700;color:#111827">Beyçelik</div>
              </button>
              <button type="button" class="login-company" data-company="ALL" data-user="admin"
                style="padding:12px 6px;border:2px solid #e5e7eb;border-radius:10px;background:#fff;cursor:pointer;
                       font-family:inherit;text-align:center;transition:all .15s">
                <div style="font-size:20px;line-height:1;margin-bottom:5px">🛡️</div>
                <div style="font-size:12px;font-weight:700;color:#111827">Admin</div>
              </button>
            </div>

            <!-- TEST grubu -->
            <div id="group-test" style="display:none;margin-bottom:20px">
              <button type="button" class="login-company" data-company="Demo" data-user="demo"
                style="width:100%;padding:14px 6px;border:2px solid #e5e7eb;border-radius:10px;background:#fff;cursor:pointer;
                       font-family:inherit;text-align:center;transition:all .15s">
                <div style="font-size:20px;line-height:1;margin-bottom:5px">🧪</div>
                <div style="font-size:12px;font-weight:700;color:#111827">Demo (Test Verisi)</div>
              </button>
            </div>

            <!-- Error -->
            <div id="login-error" style="display:none;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);
                 border-radius:8px;padding:10px 14px;font-size:13px;color:#dc2626;margin-bottom:16px"></div>

            <!-- Username -->
            <div style="margin-bottom:16px">
              <label style="display:block;font-size:12px;font-weight:600;color:#4b5563;margin-bottom:6px">Kullanıcı Adı</label>
              <input id="login-user" type="text" placeholder="kullanıcı adı" autocomplete="username"
                style="width:100%;padding:10px 13px;background:#f9fafb;border:1px solid #e5e7eb;
                       border-radius:8px;color:#111827;font-size:14px;font-family:inherit;outline:none;transition:border-color .18s,box-shadow .18s"
                onfocus="this.style.borderColor='#1a56db';this.style.boxShadow='0 0 0 3px rgba(26,86,219,0.10)'"
                onblur="this.style.borderColor='#e5e7eb';this.style.boxShadow='none'"
              />
            </div>

            <!-- Password -->
            <div style="margin-bottom:26px">
              <label style="display:block;font-size:12px;font-weight:600;color:#4b5563;margin-bottom:6px">Şifre</label>
              <input id="login-pass" type="password" placeholder="••••••••" autocomplete="current-password"
                style="width:100%;padding:10px 13px;background:#f9fafb;border:1px solid #e5e7eb;
                       border-radius:8px;color:#111827;font-size:14px;font-family:inherit;outline:none;transition:border-color .18s,box-shadow .18s"
                onfocus="this.style.borderColor='#1a56db';this.style.boxShadow='0 0 0 3px rgba(26,86,219,0.10)'"
                onblur="this.style.borderColor='#e5e7eb';this.style.boxShadow='none'"
              />
            </div>

            <!-- Submit -->
            <button id="login-btn"
              style="width:100%;padding:11px;background:#1a56db;border:none;border-radius:8px;
                     color:white;font-size:14px;font-weight:600;font-family:inherit;cursor:pointer;
                     transition:all .18s;letter-spacing:0.01em"
              onmouseover="this.style.background='#1543a5';this.style.transform='translateY(-1px)';this.style.boxShadow='0 6px 20px rgba(26,86,219,0.30)'"
              onmouseout="this.style.background='#1a56db';this.style.transform='translateY(0)';this.style.boxShadow='none'"
            >Giriş Yap →</button>

            <div id="hint-live" style="font-size:11px;color:#9ca3af;margin-top:18px;text-align:center;line-height:1.7">
              <code style="background:#f3f4f6;padding:2px 7px;border-radius:4px;color:#4b5563">warmhaus / warm123</code> ·
              <code style="background:#f3f4f6;padding:2px 7px;border-radius:4px;color:#4b5563">beycelik / bey123</code><br>
              <code style="background:#f3f4f6;padding:2px 7px;border-radius:4px;color:#4b5563">admin / admin123</code>
            </div>
            <div id="hint-test" style="display:none;font-size:11px;color:#9ca3af;margin-top:18px;text-align:center;line-height:1.7">
              <code style="background:#f3f4f6;padding:2px 7px;border-radius:4px;color:#4b5563">demo / demo123</code><br>
              <span style="color:#0d9488">Test ortamı — yalnızca sentetik veri</span>
            </div>

          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    function _finish() {
      sessionStorage.setItem('sap_ai_user', JSON.stringify(currentUser));
      overlay.style.opacity = '0';
      overlay.style.transition = 'opacity .3s';
      setTimeout(() => { overlay.remove(); onSuccess(currentUser); }, 300);
    }

    function _showError(msg) {
      const errEl = document.getElementById('login-error');
      errEl.textContent = msg || 'Geçersiz kullanıcı adı veya şifre.';
      errEl.style.display = 'block';
      document.getElementById('login-pass').value = '';
    }

    async function attempt() {
      const u = document.getElementById('login-user').value.trim();
      const p = document.getElementById('login-pass').value;

      // 1) Gerçek backend login — token'ı (demo-token-{id}-{role}) buradan al.
      //    Bu token admin onay yetkisi + kullanıcı kimliği için ŞART.
      try {
        const res = await fetch('/api/v1/auth/login', {
          method : 'POST',
          headers: { 'Content-Type': 'application/json' },
          body   : JSON.stringify({ username: u, password: p }),
        });
        if (res.ok) {
          const data = await res.json();
          localStorage.setItem('sap_ai_token', data.access_token);   // ← kritik
          const usr = data.user || {};
          currentUser = { username: usr.username || u, name: usr.name || u,
                          role: usr.role || 'VIEWER', company: usr.company || 'ALL',
                          dept: usr.department || '' };
          _finish();
          return;
        }
        // 401/diğer → backend'de olmayan demo kullanıcılar için fallback'e düş
      } catch (e) {
        // backend'e ulaşılamadı → aşağıda demo fallback
      }

      // 2) Fallback: backend yoksa istemci-taraflı demo + sentetik token
      const match = DEMO_USERS.find(x => x.username === u && x.password === p);
      if (!match) { _showError(); return; }
      const idMap = { admin: 1, warmhaus: 10, beycelik: 11, demo: 20 };
      const demoId = idMap[match.username] || 99;
      localStorage.setItem('sap_ai_token', `demo-token-${demoId}-${match.role}-${match.company}`);
      currentUser = { username: match.username, name: match.name, role: match.role,
                      company: match.company, dept: match.dept };
      _finish();
    }

    document.getElementById('login-btn').addEventListener('click', attempt);
    document.getElementById('login-pass').addEventListener('keydown', e => { if (e.key === 'Enter') attempt(); });
    document.getElementById('login-user').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('login-pass').focus(); });

    // ── Canlı / Test sekmeleri: hangi kullanıcı grubu görünsün ─────────────
    function _selectMode(mode) {
      const isTest = mode === 'test';
      // sekme görünümü
      const tLive = document.getElementById('tab-live');
      const tTest = document.getElementById('tab-test');
      [[tLive, !isTest], [tTest, isTest]].forEach(([btn, active]) => {
        btn.style.background = active ? '#fff' : 'transparent';
        btn.style.color      = active ? '#111827' : '#6b7280';
        btn.style.fontWeight = active ? '700' : '600';
        btn.style.boxShadow  = active ? '0 1px 3px rgba(0,0,0,0.10)' : 'none';
      });
      // gruplar + ipuçları
      document.getElementById('group-live').style.display = isTest ? 'none' : 'grid';
      document.getElementById('group-test').style.display = isTest ? 'block' : 'none';
      document.getElementById('hint-live').style.display  = isTest ? 'none' : 'block';
      document.getElementById('hint-test').style.display  = isTest ? 'block' : 'none';
      // alt başlık
      document.getElementById('login-subtitle').textContent = isTest
        ? 'Test ortamı — sentetik veriyle giriş yapın.'
        : 'Firmanızı seçin ve bilgilerinizle giriş yapın.';
      // seçimleri/sıfırla
      overlay.querySelectorAll('.login-company').forEach(b => {
        b.style.borderColor = '#e5e7eb'; b.style.background = '#fff'; b.style.boxShadow = 'none';
      });
      document.getElementById('login-user').value = '';
      document.getElementById('login-pass').value = '';
      document.getElementById('login-error').style.display = 'none';
    }
    overlay.querySelectorAll('.login-tab').forEach(btn => {
      btn.addEventListener('click', () => _selectMode(btn.dataset.mode));
    });

    // ── Firma seçici: highlight + kullanıcı adını otomatik doldur ──────────
    const _COMP_ACCENT = { Warmhaus: '#ea580c', Beycelik: '#1a56db', ALL: '#7c3aed', Demo: '#0d9488' };
    function _selectCompany(btn) {
      overlay.querySelectorAll('.login-company').forEach(b => {
        b.style.borderColor = '#e5e7eb';
        b.style.background   = '#fff';
        b.style.boxShadow    = 'none';
      });
      const accent = _COMP_ACCENT[btn.dataset.company] || '#1a56db';
      btn.style.borderColor = accent;
      btn.style.background   = accent + '0d';
      btn.style.boxShadow    = `0 0 0 3px ${accent}22`;
      // kullanıcı adını doldur, şifreye odaklan
      const userInput = document.getElementById('login-user');
      userInput.value = btn.dataset.user;
      document.getElementById('login-pass').focus();
    }
    overlay.querySelectorAll('.login-company').forEach(btn => {
      btn.addEventListener('click', () => _selectCompany(btn));
    });

    setTimeout(() => document.getElementById('login-user').focus(), 100);
  }

  // -------------------------------------------------------
  // Guard: call onAuth if already logged in, else showLogin
  // -------------------------------------------------------
  function guard(onAuth) {
    if (currentUser) {
      // Önceki oturumda token yoksa (eski sürüm) sentetik demo token üret —
      // aksi halde admin onay yetkisi / firma filtresi çalışmaz.
      if (!localStorage.getItem('sap_ai_token')) {
        const idMap = { admin: 1, warmhaus: 10, beycelik: 11, demo: 20 };
        const demoId = idMap[currentUser.username] || 99;
        const comp   = currentUser.company || 'ALL';
        localStorage.setItem('sap_ai_token', `demo-token-${demoId}-${currentUser.role || 'USER'}-${comp}`);
      }
      onAuth(currentUser);
    } else {
      showLogin(onAuth);
    }
  }

  function logout(onLogout) {
    currentUser = null;
    sessionStorage.removeItem('sap_ai_user');
    localStorage.removeItem('sap_ai_token');
    if (onLogout) onLogout();
  }

  function getUser() { return currentUser; }

  return { guard, showLogin, logout, getUser };
})();

window.Auth = Auth;
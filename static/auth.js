/**
 * components/auth.js
 * Login screen and session guard for the AI Admin Portal.
 */

const Auth = (() => {

  const DEMO_USERS = [
    { username: 'admin',      password: 'admin123',   name: 'System Admin',   role: 'ADMIN',       dept: 'IT' },
    { username: 'procurement',password: 'proc123',    name: 'Alice Müller',   role: 'PROCUREMENT',  dept: 'Procurement' },
    { username: 'finance',    password: 'fin123',     name: 'Robert Kaya',    role: 'FINANCE',      dept: 'Finance' },
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

            <h2 style="font-size:22px;font-weight:700;color:#111827;margin-bottom:4px;letter-spacing:-0.02em">Giriş Yap</h2>
            <p style="font-size:13px;color:#6b7280;margin-bottom:24px">Portala erişmek için bilgilerinizi girin.</p>

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

            <p style="font-size:12px;color:#9ca3af;margin-top:20px;text-align:center">
              Demo: <code style="background:#f3f4f6;padding:2px 8px;border-radius:4px;color:#4b5563;font-size:11px">admin / admin123</code>
            </p>

          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    function attempt() {
      const u = document.getElementById('login-user').value.trim();
      const p = document.getElementById('login-pass').value;
      const match = DEMO_USERS.find(x => x.username === u && x.password === p);
      const errEl = document.getElementById('login-error');

      if (!match) {
        errEl.textContent = 'Invalid username or password.';
        errEl.style.display = 'block';
        document.getElementById('login-pass').value = '';
        return;
      }

      currentUser = { username: match.username, name: match.name, role: match.role, dept: match.dept };
      sessionStorage.setItem('sap_ai_user', JSON.stringify(currentUser));
      overlay.style.opacity = '0';
      overlay.style.transition = 'opacity .3s';
      setTimeout(() => { overlay.remove(); onSuccess(currentUser); }, 300);
    }

    document.getElementById('login-btn').addEventListener('click', attempt);
    document.getElementById('login-pass').addEventListener('keydown', e => { if (e.key === 'Enter') attempt(); });
    document.getElementById('login-user').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('login-pass').focus(); });

    setTimeout(() => document.getElementById('login-user').focus(), 100);
  }

  // -------------------------------------------------------
  // Guard: call onAuth if already logged in, else showLogin
  // -------------------------------------------------------
  function guard(onAuth) {
    if (currentUser) {
      onAuth(currentUser);
    } else {
      showLogin(onAuth);
    }
  }

  function logout(onLogout) {
    currentUser = null;
    sessionStorage.removeItem('sap_ai_user');
    if (onLogout) onLogout();
  }

  function getUser() { return currentUser; }

  return { guard, showLogin, logout, getUser };
})();

window.Auth = Auth;
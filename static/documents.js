/* static/documents.js — "Belgeler" sayfası (firma bazında PDF RAG) */

const DocumentsPage = (() => {

  function _token() { return localStorage.getItem('sap_ai_token') || ''; }

  function render() {
    return `
      <div style="max-width:900px;margin:0 auto">
        <div class="card" style="margin-bottom:16px">
          <div class="card-header"><h3 class="card-title" style="margin:0">📄 Belgeler (PDF Bilgi Tabanı)</h3></div>
          <div class="card-body">
            <p style="font-size:13px;color:var(--text-muted,#6b7280);margin-bottom:14px">
              Yüklediğiniz PDF'ler firmanıza özel bilgi tabanına eklenir. "Nasıl yapılır",
              "bu hatayı nasıl çözerim", "yol haritası" gibi sorularda AI bu belgelerden yanıt verir.
            </p>
            <div id="doc-drop"
                 style="border:2px dashed #cbd5e1;border-radius:12px;padding:28px;text-align:center;
                        cursor:pointer;transition:all .15s;background:#f9fafb">
              <div style="font-size:30px;margin-bottom:8px">⬆️</div>
              <div style="font-size:14px;font-weight:600;color:#374151">PDF yüklemek için tıklayın</div>
              <div style="font-size:12px;color:#9ca3af;margin-top:4px">veya dosyayı buraya sürükleyin</div>
              <input id="doc-file" type="file" accept="application/pdf" style="display:none">
            </div>
            <div id="doc-upload-status" style="font-size:13px;margin-top:12px"></div>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h3 class="card-title" style="margin:0">Yüklü Belgeler</h3></div>
          <div id="doc-list" style="padding:4px 0"></div>
        </div>
      </div>
    `;
  }

  function init() {
    const drop = document.getElementById('doc-drop');
    const file = document.getElementById('doc-file');
    if (drop && file) {
      drop.addEventListener('click', () => file.click());
      drop.addEventListener('dragover', e => { e.preventDefault(); drop.style.borderColor = '#1a56db'; });
      drop.addEventListener('dragleave', () => { drop.style.borderColor = '#cbd5e1'; });
      drop.addEventListener('drop', e => {
        e.preventDefault(); drop.style.borderColor = '#cbd5e1';
        if (e.dataTransfer.files[0]) _upload(e.dataTransfer.files[0]);
      });
      file.addEventListener('change', () => { if (file.files[0]) _upload(file.files[0]); });
    }
    _loadList();
  }

  async function _upload(f) {
    const status = document.getElementById('doc-upload-status');
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      status.innerHTML = '<span style="color:#dc2626">Yalnızca PDF yükleyebilirsiniz.</span>';
      return;
    }
    status.innerHTML = `<span style="color:#6b7280">⏳ "${f.name}" yükleniyor ve indeksleniyor...</span>`;
    const fd = new FormData(); fd.append('file', f);
    try {
      const res = await fetch('/api/v1/documents/', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${_token()}` },
        body: fd,
      });
      const r = await res.json();
      if (!res.ok) throw new Error(r.error || `HTTP ${res.status}`);
      status.innerHTML = `<span style="color:#16a34a">✅ "${r.filename}" eklendi — ${r.pages} sayfa, ${r.chunks} parça indekslendi.</span>`;
      _loadList();
    } catch (e) {
      status.innerHTML = `<span style="color:#dc2626">Hata: ${e.message}</span>`;
    }
  }

  async function _loadList() {
    const el = document.getElementById('doc-list');
    if (!el) return;
    try {
      const res = await fetch('/api/v1/documents/', { headers: { 'Authorization': `Bearer ${_token()}` } });
      const data = await res.json();
      const items = data.items || [];
      if (!items.length) {
        el.innerHTML = `<div style="padding:18px;text-align:center;font-size:13px;color:#9ca3af">Henüz belge yok</div>`;
        return;
      }
      el.innerHTML = items.map(d => `
        <div style="display:flex;align-items:center;justify-content:space-between;
                    padding:12px 16px;border-bottom:1px solid #f1f5f9">
          <div style="min-width:0">
            <div style="font-size:13px;font-weight:600;color:#111827;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
              📄 ${d.filename}</div>
            <div style="font-size:11px;color:#9ca3af;margin-top:2px">
              ${d.page_count||0} sayfa · ${d.chunk_count||0} parça · ${d.company||''} · ${d.uploaded_at||''}</div>
          </div>
          <button onclick="DocumentsPage.remove(${d.id})"
            style="flex-shrink:0;padding:5px 12px;border:1px solid #fecaca;border-radius:6px;background:#fff;
                   color:#dc2626;font-size:12px;font-weight:600;cursor:pointer">Sil</button>
        </div>`).join('');
    } catch {
      el.innerHTML = `<div style="padding:18px;color:#dc2626;font-size:13px">Liste yüklenemedi</div>`;
    }
  }

  async function remove(id) {
    if (!confirm('Bu belgeyi silmek istiyor musunuz?')) return;
    try {
      await fetch(`/api/v1/documents/${id}`, {
        method: 'DELETE', headers: { 'Authorization': `Bearer ${_token()}` },
      });
      _loadList();
    } catch (e) { alert('Silinemedi: ' + e.message); }
  }

  return { render, init, remove };
})();

window.DocumentsPage = DocumentsPage;

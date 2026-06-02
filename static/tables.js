/**
 * components/tables.js
 * Reusable data-table component with sort, filter, and pagination.
 */

const Tables = (() => {

  /**
   * Build a DataTable inside `containerId`.
   * @param {string}   containerId  – host element ID
   * @param {string[]} columns      – [{key, label, render?, sortable?, width?}]
   * @param {Array}    rows         – raw data rows
   * @param {Object}   opts         – { pageSize, onRowClick, actionButtons }
   */
  function create(containerId, columns, rows, opts = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const pageSize = opts.pageSize || 10;
    let currentPage = 1;
    let sortKey = null;
    let sortDir = 'asc';
    let filtered = [...rows];

    function sortedFiltered() {
      let data = [...filtered];
      if (sortKey) {
        data.sort((a, b) => {
          const av = a[sortKey] ?? '';
          const bv = b[sortKey] ?? '';
          const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true });
          return sortDir === 'asc' ? cmp : -cmp;
        });
      }
      return data;
    }

    function paginated(data) {
      const start = (currentPage - 1) * pageSize;
      return data.slice(start, start + pageSize);
    }

    function render() {
      const data  = sortedFiltered();
      const page  = paginated(data);
      const total = data.length;
      const pages = Math.ceil(total / pageSize);

      container.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                ${columns.map(col => `
                  <th ${col.width ? `style="width:${col.width}"` : ''}
                      ${col.sortable !== false ? `class="sortable-th" data-key="${col.key}" style="cursor:pointer;user-select:none"` : ''}>
                    <span style="display:inline-flex;align-items:center;gap:5px">
                      ${col.label}
                      ${col.sortable !== false ? `<svg width="10" height="10" viewBox="0 0 10 10" fill="none" style="opacity:${sortKey===col.key?1:0.3}">
                        ${sortKey===col.key && sortDir==='asc'
                          ? '<path d="M5 2L9 8H1L5 2Z" fill="currentColor"/>'
                          : '<path d="M5 8L1 2H9L5 8Z" fill="currentColor"/>'}
                      </svg>` : ''}
                    </span>
                  </th>`).join('')}
                ${opts.actionButtons ? '<th style="width:100px">Actions</th>' : ''}
              </tr>
            </thead>
            <tbody>
              ${page.length === 0
                ? `<tr><td colspan="${columns.length + (opts.actionButtons ? 1 : 0)}" style="text-align:center;padding:36px;color:var(--gray-400)">No records found.</td></tr>`
                : page.map((row, idx) => `
                    <tr ${opts.onRowClick ? `class="row-clickable" data-idx="${(currentPage-1)*pageSize+idx}" style="cursor:pointer"` : ''}>
                      ${columns.map(col => `
                        <td class="${col.bold ? 'td-bold' : ''}">
                          ${col.render ? col.render(row[col.key], row) : (row[col.key] ?? '—')}
                        </td>`).join('')}
                      ${opts.actionButtons ? `<td>${opts.actionButtons(row)}</td>` : ''}
                    </tr>`).join('')}
            </tbody>
          </table>
        </div>
        ${pages > 1 ? `
        <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-top:1px solid var(--card-border)">
          <span style="font-size:12px;color:var(--gray-500)">
            ${(currentPage-1)*pageSize+1}–${Math.min(currentPage*pageSize,total)} of ${total} records
          </span>
          <div style="display:flex;gap:4px">
            <button class="btn btn-ghost btn-sm" id="pg-prev" ${currentPage===1?'disabled':''}>‹ Prev</button>
            ${Array.from({length:pages},(_, i)=>i+1).filter(p=> p===1||p===pages||Math.abs(p-currentPage)<=1).reduce((acc,p,i,arr)=>{
                if(i>0 && p-arr[i-1]>1) acc.push('…');
                acc.push(p); return acc;
              },[]).map(p=> typeof p==='number'
                ? `<button class="btn btn-sm ${p===currentPage?'btn-primary':'btn-ghost'}" data-page="${p}">${p}</button>`
                : `<span style="padding:5px 4px;color:var(--gray-400)">…</span>`).join('')}
            <button class="btn btn-ghost btn-sm" id="pg-next" ${currentPage===pages?'disabled':''}>Next ›</button>
          </div>
        </div>` : `
        <div style="padding:10px 16px;border-top:1px solid var(--card-border)">
          <span style="font-size:12px;color:var(--gray-500)">${total} record${total!==1?'s':''}</span>
        </div>`}
      `;

      // Sort listeners
      container.querySelectorAll('.sortable-th').forEach(th => {
        th.addEventListener('click', () => {
          const key = th.dataset.key;
          if (sortKey === key) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
          else { sortKey = key; sortDir = 'asc'; }
          currentPage = 1;
          render();
        });
      });

      // Pagination
      container.querySelectorAll('[data-page]').forEach(btn => {
        btn.addEventListener('click', () => { currentPage = +btn.dataset.page; render(); });
      });
      const prev = container.querySelector('#pg-prev');
      const next = container.querySelector('#pg-next');
      if (prev) prev.addEventListener('click', () => { currentPage--; render(); });
      if (next) next.addEventListener('click', () => { currentPage++; render(); });

      // Row click
      if (opts.onRowClick) {
        container.querySelectorAll('.row-clickable').forEach(tr => {
          tr.addEventListener('click', (e) => {
            if (e.target.closest('button, a')) return;
            const idx = +tr.dataset.idx;
            opts.onRowClick(sortedFiltered()[idx]);
          });
        });
      }
    }

    function search(query) {
      const q = query.toLowerCase();
      filtered = rows.filter(row =>
        columns.some(col => String(row[col.key] ?? '').toLowerCase().includes(q))
      );
      currentPage = 1;
      render();
    }

    function updateRows(newRows) {
      rows = newRows;
      filtered = [...rows];
      currentPage = 1;
      render();
    }

    render();
    return { search, updateRows, render };
  }

  return { create };
})();

window.Tables = Tables;
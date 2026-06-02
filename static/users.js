/**
 * pages/users.js
 * User Management – list, create, edit, delete, role/department assignment.
 */

const UsersPage = (() => {

  const ROLES = ['ADMIN', 'PROCUREMENT', 'FINANCE', 'LOGISTICS', 'WAREHOUSE', 'VIEWER'];
  const DEPTS = ['IT', 'Procurement', 'Finance', 'Logistics', 'Warehouse', 'Management'];

  const MOCK_USERS = [
    { id: 1, username: 'admin',      name: 'System Admin',    role: 'ADMIN',       department: 'IT',          status: 'active',   created: '2025-01-10', lastLogin: '2m ago' },
    { id: 2, username: 'a.mueller',  name: 'Alice Müller',    role: 'PROCUREMENT', department: 'Procurement', status: 'active',   created: '2025-02-14', lastLogin: '15m ago' },
    { id: 3, username: 'r.kaya',     name: 'Robert Kaya',     role: 'FINANCE',     department: 'Finance',     status: 'active',   created: '2025-02-20', lastLogin: '1h ago' },
    { id: 4, username: 'h.schmidt',  name: 'Heinz Schmidt',   role: 'PROCUREMENT', department: 'Procurement', status: 'active',   created: '2025-03-01', lastLogin: '3h ago' },
    { id: 5, username: 'm.weber',    name: 'Marta Weber',     role: 'FINANCE',     department: 'Finance',     status: 'inactive', created: '2025-03-05', lastLogin: '2d ago' },
    { id: 6, username: 'k.yilmaz',  name: 'Kemal Yılmaz',   role: 'LOGISTICS',   department: 'Logistics',   status: 'active',   created: '2025-03-08', lastLogin: '5h ago' },
    { id: 7, username: 'j.bauer',   name: 'Jana Bauer',      role: 'WAREHOUSE',   department: 'Warehouse',   status: 'active',   created: '2025-03-10', lastLogin: '1d ago' },
    { id: 8, username: 'p.frank',   name: 'Paul Frank',      role: 'VIEWER',      department: 'Management',  status: 'inactive', created: '2025-03-11', lastLogin: '5d ago' },
  ];

  let users = [...MOCK_USERS];
  let table  = null;
  let editingId = null;

  // ---- Badge helpers ----
  function roleBadge(role) {
    const map = { ADMIN:'badge-red', PROCUREMENT:'badge-blue', FINANCE:'badge-green', LOGISTICS:'badge-amber', WAREHOUSE:'badge-purple', VIEWER:'badge-gray' };
    return `<span class="badge ${map[role]||'badge-gray'}">${role}</span>`;
  }

  function statusBadge(s) {
    return s === 'active'
      ? `<span class="badge badge-green">● Active</span>`
      : `<span class="badge badge-gray">○ Inactive</span>`;
  }

  function actionBtns(row) {
    return `
      <div style="display:flex;gap:5px">
        <button class="btn btn-ghost btn-sm btn-icon" title="Edit" onclick="UsersPage.openEdit(${row.id})">
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </button>
        <button class="btn btn-ghost btn-sm btn-icon" title="Delete" style="color:var(--red-700)" onclick="UsersPage.confirmDelete(${row.id})">
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
            <path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
          </svg>
        </button>
      </div>`;
  }

  // ---- HTML ----
  function render() {
    return `
    <div class="card mb-20">
      <div class="card-header">
        <div>
          <div class="card-title">User Management</div>
          <div class="card-subtitle">${users.length} users registered</div>
        </div>
        <div style="display:flex;gap:10px;align-items:center">
          <div class="search-input-wrap" style="width:240px">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input class="input" id="user-search" placeholder="Search users…" oninput="UsersPage.onSearch(this.value)">
          </div>
          <select class="select-input" style="width:150px" id="role-filter" onchange="UsersPage.onRoleFilter(this.value)">
            <option value="">All Roles</option>
            ${ROLES.map(r=>`<option value="${r}">${r}</option>`).join('')}
          </select>
          <button class="btn btn-primary" onclick="UsersPage.openCreate()">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Add User
          </button>
        </div>
      </div>
      <div id="users-table-host"></div>
    </div>

    <!-- User Modal -->
    <div class="modal-overlay" id="user-modal">
      <div class="modal">
        <div class="modal-header">
          <div class="modal-title" id="modal-heading">Add User</div>
          <button class="modal-close" onclick="UsersPage.closeModal()">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>Full Name</label>
            <input class="input" id="u-name" placeholder="e.g. Alice Müller">
          </div>
          <div class="form-group">
            <label>Username</label>
            <input class="input" id="u-username" placeholder="e.g. a.mueller">
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
            <div class="form-group">
              <label>Role</label>
              <select class="select-input" id="u-role">
                ${ROLES.map(r=>`<option value="${r}">${r}</option>`).join('')}
              </select>
            </div>
            <div class="form-group">
              <label>Department</label>
              <select class="select-input" id="u-dept">
                ${DEPTS.map(d=>`<option value="${d}">${d}</option>`).join('')}
              </select>
            </div>
          </div>
          <div class="form-group">
            <label>Status</label>
            <select class="select-input" id="u-status">
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" onclick="UsersPage.closeModal()">Cancel</button>
          <button class="btn btn-primary" onclick="UsersPage.saveUser()">Save User</button>
        </div>
      </div>
    </div>

    <!-- Confirm Delete -->
    <div class="modal-overlay" id="delete-modal">
      <div class="modal" style="width:380px">
        <div class="modal-header">
          <div class="modal-title" style="color:var(--red-700)">Delete User</div>
          <button class="modal-close" onclick="UsersPage.closeDeleteModal()">✕</button>
        </div>
        <div class="modal-body">
          <p style="font-size:14px;color:var(--gray-700)">Are you sure you want to delete user <strong id="delete-user-name"></strong>? This action cannot be undone.</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" onclick="UsersPage.closeDeleteModal()">Cancel</button>
          <button class="btn btn-danger" onclick="UsersPage.deleteUser()">Delete</button>
        </div>
      </div>
    </div>
    `;
  }

  let deleteTargetId = null;

  function init() {
    table = Tables.create('users-table-host',
      [
        { key: 'name',       label: 'Name',       bold: true, render: (v,r) => `<div style="font-weight:600;color:var(--gray-900)">${v}</div><div style="font-size:11px;color:var(--gray-400)">@${r.username}</div>` },
        { key: 'role',       label: 'Role',        render: roleBadge },
        { key: 'department', label: 'Department' },
        { key: 'status',     label: 'Status',      render: statusBadge },
        { key: 'lastLogin',  label: 'Last Login',  sortable: false },
        { key: 'created',    label: 'Created' },
      ],
      users,
      { pageSize: 8, actionButtons: actionBtns }
    );
  }

  function onSearch(q) {
    if (!table) return;
    table.search(q);
  }

  function onRoleFilter(role) {
    if (!table) return;
    const filtered = role ? users.filter(u => u.role === role) : users;
    table.updateRows(filtered);
  }

  function openCreate() {
    editingId = null;
    document.getElementById('modal-heading').textContent = 'Add User';
    document.getElementById('u-name').value = '';
    document.getElementById('u-username').value = '';
    document.getElementById('u-role').value = 'PROCUREMENT';
    document.getElementById('u-dept').value = 'Procurement';
    document.getElementById('u-status').value = 'active';
    document.getElementById('user-modal').classList.add('open');
  }

  function openEdit(id) {
    const u = users.find(x => x.id === id);
    if (!u) return;
    editingId = id;
    document.getElementById('modal-heading').textContent = 'Edit User';
    document.getElementById('u-name').value = u.name;
    document.getElementById('u-username').value = u.username;
    document.getElementById('u-role').value = u.role;
    document.getElementById('u-dept').value = u.department;
    document.getElementById('u-status').value = u.status;
    document.getElementById('user-modal').classList.add('open');
  }

  function closeModal()       { document.getElementById('user-modal').classList.remove('open'); }
  function closeDeleteModal() { document.getElementById('delete-modal').classList.remove('open'); }

  function saveUser() {
    const name  = document.getElementById('u-name').value.trim();
    const uname = document.getElementById('u-username').value.trim();
    if (!name || !uname) { alert('Name and username are required.'); return; }

    const record = {
      name, username: uname,
      role:       document.getElementById('u-role').value,
      department: document.getElementById('u-dept').value,
      status:     document.getElementById('u-status').value,
    };

    if (editingId) {
      const idx = users.findIndex(u => u.id === editingId);
      if (idx > -1) users[idx] = { ...users[idx], ...record };
    } else {
      users.push({ id: Date.now(), ...record, created: new Date().toISOString().slice(0,10), lastLogin: 'Never' });
    }

    table.updateRows(users);
    document.querySelector('.card-subtitle').textContent = `${users.length} users registered`;
    closeModal();
  }

  function confirmDelete(id) {
    deleteTargetId = id;
    const u = users.find(x => x.id === id);
    document.getElementById('delete-user-name').textContent = u ? u.name : id;
    document.getElementById('delete-modal').classList.add('open');
  }

  function deleteUser() {
    users = users.filter(u => u.id !== deleteTargetId);
    table.updateRows(users);
    document.querySelector('.card-subtitle').textContent = `${users.length} users registered`;
    closeDeleteModal();
  }

  return { render, init, onSearch, onRoleFilter, openCreate, openEdit, closeModal, saveUser, confirmDelete, deleteUser, closeDeleteModal };
})();

window.UsersPage = UsersPage;
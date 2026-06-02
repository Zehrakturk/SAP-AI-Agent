/**
 * services/api_client.js
 * Central API client for the SAP AI Copilot Admin Portal.
 * Communicates with the Python AI Backend REST API.
 */

const ApiClient = (() => {
  // --------------------------------------------------
  // Configuration
  // --------------------------------------------------
  const CONFIG = {
    baseUrl: window.API_BASE_URL || 'http://localhost:8000/api/v1',
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  };

  let authToken = localStorage.getItem('sap_ai_token') || null;

  // --------------------------------------------------
  // Core request helper
  // --------------------------------------------------
  async function request(method, endpoint, body = null, signal = null) {
    const url = `${CONFIG.baseUrl}${endpoint}`;
    const headers = { ...CONFIG.headers };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);
    if (signal) options.signal = signal;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), CONFIG.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: signal || controller.signal,
      });
      clearTimeout(timeoutId);

      if (response.status === 401) {
        authToken = null;
        localStorage.removeItem('sap_ai_token');
        window.dispatchEvent(new Event('auth:expired'));
        throw new Error('Unauthorized — session expired.');
      }

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.detail || `HTTP ${response.status}`);
      }

      return data;
    } catch (err) {
      clearTimeout(timeoutId);
      throw err;
    }
  }

  // --------------------------------------------------
  // Auth
  // --------------------------------------------------
  const Auth = {
    async login(username, password) {
      const data = await request('POST', '/auth/login', { username, password });
      authToken = data.access_token;
      localStorage.setItem('sap_ai_token', authToken);
      return data;
    },
    logout() {
      authToken = null;
      localStorage.removeItem('sap_ai_token');
    },
    isAuthenticated() { return !!authToken; },
    getToken()        { return authToken; },
    setToken(token)   { authToken = token; localStorage.setItem('sap_ai_token', token); },
  };

  // --------------------------------------------------
  // Users  →  /users
  // --------------------------------------------------
  const Users = {
    list(params = {})        { return request('GET', `/users?${new URLSearchParams(params)}`); },
    get(id)                  { return request('GET', `/users/${id}`); },
    create(payload)          { return request('POST', '/users', payload); },
    update(id, payload)      { return request('PUT', `/users/${id}`, payload); },
    delete(id)               { return request('DELETE', `/users/${id}`); },
    assignRole(id, role)     { return request('PATCH', `/users/${id}/role`, { role }); },
    assignDept(id, dept)     { return request('PATCH', `/users/${id}/department`, { department: dept }); },
  };

  // --------------------------------------------------
  // Chat Sessions  →  /chats
  // --------------------------------------------------
  const Chats = {
    sessions(params = {})    { return request('GET', `/chats/sessions?${new URLSearchParams(params)}`); },
    getSession(sessionId)    { return request('GET', `/chats/sessions/${sessionId}`); },
    messages(sessionId)      { return request('GET', `/chats/sessions/${sessionId}/messages`); },
    deleteSession(sessionId) { return request('DELETE', `/chats/sessions/${sessionId}`); },
    export(sessionId, fmt)   { return request('POST', `/chats/sessions/${sessionId}/export`, { format: fmt }); },
  };

  // --------------------------------------------------
  // AI Logs  →  /logs
  // --------------------------------------------------
  const Logs = {
    list(params = {})        { return request('GET', `/logs?${new URLSearchParams(params)}`); },
    get(id)                  { return request('GET', `/logs/${id}`); },
    summary(range)           { return request('GET', `/logs/summary?range=${range}`); },
    export(params = {})      { return request('POST', '/logs/export', params); },
  };

  // --------------------------------------------------
  // Analytics  →  /analytics
  // --------------------------------------------------
  const Analytics = {
    dashboard()              { return request('GET', '/analytics/dashboard'); },
    dailyActivity(days)      { return request('GET', `/analytics/daily?days=${days}`); },
    tokenUsage(range)        { return request('GET', `/analytics/tokens?range=${range}`); },
    topQuestions(limit)      { return request('GET', `/analytics/top-questions?limit=${limit}`); },
    modelUsage()             { return request('GET', '/analytics/model-usage'); },
  };

  // --------------------------------------------------
  // Settings  →  /settings
  // --------------------------------------------------
  const Settings = {
    get()                    { return request('GET', '/settings'); },
    update(payload)          { return request('PUT', '/settings', payload); },
    models()                 { return request('GET', '/settings/models'); },
    testConnection()         { return request('POST', '/settings/test-connection'); },
    connectors()             { return request('GET', '/settings/connectors'); },
  };

  // --------------------------------------------------
  // SAP Tools  →  /tools  (read-only; write actions excluded per project doc)
  // --------------------------------------------------
  const SapTools = {
    getPurchaseOrders(params) { return request('POST', '/tools/get_purchase_orders', params); },
    getQuoteRequests(params)  { return request('POST', '/tools/get_quote_requests', params); },
    getSupplierPerf(params)   { return request('POST', '/tools/get_supplier_performance', params); },
    getStockLevels(params)    { return request('POST', '/tools/get_stock_levels', params); },
    getFinancialSummary(p)    { return request('POST', '/tools/get_financial_summary', p); },
  };

  // --------------------------------------------------
  // Public surface
  // --------------------------------------------------
  return { CONFIG, Auth, Users, Chats, Logs, Analytics, Settings, SapTools };
})();

// Make globally available
window.ApiClient = ApiClient;
window.API       = ApiClient;
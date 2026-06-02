/* static/dashboard.js — Dashboard Page */

const DashboardPage = (() => {

  function render() {
    return `
    ${window.InsightsPanel ? InsightsPanel.render() : ''}

    <div class="stat-grid" id="dash-stats">
      ${_statCardHtml('Toplam Kullanıcı',    '…', 'blue',   '—')}
      ${_statCardHtml('Günlük Mesaj',        '…', 'red',    '—')}
      ${_statCardHtml('Ortalama Token',      '…', 'teal',   '—')}
      ${_statCardHtml('Ort. Yanıt Süresi',   '…', 'amber',  '—')}
    </div>

    <div class="grid-2 mb-20">
      <div class="card">
        <div class="card-header">
          <div><div class="card-title">Günlük Aktivite</div>
               <div class="card-subtitle">Son 14 günlük mesaj sayısı</div></div>
        </div>
        <div class="card-body">
          <div class="chart-container" style="height:200px"><canvas id="chart-activity"></canvas></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header">
          <div><div class="card-title">Soru Kategorileri</div>
               <div class="card-subtitle">En çok sorulan konular</div></div>
        </div>
        <div class="card-body">
          <div class="chart-container" style="height:200px"><canvas id="chart-top-q"></canvas></div>
        </div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-header">
          <div><div class="card-title">Model Kullanım Dağılımı</div></div>
        </div>
        <div class="card-body">
          <div class="chart-container" style="height:200px"><canvas id="chart-model"></canvas></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header">
          <div class="card-title">Gecikme Trendi</div>
          <span class="badge badge-blue">ms</span>
        </div>
        <div class="card-body">
          <div class="chart-container" style="height:200px"><canvas id="chart-latency"></canvas></div>
        </div>
      </div>
    </div>`;
  }

  function _statCardHtml(label, value, color, delta) {
    const icons = {
      blue : `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
      red  : `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
      teal : `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`,
      amber: `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
    };
    return `
      <div class="stat-card ${color}" id="stat-${color}">
        <div class="stat-header">
          <div class="stat-label">${label}</div>
          <div class="stat-icon-wrap ${color}">${icons[color]}</div>
        </div>
        <div class="stat-value" id="statval-${color}">${value}</div>
        <div class="stat-delta" id="statdelta-${color}">${delta}</div>
      </div>`;
  }

  async function init() {
    // Insights paneli (non-blocking)
    if (window.InsightsPanel) {
      InsightsPanel.init().catch(e => console.warn('[Insights init]', e));
    }

    try {
      const [kpi, daily, topQ] = await Promise.all([
        API.Analytics.dashboard(),
        API.Analytics.dailyActivity(14),
        API.Analytics.topQuestions(5),
      ]);

      // KPI kartları
      document.getElementById('statval-blue').textContent  = kpi.total_users    ?? '—';
      document.getElementById('statval-red').textContent   = kpi.messages_today ?? '—';
      document.getElementById('statval-teal').textContent  = kpi.tokens_today   ? (kpi.tokens_today / 1000).toFixed(0) + 'K' : '—';
      document.getElementById('statval-amber').textContent = kpi.avg_latency    ? (kpi.avg_latency / 1000).toFixed(1) + 's' : '—';

      // Model dağılımı (summary'den)
      const modelData   = kpi.by_model   || {};
      const modelLabels = Object.keys(modelData);
      const modelCounts = Object.values(modelData);

      // Latency (14 günlük basit trend: son 14 değer)
      const latencyData = daily.data ? daily.data.map(() => kpi.avg_latency ?? 1000) : [];

      setTimeout(() => {
        Charts.renderActivityChart('chart-activity', daily.labels || [], daily.data || []);
        Charts.renderTopQuestionsChart('chart-top-q', topQ.labels || [], topQ.data || []);
        if (modelLabels.length) Charts.renderModelChart('chart-model', modelLabels, modelCounts);
        if (latencyData.length) Charts.renderLatencyChart('chart-latency', daily.labels || [], latencyData);
      }, 50);

    } catch (e) {
      console.error('[Dashboard] API hatası:', e);
    }
  }

  return { render, init };
})();


/**
 * components/charts.js
 * Reusable chart components powered by Chart.js.
 * Corporate palette: --blue-800 / --red-700
 */

const Charts = (() => {

  // Shared palette
  const BLUE   = '#003087';
  const BLUE_L = '#1565C0';
  const RED    = '#C8102E';
  const GRAY   = '#8A9BB8';
  const GRID   = 'rgba(184,196,216,0.35)';

  const baseFont = { family: "'Barlow', sans-serif", size: 12 };

  Chart.defaults.font = baseFont;
  Chart.defaults.color = '#5A6B8A';

  // --------------------------------------------------------
  // Daily Activity Line Chart
  // --------------------------------------------------------
  function renderActivityChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    // Destroy existing
    const existing = Chart.getChart(canvasId);
    if (existing) existing.destroy();

    return new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Messages',
          data,
          borderColor: BLUE,
          backgroundColor: 'rgba(0,48,135,0.08)',
          borderWidth: 2.5,
          pointBackgroundColor: BLUE,
          pointRadius: 4,
          pointHoverRadius: 6,
          fill: true,
          tension: 0.4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0F1923',
            titleColor: '#fff',
            bodyColor: '#B8C4D8',
            padding: 10,
            cornerRadius: 8,
          },
        },
        scales: {
          x: { grid: { color: GRID }, ticks: { font: baseFont } },
          y: { grid: { color: GRID }, ticks: { font: baseFont }, beginAtZero: true },
        },
      },
    });
  }

  // --------------------------------------------------------
  // Token Usage Bar Chart
  // --------------------------------------------------------
  function renderTokenChart(canvasId, labels, inputData, outputData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    const existing = Chart.getChart(canvasId);
    if (existing) existing.destroy();

    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Input Tokens',
            data: inputData,
            backgroundColor: BLUE,
            borderRadius: 4,
            barPercentage: 0.55,
          },
          {
            label: 'Output Tokens',
            data: outputData,
            backgroundColor: RED,
            borderRadius: 4,
            barPercentage: 0.55,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: 'top',
            align: 'end',
            labels: { boxWidth: 10, padding: 16, font: baseFont },
          },
          tooltip: {
            backgroundColor: '#0F1923',
            titleColor: '#fff',
            bodyColor: '#B8C4D8',
            padding: 10,
            cornerRadius: 8,
          },
        },
        scales: {
          x: { grid: { display: false }, stacked: false },
          y: { grid: { color: GRID }, beginAtZero: true, ticks: { font: baseFont } },
        },
      },
    });
  }

  // --------------------------------------------------------
  // Top Questions Horizontal Bar
  // --------------------------------------------------------
  function renderTopQuestionsChart(canvasId, labels, counts) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    const existing = Chart.getChart(canvasId);
    if (existing) existing.destroy();

    const colors = [BLUE, BLUE_L, RED, '#0097A7', '#F57C00'];

    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Queries',
          data: counts,
          backgroundColor: colors,
          borderRadius: 4,
          barPercentage: 0.65,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0F1923',
            padding: 10,
            cornerRadius: 8,
            titleColor: '#fff',
            bodyColor: '#B8C4D8',
          },
        },
        scales: {
          x: { grid: { color: GRID }, beginAtZero: true },
          y: { grid: { display: false }, ticks: { font: { ...baseFont, size: 11 } } },
        },
      },
    });
  }

  // --------------------------------------------------------
  // Model Usage Doughnut
  // --------------------------------------------------------
  function renderModelChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    const existing = Chart.getChart(canvasId);
    if (existing) existing.destroy();

    return new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: [BLUE, RED, '#0097A7', '#F57C00', GRAY],
          borderWidth: 2,
          borderColor: '#fff',
          hoverOffset: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '68%',
        plugins: {
          legend: {
            display: true,
            position: 'bottom',
            labels: { boxWidth: 10, padding: 12, font: baseFont },
          },
          tooltip: {
            backgroundColor: '#0F1923',
            padding: 10,
            cornerRadius: 8,
            titleColor: '#fff',
            bodyColor: '#B8C4D8',
          },
        },
      },
    });
  }

  // --------------------------------------------------------
  // Response Latency Area Sparkline
  // --------------------------------------------------------
  function renderLatencyChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    const existing = Chart.getChart(canvasId);
    if (existing) existing.destroy();

    return new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Avg Latency (ms)',
          data,
          borderColor: RED,
          backgroundColor: 'rgba(200,16,46,0.07)',
          borderWidth: 2,
          pointRadius: 3,
          fill: true,
          tension: 0.4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0F1923', padding: 10, cornerRadius: 8,
            titleColor: '#fff', bodyColor: '#B8C4D8',
          },
        },
        scales: {
          x: { grid: { color: GRID }, ticks: { font: baseFont } },
          y: { grid: { color: GRID }, beginAtZero: true, ticks: { font: baseFont } },
        },
      },
    });
  }

  // --------------------------------------------------------
  // Utility: last N days labels
  // --------------------------------------------------------
  function lastNDays(n) {
    const labels = [];
    for (let i = n - 1; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      labels.push(d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }));
    }
    return labels;
  }

  return {
    renderActivityChart,
    renderTokenChart,
    renderTopQuestionsChart,
    renderModelChart,
    renderLatencyChart,
    lastNDays,
  };
})();

window.Charts = Charts;
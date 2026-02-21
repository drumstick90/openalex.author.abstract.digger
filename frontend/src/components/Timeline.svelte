<script>
  import { onMount, onDestroy } from 'svelte';
  import { Chart, BarController, BarElement, CategoryScale, LinearScale, Tooltip } from 'chart.js';

  Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);

  let { works = [] } = $props();

  let canvas = $state(null);
  let chart = null;

  let yearCounts = $derived.by(() => {
    const counts = {};
    for (const w of works) {
      const y = w.publication_year;
      if (y) counts[y] = (counts[y] || 0) + 1;
    }
    const sorted = Object.entries(counts).sort(([a], [b]) => +a - +b);
    return { labels: sorted.map(([y]) => y), data: sorted.map(([, c]) => c) };
  });

  let hasData = $derived(yearCounts.labels.length > 1);

  function buildChart() {
    if (!canvas || !hasData) return;
    if (chart) chart.destroy();
    chart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: yearCounts.labels,
        datasets: [{
          data: yearCounts.data,
          backgroundColor: 'rgba(10,10,10,0.8)',
          borderRadius: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: true } },
        scales: {
          x: { grid: { display: false }, ticks: { font: { family: 'IBM Plex Mono', size: 10 }, color: '#737373' } },
          y: { grid: { color: '#e5e5e5' }, ticks: { font: { family: 'IBM Plex Mono', size: 10 }, color: '#737373', stepSize: 1 } },
        },
      },
    });
  }

  $effect(() => {
    if (canvas && hasData) buildChart();
  });

  onDestroy(() => { if (chart) chart.destroy(); });
</script>

{#if hasData}
  <div class="timeline-section">
    <div class="timeline-header">
      <span class="label">Publication Timeline</span>
      <span class="label">{yearCounts.labels[0]}–{yearCounts.labels[yearCounts.labels.length - 1]}</span>
    </div>
    <div class="chart-wrapper">
      <canvas bind:this={canvas}></canvas>
    </div>
  </div>
{/if}

<style>
  .timeline-section {
    margin-top: var(--space-xl);
    border: var(--border);
    padding: var(--space-lg);
    background: var(--gray-50);
  }

  .timeline-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-md);
  }

  .chart-wrapper {
    height: 140px;
    position: relative;
  }
</style>

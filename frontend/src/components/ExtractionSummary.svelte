<script>
  let { summary = null, totalExtracted = 0 } = $props();

  const evidenceLabels = {
    1: 'Meta-analysis/SR', 2: 'RCT', 3: 'Cohort/Case-ctrl',
    4: 'Case series', 5: 'Expert/Theory',
  };
</script>

{#if summary}
  <div class="extraction-summary">
    <div class="summary-header">
      <span class="label">Extraction Summary</span>
      <span class="label" style="color: var(--color-success);">{totalExtracted} papers analyzed</span>
    </div>

    <div class="summary-grid">
      {#if summary.evidence_levels}
        <div class="summary-card">
          <span class="card-title label">Evidence Levels</span>
          {#each Object.entries(summary.evidence_levels).filter(([, c]) => c > 0) as [level, count]}
            <div class="row"><span>{evidenceLabels[level] || `Level ${level}`}</span><span class="mono">{count}</span></div>
          {/each}
        </div>
      {/if}

      {#if summary.novelty}
        <div class="summary-card">
          <span class="card-title label">Research Novelty</span>
          {#each Object.entries(summary.novelty).slice(0, 4) as [type, count]}
            <div class="row"><span>{type}</span><span class="mono">{count}</span></div>
          {/each}
        </div>
      {/if}

      {#if summary.study_types}
        <div class="summary-card">
          <span class="card-title label">Study Types</span>
          {#each Object.entries(summary.study_types).slice(0, 5) as [type, count]}
            <div class="row"><span>{type}</span><span class="mono">{count}</span></div>
          {/each}
        </div>
      {/if}

      {#if summary.top_keywords?.length}
        <div class="summary-card">
          <span class="card-title label">Top Keywords</span>
          {#each summary.top_keywords.slice(0, 5) as [kw, count]}
            <div class="row"><span>{kw}</span><span class="mono">{count}</span></div>
          {/each}
        </div>
      {/if}

      {#if summary.top_drugs?.length}
        <div class="summary-card">
          <span class="card-title label">Drugs / Compounds</span>
          {#each summary.top_drugs.slice(0, 4) as [drug, count]}
            <div class="row"><span>{drug}</span><span class="mono">{count}</span></div>
          {/each}
        </div>
      {/if}

      {#if summary.top_conditions?.length}
        <div class="summary-card">
          <span class="card-title label">Conditions</span>
          {#each summary.top_conditions.slice(0, 4) as [cond, count]}
            <div class="row"><span>{cond}</span><span class="mono">{count}</span></div>
          {/each}
        </div>
      {/if}

      {#if summary.top_biomarkers?.length}
        <div class="summary-card">
          <span class="card-title label">Biomarkers</span>
          {#each summary.top_biomarkers.slice(0, 4) as [bio, count]}
            <div class="row"><span>{bio}</span><span class="mono">{count}</span></div>
          {/each}
        </div>
      {/if}
    </div>

    <div class="meta-stats mono">
      <span><strong>{summary.with_limitations || 0}</strong> report limitations</span>
      <span><strong>{summary.with_clinical_implications || 0}</strong> have clinical implications</span>
    </div>
  </div>
{/if}

<style>
  .extraction-summary {
    padding: var(--space-xl);
    background: var(--gray-50);
    border: var(--border);
  }

  .summary-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-lg);
  }

  .summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: var(--space-md);
    margin-bottom: var(--space-lg);
  }

  .summary-card {
    padding: var(--space-md);
    background: var(--white);
    border: var(--border);
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .card-title {
    margin-bottom: var(--space-xs);
  }

  .row {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    color: var(--gray-600);
  }

  .meta-stats {
    display: flex;
    gap: var(--space-xl);
    font-size: 0.75rem;
    color: var(--gray-500);
    padding-top: var(--space-md);
    border-top: var(--border);
  }

  .meta-stats strong {
    color: var(--black);
  }
</style>

<script>
  import { corpusStore } from '../lib/stores.js';
  import WorkCard from './WorkCard.svelte';
  import Timeline from './Timeline.svelte';
  import ProgressBar from './ProgressBar.svelte';
  import IntelligencePanel from './IntelligencePanel.svelte';

  let sortKey = $state('year-desc');

  let corpus = $derived($corpusStore);
  let active = $derived(corpus.status !== 'idle');

  let sortedWorks = $derived.by(() => {
    const arr = [...corpus.works];
    switch (sortKey) {
      case 'year-desc': return arr.sort((a, b) => (b.publication_year || 0) - (a.publication_year || 0));
      case 'year-asc': return arr.sort((a, b) => (a.publication_year || 0) - (b.publication_year || 0));
      case 'title-asc': return arr.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
      case 'title-desc': return arr.sort((a, b) => (b.title || '').localeCompare(a.title || ''));
      case 'citations-desc': return arr.sort((a, b) => (b.cited_by_count || 0) - (a.cited_by_count || 0));
      case 'citations-asc': return arr.sort((a, b) => (a.cited_by_count || 0) - (b.cited_by_count || 0));
      default: return arr;
    }
  });
</script>

{#if active}
  <div class="corpus-panel">
    {#if corpus.status === 'loading'}
      <ProgressBar
        percent={corpus.progress.percent}
        message={corpus.progress.message}
        phase={corpus.progress.phase}
      />
    {/if}

    {#if corpus.works.length > 0}
      <Timeline works={corpus.works} />

      <IntelligencePanel />

      <div class="works-toolbar">
        <div class="works-stats mono">
          <span class="stat"><span class="badge-inline oa">OA</span> {corpus.stats.openalex}</span>
          <span class="stat"><span class="badge-inline pm">PM</span> {corpus.stats.pubmed}</span>
          <span class="stat"><span class="badge-inline none">&mdash;</span> {corpus.stats.none}</span>
        </div>
        <div class="works-controls">
          <label class="label" for="sortWorks">Sort</label>
          <select id="sortWorks" bind:value={sortKey}>
            <option value="year-desc">Year ↓</option>
            <option value="year-asc">Year ↑</option>
            <option value="title-asc">Title A–Z</option>
            <option value="title-desc">Title Z–A</option>
            <option value="citations-desc">Citations ↓</option>
            <option value="citations-asc">Citations ↑</option>
          </select>
          <span class="label">{sortedWorks.length} works</span>
        </div>
      </div>

      <div class="works-list">
        {#each sortedWorks as work (work.openalex_id)}
          <WorkCard {work} />
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .corpus-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-lg);
  }

  .works-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-md);
    padding: var(--space-md) 0;
    border-bottom: var(--border);
  }

  .works-stats {
    display: flex;
    gap: var(--space-lg);
    font-size: 0.8rem;
    color: var(--gray-500);
    align-items: center;
  }

  .stat {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
  }

  .badge-inline {
    display: inline-block;
    font-size: 0.55rem;
    font-family: var(--font-mono);
    padding: 1px 4px;
    border: 1px solid;
    line-height: 1;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .badge-inline.oa {
    background: var(--black);
    color: var(--white);
    border-color: var(--black);
  }

  .badge-inline.pm {
    background: var(--gray-200);
    color: var(--gray-700);
    border-color: var(--gray-300);
  }

  .badge-inline.none {
    background: transparent;
    color: var(--gray-400);
    border-color: var(--gray-200);
  }

  .works-controls {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  select {
    padding: var(--space-xs) var(--space-sm);
    border: var(--border);
    font-size: 0.8rem;
    font-family: var(--font-mono);
    background: var(--white);
    cursor: pointer;
  }

  .works-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }
</style>

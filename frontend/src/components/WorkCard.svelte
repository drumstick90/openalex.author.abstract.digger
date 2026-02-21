<script>
  import SourceBadge from './SourceBadge.svelte';

  let { work } = $props();

  let doi = $derived(work.doi);
  let hasAbstract = $derived(!!work.abstract);
</script>

<article class="work-card">
  <div class="work-header">
    <SourceBadge source={work.abstract_source} />
    <h4 class="work-title">
      {#if doi}
        <a href={doi} target="_blank" rel="noopener">{work.title || 'Untitled'}</a>
      {:else}
        {work.title || 'Untitled'}
      {/if}
    </h4>
  </div>

  <div class="work-meta mono">
    {#if work.publication_year}<span>{work.publication_year}</span>{/if}
    {#if work.type}<span>{work.type}</span>{/if}
    {#if work.cited_by_count != null}<span>{work.cited_by_count} citations</span>{/if}
  </div>

  {#if hasAbstract}
    <p class="work-abstract serif">{work.abstract}</p>
  {:else}
    <p class="work-abstract missing">No abstract available</p>
  {/if}
</article>

<style>
  .work-card {
    padding: var(--space-lg);
    border: var(--border);
    background: var(--white);
    transition: background 0.15s;
  }

  .work-card:hover {
    background: var(--gray-50);
  }

  .work-header {
    display: flex;
    align-items: flex-start;
    gap: var(--space-sm);
    margin-bottom: var(--space-sm);
  }

  .work-title {
    font-family: var(--font-ui);
    font-size: 0.95rem;
    font-weight: 600;
    line-height: 1.3;
  }

  .work-title a {
    text-decoration: none;
    border-bottom: 1px solid transparent;
    transition: border-color 0.15s;
  }

  .work-title a:hover {
    border-bottom-color: var(--black);
  }

  .work-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-md);
    font-size: 0.7rem;
    color: var(--gray-500);
    margin-bottom: var(--space-sm);
  }

  .work-abstract {
    font-size: 0.9rem;
    line-height: 1.7;
    color: var(--gray-700);
  }

  .work-abstract.missing {
    font-style: italic;
    color: var(--gray-400);
    font-family: var(--font-mono);
    font-size: 0.8rem;
  }
</style>

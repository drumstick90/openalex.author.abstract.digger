<script>
  import { authorStore } from '../lib/stores.js';

  let author = $derived($authorStore.data);
</script>

{#if author}
  <div class="author-card">
    <h2 class="author-name">{author.display_name}</h2>

    <div class="meta-row">
      <div class="meta-item">
        <span class="label">Works</span>
        <span class="meta-value">{author.works_count?.toLocaleString() ?? '—'}</span>
      </div>
      <div class="meta-item">
        <span class="label">Citations</span>
        <span class="meta-value">{author.cited_by_count?.toLocaleString() ?? '—'}</span>
      </div>
      {#if author.orcid}
        <div class="meta-item">
          <span class="label">ORCID</span>
          <span class="meta-value mono">{author.orcid.replace('https://orcid.org/', '')}</span>
        </div>
      {/if}
    </div>

    {#if author.affiliations?.length}
      <div class="affiliations">
        {#each author.affiliations.filter(Boolean) as aff}
          <span class="aff-tag">{aff}</span>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .author-card {
    padding: var(--space-xl);
    border: var(--border-strong);
    background: var(--white);
    position: relative;
  }

  .author-card::after {
    content: '';
    position: absolute;
    top: 6px;
    left: 6px;
    right: -6px;
    bottom: -6px;
    border: var(--border-strong);
    z-index: -1;
  }

  .author-name {
    font-family: var(--font-reading);
    font-size: 1.6rem;
    font-weight: 600;
    margin-bottom: var(--space-lg);
    line-height: 1.2;
  }

  .meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xl);
    margin-bottom: var(--space-lg);
  }

  .meta-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .meta-value {
    font-size: 1.1rem;
    font-weight: 600;
  }

  .affiliations {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
  }

  .aff-tag {
    font-size: 0.75rem;
    font-family: var(--font-mono);
    padding: 2px 8px;
    background: var(--gray-50);
    border: var(--border);
    color: var(--gray-600);
  }
</style>

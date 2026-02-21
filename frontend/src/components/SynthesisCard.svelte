<script>
  let { content = '', model = '', worksCount = 0, source = '' } = $props();

  let formattedContent = $derived(
    content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n/g, '<br>')
  );
</script>

<div class="synthesis-card">
  <div class="synthesis-header">
    <span class="label">Research Profile</span>
    <span class="label">
      {model}
      {#if worksCount}&middot; {worksCount} works{/if}
      {#if source === 'cached_extracts'}
        &middot; <span class="cached">from cached extracts</span>
      {/if}
    </span>
  </div>
  <div class="synthesis-body serif">
    <p>{@html formattedContent}</p>
  </div>
</div>

<style>
  .synthesis-card {
    background: var(--gray-50);
    padding: var(--space-xl);
    border-left: 4px solid var(--black);
  }

  .synthesis-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-lg);
    padding-bottom: var(--space-md);
    border-bottom: var(--border);
    flex-wrap: wrap;
    gap: var(--space-sm);
  }

  .cached {
    color: var(--color-success);
  }

  .synthesis-body {
    font-size: 1.05rem;
    line-height: 1.8;
    color: var(--black);
  }

  .synthesis-body :global(strong) {
    font-weight: 600;
  }

  .synthesis-body :global(p) {
    margin-bottom: var(--space-md);
  }
</style>

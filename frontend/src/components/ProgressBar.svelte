<script>
  let { percent = 0, message = '', phase = '' } = $props();
</script>

{#if phase && phase !== 'complete'}
  <div class="progress-panel">
    <div class="progress-track">
      <div class="progress-fill" style:width="{Math.min(100, percent)}%"></div>
    </div>
    {#if message}
      <p class="progress-message mono">{message}</p>
    {/if}
  </div>
{/if}

<style>
  .progress-panel {
    padding: var(--space-lg);
    background: var(--gray-50);
    border: var(--border);
  }

  .progress-track {
    height: 4px;
    background: var(--gray-200);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: var(--space-sm);
  }

  .progress-fill {
    height: 100%;
    background: var(--black);
    transition: width 0.3s ease;
  }

  .progress-message {
    font-size: 0.75rem;
    color: var(--gray-500);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>

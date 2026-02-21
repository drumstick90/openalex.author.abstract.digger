<script>
  import { intelligenceStore } from '../lib/stores.js';
  import { synthesize, analyze, PRESET_PROMPTS } from '../lib/api.js';

  let question = $state('');
  let loading = $state(false);

  let hasExtracts = $derived(
    $intelligenceStore.status === 'complete' || $intelligenceStore.extractionSummary != null
  );

  async function handleAsk() {
    const q = question.trim();
    if (!q || loading) return;

    loading = true;

    try {
      const fn = hasExtracts ? synthesize : analyze;
      const result = await fn(q);

      intelligenceStore.update((s) => ({
        ...s,
        qaHistory: [
          ...s.qaHistory,
          {
            question: q,
            answer: result.answer,
            model: result.model,
            worksCount: result.extracts_used || result.works_analyzed,
            source: hasExtracts ? 'cached_extracts' : 'direct',
          },
        ],
      }));

      question = '';
    } catch (err) {
      intelligenceStore.update((s) => ({
        ...s,
        qaHistory: [
          ...s.qaHistory,
          { question: q, answer: null, error: err.message },
        ],
      }));
    } finally {
      loading = false;
    }
  }
</script>

<div class="qa-section">
  <span class="label">Ask a follow-up</span>
  <div class="qa-input-row">
    <input
      type="text"
      bind:value={question}
      placeholder="Methods used? Collaborations? Evolution over time?"
      disabled={loading}
      onkeydown={(e) => e.key === 'Enter' && handleAsk()}
    />
    <button disabled={loading || !question.trim()} onclick={handleAsk}>
      {#if loading}
        <span class="spinner"></span>
      {:else}
        Ask
      {/if}
    </button>
  </div>
  <div class="preset-row">
    <button
      class="preset-btn"
      disabled={loading}
      onclick={() => { question = PRESET_PROMPTS.critica; handleAsk(); }}
    >Analisi critica completa</button>
  </div>
</div>

{#if $intelligenceStore.qaHistory.length > 0}
  <div class="qa-history">
    {#each $intelligenceStore.qaHistory as entry, i}
      <div class="qa-entry">
        <p class="qa-question mono">{entry.question}</p>
        {#if entry.error}
          <p class="qa-error mono">{entry.error}</p>
        {:else if entry.answer}
          <div class="qa-answer serif">
            <p>{@html entry.answer
              .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
              .replace(/\*(.*?)\*/g, '<em>$1</em>')
              .replace(/\n\n/g, '</p><p>')
              .replace(/\n/g, '<br>')
            }</p>
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/if}

<style>
  .qa-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    border-top: var(--border);
    padding-top: var(--space-lg);
  }

  .qa-input-row {
    display: flex;
    gap: var(--space-sm);
  }

  input {
    flex: 1;
    padding: var(--space-md);
    font-size: 0.9rem;
    background: var(--gray-50);
    border: var(--border);
    color: var(--black);
    outline: none;
  }

  input:focus {
    border-color: var(--black);
  }

  button {
    padding: var(--space-sm) var(--space-lg);
    background: var(--black);
    color: var(--white);
    border: var(--border-strong);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.85rem;
    min-width: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid var(--gray-400);
    border-top-color: var(--white);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .preset-row {
    margin-top: var(--space-xs);
  }

  .preset-btn {
    padding: var(--space-xs) var(--space-md);
    background: var(--gray-50);
    color: var(--gray-600);
    border: var(--border);
    font-family: var(--font-mono);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    transition: background 0.15s, color 0.15s;
  }

  .preset-btn:hover:not(:disabled) {
    background: var(--black);
    color: var(--white);
  }

  .preset-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .qa-history {
    display: flex;
    flex-direction: column;
    gap: var(--space-lg);
    margin-top: var(--space-lg);
  }

  .qa-entry {
    border-left: 3px solid var(--gray-200);
    padding-left: var(--space-lg);
  }

  .qa-question {
    font-size: 0.75rem;
    color: var(--gray-500);
    margin-bottom: var(--space-sm);
  }

  .qa-answer {
    font-size: 1rem;
    line-height: 1.7;
    color: var(--black);
  }

  .qa-answer :global(strong) { font-weight: 600; }

  .qa-error {
    font-size: 0.8rem;
    color: var(--color-error);
  }
</style>

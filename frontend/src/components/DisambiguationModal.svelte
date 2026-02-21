<script>
  import { authorStore, corpusStore } from '../lib/stores.js';
  import { fetchAuthorWorks, connectProgress } from '../lib/api.js';

  let selected = $state(new Set());
  let loading = $state(false);

  let candidates = $derived($authorStore.candidates || []);
  let open = $derived($authorStore.status === 'disambiguating');

  function toggle(id) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selected = next;
  }

  function close() {
    authorStore.update((s) => ({ ...s, status: 'idle', candidates: null }));
    selected = new Set();
  }

  async function fetchSelected() {
    if (selected.size === 0) return;
    loading = true;

    const ids = [...selected];
    const allWorks = [];
    const authors = [];
    const totalStats = { openalex: 0, pubmed: 0, none: 0 };

    for (const id of ids) {
      const sessionId = `fetch_${id}_${Date.now()}`;
      const closeSSE = connectProgress(sessionId, (data) => {
        corpusStore.update((s) => ({
          ...s,
          status: 'loading',
          progress: {
            percent: data.progress ?? s.progress.percent,
            message: data.message ?? s.progress.message,
            phase: data.phase ?? s.progress.phase,
          },
        }));
      });

      try {
        const result = await fetchAuthorWorks(id, sessionId);
        if (result.author) authors.push(result.author);
        if (result.works) allWorks.push(...result.works);
        if (result.abstract_stats) {
          totalStats.openalex += result.abstract_stats.openalex || 0;
          totalStats.pubmed += result.abstract_stats.pubmed || 0;
          totalStats.none += result.abstract_stats.none || 0;
        }
      } finally {
        closeSSE();
      }
    }

    const deduped = [...new Map(allWorks.map((w) => [w.openalex_id, w])).values()];

    const combinedAuthor = authors.length === 1
      ? authors[0]
      : {
          id: authors.map((a) => a.id).join('+'),
          display_name: authors.map((a) => a.display_name).join(' + '),
          works_count: deduped.length,
          cited_by_count: authors.reduce((s, a) => s + (a.cited_by_count || 0), 0),
          affiliations: [...new Set(authors.flatMap((a) => a.affiliations || []))],
          orcid: authors.length === 1 ? authors[0].orcid : null,
        };

    authorStore.set({ status: 'complete', data: combinedAuthor, candidates: null, error: null });
    corpusStore.set({
      status: 'complete',
      works: deduped,
      stats: totalStats,
      funding: null,
      progress: { percent: 100, message: 'Complete', phase: 'complete' },
      error: null,
    });

    loading = false;
    selected = new Set();
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="overlay" onclick={(e) => e.target === e.currentTarget && close()}>
    <div class="modal" role="dialog" aria-modal="true" aria-label="Disambiguate authors">
      <div class="modal-header">
        <div>
          <h2>Multiple Authors Found</h2>
          <p class="label">Select one or more to fetch</p>
        </div>
        <button class="close-btn" onclick={close} aria-label="Close">&times;</button>
      </div>

      <div class="candidate-list">
        {#each candidates as c (c.id)}
          <button
            class="candidate"
            class:selected={selected.has(c.id)}
            onclick={() => toggle(c.id)}
          >
            <span class="candidate-name">
              {c.display_name}
              {#if c.orcid}<span class="orcid-badge">ORCID</span>{/if}
            </span>
            <span class="candidate-meta mono">
              {c.works_count?.toLocaleString() ?? '?'} works
              &middot;
              {c.cited_by_count?.toLocaleString() ?? '?'} citations
            </span>
            {#if c.affiliations?.length}
              <span class="candidate-affs">
                {c.affiliations.filter(Boolean).join(' · ')}
              </span>
            {/if}
          </button>
        {/each}
      </div>

      <div class="modal-footer">
        <span class="mono label">{selected.size} selected</span>
        <button class="fetch-btn" disabled={selected.size === 0 || loading} onclick={fetchSelected}>
          {#if loading}
            <span class="spinner"></span>
          {:else}
            Fetch Selected
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    padding: var(--space-lg);
  }

  .modal {
    background: var(--white);
    border: var(--border-strong);
    max-width: 640px;
    width: 100%;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: var(--space-xl);
    border-bottom: var(--border);
  }

  .modal-header h2 {
    font-size: 1.25rem;
    font-weight: 600;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 1.5rem;
    line-height: 1;
    padding: var(--space-xs);
    color: var(--gray-500);
  }

  .candidate-list {
    overflow-y: auto;
    padding: var(--space-lg);
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }

  .candidate {
    text-align: left;
    width: 100%;
    padding: var(--space-lg);
    background: var(--gray-50);
    border: 2px solid transparent;
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    transition: border-color 0.15s;
  }

  .candidate:hover {
    background: var(--gray-100);
  }

  .candidate.selected {
    border-color: var(--black);
    background: var(--white);
  }

  .candidate-name {
    font-weight: 600;
    font-size: 1rem;
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .orcid-badge {
    font-family: var(--font-mono);
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    background: var(--black);
    color: var(--white);
    padding: 2px 6px;
  }

  .candidate-meta {
    font-size: 0.8rem;
    color: var(--gray-500);
  }

  .candidate-affs {
    font-size: 0.75rem;
    color: var(--gray-400);
  }

  .modal-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-lg) var(--space-xl);
    border-top: var(--border);
  }

  .fetch-btn {
    padding: var(--space-sm) var(--space-xl);
    background: var(--black);
    color: var(--white);
    border: var(--border-strong);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    min-width: 140px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .fetch-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid var(--gray-400);
    border-top-color: var(--white);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>

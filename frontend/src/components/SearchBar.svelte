<script>
  import { authorStore, corpusStore, intelligenceStore, resetAll } from '../lib/stores.js';
  import { searchAuthor, connectProgress } from '../lib/api.js';

  let identifier = $state('');
  let loading = $state(false);
  let errorMsg = $state('');

  // Autocomplete state
  let suggestions = $state([]);
  let showDropdown = $state(false);
  let acLoading = $state(false);
  let selectedIndex = $state(-1);
  let debounceTimer = null;

  // Whether input looks like a direct ID (skip autocomplete)
  function isDirectId(v) {
    return /^A\d{6,}$/.test(v) || /^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/.test(v);
  }

  function handleInput() {
    const q = identifier.trim();
    selectedIndex = -1;

    if (q.length < 2 || isDirectId(q)) {
      suggestions = [];
      showDropdown = false;
      return;
    }

    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => fetchSuggestions(q), 220);
  }

  async function fetchSuggestions(q) {
    acLoading = true;
    try {
      const url = `https://api.openalex.org/autocomplete/authors?q=${encodeURIComponent(q)}`;
      const res = await fetch(url);
      const data = await res.json();
      suggestions = (data.results || []).slice(0, 7);
      showDropdown = suggestions.length > 0;
    } catch {
      suggestions = [];
      showDropdown = false;
    } finally {
      acLoading = false;
    }
  }

  function selectSuggestion(s) {
    // Use the OpenAlex short ID so the backend resolves it directly — no disambiguation
    identifier = s.id.replace('https://openalex.org/', '');
    suggestions = [];
    showDropdown = false;
    submitSearch();
  }

  function handleKeydown(e) {
    if (!showDropdown) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, suggestions.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, -1);
    } else if (e.key === 'Enter' && selectedIndex >= 0) {
      e.preventDefault();
      selectSuggestion(suggestions[selectedIndex]);
    } else if (e.key === 'Escape') {
      showDropdown = false;
      selectedIndex = -1;
    }
  }

  function handleBlur() {
    // Delay so click on suggestion registers before dropdown closes
    setTimeout(() => { showDropdown = false; selectedIndex = -1; }, 150);
  }

  async function submitSearch() {
    const query = identifier.trim();
    if (!query) return;

    resetAll();
    loading = true;
    errorMsg = '';

    const sessionId = `search_${Date.now()}`;

    const closeSSE = connectProgress(sessionId, (data) => {
      corpusStore.update((s) => ({
        ...s,
        progress: {
          percent: data.progress ?? s.progress.percent,
          message: data.message ?? s.progress.message,
          phase: data.phase ?? s.progress.phase,
        },
      }));
    });

    try {
      const result = await searchAuthor(query, sessionId);

      if (result.needs_disambiguation) {
        authorStore.set({
          status: 'disambiguating',
          data: null,
          candidates: result.candidates,
          error: null,
        });
        loading = false;
        closeSSE();
        return;
      }

      authorStore.set({
        status: 'complete',
        data: result.author,
        candidates: null,
        error: null,
      });

      corpusStore.set({
        status: 'complete',
        works: result.works || [],
        stats: result.abstract_stats || { openalex: 0, pubmed: 0, none: 0 },
        funding: result.funding || null,
        progress: { percent: 100, message: 'Complete', phase: 'complete' },
        error: null,
      });
    } catch (err) {
      errorMsg = err.message;
      authorStore.update((s) => ({ ...s, status: 'error', error: err.message }));
    } finally {
      loading = false;
      closeSSE();
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    showDropdown = false;
    await submitSearch();
  }

  function hintText(s) {
    const parts = [];
    if (s.hint) parts.push(s.hint);         // institution from OpenAlex
    if (s.works_count) parts.push(`${s.works_count.toLocaleString()} works`);
    return parts.join(' · ');
  }
</script>

<form class="search-bar" onsubmit={handleSubmit}>
  <div class="search-input-group">
    <div class="input-wrapper">
      <input
        type="text"
        bind:value={identifier}
        placeholder="Author name, OpenAlex ID, or ORCID"
        disabled={loading}
        required
        autocomplete="off"
        oninput={handleInput}
        onkeydown={handleKeydown}
        onblur={handleBlur}
      />

      {#if showDropdown}
        <ul class="dropdown" role="listbox">
          {#each suggestions as s, i}
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <li
              class="suggestion"
              class:highlighted={i === selectedIndex}
              role="option"
              aria-selected={i === selectedIndex}
              onmousedown={() => selectSuggestion(s)}
            >
              <span class="suggestion-name">{s.display_name}</span>
              {#if hintText(s)}
                <span class="suggestion-hint">{hintText(s)}</span>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <button type="submit" disabled={loading || !identifier.trim()}>
      {#if loading}
        <span class="spinner"></span>
      {:else}
        Search
      {/if}
    </button>
  </div>

  {#if errorMsg}
    <p class="search-error">{errorMsg}</p>
  {/if}
</form>

<style>
  .search-bar {
    width: 100%;
    max-width: 640px;
    margin: 0 auto;
  }

  .search-input-group {
    display: flex;
    gap: var(--space-sm);
  }

  .input-wrapper {
    flex: 1;
    position: relative;
  }

  input {
    width: 100%;
    padding: var(--space-md) var(--space-lg);
    font-size: 1rem;
    border: var(--border-strong);
    background: var(--white);
    color: var(--black);
    outline: none;
    transition: box-shadow 0.15s;
  }

  input:focus {
    box-shadow: 4px 4px 0 var(--black);
  }

  .dropdown {
    position: absolute;
    top: calc(100% + 2px);
    left: 0;
    right: 0;
    background: var(--white);
    border: var(--border-strong);
    border-top: none;
    list-style: none;
    z-index: 50;
    margin: 0;
    padding: 0;
    box-shadow: var(--shadow-md);
  }

  .suggestion {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: var(--space-md) var(--space-lg);
    cursor: pointer;
    border-bottom: var(--border);
    transition: background 0.1s;
  }

  .suggestion:last-child {
    border-bottom: none;
  }

  .suggestion:hover,
  .suggestion.highlighted {
    background: var(--gray-50);
  }

  .suggestion-name {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--black);
  }

  .suggestion-hint {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--gray-500);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  button {
    padding: var(--space-md) var(--space-xl);
    font-size: 1rem;
    font-weight: 600;
    background: var(--black);
    color: var(--white);
    border: var(--border-strong);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    transition: background 0.15s;
    min-width: 120px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  button:hover:not(:disabled) {
    background: var(--gray-700);
  }

  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .spinner {
    display: inline-block;
    width: 18px;
    height: 18px;
    border: 2px solid var(--gray-400);
    border-top-color: var(--white);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .search-error {
    margin-top: var(--space-sm);
    font-size: 0.85rem;
    color: var(--color-error);
    font-family: var(--font-mono);
  }
</style>

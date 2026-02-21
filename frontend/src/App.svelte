<script>
  import { authorStore, corpusStore } from './lib/stores.js';
  import SearchBar from './components/SearchBar.svelte';
  import DisambiguationModal from './components/DisambiguationModal.svelte';
  import AuthorCard from './components/AuthorCard.svelte';
  import CorpusPanel from './components/CorpusPanel.svelte';
  import SettingsPanel from './components/SettingsPanel.svelte';

  let hasResults = $derived(
    $authorStore.status === 'complete' || $corpusStore.status !== 'idle'
  );
</script>

<div class="app">
  <header class="app-header">
    <div class="header-top">
      <div class="header-content">
        <h1 class="app-title">Biomedical Abstract Explorer</h1>
        <p class="app-tagline">Understand any researcher's work in 60 seconds</p>
      </div>
      {#if hasResults}
        <SettingsPanel mode="icon" />
      {/if}
    </div>
    <SearchBar />
    {#if !hasResults}
      <SettingsPanel mode="inline" />
    {/if}
  </header>

  {#if hasResults}
    <div class="layout">
      <aside class="sidebar">
        <AuthorCard />
      </aside>
      <main class="main-content">
        <CorpusPanel />
      </main>
    </div>
  {/if}

  <DisambiguationModal />
</div>

<style>
  @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Mono:wght@400;500&family=Syne:wght@400;500;600;700&display=swap');

  .app {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  .app-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2xl);
    padding: var(--space-3xl) var(--space-xl);
    text-align: center;
    border-bottom: var(--border);
    position: relative;
  }

  .header-top {
    display: flex;
    align-items: flex-start;
    justify-content: center;
    width: 100%;
    max-width: var(--max-content);
    position: relative;
  }

  .header-top :global(.settings-wrapper) {
    position: absolute;
    right: 0;
    top: 0;
  }

  .app-title {
    font-family: var(--font-ui);
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
  }

  .app-tagline {
    font-family: var(--font-reading);
    font-size: 1.1rem;
    color: var(--gray-500);
    margin-top: calc(-1 * var(--space-xl));
  }

  .layout {
    display: grid;
    grid-template-columns: var(--sidebar-width) 1fr;
    max-width: var(--max-content);
    margin: 0 auto;
    width: 100%;
    flex: 1;
  }

  .sidebar {
    border-right: var(--border);
    padding: var(--space-xl);
    display: flex;
    flex-direction: column;
    gap: var(--space-2xl);
    height: calc(100vh - var(--header-height, 200px));
    overflow-y: auto;
    position: sticky;
    top: 0;
  }

  .main-content {
    padding: var(--space-xl);
    overflow-y: auto;
  }

  @media (max-width: 768px) {
    .layout {
      grid-template-columns: 1fr;
    }

    .sidebar {
      position: static;
      height: auto;
      border-right: none;
      border-bottom: var(--border);
    }

    .app-title {
      font-size: 1.5rem;
    }
  }
</style>

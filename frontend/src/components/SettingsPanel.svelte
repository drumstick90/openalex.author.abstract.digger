<script>
  import { aiConfigStore } from '../lib/stores.js';
  import { getProviders } from '../lib/api.js';
  import { onMount } from 'svelte';

  let { mode = 'icon' } = $props();

  let open = $state(false);
  let providers = $state([]);
  let config = $derived($aiConfigStore);

  let currentProvider = $derived(
    providers.find((p) => p.id === config.provider) || null
  );

  let showPanel = $derived(mode === 'inline' || open);

  onMount(async () => {
    try {
      const data = await getProviders();
      providers = data.providers || [];
    } catch {
      providers = [];
    }
  });

  function setProvider(id) {
    aiConfigStore.update((c) => ({ ...c, provider: id, model: '' }));
  }

  function setApiKey(e) {
    aiConfigStore.update((c) => ({ ...c, apiKey: e.target.value }));
  }

  function setModel(e) {
    aiConfigStore.update((c) => ({ ...c, model: e.target.value }));
  }
</script>

<div class="settings-wrapper" class:inline={mode === 'inline'}>
  {#if mode === 'icon'}
    <button class="toggle-btn" onclick={() => (open = !open)} aria-label="AI Settings" title="AI Settings">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
    </button>
  {/if}

  {#if showPanel}
    <div class="panel" class:dropdown={mode === 'icon'}>
      <div class="panel-header">
        <span class="label">AI Provider</span>
        {#if currentProvider?.has_server_key && !config.apiKey}
          <span class="server-badge">using server key</span>
        {/if}
      </div>

      <div class="provider-tabs">
        {#each providers as p}
          <button
            class="provider-tab"
            class:active={config.provider === p.id}
            onclick={() => setProvider(p.id)}
          >
            {p.name}
          </button>
        {/each}
      </div>

      <div class="fields-row">
        <div class="field key-field">
          <label class="label" for="aiKey-{mode}">API Key</label>
          <input
            id="aiKey-{mode}"
            type="password"
            value={config.apiKey}
            oninput={setApiKey}
            placeholder={currentProvider?.has_server_key ? 'Optional (server key available)' : 'Required'}
          />
          <span class="hint">Stored in your browser only</span>
        </div>

        {#if currentProvider?.models?.length}
          <div class="field model-field">
            <label class="label" for="aiModel-{mode}">Model</label>
            <select id="aiModel-{mode}" value={config.model} onchange={setModel}>
              <option value="">Default ({currentProvider.default_model})</option>
              {#each currentProvider.models as m}
                <option value={m}>{m}</option>
              {/each}
            </select>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .settings-wrapper {
    position: relative;
  }

  .settings-wrapper.inline {
    width: 100%;
    max-width: 640px;
    margin: 0 auto;
  }

  .toggle-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background: var(--gray-50);
    border: var(--border);
    border-radius: 50%;
    color: var(--gray-500);
    transition: color 0.15s, background 0.15s;
  }

  .toggle-btn:hover {
    color: var(--black);
    background: var(--gray-100);
  }

  .panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
  }

  .panel.dropdown {
    position: absolute;
    top: calc(100% + var(--space-sm));
    right: 0;
    width: 320px;
    background: var(--white);
    border: var(--border-strong);
    padding: var(--space-lg);
    z-index: 60;
    box-shadow: var(--shadow-md);
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .server-badge {
    font-family: var(--font-mono);
    font-size: 0.6rem;
    color: var(--color-success);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .provider-tabs {
    display: flex;
    gap: 0;
    border: var(--border-strong);
  }

  .provider-tab {
    flex: 1;
    padding: var(--space-sm) var(--space-xs);
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    background: var(--white);
    color: var(--gray-500);
    border: none;
    border-right: var(--border-strong);
    transition: background 0.15s, color 0.15s;
  }

  .provider-tab:last-child {
    border-right: none;
  }

  .provider-tab:hover {
    background: var(--gray-50);
  }

  .provider-tab.active {
    background: var(--black);
    color: var(--white);
  }

  .fields-row {
    display: flex;
    gap: var(--space-md);
    align-items: flex-start;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .key-field {
    flex: 1;
  }

  .model-field {
    flex: 0 0 auto;
    min-width: 180px;
  }

  .panel.dropdown .fields-row {
    flex-direction: column;
  }

  .panel.dropdown .model-field {
    min-width: 0;
    width: 100%;
  }

  input, select {
    padding: var(--space-sm) var(--space-md);
    font-size: 0.85rem;
    border: var(--border);
    background: var(--gray-50);
    color: var(--black);
    font-family: var(--font-mono);
    outline: none;
    width: 100%;
  }

  input:focus, select:focus {
    border-color: var(--black);
  }

  .hint {
    font-size: 0.65rem;
    color: var(--gray-400);
    font-family: var(--font-mono);
  }
</style>

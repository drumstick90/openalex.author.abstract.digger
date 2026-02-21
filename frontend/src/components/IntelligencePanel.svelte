<script>
  import { corpusStore, authorStore, intelligenceStore } from '../lib/stores.js';
  import { storeWorksForGemini, startExtraction, connectExtractionProgress, getExtracts, analyze, synthesize, PRESET_PROMPTS } from '../lib/api.js';
  import ProgressBar from './ProgressBar.svelte';
  import SynthesisCard from './SynthesisCard.svelte';
  import ExtractionSummary from './ExtractionSummary.svelte';
  import QAInput from './QAInput.svelte';

  let autoTriggered = $state(false);
  let synthesisLoading = $state(false);

  let corpus = $derived($corpusStore);
  let author = $derived($authorStore.data);
  let intel = $derived($intelligenceStore);
  let shouldActivate = $derived(corpus.status === 'complete' && author && !autoTriggered);

  $effect(() => {
    if (shouldActivate) {
      autoTriggered = true;
      runPipeline();
    }
  });

  async function runPipeline() {
    const works = corpus.works;
    const authorName = author.display_name;
    const authorId = author.id;

    intelligenceStore.update((s) => ({ ...s, status: 'storing' }));

    try {
      const storeResult = await storeWorksForGemini(works, authorName, authorId);

      if (storeResult.has_cached_extracts) {
        await loadCachedSummary();
        intelligenceStore.update((s) => ({ ...s, status: 'complete' }));
        runCriticaAnalysis(true);
        return;
      }

      await runExtraction();
    } catch (err) {
      intelligenceStore.update((s) => ({ ...s, status: 'error', error: err.message }));
    }
  }

  async function runCriticaAnalysis(hasExtracts) {
    synthesisLoading = true;
    try {
      const fn = hasExtracts ? synthesize : analyze;
      const result = await fn(PRESET_PROMPTS.critica);
      intelligenceStore.update((s) => ({
        ...s,
        synthesis: {
          answer: result.answer,
          model: result.model,
          worksCount: result.extracts_used || result.works_analyzed,
          source: hasExtracts ? 'cached_extracts' : 'direct',
        },
      }));
    } catch (err) {
      intelligenceStore.update((s) => ({
        ...s,
        synthesis: { answer: null, error: err.message },
      }));
    } finally {
      synthesisLoading = false;
    }
  }

  async function runExtraction() {
    intelligenceStore.update((s) => ({ ...s, status: 'extracting' }));

    const sessionId = `extract_${Date.now()}`;

    const closeSSE = connectExtractionProgress(sessionId, (data) => {
      if (data.phase === 'complete') {
        closeSSE();
        loadCachedSummary().then(() => {
          intelligenceStore.update((s) => ({ ...s, status: 'complete' }));
          runCriticaAnalysis(true);
        });
      } else if (data.phase === 'error') {
        closeSSE();
        intelligenceStore.update((s) => ({ ...s, status: 'error', error: data.error }));
      } else if (data.completed !== undefined) {
        intelligenceStore.update((s) => ({
          ...s,
          progress: {
            percent: data.progress || 0,
            message: data.message || `${data.completed}/${data.total}`,
          },
        }));
      }
    });

    try {
      await startExtraction(sessionId);
    } catch (err) {
      closeSSE();
      intelligenceStore.update((s) => ({ ...s, status: 'error', error: err.message }));
    }
  }

  async function loadCachedSummary() {
    try {
      const data = await getExtracts();
      intelligenceStore.update((s) => ({
        ...s,
        extractionSummary: { summary: data.summary, totalExtracted: data.successful },
      }));
    } catch { /* may not have summary yet */ }
  }
</script>

{#if intel.status !== 'idle'}
  <div class="intelligence-panel">
    <div class="panel-header">
      <h3>Research Intelligence</h3>
      <span class="label">
        {#if intel.status === 'storing'}storing...
        {:else if intel.status === 'extracting'}extracting...
        {:else if intel.status === 'complete'}ready
        {:else if intel.status === 'error'}error
        {/if}
      </span>
    </div>

    {#if intel.status === 'extracting'}
      <ProgressBar percent={intel.progress.percent} message={intel.progress.message} phase="extracting" />
    {/if}

    {#if intel.status === 'storing'}
      <div class="loading-block mono">Preparing abstracts for analysis...</div>
    {/if}

    {#if intel.status === 'error'}
      <div class="error-block mono">{intel.error}</div>
    {/if}

    {#if intel.extractionSummary}
      <ExtractionSummary
        summary={intel.extractionSummary.summary}
        totalExtracted={intel.extractionSummary.totalExtracted}
      />
    {/if}

    {#if synthesisLoading}
      <div class="loading-block mono">
        <span class="spinner"></span>
        Generating research trajectory analysis...
      </div>
    {/if}

    {#if intel.synthesis?.answer}
      <SynthesisCard
        content={intel.synthesis.answer}
        model={intel.synthesis.model}
        worksCount={intel.synthesis.worksCount}
        source={intel.synthesis.source}
      />
    {:else if intel.synthesis?.error}
      <div class="error-block mono">Analysis failed: {intel.synthesis.error}</div>
    {/if}

    {#if intel.status === 'complete'}
      <QAInput />
    {/if}
  </div>
{/if}

<style>
  .intelligence-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-lg);
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: var(--space-md);
    border-bottom: var(--border);
  }

  .panel-header h3 {
    font-family: var(--font-reading);
    font-size: 1.25rem;
    font-weight: 600;
  }

  .loading-block {
    padding: var(--space-lg);
    background: var(--gray-50);
    font-size: 0.8rem;
    color: var(--gray-500);
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .error-block {
    padding: var(--space-lg);
    background: var(--gray-50);
    font-size: 0.8rem;
    color: var(--color-error);
    border-left: 4px solid var(--color-error);
  }

  .spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid var(--gray-300);
    border-top-color: var(--black);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }
</style>

<script>
  let { source = null } = $props();

  let label = $derived(
    source === 'openalex' ? 'OA'
    : source?.startsWith('pubmed') ? 'PM'
    : '—'
  );

  let variant = $derived(
    source === 'openalex' ? 'oa'
    : source?.startsWith('pubmed') ? 'pm'
    : 'none'
  );
</script>

<span class="badge {variant}">{label}</span>

<style>
  .badge {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 0.6rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 2px 6px;
    border: 1px solid;
    line-height: 1;
  }

  .oa {
    background: var(--black);
    color: var(--white);
    border-color: var(--black);
  }

  .pm {
    background: var(--gray-200);
    color: var(--gray-700);
    border-color: var(--gray-300);
  }

  .none {
    background: transparent;
    color: var(--gray-400);
    border-color: var(--gray-200);
  }
</style>

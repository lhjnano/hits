<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { uiStore } from '../lib/stores';
  import { t, subscribeLocale } from '../lib/i18n';

  let loading = $state(true);
  let error = $state('');
  let checkpointData = $state<any>(null);
  let checkpoints = $state<any[]>([]);
  let localeTick = $state(0);
  let showHistory = $state(false);

  onMount(() => {
    const unsub = subscribeLocale(() => localeTick++);
    loadResume();
    return unsub;
  });

  $effect(() => {
    const project = uiStore.value.selectedProject;
    if (project) loadResume();
  });

  async function loadResume() {
    const project = uiStore.value.selectedProject;
    if (!project) {
      loading = false;
      return;
    }

    loading = true;
    error = '';

    const res = await api.checkpoints.resume(project, 2000);
    if (res.success && res.data) {
      checkpointData = res.data;
    } else {
      error = res.error || 'No checkpoint data available';
    }
    loading = false;
  }

  async function loadHistory() {
    const project = uiStore.value.selectedProject;
    if (!project) return;

    const res = await api.checkpoints.list(project, 10);
    if (res.success && res.data) {
      checkpoints = res.data;
      showHistory = true;
    }
  }

  function progressBar(pct: number): string {
    const filled = '█'.repeat(Math.floor(pct / 10));
    const empty = '░'.repeat(10 - Math.floor(pct / 10));
    return `${filled}${empty} ${pct}%`;
  }
</script>

<div data-locale-tick={localeTick}>
  <div class="flex items-center" style="margin-bottom:16px;">
    <h2 style="font-size:16px; flex:1;">▶ Resume</h2>
    <button class="btn btn-secondary btn-sm" onclick={loadHistory}>📋 History</button>
    <button class="btn btn-secondary btn-sm" onclick={loadResume} style="margin-left:4px;">🔄</button>
  </div>

  {#if !uiStore.value.selectedProject}
    <div class="empty-state">
      <div class="icon">▶</div>
      <div class="message">Select a project to resume</div>
    </div>
  {:else if loading}
    <div class="loading"><div class="spinner"></div></div>
  {:else if error}
    <div class="card" style="text-align:center; color:var(--text-muted);">{error}</div>
  {:else if checkpointData}
    <!-- Pending Signals -->
    {#if checkpointData.signals?.length}
      <div class="handover-section" style="border-left-color:var(--warning);">
        <h3>📬 Pending Signals</h3>
        {#each checkpointData.signals as sig}
          <div class="handover-item">
            <span class="badge" class:badge-critical={sig.priority === 'urgent'} class:badge-high={sig.priority === 'high'}>
              {sig.priority === 'urgent' ? '🔴' : sig.priority === 'high' ? '🟡' : '🟢'}
            </span>
            <strong style="margin-left:8px;">{sig.sender}</strong>: {sig.summary}
            {#if sig.pending_items?.length}
              <ul style="margin:4px 0 0 20px; font-size:12px;">
                {#each sig.pending_items as item}
                  <li>{item}</li>
                {/each}
              </ul>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    <!-- Checkpoint -->
    {#if checkpointData.checkpoint}
      {@const cp = checkpointData.checkpoint}

      <!-- Header -->
      <div class="card" style="margin-bottom:16px;">
        <div class="flex items-center gap-sm">
          <span style="font-size:24px;">💾</span>
          <div style="flex:1;">
            <div style="font-weight:600;">{cp.project_name}</div>
            <div class="text-sm text-muted" style="font-family:var(--font-mono);">{cp.purpose || 'No purpose set'}</div>
          </div>
          <div class="badge badge-what">{progressBar(cp.completion_pct)}</div>
        </div>
        <div class="flex gap-sm" style="margin-top:8px;">
          {#if cp.git_branch}
            <span class="badge">🔀 {cp.git_branch}</span>
          {/if}
          <span class="badge">{cp.performer}</span>
          <span class="text-xs text-muted">{(cp.created_at || '').slice(0, 16)}</span>
        </div>
      </div>

      <!-- Current State -->
      {#if cp.current_state}
        <div class="handover-section">
          <h3>📊 Achieved</h3>
          <div class="handover-item">{cp.current_state}</div>
        </div>
      {/if}

      <!-- Next Steps (most important!) -->
      {#if cp.next_steps?.length}
        <div class="handover-section" style="border-left-color:var(--success);">
          <h3>▶ Next Steps</h3>
          {#each cp.next_steps as step, i}
            <div class="handover-item" style="display:flex; flex-direction:column; gap:2px;">
              <div class="flex items-center gap-sm">
                <span class="badge" class:badge-critical={step.priority === 'critical'} class:badge-high={step.priority === 'high'}>
                  {step.priority === 'critical' ? '🔴' : step.priority === 'high' ? '🟡' : '🟢'}
                </span>
                <strong>{i + 1}. {step.action}</strong>
              </div>
              {#if step.command}
                <code class="text-sm" style="margin-left:24px; color:var(--info);">→ {step.command}</code>
              {/if}
              {#if step.file}
                <span class="text-xs text-muted" style="margin-left:24px;">📄 {step.file}</span>
              {/if}
            </div>
          {/each}
        </div>
      {/if}

      <!-- Must Know -->
      {#if cp.required_context?.length}
        <div class="handover-section" style="border-left-color:var(--warning);">
          <h3>⚠ Must Know</h3>
          {#each cp.required_context as ctx}
            <div class="handover-item">• {ctx}</div>
          {/each}
        </div>
      {/if}

      <!-- Decisions -->
      {#if cp.decisions_made?.length}
        <div class="handover-section">
          <h3>★ Decisions</h3>
          {#each cp.decisions_made as d}
            <div class="handover-item">
              {d.decision}
              {#if d.rationale}
                <div class="text-xs text-muted">→ {d.rationale}</div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}

      <!-- Blocks -->
      {#if cp.blocks?.length}
        <div class="handover-section" style="border-left-color:var(--danger);">
          <h3>🚫 Blockers</h3>
          {#each cp.blocks as b}
            <div class="handover-item">
              {b.issue}
              {#if b.workaround}
                <div class="text-xs" style="color:var(--success);">Workaround: {b.workaround}</div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}

      <!-- Files Delta -->
      {#if cp.files_delta?.length}
        <div class="handover-section">
          <h3>📄 Files ({cp.files_delta.length})</h3>
          {#each cp.files_delta.slice(0, 10) as fd}
            <div class="handover-item" style="font-family:var(--font-mono); font-size:12px;">
              [{fd.change_type === 'created' ? '+' : fd.change_type === 'deleted' ? '-' : '~'}] {fd.path}
            </div>
          {/each}
        </div>
      {/if}

      <!-- Compressed View -->
      {#if checkpointData.compressed}
        <details style="margin-top:16px;">
          <summary class="text-sm text-muted" style="cursor:pointer;">Compressed (for AI context)</summary>
          <pre class="card" style="margin-top:8px; padding:12px; font-size:11px; white-space:pre-wrap; max-height:400px; overflow-y:auto;">{checkpointData.compressed}</pre>
        </details>
      {/if}
    {:else}
      <div class="empty-state">
        <div class="icon">▶</div>
        <div class="message">No checkpoint available. Use hits_auto_checkpoint() at session end.</div>
      </div>
    {/if}
  {/if}

  <!-- History Modal -->
  {#if showHistory}
    <div class="modal-overlay" onclick={() => showHistory = false}>
      <div class="modal" onclick={(e) => e.stopPropagation()} style="max-width:600px;">
        <h2>📋 Checkpoint History</h2>
        {#if checkpoints.length === 0}
          <div class="text-muted text-sm">No checkpoints found.</div>
        {:else}
          {#each checkpoints as cp, i}
            <div class="handover-item" style="margin-bottom:8px;">
              <div class="flex items-center gap-sm">
                <strong>{i + 1}. [{(cp.created_at || '').slice(5, 16)}] {cp.performer}</strong>
                <span class="badge">{progressBar(cp.completion_pct)}</span>
              </div>
              <div class="text-sm">{cp.purpose}</div>
              {#if cp.first_next_step}
                <div class="text-xs text-muted">Next: {cp.first_next_step}</div>
              {/if}
            </div>
          {/each}
        {/if}
        <div style="margin-top:16px; text-align:right;">
          <button class="btn btn-secondary" onclick={() => showHistory = false}>Close</button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .badge-critical { background: var(--danger); color: white; }
  .badge-high { background: var(--warning); color: white; }
</style>

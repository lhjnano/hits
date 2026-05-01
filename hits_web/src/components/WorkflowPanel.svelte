<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { wsClient } from '../lib/ws';

  let workflows: any[] = $state([]);
  let selectedWf: any = $state(null);
  let resumeContext: string = $state('');
  let loading = $state(false);
  let showContext = $state(false);

  const statusIcon: Record<string, string> = {
    pending: '⏳',
    running: '▶️',
    completed: '✅',
    failed: '❌',
    skipped: '⏭️',
    partially_completed: '⚠️',
  };

  const statusColor: Record<string, string> = {
    pending: 'var(--text-muted)',
    running: 'var(--primary)',
    completed: 'var(--success)',
    failed: '#e53e3e',
    skipped: 'var(--text-muted)',
    partially_completed: '#d69e2e',
  };

  onMount(() => {
    loadWorkflows();
    const unsub = wsClient.on('workflow_updated', () => loadWorkflows());
    return unsub;
  });

  async function loadWorkflows() {
    loading = true;
    const res = await api.workflow.list(undefined, 30);
    if (res.success && res.data) workflows = res.data;
    if (selectedWf) await loadWorkflowDetail(selectedWf.workflow_id);
    loading = false;
  }

  async function loadWorkflowDetail(id: string) {
    const res = await api.workflow.get(id);
    if (res.success && res.data) {
      selectedWf = res.data;
      resumeContext = '';
      showContext = false;
    }
  }

  async function loadContext() {
    if (!selectedWf) return;
    const res = await api.workflow.context(selectedWf.workflow_id, 3000);
    if (res.success && res.data) {
      resumeContext = res.data.context || '';
      showContext = true;
    }
  }

  function stageProgress(wf: any): number {
    if (!wf.stages?.length) return 0;
    const done = (wf.stage_checkpoints || []).filter(
      (s: any) => s.status === 'completed'
    ).length;
    return Math.round((done / wf.stages.length) * 100);
  }
</script>

<div class="workflow-panel">
  {#if loading && workflows.length === 0}
    <div class="text-muted text-center p-md">Loading...</div>
  {:else if workflows.length === 0 && !selectedWf}
    <!-- Empty state with explanation -->
    <div class="intro-card">
      <div class="intro-icon">🔄</div>
      <h2>Workflow Pipeline</h2>
      <p class="intro-desc">
        Track multi-agent pipelines from start to finish.
        Each workflow has stages that run sequentially or in parallel,
        with full checkpointing so you can resume from any failure.
      </p>

      <div class="how-it-works">
        <h4>How it works</h4>
        <div class="steps">
          <div class="step">
            <div class="step-num">1</div>
            <div>
              <strong>Create a workflow</strong>
              <p class="step-desc">Define stages like "Analysis → Design → Implementation → Validation". Each stage can be assigned to a different AI agent.</p>
            </div>
          </div>
          <div class="step">
            <div class="step-num">2</div>
            <div>
              <strong>Execute stages</strong>
              <p class="step-desc">Stages run with dependency ordering. Each completed stage saves a checkpoint with context for the next stage.</p>
            </div>
          </div>
          <div class="step">
            <div class="step-num">3</div>
            <div>
              <strong>Resume on failure</strong>
              <p class="step-desc">If a stage fails, the workflow stops. Resume from the failed stage — all prior context is preserved.</p>
            </div>
          </div>
        </div>
      </div>

      <div class="intro-note">
        <strong>No workflows yet.</strong> Workflows are created via the MCP tool or API when running multi-agent pipelines.
        They appear here automatically.
      </div>
    </div>
  {:else}
    <div class="wf-grid">
      <!-- Left: Workflow list -->
      <div class="card list-card">
        <h3>🔄 Workflows ({workflows.length})</h3>
        <div class="wf-list">
          {#each workflows as wf}
            <div
              class="wf-row"
              class:selected={selectedWf?.workflow_id === wf.workflow_id}
              role="button"
              tabindex="0"
              onclick={() => loadWorkflowDetail(wf.workflow_id)}
              onkeydown={(e) => { if (e.key === 'Enter') loadWorkflowDetail(wf.workflow_id); }}
            >
              <div class="wf-row-top">
                <span class="status-dot" style="background: {statusColor[wf.status] || 'var(--text-muted)'}"></span>
                <span class="wf-name">{wf.name || wf.workflow_id}</span>
              </div>
              <div class="wf-row-bottom">
                <span class="text-xs">📂 {wf.project_name || wf.project_path?.split('/').pop()}</span>
                <div class="mini-progress">
                  <div class="mini-bar" style="width: {stageProgress(wf)}%"></div>
                </div>
                <span class="text-xs">{stageProgress(wf)}%</span>
              </div>
            </div>
          {/each}
        </div>
      </div>

      <!-- Right: Workflow detail -->
      {#if selectedWf}
        <div class="card detail-card">
          <div class="detail-header">
            <div>
              <h3>{selectedWf.name || selectedWf.workflow_id}</h3>
              <div class="meta-row">
                <span class="status-badge" style="background: {statusColor[selectedWf.status]}">
                  {statusIcon[selectedWf.status]} {selectedWf.status}
                </span>
                <span class="text-xs text-muted">
                  {selectedWf.completed_count || 0}/{selectedWf.total_stages || selectedWf.stages?.length || 0} stages
                  · {selectedWf.progress_pct || 0}%
                </span>
                <span class="text-xs text-muted">
                  by {selectedWf.performer}
                </span>
              </div>
            </div>
            <button class="btn-sm" onclick={loadContext}>
              📋 Resume Context
            </button>
          </div>

          <!-- Progress bar -->
          <div class="progress-bar-bg">
            <div class="progress-bar" style="width: {selectedWf.progress_pct || 0}%"></div>
          </div>

          <!-- Stage pipeline -->
          <div class="stage-pipeline">
            {#each selectedWf.stages || [] as stage, i}
              {@const sc = (selectedWf.stage_checkpoints || []).find((s: any) => s.stage_id === stage.id)}
              {@const sStatus = sc?.status || 'pending'}
              <div class="stage-node" class:stage-{sStatus}>
                <div class="stage-connector">
                  {#if i > 0}
                    <div class="connector-line"></div>
                  {/if}
                </div>
                <div class="stage-content">
                  <div class="stage-icon">{statusIcon[sStatus] || '⏳'}</div>
                  <div class="stage-info">
                    <span class="stage-name">{stage.name}</span>
                    <span class="stage-agent text-xs text-muted">
                      {stage.agent || 'unassigned'}
                    </span>
                    {#if stage.depends_on?.length}
                      <span class="text-xs text-muted">
                        after: {stage.depends_on.join(', ')}
                      </span>
                    {/if}
                    {#if sc?.error}
                      <span class="stage-error text-xs">{sc.error}</span>
                    {/if}
                  </div>
                </div>
              </div>
            {/each}
          </div>

          <!-- Files / Decisions / Errors -->
          {#if (selectedWf.total_files_modified?.length || 0) > 0 || (selectedWf.total_decisions?.length || 0) > 0}
            <div class="results-section">
              {#if selectedWf.total_files_modified?.length}
                <div class="result-group">
                  <h4>📝 Files ({selectedWf.total_files_modified.length})</h4>
                  {#each selectedWf.total_files_modified.slice(0, 10) as f}
                    <div class="result-item mono text-xs">{f}</div>
                  {/each}
                  {#if selectedWf.total_files_modified.length > 10}
                    <div class="text-xs text-muted">+{selectedWf.total_files_modified.length - 10} more</div>
                  {/if}
                </div>
              {/if}
              {#if selectedWf.total_decisions?.length}
                <div class="result-group">
                  <h4>★ Decisions ({selectedWf.total_decisions.length})</h4>
                  {#each selectedWf.total_decisions.slice(0, 5) as d}
                    <div class="result-item text-xs">{d}</div>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}

          <!-- Resume context -->
          {#if showContext && resumeContext}
            <div class="context-section">
              <h4>📋 Resume Context</h4>
              <pre class="context-pre">{resumeContext}</pre>
            </div>
          {/if}
        </div>
      {:else}
        <div class="card">
          <p class="text-muted">Select a workflow to see stage details and pipeline progress.</p>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .workflow-panel { padding: 16px; }

  .intro-card {
    max-width: 640px; margin: 0 auto;
    text-align: center; padding: 32px 24px;
  }
  .intro-icon { font-size: 48px; margin-bottom: 8px; }
  .intro-card h2 { font-size: 20px; margin-bottom: 8px; }
  .intro-desc { color: var(--text-secondary); font-size: 14px; line-height: 1.6; margin-bottom: 24px; }
  .how-it-works { text-align: left; }
  .how-it-works h4 { font-size: 13px; color: var(--text-muted); margin-bottom: 12px; text-align: center; }
  .steps { display: flex; flex-direction: column; gap: 12px; }
  .step { display: flex; gap: 12px; align-items: flex-start; }
  .step-num {
    background: var(--primary); color: #fff;
    width: 24px; height: 24px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; flex-shrink: 0;
  }
  .step strong { font-size: 13px; }
  .step-desc { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
  .intro-note {
    margin-top: 24px; padding: 12px 16px;
    background: var(--bg-secondary); border-radius: 8px;
    font-size: 13px; text-align: center;
  }

  .wf-grid { display: grid; grid-template-columns: 320px 1fr; gap: 16px; }
  @media (max-width: 768px) { .wf-grid { grid-template-columns: 1fr; } }

  .card {
    background: var(--bg-secondary); border: 1px solid var(--border-color);
    border-radius: 8px; padding: 16px;
  }
  .card h3 { font-size: 15px; margin-bottom: 12px; }
  .card h4 { font-size: 13px; margin: 12px 0 6px; color: var(--text-secondary); }

  .wf-list { display: flex; flex-direction: column; gap: 6px; max-height: 500px; overflow-y: auto; }
  .wf-row {
    padding: 10px 12px; border-radius: 6px; cursor: pointer;
    border: 1px solid transparent; transition: all 0.15s;
  }
  .wf-row:hover { background: var(--border-color); }
  .wf-row.selected { border-color: var(--primary); background: rgba(59,130,246,0.08); }

  .wf-row-top { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .wf-name { font-weight: 600; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .wf-row-bottom { display: flex; align-items: center; gap: 6px; padding-left: 16px; }
  .mini-progress { flex: 1; height: 4px; background: var(--bg-primary); border-radius: 2px; overflow: hidden; }
  .mini-bar { height: 100%; background: var(--primary); border-radius: 2px; transition: width 0.3s; }

  .detail-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
  .meta-row { display: flex; align-items: center; gap: 8px; margin-top: 4px; flex-wrap: wrap; }
  .status-badge {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 2px 8px; border-radius: 10px; font-size: 11px;
    color: #fff; font-weight: 600;
  }

  .btn-sm {
    padding: 4px 10px; font-size: 12px; border-radius: 6px;
    border: 1px solid var(--border-color); background: var(--bg-primary);
    cursor: pointer; color: var(--text-primary); transition: border-color 0.15s;
  }
  .btn-sm:hover { border-color: var(--primary); }

  .progress-bar-bg { height: 6px; background: var(--bg-primary); border-radius: 3px; overflow: hidden; margin-bottom: 16px; }
  .progress-bar { height: 100%; background: var(--primary); border-radius: 3px; transition: width 0.3s; }

  .stage-pipeline { display: flex; flex-direction: column; gap: 0; margin-bottom: 16px; }
  .stage-node { display: flex; }
  .stage-connector { display: flex; flex-direction: column; align-items: center; width: 40px; flex-shrink: 0; }
  .connector-line { width: 2px; height: 16px; background: var(--border-color); }
  .stage-content { display: flex; gap: 10px; align-items: flex-start; padding: 8px 12px; border-radius: 6px; background: var(--bg-primary); flex: 1; margin-bottom: 4px; }
  .stage-icon { font-size: 18px; flex-shrink: 0; }
  .stage-info { display: flex; flex-direction: column; gap: 2px; }
  .stage-name { font-weight: 600; font-size: 13px; }
  .stage-agent { font-family: monospace; }
  .stage-error { color: #e53e3e; }
  .stage-running .stage-content { border-left: 3px solid var(--primary); }
  .stage-failed .stage-content { border-left: 3px solid #e53e3e; }

  .results-section { display: flex; gap: 16px; flex-wrap: wrap; }
  .result-group { flex: 1; min-width: 200px; }
  .result-item { padding: 3px 8px; border-radius: 3px; margin-bottom: 2px; }
  .result-item:nth-child(odd) { background: var(--bg-primary); }
  .mono { font-family: monospace; }

  .context-section { margin-top: 12px; }
  .context-pre {
    background: var(--bg-primary); border-radius: 6px; padding: 12px;
    font-size: 11px; line-height: 1.5; white-space: pre-wrap; word-break: break-word;
    max-height: 300px; overflow-y: auto; font-family: monospace;
  }
</style>

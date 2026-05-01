<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { wsClient } from '../lib/ws';

  let workflows: any[] = $state([]);
  let selectedWf: any = $state(null);
  let resumeContext: string = $state('');
  let loading = $state(false);

  onMount(() => {
    loadWorkflows();
  });

  async function loadWorkflows() {
    loading = true;
    // Workflows are stored under ~/.hits/data/workflows/
    // For now, we'll load via the handover project list as proxy
    const res = await api.handover.projects();
    if (res.success && res.data) {
      workflows = res.data;
    }
    loading = false;
  }

  const statusIcon: Record<string, string> = {
    pending: '⏳',
    running: '▶️',
    completed: '✅',
    failed: '❌',
    skipped: '⏭️',
  };

  const statusColor: Record<string, string> = {
    pending: 'var(--text-muted)',
    running: 'var(--primary)',
    completed: 'var(--success)',
    failed: '#e53e3e',
    skipped: 'var(--text-muted)',
  };
</script>

<div class="workflow-panel">
  <div class="panel-header">
    <h3>🔄 Workflow Pipeline</h3>
    <span class="text-sm text-muted">
      {workflows.length} project{workflows.length !== 1 ? 's' : ''}
    </span>
  </div>

  {#if loading}
    <div class="text-muted text-center p-md">Loading...</div>
  {:else if workflows.length === 0}
    <div class="empty-state">
      <div class="empty-icon">🔄</div>
      <p>No workflows yet.</p>
      <p class="text-sm text-muted">Workflows are created when multi-agent pipelines run via MCP tools.</p>
    </div>
  {:else}
    <div class="workflow-list">
      {#each workflows as wf}
        <div class="workflow-card">
          <div class="wf-header">
            <span class="wf-name">📂 {wf.project_path?.split('/').pop() || 'Unknown'}</span>
            <span class="wf-logs-badge">{wf.total_logs || 0} logs</span>
          </div>
          <div class="wf-meta">
            {#if wf.last_activity}
              <span class="text-xs text-muted">{wf.last_activity?.slice(0, 16)}</span>
            {/if}
            {#if wf.performers}
              <span class="text-xs">
                {#each Object.keys(wf.performers || {}) as performer}
                  <span class="performer-badge">{performer}</span>
                {/each}
              </span>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .workflow-panel {
    padding: 16px;
  }
  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }
  .panel-header h3 { font-size: 16px; color: var(--text-primary); }

  .empty-state {
    text-align: center;
    padding: 48px 16px;
    color: var(--text-muted);
  }
  .empty-icon { font-size: 48px; margin-bottom: 12px; }

  .workflow-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .workflow-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 12px 16px;
    transition: border-color 0.15s;
  }
  .workflow-card:hover {
    border-color: var(--primary);
  }
  .wf-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }
  .wf-name { font-weight: 600; font-size: 14px; }
  .wf-logs-badge {
    font-size: 12px;
    background: var(--bg-primary);
    padding: 2px 8px;
    border-radius: 10px;
    color: var(--text-secondary);
  }
  .wf-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .performer-badge {
    background: var(--primary);
    color: #fff;
    padding: 1px 6px;
    border-radius: 8px;
    font-size: 10px;
    margin-right: 4px;
  }
</style>

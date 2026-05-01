<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';

  let projects: any[] = $state([]);
  let selectedProject = $state('');
  let nodes: any[] = $state([]);
  let expandedNodes = $state<Set<string>>(new Set());
  let loading = $state(false);

  onMount(async () => {
    const res = await api.handover.projects();
    if (res.success && res.data) {
      projects = res.data;
    }
  });

  function toggleNode(id: string) {
    const next = new Set(expandedNodes);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    expandedNodes = next;
  }

  const typeIcon: Record<string, string> = {
    raw: '📄',
    summary: '📋',
    merge: '🔀',
  };

  const levelColor: Record<string, string> = {
    L0: '#6b7280',
    L1: '#3b82f6',
    L2: '#8b5cf6',
    L3: '#ef4444',
  };
</script>

<div class="dag-panel">
  <div class="panel-header">
    <h3>🌳 Context DAG</h3>
    <span class="text-sm text-muted">Lossless Context Graph</span>
  </div>

  {#if projects.length === 0}
    <div class="empty-state">
      <div class="empty-icon">🌳</div>
      <p>No context data yet.</p>
      <p class="text-sm text-muted">DAG nodes are created when work logs and checkpoints are recorded.</p>
    </div>
  {:else}
    <div class="project-selector">
      <label class="text-sm text-muted">Project:</label>
      <select class="input" bind:value={selectedProject} style="max-width:300px;">
        <option value="">Select...</option>
        {#each projects as p}
          <option value={p.project_path}>{p.project_path?.split('/').pop()}</option>
        {/each}
      </select>
    </div>

    {#if selectedProject}
      <div class="dag-info">
        <div class="info-row">
          <span>📂 {selectedProject.split('/').pop()}</span>
          <span class="text-xs text-muted">Context graph will populate as data is recorded</span>
        </div>
      </div>
    {/if}
  {/if}
</div>

<style>
  .dag-panel { padding: 16px; }
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
  .project-selector {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
  }
  .dag-info {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 16px;
  }
  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
</style>

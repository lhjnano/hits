<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';

  let dagList: any[] = $state([]);
  let selectedProject = $state('');
  let dagData: any = $state(null);
  let lineageData: any[] = $state([]);
  let selectedNode: any = $state(null);
  let searchQuery = $state('');
  let searchResults: any[] = $state([]);
  let loading = $state(false);

  const levelIcon: Record<string, string> = {
    L0: '📄',
    L1: '📋',
    L2: '📊',
    L3: '🎯',
  };

  const levelColor: Record<string, string> = {
    L0: '#6b7280',
    L1: '#3b82f6',
    L2: '#8b5cf6',
    L3: '#ef4444',
  };

  const typeIcon: Record<string, string> = {
    raw: '📄',
    summary: '📋',
    merge: '🔀',
  };

  onMount(() => { loadDags(); });

  async function loadDags() {
    loading = true;
    const res = await api.dag.list();
    if (res.success && res.data) dagList = res.data;
    loading = false;
  }

  async function selectProject(path: string) {
    selectedProject = path;
    selectedNode = null;
    lineageData = [];
    searchResults = [];
    loading = true;
    const res = await api.dag.get(path);
    if (res.success && res.data) dagData = res.data;
    loading = false;
  }

  async function searchNodes() {
    if (!selectedProject || !searchQuery.trim()) return;
    const res = await api.dag.search(selectedProject, searchQuery);
    if (res.success && res.data) searchResults = res.data;
  }

  async function showLineage(nodeId: string) {
    if (!selectedProject) return;
    const res = await api.dag.lineage(selectedProject, nodeId);
    if (res.success && res.data) lineageData = res.data;
  }

  async function selectNode(nodeId: string) {
    if (!dagData) return;
    const node = dagData.nodes.find((n: any) => n.id === nodeId);
    if (node) {
      selectedNode = node;
      await showLineage(nodeId);
    }
  }

  function formatTokens(n: number): string {
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
  }

  // Group nodes by level for visualization
  let nodesByLevel = $derived.by(() => {
    if (!dagData?.nodes) return {};
    const grouped: Record<string, any[]> = { L0: [], L1: [], L2: [], L3: [] };
    for (const node of dagData.nodes) {
      const lvl = node.level || 'L0';
      if (!grouped[lvl]) grouped[lvl] = [];
      grouped[lvl].push(node);
    }
    return grouped;
  });
</script>

<div class="dag-panel">
  {#if loading && dagList.length === 0}
    <div class="text-muted text-center p-md">Loading...</div>
  {:else if dagList.length === 0 && !dagData}
    <!-- Empty state with explanation -->
    <div class="intro-card">
      <div class="intro-icon">🌳</div>
      <h2>Context DAG</h2>
      <p class="intro-desc">
        Every work log and checkpoint is preserved as a node in a
        <strong>Directed Acyclic Graph</strong>. Raw data (L0) is never deleted —
        it gets compressed upward into summaries (L1 → L2 → L3).
      </p>

      <div class="how-it-works">
        <h4>Compression Levels</h4>
        <div class="level-diagram">
          <div class="level-row">
            <span class="level-badge l3">L3</span>
            <span class="level-desc">🎯 Project-level ultra-summary</span>
          </div>
          <div class="level-row">
            <span class="level-badge l2">L2</span>
            <span class="level-desc">📊 Multi-session compact summary</span>
          </div>
          <div class="level-row">
            <span class="level-badge l1">L1</span>
            <span class="level-desc">📋 Per-session summary</span>
          </div>
          <div class="level-row">
            <span class="level-badge l0">L0</span>
            <span class="level-desc">📄 Raw work log / checkpoint data (never deleted)</span>
          </div>
        </div>
      </div>

      <div class="how-it-works">
        <h4>What you can do here</h4>
        <div class="steps">
          <div class="step">
            <div class="step-num">1</div>
            <div>
              <strong>Browse the graph</strong>
              <p class="step-desc">Select a project to see all its context nodes organized by compression level.</p>
            </div>
          </div>
          <div class="step">
            <div class="step-num">2</div>
            <div>
              <strong>Search context</strong>
              <p class="step-desc">Find specific work by keyword across all levels of the graph.</p>
            </div>
          </div>
          <div class="step">
            <div class="step-num">3</div>
            <div>
              <strong>Trace lineage</strong>
              <p class="step-desc">Click any node to see its full ancestry — from summary all the way back to original raw data.</p>
            </div>
          </div>
        </div>
      </div>

      <div class="intro-note">
        <strong>No context data yet.</strong> Nodes appear here automatically when work logs and checkpoints are recorded via MCP tools.
      </div>
    </div>
  {:else}
    <div class="dag-grid">
      <!-- Left: Project selector + node tree -->
      <div class="card tree-card">
        <h3>🌳 Projects</h3>
        <div class="project-list">
          {#each dagList as proj}
            <div
              class="project-row"
              class:selected={selectedProject === proj.project_path}
              role="button"
              tabindex="0"
              onclick={() => selectProject(proj.project_path)}
              onkeydown={(e) => { if (e.key === 'Enter') selectProject(proj.project_path); }}
            >
              <span class="project-name">📂 {proj.project_name || proj.project_path?.split('/').pop()}</span>
              <span class="node-count">{proj.total_nodes} nodes</span>
            </div>
          {/each}
        </div>

        {#if dagData}
          <!-- Stats -->
          <div class="dag-stats">
            <div class="stat-chip">
              <span class="stat-dot" style="background: var(--text-muted)"></span>
              {dagData.stats?.raw_nodes || 0} raw
            </div>
            <div class="stat-chip">
              <span class="stat-dot" style="background: var(--primary)"></span>
              {dagData.stats?.summary_nodes || 0} summary
            </div>
            <div class="stat-chip">
              💾 {formatTokens(dagData.stats?.total_tokens_preserved || 0)}
            </div>
          </div>

          <!-- Search -->
          <div class="search-box">
            <input
              type="text"
              class="input"
              placeholder="Search nodes..."
              bind:value={searchQuery}
              onkeydown={(e) => { if (e.key === 'Enter') searchNodes(); }}
            />
            <button class="btn-sm" onclick={searchNodes}>🔍</button>
          </div>

          {#if searchResults.length > 0}
            <div class="search-results">
              <h4>Search Results</h4>
              {#each searchResults as node}
                <div class="node-row" role="button" onclick={() => selectNode(node.id)}>
                  <span>{levelIcon[node.level]} {node.title?.slice(0, 40)}</span>
                </div>
              {/each}
            </div>
          {/if}

          <!-- Level tree -->
          <div class="level-tree">
            {#each ['L3', 'L2', 'L1', 'L0'] as level}
              {@const nodes = nodesByLevel[level] || []}
              {#if nodes.length > 0}
                <div class="level-section">
                  <div class="level-header">
                    <span class="level-badge" style="background: {levelColor[level]}">{levelIcon[level]} {level}</span>
                    <span class="text-xs text-muted">{nodes.length}</span>
                  </div>
                  {#each nodes as node}
                    <div
                      class="node-row"
                      class:node-selected={selectedNode?.id === node.id}
                      role="button"
                      tabindex="0"
                      onclick={() => selectNode(node.id)}
                      onkeydown={(e) => { if (e.key === 'Enter') selectNode(node.id); }}
                    >
                      <span class="node-title">
                        {typeIcon[node.node_type] || '·'} {node.title?.slice(0, 50) || node.id}
                      </span>
                      <span class="node-tokens text-xs">{formatTokens(node.token_count)}</span>
                    </div>
                  {/each}
                </div>
              {/if}
            {/each}
          </div>
        {/if}
      </div>

      <!-- Right: Node detail + lineage -->
      <div class="card detail-card">
        {#if selectedNode}
          <div class="node-detail">
            <div class="detail-header">
              <span class="level-badge large" style="background: {levelColor[selectedNode.level]}">
                {levelIcon[selectedNode.level]} {selectedNode.level}
              </span>
              <span class="node-type-badge">{selectedNode.node_type}</span>
            </div>
            <h3 class="node-title-full">{selectedNode.title || selectedNode.id}</h3>

            <div class="detail-meta">
              <span>🕐 {selectedNode.created_at?.slice(0, 16) || '?'}</span>
              <span>🔧 {selectedNode.performer || '?'}</span>
              <span>📏 {formatTokens(selectedNode.token_count)} tokens</span>
              {#if selectedNode.source_type}
                <span>📎 {selectedNode.source_type}</span>
              {/if}
            </div>

            {#if selectedNode.tags?.length}
              <div class="tag-list">
                {#each selectedNode.tags as tag}
                  <span class="tag">{tag}</span>
                {/each}
              </div>
            {/if}

            {#if selectedNode.content}
              <div class="content-section">
                <h4>Content</h4>
                <pre class="content-pre">{selectedNode.content.slice(0, 2000)}{selectedNode.content.length > 2000 ? '...' : ''}</pre>
              </div>
            {/if}

            {#if selectedNode.child_ids?.length}
              <div class="relations">
                <h4>↓ Children ({selectedNode.child_ids.length})</h4>
                {#each selectedNode.child_ids as cid}
                  <div class="rel-row" role="button" onclick={() => selectNode(cid)}>
                    ↳ {cid}
                  </div>
                {/each}
              </div>
            {/if}

            {#if selectedNode.parent_ids?.length}
              <div class="relations">
                <h4>↑ Parents ({selectedNode.parent_ids.length})</h4>
                {#each selectedNode.parent_ids as pid}
                  <div class="rel-row" role="button" onclick={() => selectNode(pid)}>
                    ⇡ {pid}
                  </div>
                {/each}
              </div>
            {/if}

            {#if lineageData.length > 0}
              <div class="lineage-section">
                <h4>🔍 Full Lineage ({lineageData.length} nodes)</h4>
                <div class="lineage-chain">
                  {#each lineageData as ln}
                    <div
                      class="lineage-node"
                      class:lineage-active={ln.id === selectedNode.id}
                      role="button"
                      tabindex="0"
                      onclick={() => selectNode(ln.id)}
                      onkeydown={(e) => { if (e.key === 'Enter') selectNode(ln.id); }}
                    >
                      <span class="level-dot" style="background: {levelColor[ln.level]}"></span>
                      <span class="text-xs">{ln.title?.slice(0, 30) || ln.id}</span>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        {:else if dagData}
          <div class="dag-overview">
            <h3>📊 {dagData.project_name || dagData.project_path?.split('/').pop()}</h3>
            <div class="overview-stats">
              {#each Object.entries(dagData.levels || {}) as [level, count]}
                <div class="ov-stat">
                  <span class="level-badge small" style="background: {levelColor[level]}">{level}</span>
                  <span class="ov-count">{count as number}</span>
                </div>
              {/each}
            </div>
            {#if dagData.edges?.length}
              <div class="edges-info">
                <span class="text-sm">🔗 {dagData.edges.length} edges</span>
                {#if dagData.root_id}
                  <span class="text-sm">🌱 Root: {dagData.root_id}</span>
                {/if}
              </div>
            {/if}
            <p class="text-muted text-sm" style="margin-top:12px;">
              Click a node on the left to see its content, relationships, and lineage.
            </p>
          </div>
        {:else}
          <p class="text-muted">Select a project to explore its context graph.</p>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .dag-panel { padding: 16px; }

  .intro-card {
    max-width: 640px; margin: 0 auto;
    text-align: center; padding: 32px 24px;
  }
  .intro-icon { font-size: 48px; margin-bottom: 8px; }
  .intro-card h2 { font-size: 20px; margin-bottom: 8px; }
  .intro-desc { color: var(--text-secondary); font-size: 14px; line-height: 1.6; margin-bottom: 24px; }
  .how-it-works { text-align: left; margin-bottom: 20px; }
  .how-it-works h4 { font-size: 13px; color: var(--text-muted); margin-bottom: 12px; text-align: center; }

  .level-diagram { display: flex; flex-direction: column; gap: 8px; }
  .level-row { display: flex; align-items: center; gap: 10px; }
  .level-badge {
    display: inline-flex; align-items: center; justify-content: center;
    padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;
    color: #fff; min-width: 40px;
  }
  .level-badge.l0 { background: #6b7280; }
  .level-badge.l1 { background: #3b82f6; }
  .level-badge.l2 { background: #8b5cf6; }
  .level-badge.l3 { background: #ef4444; }
  .level-badge.small { font-size: 10px; padding: 1px 6px; min-width: 30px; }
  .level-badge.large { font-size: 13px; padding: 4px 12px; }
  .level-desc { font-size: 13px; }

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

  .dag-grid { display: grid; grid-template-columns: 340px 1fr; gap: 16px; }
  @media (max-width: 768px) { .dag-grid { grid-template-columns: 1fr; } }

  .card {
    background: var(--bg-secondary); border: 1px solid var(--border-color);
    border-radius: 8px; padding: 16px;
  }
  .card h3 { font-size: 15px; margin-bottom: 12px; }
  .card h4 { font-size: 13px; margin: 10px 0 6px; color: var(--text-secondary); }

  .project-list { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
  .project-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 10px; border-radius: 6px; cursor: pointer; transition: background 0.15s;
  }
  .project-row:hover { background: var(--border-color); }
  .project-row.selected { background: rgba(59,130,246,0.08); border: 1px solid var(--primary); border-radius: 6px; }
  .project-name { font-size: 13px; font-weight: 600; }
  .node-count { font-size: 11px; color: var(--text-muted); }

  .dag-stats { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
  .stat-chip { display: flex; align-items: center; gap: 4px; font-size: 11px; }
  .stat-dot { width: 6px; height: 6px; border-radius: 50%; }

  .search-box { display: flex; gap: 4px; margin-bottom: 12px; }
  .search-box .input { flex: 1; font-size: 12px; }
  .btn-sm {
    padding: 4px 8px; font-size: 12px; border-radius: 4px;
    border: 1px solid var(--border-color); background: var(--bg-primary);
    cursor: pointer; color: var(--text-primary);
  }
  .btn-sm:hover { border-color: var(--primary); }

  .search-results { margin-bottom: 12px; }
  .search-results h4 { font-size: 12px; margin-bottom: 4px; }

  .level-tree { max-height: 400px; overflow-y: auto; }
  .level-section { margin-bottom: 8px; }
  .level-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }

  .node-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 4px 8px 4px 24px; border-radius: 4px; cursor: pointer;
    font-size: 12px; transition: background 0.1s;
  }
  .node-row:hover { background: var(--border-color); }
  .node-row.node-selected { background: rgba(59,130,246,0.12); border-left: 2px solid var(--primary); }
  .node-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .node-tokens { color: var(--text-muted); flex-shrink: 0; }

  /* Detail panel */
  .node-detail {}
  .detail-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .node-type-badge {
    font-size: 11px; padding: 1px 6px; border-radius: 3px;
    background: var(--bg-primary); border: 1px solid var(--border-color);
    text-transform: uppercase; font-family: monospace;
  }
  .node-title-full { font-size: 15px; margin-bottom: 8px; word-break: break-word; }

  .detail-meta {
    display: flex; gap: 10px; flex-wrap: wrap; font-size: 12px;
    color: var(--text-secondary); margin-bottom: 10px;
  }
  .tag-list { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 10px; }
  .tag {
    font-size: 10px; padding: 1px 6px; border-radius: 3px;
    background: var(--bg-primary); border: 1px solid var(--border-color);
  }

  .content-section { margin-top: 8px; }
  .content-pre {
    background: var(--bg-primary); border-radius: 6px; padding: 10px;
    font-size: 11px; line-height: 1.5; white-space: pre-wrap; word-break: break-word;
    max-height: 250px; overflow-y: auto; font-family: monospace;
  }

  .relations { margin-top: 8px; }
  .rel-row {
    font-size: 11px; padding: 3px 8px; border-radius: 3px;
    cursor: pointer; font-family: monospace;
  }
  .rel-row:hover { background: var(--bg-primary); }

  .lineage-section { margin-top: 12px; }
  .lineage-chain { display: flex; flex-direction: column; gap: 2px; }
  .lineage-node {
    display: flex; align-items: center; gap: 6px;
    padding: 4px 8px; border-radius: 4px; cursor: pointer;
    transition: background 0.1s;
  }
  .lineage-node:hover { background: var(--bg-primary); }
  .lineage-node.lineage-active { background: rgba(59,130,246,0.12); }
  .level-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

  /* Overview */
  .dag-overview {}
  .overview-stats { display: flex; gap: 12px; margin: 12px 0; }
  .ov-stat { display: flex; align-items: center; gap: 6px; }
  .ov-count { font-size: 16px; font-weight: 700; }
  .edges-info { display: flex; gap: 12px; margin-top: 8px; }
</style>

<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { wsClient } from '../lib/ws';

  let topProjects: any[] = $state([]);
  let dailyData: any[] = $state([]);
  let selectedProject = $state('');
  let projectStats: any = $state(null);
  let budget: any = $state(null);
  let loading = $state(false);
  let liveEvent: string | null = $state(null);

  let maxDaily = $derived(Math.max(...dailyData.map((d: any) => d.tokens_total), 1));

  onMount(() => {
    loadData();
    const unsub = wsClient.on('token_usage_updated', (ev) => {
      liveEvent = `${ev.performer || 'unknown'}: +${ev.data.tokens_used} tokens (${ev.data.model || '?'})`;
      setTimeout(() => { liveEvent = null; }, 3000);
      loadData();
    });
    return unsub;
  });

  async function loadData() {
    loading = true;
    const [topRes] = await Promise.all([
      api.tokens.topProjects(20),
    ]);
    if (topRes.success && topRes.data) topProjects = topRes.data;
    if (selectedProject) await loadProject(selectedProject);
    loading = false;
  }

  async function loadProject(path: string) {
    selectedProject = path;
    const [statsRes, dailyRes, budgetRes] = await Promise.all([
      api.tokens.stats(path),
      api.tokens.daily({ project_path: path, days: 14 }),
      api.tokens.budget(path),
    ]);
    if (statsRes.success && statsRes.data) projectStats = statsRes.data;
    if (dailyRes.success && dailyRes.data) dailyData = dailyRes.data;
    if (budgetRes.success && budgetRes.data) budget = budgetRes.data;
  }

  function formatTokens(n: number): string {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
    return String(n);
  }
  function formatCost(n: number): string { return '$' + n.toFixed(4); }
</script>

<div class="token-dashboard">
  {#if liveEvent}
    <div class="live-banner">⚡ {liveEvent}</div>
  {/if}

  <!-- No data at all: explain what this is -->
  {#if !loading && topProjects.length === 0 && !projectStats}
    <div class="intro-card">
      <div class="intro-icon">📊</div>
      <h2>Token Usage Dashboard</h2>
      <p class="intro-desc">
        Track how many tokens each AI tool (Claude, OpenCode, Cursor) consumes per project.
        Set monthly budgets and get alerts before you overspend.
      </p>

      <div class="how-it-works">
        <h4>How it works</h4>
        <div class="steps">
          <div class="step">
            <div class="step-num">1</div>
            <div>
              <strong>Auto-tracked</strong>
              <p class="step-desc">Every MCP tool call (record_work, auto_checkpoint, resume, etc.) automatically records estimated token usage.</p>
            </div>
          </div>
          <div class="step">
            <div class="step-num">2</div>
            <div>
              <strong>Per-project breakdown</strong>
              <p class="step-desc">See which tools, models, and operations consume the most tokens for each project.</p>
            </div>
          </div>
          <div class="step">
            <div class="step-num">3</div>
            <div>
              <strong>Budget alerts</strong>
              <p class="step-desc">Set a monthly token budget per project. Get warned when you hit 80%.</p>
            </div>
          </div>
        </div>
      </div>

      <div class="intro-note">
        <strong>No data yet.</strong> Start using HITS MCP tools (hits_record_work, hits_auto_checkpoint) and token usage will appear here automatically.
      </div>
    </div>
  {:else}
    <div class="dashboard-grid">
      <!-- Left: Project list -->
      <div class="card">
        <h3>📊 Projects by Token Usage</h3>
        {#if topProjects.length === 0}
          <p class="text-muted text-sm">No token usage recorded yet.</p>
        {:else}
          <div class="project-list">
            {#each topProjects as proj}
              <div
                class="project-row"
                class:selected={selectedProject === proj.project_path}
                role="button"
                tabindex="0"
                onclick={() => loadProject(proj.project_path)}
                onkeydown={(e) => { if (e.key === 'Enter') loadProject(proj.project_path); }}
              >
                <span class="project-name">
                  📂 {proj.project_path?.split('/').pop() || proj.project_path}
                </span>
                <span class="token-badge">{formatTokens(proj.total_tokens)}</span>
                <span class="cost-badge">{formatCost(proj.total_cost_usd)}</span>
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Right: Project detail -->
      {#if projectStats}
        <div class="card detail-card">
          <h3>📈 {projectStats.project_name || selectedProject.split('/').pop()}</h3>

          <div class="stats-grid">
            <div class="stat-box">
              <div class="stat-value">{formatTokens(projectStats.total_tokens)}</div>
              <div class="stat-label">Total Tokens</div>
            </div>
            <div class="stat-box">
              <div class="stat-value">{projectStats.total_records}</div>
              <div class="stat-label">API Calls</div>
            </div>
            <div class="stat-box">
              <div class="stat-value">{formatCost(projectStats.total_cost_usd)}</div>
              <div class="stat-label">Est. Cost</div>
            </div>
            <div class="stat-box">
              <div class="stat-value">{projectStats.active_days}</div>
              <div class="stat-label">Active Days</div>
            </div>
          </div>

          <!-- Budget -->
          {#if budget && budget.monthly_token_limit > 0}
            <div class="budget-section">
              <h4>💰 Monthly Budget</h4>
              <div class="budget-bar-bg">
                <div
                  class="budget-bar"
                  class:warning={budget.budget_used_pct > 80}
                  style="width: {Math.min(budget.budget_used_pct, 100)}%"
                ></div>
              </div>
              <div class="budget-text">
                {budget.budget_used_pct?.toFixed(1)}% used · {formatTokens(budget.remaining || 0)} remaining
              </div>
              {#if budget.alert}
                <div class="alert-msg">⚠️ {budget.alert}</div>
              {/if}
            </div>
          {/if}

          <!-- Daily chart -->
          {#if dailyData.length > 0}
            <div class="chart-section">
              <h4>📅 Daily Usage (14 days)</h4>
              <div class="bar-chart">
                {#each dailyData as day}
                  <div class="bar-col" title="{day.date}: {formatTokens(day.tokens_total)}">
                    <div class="bar" style="height: {(day.tokens_total / maxDaily) * 100}%"></div>
                    <div class="bar-label">{day.date.slice(-2)}</div>
                  </div>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Breakdown -->
          {#if Object.keys(projectStats.by_model || {}).length > 0 || Object.keys(projectStats.by_performer || {}).length > 0}
            <div class="breakdown-section">
              {#if Object.keys(projectStats.by_performer || {}).length > 0}
                <h4>🔧 By Tool</h4>
                <div class="breakdown-list">
                  {#each Object.entries(projectStats.by_performer) as [tool, tokens]}
                    <div class="breakdown-row">
                      <span>{tool}</span>
                      <span>{formatTokens(tokens as number)}</span>
                    </div>
                  {/each}
                </div>
              {/if}
              {#if Object.keys(projectStats.by_operation || {}).length > 0}
                <h4>⚙️ By Operation</h4>
                <div class="breakdown-list">
                  {#each Object.entries(projectStats.by_operation) as [op, tokens]}
                    <div class="breakdown-row">
                      <span class="mono">{op}</span>
                      <span>{formatTokens(tokens as number)}</span>
                    </div>
                  {/each}
                </div>
              {/if}
              {#if Object.keys(projectStats.by_model || {}).length > 0}
                <h4>🤖 By Model</h4>
                <div class="breakdown-list">
                  {#each Object.entries(projectStats.by_model) as [model, tokens]}
                    <div class="breakdown-row">
                      <span>{model}</span>
                      <span>{formatTokens(tokens as number)}</span>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {:else}
        <div class="card">
          <p class="text-muted">Select a project on the left to see detailed usage breakdown.</p>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .token-dashboard { padding: 16px; }
  .live-banner {
    position: fixed; top: 8px; right: 8px;
    background: var(--success); color: #fff;
    padding: 6px 14px; border-radius: 6px;
    font-size: 12px; z-index: 100;
  }

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

  .dashboard-grid { display: grid; grid-template-columns: 320px 1fr; gap: 16px; }
  @media (max-width: 768px) { .dashboard-grid { grid-template-columns: 1fr; } }

  .card {
    background: var(--bg-secondary); border: 1px solid var(--border-color);
    border-radius: 8px; padding: 16px;
  }
  .card h3 { font-size: 15px; margin-bottom: 12px; }
  .card h4 { font-size: 13px; margin: 12px 0 8px; color: var(--text-secondary); }

  .project-row {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 10px; border-radius: 6px; cursor: pointer; transition: background 0.15s;
  }
  .project-row:hover { background: var(--border-color); }
  .project-row.selected { background: var(--primary); color: #fff; }
  .project-name { flex: 1; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .token-badge { font-size: 12px; font-weight: 600; color: var(--primary); }
  .cost-badge { font-size: 11px; color: var(--text-muted); min-width: 50px; text-align: right; }

  .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 16px; }
  @media (max-width: 600px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }
  .stat-box { background: var(--bg-primary); border-radius: 6px; padding: 12px; text-align: center; }
  .stat-value { font-size: 18px; font-weight: 700; color: var(--primary); }
  .stat-label { font-size: 11px; color: var(--text-muted); margin-top: 4px; }

  .budget-bar-bg { height: 8px; background: var(--bg-primary); border-radius: 4px; overflow: hidden; margin: 8px 0; }
  .budget-bar { height: 100%; background: var(--primary); border-radius: 4px; transition: width 0.3s ease; }
  .budget-bar.warning { background: #e53e3e; }
  .budget-text { font-size: 12px; color: var(--text-secondary); }
  .alert-msg { background: rgba(229,62,62,0.1); color: #e53e3e; padding: 8px 12px; border-radius: 6px; font-size: 12px; margin-top: 8px; }

  .bar-chart { display: flex; align-items: flex-end; gap: 2px; height: 120px; padding: 8px 0; }
  .bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; }
  .bar { width: 100%; background: var(--primary); border-radius: 2px 2px 0 0; min-height: 2px; }
  .bar-label { font-size: 9px; color: var(--text-muted); margin-top: 2px; }

  .breakdown-list { margin-bottom: 8px; }
  .breakdown-row { display: flex; justify-content: space-between; font-size: 12px; padding: 4px 8px; border-radius: 4px; }
  .breakdown-row:nth-child(even) { background: var(--bg-primary); }
  .mono { font-family: monospace; font-size: 11px; }
</style>

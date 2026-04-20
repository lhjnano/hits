<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { t, subscribeLocale } from '../lib/i18n';

  let { selectedProject = $bindable('') } = $props<{ selectedProject: string }>();

  let loading = $state(true);
  let error = $state('');
  let checkpointData = $state<any>(null);
  let handoverData = $state<any>(null);
  let checkpoints = $state<any[]>([]);
  let localeTick = $state(0);
  let showHistory = $state(false);
  let copyFeedback = $state('');
  let expandedSections = $state<Record<string, boolean>>({
    achieved: true,
    nextSteps: true,
    mustKnow: true,
    decisions: false,
    blockers: false,
    files: false,
    sessionHistory: false,
    recentWork: false,
  });

  onMount(() => {
    const unsub = subscribeLocale(() => localeTick++);
    return unsub;
  });

  // Reload when project changes
  $effect(() => {
    if (selectedProject) loadAll();
  });

  async function loadAll() {
    loading = true;
    error = '';
    checkpointData = null;
    handoverData = null;

    const [cpRes, hvRes] = await Promise.all([
      api.checkpoints.resume(selectedProject, 2000),
      api.handover.get(selectedProject),
    ]);

    if (cpRes.success && cpRes.data) checkpointData = cpRes.data;
    if (hvRes.success && hvRes.data) handoverData = hvRes.data;

    if (!cpRes.success && !hvRes.success) {
      error = cpRes.error || hvRes.error || 'No data available';
    }
    loading = false;
  }

  async function loadHistory() {
    const res = await api.checkpoints.list(selectedProject, 10);
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

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
  }

  async function resumeWith(tool: string) {
    if (tool === 'copy') {
      const context = buildResumePrompt();
      await copyText(context);
      copyFeedback = '✅ Copied!';
      setTimeout(() => { copyFeedback = ''; }, 3000);
      return;
    }

    const cp = checkpointData?.checkpoint;
    const toolLabel = tool === 'claude' ? 'Claude Code' : 'OpenCode';

    // Send signal so hook picks it up on next session start
    const res = await api.signals.send({
      sender: 'web-ui',
      recipient: tool,
      signal_type: 'task_ready',
      project_path: selectedProject,
      summary: cp?.purpose || 'Resume via web UI',
      context: cp?.current_state || '',
      pending_items: (cp?.next_steps || []).map((s: any) => s.action),
      tags: ['resume', 'web-ui'],
    });

    if (res.success) {
      copyFeedback = `✅ Signal sent to ${toolLabel} — will auto-resume on next session start`;
    } else {
      const context = buildResumePrompt();
      await copyText(context);
      copyFeedback = `⚠ Copy instead — paste into ${toolLabel}`;
    }
    setTimeout(() => { copyFeedback = ''; }, 5000);
  }

  function buildResumePrompt(): string {
    const lines: string[] = [];
    const cp = checkpointData?.checkpoint;

    lines.push(`# Resume: ${selectedProject.split('/').pop()}`);
    lines.push('');

    if (cp) {
      lines.push('## Goal');
      lines.push(cp.purpose || '(no purpose set)');
      lines.push('');
      lines.push('## Current State');
      lines.push(cp.current_state || '(no state recorded)');
      lines.push('');

      if (cp.next_steps?.length) {
        lines.push('## Next Steps');
        for (let i = 0; i < cp.next_steps.length; i++) {
          const s = cp.next_steps[i];
          lines.push(`${i + 1}. [${s.priority || 'medium'}] ${s.action}`);
          if (s.command) lines.push(`   → ${s.command}`);
          if (s.file) lines.push(`   📄 ${s.file}`);
        }
        lines.push('');
      }

      if (cp.required_context?.length) {
        lines.push('## Must Know');
        for (const ctx of cp.required_context) lines.push(`- ${ctx}`);
        lines.push('');
      }

      if (cp.decisions_made?.length) {
        lines.push('## Decisions');
        for (const d of cp.decisions_made) {
          lines.push(`- ${d.decision}${d.rationale ? ` (${d.rationale})` : ''}`);
        }
        lines.push('');
      }

      if (cp.blocks?.length) {
        lines.push('## Blockers');
        for (const b of cp.blocks) {
          lines.push(`- ${b.issue}${b.workaround ? ` → Workaround: ${b.workaround}` : ''}`);
        }
        lines.push('');
      }
    }

    // Pending signals
    if (checkpointData?.signals?.length) {
      lines.push('## Pending Signals');
      for (const sig of checkpointData.signals) {
        lines.push(`- [${sig.priority}] ${sig.sender}: ${sig.summary}`);
        if (sig.pending_items) lines.push(`  Items: ${sig.pending_items.join(', ')}`);
      }
      lines.push('');
    }

    // Compressed version available
    if (checkpointData?.compressed) {
      lines.push('---');
      lines.push('## Compressed Context (paste directly)');
      lines.push(checkpointData.compressed);
    }

    return lines.join('\n');
  }

  function toggleSection(key: string) {
    expandedSections[key] = !expandedSections[key];
  }
</script>

<div data-locale-tick={localeTick}>
  <!-- Header with action buttons -->
  <div class="flex items-center" style="margin-bottom:16px;">
    <h2 style="font-size:16px; flex:1;">
      ▶ {selectedProject ? selectedProject.split('/').pop() : 'Resume'}
    </h2>
    {#if copyFeedback}
      <span style="color:var(--success); font-size:12px; margin-right:8px;">{copyFeedback}</span>
    {/if}
    <button class="btn btn-secondary btn-sm" onclick={loadHistory}>📋 History</button>
    <button class="btn btn-secondary btn-sm" onclick={loadAll} style="margin-left:4px;">🔄</button>
  </div>

  {#if !selectedProject}
    <div class="empty-state">
      <div class="icon">▶</div>
      <div class="message">Select a project from the sidebar</div>
    </div>
  {:else if loading}
    <div class="loading"><div class="spinner"></div></div>
  {:else if error && !checkpointData && !handoverData}
    <div class="card" style="text-align:center; color:var(--text-muted);">{error}</div>
  {:else}
    <!-- ═══ RESUME ACTIONS (most important!) ═══ -->
    {#if checkpointData?.checkpoint || checkpointData?.compressed}
      <div class="card" style="margin-bottom:16px; border:2px solid var(--success);">
        <div class="flex items-center" style="margin-bottom:12px;">
          <h3 style="color:var(--success); flex:1;">🚀 Resume Work</h3>
          <button class="btn btn-secondary btn-sm" onclick={() => resumeWith('copy')}>
            📋 Copy
          </button>
        </div>

        <div class="flex gap-sm" style="margin-bottom:12px;">
          <button class="btn btn-primary" onclick={() => resumeWith('claude')}>
            ▶ Claude Code
          </button>
          <button class="btn btn-primary" onclick={() => resumeWith('opencode')}>
            ▶ OpenCode
          </button>
        </div>

        {#if copyFeedback}
          <div style="color:var(--success); font-size:13px;">{copyFeedback}</div>
        {/if}

        <!-- Hook setup (collapsible) -->
        <details>
          <summary class="text-sm text-muted" style="cursor:pointer;">First time? Set up auto-resume hooks</summary>
          <div style="margin-top:8px;">
            <div class="text-sm text-muted" style="margin-bottom:4px;">
              Connect once — then resume is automatic every time you start your AI tool.
            </div>
            <code style="display:block; padding:8px; background:var(--bg-secondary); border-radius:4px; font-size:12px; user-select:all;">
              npx @purpleraven/hits connect claude
            </code>
            <code style="display:block; padding:8px; background:var(--bg-secondary); border-radius:4px; font-size:12px; margin-top:4px; user-select:all;">
              npx @purpleraven/hits connect opencode
            </code>
          </div>
        </details>
      </div>
    {/if}

    <!-- ═══ CHECKPOINT DATA ═══ -->
    {#if checkpointData?.checkpoint}
      {@const cp = checkpointData.checkpoint}

      <!-- Header -->
      <div class="card" style="margin-bottom:16px;">
        <div class="flex items-center gap-sm">
          <span style="font-size:24px;">💾</span>
          <div style="flex:1;">
            <div style="font-weight:600;">{cp.purpose || 'No purpose set'}</div>
            <div class="text-sm text-muted">{cp.current_state || ''}</div>
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

      <!-- Next Steps (always expanded) -->
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

      <!-- Collapsible sections -->
      {#if cp.decisions_made?.length}
        <div class="handover-section">
          <h3 style="cursor:pointer;" onclick={() => toggleSection('decisions')}>
            {expandedSections.decisions ? '▼' : '▶'} ★ Decisions
          </h3>
          {#if expandedSections.decisions}
            {#each cp.decisions_made as d}
              <div class="handover-item">
                {d.decision}
                {#if d.rationale}
                  <div class="text-xs text-muted">→ {d.rationale}</div>
                {/if}
              </div>
            {/each}
          {/if}
        </div>
      {/if}

      {#if cp.blocks?.length}
        <div class="handover-section" style="border-left-color:var(--danger);">
          <h3 style="cursor:pointer;" onclick={() => toggleSection('blockers')}>
            {expandedSections.blockers ? '▼' : '▶'} 🚫 Blockers
          </h3>
          {#if expandedSections.blockers}
            {#each cp.blocks as b}
              <div class="handover-item">
                {b.issue}
                {#if b.workaround}
                  <div class="text-xs" style="color:var(--success);">Workaround: {b.workaround}</div>
                {/if}
              </div>
            {/each}
          {/if}
        </div>
      {/if}

      {#if cp.files_delta?.length}
        <div class="handover-section">
          <h3 style="cursor:pointer;" onclick={() => toggleSection('files')}>
            {expandedSections.files ? '▼' : '▶'} 📄 Files ({cp.files_delta.length})
          </h3>
          {#if expandedSections.files}
            {#each cp.files_delta.slice(0, 10) as fd}
              <div class="handover-item" style="font-family:var(--font-mono); font-size:12px;">
                [{fd.change_type === 'created' ? '+' : fd.change_type === 'deleted' ? '-' : '~'}] {fd.path}
              </div>
            {/each}
          {/if}
        </div>
      {/if}
    {/if}

    <!-- ═══ PENDING SIGNALS ═══ -->
    {#if checkpointData?.signals?.length}
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

    <!-- ═══ HANDOVER DATA (session history, recent work) ═══ -->
    {#if handoverData}
      {#if handoverData.session_history?.length}
        <div class="handover-section" style="margin-top:16px;">
          <h3 style="cursor:pointer;" onclick={() => toggleSection('sessionHistory')}>
            {expandedSections.sessionHistory ? '▼' : '▶'} 👥 Session History
          </h3>
          {#if expandedSections.sessionHistory}
            {#each handoverData.session_history as session}
              <div class="handover-item">
                <strong>{session.performed_by}</strong>: {session.log_count}
                <span class="text-xs text-muted" style="margin-left:8px;">
                  {(session.last_activity || '').slice(0, 16)}
                </span>
              </div>
            {/each}
          {/if}
        </div>
      {/if}

      {#if handoverData.recent_logs?.length}
        <div class="handover-section">
          <h3 style="cursor:pointer;" onclick={() => toggleSection('recentWork')}>
            {expandedSections.recentWork ? '▼' : '▶'} 📝 Recent Work
          </h3>
          {#if expandedSections.recentWork}
            {#each handoverData.recent_logs.slice(0, 10) as log}
              <div class="handover-item">
                <span class="text-xs text-muted">{(log.performed_at || '').slice(5, 16)}</span>
                <span style="margin-left:8px;" class="badge">{log.performed_by}</span>
                <span style="margin-left:8px;">{(log.request_text || '').slice(0, 80)}</span>
                {#if log.tags?.length}
                  <div class="tags" style="display:inline-flex; margin-left:4px;">
                    {#each log.tags as tag}
                      <span class="tag">{tag}</span>
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          {/if}
        </div>
      {/if}
    {/if}

    <!-- Empty state: no checkpoint, no handover -->
    {#if !checkpointData?.checkpoint && !handoverData}
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

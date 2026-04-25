<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { t, subscribeLocale } from '../lib/i18n';

  let { selectedProject = $bindable('') } = $props<{ selectedProject: string }>();

  let loading = $state(true);
  let localeTick = $state(0);
  let copyFeedback = $state('');
  let feedback = $state('');
  let feedbackType = $state<'success' | 'error' | 'info'>('info');

  // Data
  let tasks = $state<any[]>([]);
  let slackChannels = $state<any[]>([]);
  let checkpointData = $state<any>(null);
  let handoverData = $state<any>(null);

  // Modals
  let showAddModal = $state(false);
  let showEditModal = $state<string | null>(null);
  let showSlackSettings = $state(false);
  let showExportMenu = $state<string | null>(null);
  let showHistory = $state(false);
  let checkpoints = $state<any[]>([]);
  let expandedTask = $state<string | null>(null);

  // Add/Edit form
  let formTitle = $state('');
  let formProject = $state('');
  let formPriority = $state('medium');
  let formContext = $state('');
  let formError = $state('');
  let editTitle = $state('');
  let editProject = $state('');
  let editPriority = $state('medium');
  let editContext = $state('');

  // Slack form
  let slackName = $state('');
  let slackUrl = $state('');
  let slackBotToken = $state('');
  let slackChannelId = $state('');

  // Section expansion for checkpoint details
  let expandedSections = $state<Record<string, boolean>>({
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

  $effect(() => {
    if (selectedProject) loadAll();
  });

  async function loadAll() {
    loading = true;
    const [tasksRes, channelsRes, cpRes, hvRes] = await Promise.all([
      api.tasks.list({ project_path: selectedProject }),
      api.tasks.slackChannels(),
      api.checkpoints.resume(selectedProject, 2000),
      api.handover.get(selectedProject),
    ]);
    if (tasksRes.success && tasksRes.data) tasks = tasksRes.data;
    if (channelsRes.success && channelsRes.data) slackChannels = channelsRes.data;
    if (cpRes.success && cpRes.data) checkpointData = cpRes.data;
    if (hvRes.success && hvRes.data) handoverData = hvRes.data;
    loading = false;
  }

  function setFeedback(msg: string, type: 'success' | 'error' | 'info' = 'info') {
    feedback = msg; feedbackType = type;
    setTimeout(() => feedback = '', 4000);
  }

  // --- Task CRUD ---
  async function addTask() {
    if (!formTitle.trim()) return;
    formError = '';
    const res = await api.tasks.create({
      title: formTitle, project_path: formProject || selectedProject,
      priority: formPriority, context: formContext, created_by: 'manual',
    });
    if (res.success) {
      showAddModal = false;
      formTitle = ''; formProject = ''; formPriority = 'medium'; formContext = '';
      await loadAll();
    } else { formError = res.error || 'Failed'; }
  }

  function openEditModal(task: any) {
    showEditModal = task.id;
    editTitle = task.title; editProject = task.project_path || '';
    editPriority = task.priority; editContext = task.context || '';
  }

  async function saveEdit() {
    if (!showEditModal) return;
    await api.tasks.update(showEditModal, {
      title: editTitle, project_path: editProject,
      priority: editPriority, context: editContext,
    });
    showEditModal = null;
    await loadAll();
  }

  async function startTask(id: string) {
    const res = await api.tasks.start(id);
    if (res.success) {
      setFeedback(res.data?.action === 'started' ? '🚀 작업 시작' : '▶ 작업 재개', 'success');
    } else {
      setFeedback(res.error || '시작 실패', 'error');
    }
    await loadAll();
  }

  async function markDone(id: string) {
    await api.tasks.update(id, { status: 'done' });
    await loadAll();
  }

  async function reopen(id: string) {
    await api.tasks.update(id, { status: 'pending' });
    await loadAll();
  }

  async function deleteTask(id: string) {
    await api.tasks.delete(id);
    await loadAll();
  }

  // --- Slack ---
  function hasSlackConnection(): boolean { return slackChannels.length > 0; }

  async function addSlackChannel() {
    if (!slackName.trim() || !slackUrl.trim()) return;
    await api.tasks.addSlackChannel({
      name: slackName, webhook_url: slackUrl,
      bot_token: slackBotToken, channel_id: slackChannelId,
    });
    slackName = ''; slackUrl = ''; slackBotToken = ''; slackChannelId = '';
    await loadAll();
  }

  async function removeSlackChannel(name: string) {
    await api.tasks.deleteSlackChannel(name);
    await loadAll();
  }

  async function exportToSlack(taskId: string, channel: string) {
    const res = await api.tasks.exportToSlack(taskId, channel);
    if (res.success) setFeedback(`✅ ${channel}에 내보냄`, 'success');
    else setFeedback(`❌ ${res.error}`, 'error');
    showExportMenu = null;
    await loadAll();
  }

  async function importFromSlack(channel: string) {
    setFeedback('⏳ 가져오는 중...', 'info');
    const res = await api.tasks.importFromSlack(channel);
    if (res.success) setFeedback(`✅ ${channel}에서 ${res.data?.imported || 0}개 가져옴`, 'success');
    else setFeedback(`⚠️ ${res.data?.hint || res.error}`, 'error');
    await loadAll();
  }

  // --- Resume ---
  async function copyText(text: string) {
    try { await navigator.clipboard.writeText(text); }
    catch { const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); }
  }

  function buildResumePrompt(task: any, cp?: any): string {
    const lines: string[] = [];
    lines.push(`# ${t('resume.title')}: ${task.title}`);
    lines.push('');
    if (cp) {
      lines.push('## Goal');
      lines.push(cp.purpose || task.title);
      lines.push('');
      lines.push('## Current State');
      lines.push(cp.current_state || task.context || '');
      lines.push('');
      if (cp.next_steps?.length) {
        lines.push(`## ${t('resume.nextSteps')}`);
        for (const s of cp.next_steps) {
          lines.push(`- [${s.priority || 'medium'}] ${s.action}`);
          if (s.command) lines.push(`  → ${s.command}`);
          if (s.file) lines.push(`  📄 ${s.file}`);
        }
        lines.push('');
      }
      if (cp.required_context?.length) {
        lines.push(`## ${t('resume.mustKnow')}`);
        for (const c of cp.required_context) lines.push(`- ${c}`);
        lines.push('');
      }
      if (cp.decisions_made?.length) {
        lines.push(`## ${t('resume.decisions')}`);
        for (const d of cp.decisions_made) lines.push(`- ${d.decision}${d.rationale ? ` (${d.rationale})` : ''}`);
        lines.push('');
      }
      if (cp.blocks?.length) {
        lines.push(`## ${t('resume.blockers')}`);
        for (const b of cp.blocks) lines.push(`- ${b.issue}${b.workaround ? ` → ${b.workaround}` : ''}`);
        lines.push('');
      }
      if (cp.knowledge_tips?.length) {
        lines.push(`## ${t('resume.projectTips')}`);
        for (const tip of cp.knowledge_tips) {
          const icon = tip.negative ? '🚫' : tip.layer === 'how' ? '🔧' : tip.layer === 'why' ? '🎯' : '📄';
          lines.push(`${icon} ${tip.name}${tip.action ? ` → ${tip.action}` : ''}`);
        }
        lines.push('');
      }
    } else {
      if (task.context) { lines.push('## Context'); lines.push(task.context); lines.push(''); }
      if (task.project_path) { lines.push('## Project'); lines.push(task.project_path); lines.push(''); }
    }
    if (task.source === 'slack') {
      lines.push(`## Source: Slack #${task.slack_channel}`);
      if (task.source_env?.hostname) lines.push(`Original env: ${task.source_env.hostname}`);
      lines.push('');
    }
    return lines.join('\n');
  }

  async function resumeWith(tool: string, task: any, cp?: any) {
    const prompt = buildResumePrompt(task, cp);
    await copyText(prompt);
    const toolLabel = tool === 'claude' ? 'Claude Code' : 'OpenCode';
    const res = await api.signals.send({
      sender: 'web-ui', recipient: tool, signal_type: 'task_ready',
      project_path: task.project_path || selectedProject,
      summary: task.title, context: cp?.current_state || task.context || '',
      pending_items: cp?.next_steps?.map((s: any) => s.action) || [],
      tags: ['resume', 'web-ui'],
    });
    if (res.success) setFeedback(`✅ ${toolLabel} 시그널 전송 + 프롬프트 복사됨`, 'success');
    else setFeedback(`✅ 프롬프트 복사됨 — ${toolLabel}에 붙여넣으세요`, 'info');
  }

  async function copyResume(task: any, cp?: any) {
    await copyText(buildResumePrompt(task, cp));
    copyFeedback = '✅ Copied!';
    setTimeout(() => copyFeedback = '', 3000);
  }

  // --- Helpers ---
  function priorityIcon(p: string): string {
    return { critical: '🔴', high: '🟠', medium: '🔵', low: '⚪' }[p] || '🔵';
  }
  function sourceLabel(task: any): string {
    return task.source === 'slack' ? `💬 ${task.slack_channel}` : '💻 Local';
  }
  function isRemote(task: any): boolean {
    return task.source !== 'local' && task.source_env?.hostname;
  }
  function progressBar(pct: number): string {
    return `${'█'.repeat(Math.floor(pct / 10))}${'░'.repeat(10 - Math.floor(pct / 10))} ${pct}%`;
  }
  function toggleSection(key: string) { expandedSections[key] = !expandedSections[key]; }

  // --- Derived ---
  let pendingTasks = $derived(tasks.filter(t => t.status === 'pending'));
  let activeTasks = $derived(tasks.filter(t => t.status === 'in_progress'));
  let doneTasks = $derived(tasks.filter(t => t.status === 'done'));

  async function loadHistory() {
    const res = await api.checkpoints.list(selectedProject, 10);
    if (res.success && res.data) { checkpoints = res.data; showHistory = true; }
  }
</script>

<div data-locale-tick={localeTick} class="resume-panel">
  <!-- Feedback -->
  {#if feedback}
    <div class="feedback-bar" class:feedback-success={feedbackType === 'success'} class:feedback-error={feedbackType === 'error'}>{feedback}</div>
  {/if}

  <!-- Header -->
  <div class="header-row">
    <h2>▶ {selectedProject ? selectedProject.split('/').pop() : t('resume.title')}</h2>
    <div class="header-actions">
      {#if copyFeedback}<span style="color:var(--success);font-size:12px;margin-right:8px;">{copyFeedback}</span>{/if}
      <button class="btn btn-secondary btn-sm" onclick={() => showSlackSettings = !showSlackSettings}>⚙️ Slack</button>
      <button class="btn btn-secondary btn-sm" onclick={loadHistory}>📋 {t('resume.history')}</button>
      <button class="btn btn-secondary btn-sm" onclick={loadAll}>🔄</button>
      <button class="btn btn-primary btn-sm" onclick={() => showAddModal = true}>+ {t('tasks.addTask')}</button>
    </div>
  </div>

  <!-- Slack Settings -->
  {#if showSlackSettings}
    <div class="card slack-settings">
      <div class="settings-title">⚙️ Slack 연결</div>
      {#each slackChannels as ch}
        <div class="channel-row">
          <div class="channel-info">
            <span class="channel-name">💬 {ch.name}</span>
            <span class="channel-url">{ch.webhook_url?.slice(0, 40)}...</span>
            {#if ch.bot_token}<span class="channel-meta">📥 읽기 가능</span>{:else}<span class="channel-meta">📤 내보내기 전용</span>{/if}
          </div>
          <div class="channel-actions">
            {#if ch.bot_token && ch.channel_id}
              <button class="btn btn-secondary btn-sm" onclick={() => importFromSlack(ch.name)}>📥 {t('tasks.import')}</button>
            {/if}
            <button class="btn-icon btn-delete" onclick={() => removeSlackChannel(ch.name)}>✕</button>
          </div>
        </div>
      {/each}
      <div class="add-channel-form">
        <input class="input channel-name-input" placeholder="#channel-name" bind:value={slackName} />
        <input class="input channel-url-input" placeholder="Webhook URL (내보내기용)" bind:value={slackUrl} />
      </div>
      <details class="slack-advanced">
        <summary>고급: 읽기(가져오기) 설정</summary>
        <div class="advanced-fields">
          <input class="input" placeholder="Bot Token xoxb-... (가져오기용)" bind:value={slackBotToken} />
          <input class="input" placeholder="Channel ID C0XXXXXX" bind:value={slackChannelId} />
        </div>
      </details>
      <button class="btn btn-primary btn-sm" style="margin-top:8px;" onclick={addSlackChannel}>+ {t('tasks.addChannel')}</button>
    </div>
  {/if}

  {#if !selectedProject}
    <div class="empty-state"><div class="icon">▶</div><div class="message">{t('resume.selectProject')}</div></div>
  {:else if loading}
    <div class="loading"><div class="spinner"></div></div>
  {:else}

    <!-- ═══ IN PROGRESS ═══ -->
    {#if activeTasks.length > 0}
      <div class="section-label">🔄 {t('tasks.inProgress')} ({activeTasks.length})</div>
      {#each activeTasks as task (task.id)}
        {@const cp = checkpointData?.checkpoint?.purpose === task.title ? checkpointData.checkpoint : null}
        <div class="task-card in-progress" class:task-remote={isRemote(task)}>
          <!-- Title row -->
          <div class="task-header">
            <span class="priority">{priorityIcon(task.priority)}</span>
            <strong class="task-title">{task.title}</strong>
            {#if task.project_name}<span class="badge">📂 {task.project_name}</span>{/if}
            <span class="source-badge">{sourceLabel(task)}</span>
            {#if cp}<span class="badge progress-badge">{progressBar(cp.completion_pct || 0)}</span>{/if}
          </div>

          <!-- Current state -->
          {#if cp?.current_state}
            <div class="task-context">{cp.current_state}</div>
          {:else if task.context}
            <div class="task-context">{task.context}</div>
          {/if}

          {#if isRemote(task)}
            <div class="env-warning">⚠️ {task.source_env.hostname} {task.source_env.os || ''}</div>
          {/if}

          <!-- ══ Resume Actions ══ -->
          <div class="resume-actions">
            <button class="btn btn-primary" onclick={() => resumeWith('claude', task, cp)}>
              ▶ Claude Code
            </button>
            <button class="btn btn-primary" onclick={() => resumeWith('opencode', task, cp)}>
              ▶ OpenCode
            </button>
            <button class="btn btn-secondary btn-sm" onclick={() => copyResume(task, cp)}>
              📋 {t('resume.copy')}
            </button>
          </div>

          <!-- ══ Checkpoint Detail ══ -->
          {#if cp}
            <!-- Next Steps -->
            {#if cp.next_steps?.length}
              <div class="handover-section" style="border-left-color:var(--success);">
                <h3>▶ {t('resume.nextSteps')}</h3>
                {#each cp.next_steps as step, i}
                  <div class="handover-item">
                    <div class="flex items-center gap-sm">
                      <span class="badge" class:badge-critical={step.priority === 'critical'} class:badge-high={step.priority === 'high'}>
                        {step.priority === 'critical' ? '🔴' : step.priority === 'high' ? '🟡' : '🟢'}
                      </span>
                      <strong>{i + 1}. {step.action}</strong>
                    </div>
                    {#if step.command}<code class="text-sm" style="margin-left:24px;color:var(--info);">→ {step.command}</code>{/if}
                    {#if step.file}<span class="text-xs text-muted" style="margin-left:24px;">📄 {step.file}</span>{/if}
                  </div>
                {/each}
              </div>
            {/if}

            <!-- Must Know -->
            {#if cp.required_context?.length}
              <div class="handover-section" style="border-left-color:var(--warning);">
                <h3>⚠ {t('resume.mustKnow')}</h3>
                {#each cp.required_context as ctx}<div class="handover-item">• {ctx}</div>{/each}
              </div>
            {/if}

            <!-- Knowledge Tips -->
            {#if cp.knowledge_tips?.length}
              <div class="handover-section" style="border-left-color:var(--info, #4a9eff);">
                <h3>💡 {t('resume.projectTips')}</h3>
                {#each cp.knowledge_tips as tip}
                  <div class="handover-item" style="display:flex;align-items:flex-start;gap:6px;">
                    {#if tip.negative}<span style="color:var(--danger);flex-shrink:0;">🚫</span>
                    {:else if tip.layer === 'how'}<span style="color:var(--info,#4a9eff);flex-shrink:0;">🔧</span>
                    {:else if tip.layer === 'why'}<span style="color:var(--warning);flex-shrink:0;">🎯</span>
                    {:else}<span style="color:var(--text-muted);flex-shrink:0;">📄</span>{/if}
                    <div style="flex:1;min-width:0;">
                      <span>{tip.name}</span>
                      {#if tip.action}<div class="text-xs text-muted" style="margin-top:2px;">→ {tip.action}</div>{/if}
                    </div>
                  </div>
                {/each}
              </div>
            {/if}

            <!-- Decisions -->
            {#if cp.decisions_made?.length}
              <div class="handover-section">
                <h3 style="cursor:pointer;" onclick={() => toggleSection('decisions')}>
                  {expandedSections.decisions ? '▼' : '▶'} ★ {t('resume.decisions')}
                </h3>
                {#if expandedSections.decisions}
                  {#each cp.decisions_made as d}
                    <div class="handover-item">{d.decision}{#if d.rationale}<div class="text-xs text-muted">→ {d.rationale}</div>{/if}</div>
                  {/each}
                {/if}
              </div>
            {/if}

            <!-- Blockers -->
            {#if cp.blocks?.length}
              <div class="handover-section" style="border-left-color:var(--danger);">
                <h3 style="cursor:pointer;" onclick={() => toggleSection('blockers')}>
                  {expandedSections.blockers ? '▼' : '▶'} 🚫 {t('resume.blockers')}
                </h3>
                {#if expandedSections.blockers}
                  {#each cp.blocks as b}
                    <div class="handover-item">{b.issue}{#if b.workaround}<div class="text-xs" style="color:var(--success);">{t('resume.workaround')}: {b.workaround}</div>{/if}</div>
                  {/each}
                {/if}
              </div>
            {/if}

            <!-- Files -->
            {#if cp.files_delta?.length}
              <div class="handover-section">
                <h3 style="cursor:pointer;" onclick={() => toggleSection('files')}>
                  {expandedSections.files ? '▼' : '▶'} 📄 {t('resume.files')} ({cp.files_delta.length})
                </h3>
                {#if expandedSections.files}
                  {#each cp.files_delta.slice(0, 10) as fd}
                    <div class="handover-item" style="font-family:var(--font-mono);font-size:12px;">
                      [{fd.change_type === 'created' ? '+' : fd.change_type === 'deleted' ? '-' : '~'}] {fd.path}
                    </div>
                  {/each}
                {/if}
              </div>
            {/if}
          {/if}

          <!-- Task management actions -->
          <div class="task-actions">
            {#if hasSlackConnection()}
              <button class="btn btn-secondary btn-sm" onclick={() => showExportMenu = showExportMenu === task.id ? null : task.id}>📤 {t('tasks.export')}</button>
            {/if}
            <button class="btn btn-secondary btn-sm btn-done" onclick={() => markDone(task.id)}>✅ {t('tasks.done')}</button>
            <button class="btn btn-secondary btn-sm" onclick={() => openEditModal(task)}>✏️</button>
            <button class="btn-icon btn-delete" onclick={() => deleteTask(task.id)}>✕</button>
          </div>

          {#if showExportMenu === task.id}
            <div class="export-dropdown">
              {#each slackChannels as ch}<button class="btn btn-secondary btn-sm" onclick={() => exportToSlack(task.id, ch.name)}>💬 {ch.name}</button>{/each}
            </div>
          {/if}

          <!-- Hook setup -->
          <details style="margin-top:6px;margin-left:24px;">
            <summary class="text-sm text-muted" style="cursor:pointer;">{t('resume.hookSetup')}</summary>
            <div style="margin-top:4px;">
              <code style="display:block;padding:6px;background:var(--bg-surface2);border-radius:4px;font-size:11px;user-select:all;">npx @purpleraven/hits connect claude</code>
              <code style="display:block;padding:6px;background:var(--bg-surface2);border-radius:4px;font-size:11px;margin-top:2px;user-select:all;">npx @purpleraven/hits connect opencode</code>
            </div>
          </details>
        </div>
      {/each}
    {/if}

    <!-- ═══ PENDING ═══ -->
    {#if pendingTasks.length > 0}
      <div class="section-label">📋 {t('tasks.pending')} ({pendingTasks.length})</div>
      {#each pendingTasks as task (task.id)}
        <div class="task-card" class:task-remote={isRemote(task)}>
          <div class="task-header">
            <span class="priority">{priorityIcon(task.priority)}</span>
            <span class="task-title">{task.title}</span>
            {#if task.project_name}<span class="badge">📂 {task.project_name}</span>{/if}
            <span class="source-badge">{sourceLabel(task)}</span>
          </div>
          {#if task.context}<div class="task-context">{task.context}</div>{/if}
          {#if isRemote(task)}
            <div class="env-warning">⚠️ {task.source_env.hostname} {task.source_env.os || ''}</div>
          {/if}
          <div class="task-actions">
            <button class="btn btn-primary btn-sm" onclick={() => startTask(task.id)}>▶ {t('tasks.startWork')}</button>
            <button class="btn btn-secondary btn-sm" onclick={() => openEditModal(task)}>✏️</button>
            <button class="btn-icon btn-delete" onclick={() => deleteTask(task.id)}>✕</button>
          </div>
        </div>
      {/each}
    {/if}

    <!-- ═══ DONE ═══ -->
    {#if doneTasks.length > 0}
      <details class="done-section">
        <summary class="section-label">✅ {t('tasks.done')} ({doneTasks.length})</summary>
        {#each doneTasks as task (task.id)}
          <div class="task-card done">
            <div class="task-header">
              <span>✅</span>
              <span class="task-title completed">{task.title}</span>
              <span class="text-xs text-muted">{(task.completed_at || '').slice(0, 10)}</span>
            </div>
            <div class="task-actions">
              <button class="btn btn-secondary btn-sm" onclick={() => reopen(task.id)}>🔙 {t('tasks.reopen')}</button>
              <button class="btn-icon btn-delete" onclick={() => deleteTask(task.id)}>✕</button>
            </div>
          </div>
        {/each}
      </details>
    {/if}

    <!-- ═══ PENDING SIGNALS ═══ -->
    {#if checkpointData?.signals?.length}
      <div class="handover-section" style="border-left-color:var(--warning);">
        <h3>📬 {t('resume.pendingSignals')}</h3>
        {#each checkpointData.signals as sig}
          <div class="handover-item">
            <span class="badge" class:badge-critical={sig.priority === 'urgent'} class:badge-high={sig.priority === 'high'}>
              {sig.priority === 'urgent' ? '🔴' : sig.priority === 'high' ? '🟡' : '🟢'}
            </span>
            <strong style="margin-left:8px;">{sig.sender}</strong>: {sig.summary}
            {#if sig.pending_items?.length}
              <ul style="margin:4px 0 0 20px;font-size:12px;">{#each sig.pending_items as item}<li>{item}</li>{/each}</ul>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    <!-- ═══ SESSION HISTORY & RECENT WORK ═══ -->
    {#if handoverData}
      {#if handoverData.session_history?.length}
        <div class="handover-section" style="margin-top:12px;">
          <h3 style="cursor:pointer;" onclick={() => toggleSection('sessionHistory')}>
            {expandedSections.sessionHistory ? '▼' : '▶'} 👥 {t('resume.sessionHistory')}
          </h3>
          {#if expandedSections.sessionHistory}
            {#each handoverData.session_history as session}
              <div class="handover-item">
                <strong>{session.performed_by}</strong>: {session.log_count}
                <span class="text-xs text-muted" style="margin-left:8px;">{(session.last_activity || '').slice(0, 16)}</span>
              </div>
            {/each}
          {/if}
        </div>
      {/if}
      {#if handoverData.recent_logs?.length}
        <div class="handover-section">
          <h3 style="cursor:pointer;" onclick={() => toggleSection('recentWork')}>
            {expandedSections.recentWork ? '▼' : '▶'} 📝 {t('resume.recentWork')}
          </h3>
          {#if expandedSections.recentWork}
            {#each handoverData.recent_logs.slice(0, 10) as log}
              <div class="handover-item">
                <span class="text-xs text-muted">{(log.performed_at || '').slice(5, 16)}</span>
                <span style="margin-left:8px;" class="badge">{log.performed_by}</span>
                <span style="margin-left:8px;">{(log.request_text || '').slice(0, 80)}</span>
                {#if log.tags?.length}
                  <div class="tags" style="display:inline-flex;margin-left:4px;">
                    {#each log.tags as tag}<span class="tag">{tag}</span>{/each}
                  </div>
                {/if}
              </div>
            {/each}
          {/if}
        </div>
      {/if}
    {/if}

    <!-- ═══ EMPTY ═══ -->
    {#if tasks.length === 0 && !checkpointData?.checkpoint}
      <div class="empty-state">
        <div class="icon">▶</div>
        <div class="message">{t('tasks.noTasks')}</div>
        <button class="btn btn-primary btn-sm" onclick={() => showAddModal = true}>{t('tasks.createTask')}</button>
      </div>
    {/if}

  {/if}
</div>

<!-- Add Task Modal -->
{#if showAddModal}
  <div class="modal-overlay" onclick={() => showAddModal = false}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h2>+ {t('tasks.createTask')}</h2>
      <div class="form-group"><label>{t('tasks.taskTitle')}</label><input class="input" bind:value={formTitle} placeholder={t('tasks.taskTitlePlaceholder')} /></div>
      <div class="form-group"><label>{t('tasks.project')}</label><input class="input" bind:value={formProject} placeholder={selectedProject || '/path/to/project'} /></div>
      <div class="form-group">
        <label>{t('tasks.priority')}</label>
        <select class="input" bind:value={formPriority}>
          <option value="critical">🔴 Critical</option><option value="high">🟠 High</option>
          <option value="medium">🔵 Medium</option><option value="low">⚪ Low</option>
        </select>
      </div>
      <div class="form-group"><label>{t('tasks.details')}</label><textarea class="input" rows="3" bind:value={formContext} placeholder={t('tasks.detailsPlaceholder')}></textarea></div>
      {#if formError}<div class="error-msg">{formError}</div>{/if}
      <div class="modal-footer"><button class="btn btn-secondary" onclick={() => showAddModal = false}>{t('cancel')}</button><button class="btn btn-primary" onclick={addTask}>{t('tasks.addTask')}</button></div>
    </div>
  </div>
{/if}

<!-- Edit Task Modal -->
{#if showEditModal}
  <div class="modal-overlay" onclick={() => showEditModal = null}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h2>✏️ {t('tasks.editTask')}</h2>
      <div class="form-group"><label>{t('tasks.taskTitle')}</label><input class="input" bind:value={editTitle} /></div>
      <div class="form-group"><label>{t('tasks.project')}</label><input class="input" bind:value={editProject} /></div>
      <div class="form-group">
        <label>{t('tasks.priority')}</label>
        <select class="input" bind:value={editPriority}>
          <option value="critical">🔴 Critical</option><option value="high">🟠 High</option>
          <option value="medium">🔵 Medium</option><option value="low">⚪ Low</option>
        </select>
      </div>
      <div class="form-group"><label>{t('tasks.details')}</label><textarea class="input" rows="3" bind:value={editContext}></textarea></div>
      <div class="modal-footer"><button class="btn btn-secondary" onclick={() => showEditModal = null}>{t('cancel')}</button><button class="btn btn-primary" onclick={saveEdit}>{t('save')}</button></div>
    </div>
  </div>
{/if}

<!-- History Modal -->
{#if showHistory}
  <div class="modal-overlay" onclick={() => showHistory = false}>
    <div class="modal" onclick={(e) => e.stopPropagation()} style="max-width:600px;">
      <h2>📋 {t('resume.checkpointHistory')}</h2>
      {#if checkpoints.length === 0}
        <div class="text-muted text-sm">{t('resume.noCheckpoints')}</div>
      {:else}
        {#each checkpoints as cp, i}
          <div class="handover-item" style="margin-bottom:8px;">
            <div class="flex items-center gap-sm">
              <strong>{i + 1}. [{(cp.created_at || '').slice(5, 16)}] {cp.performer}</strong>
              <span class="badge">{progressBar(cp.completion_pct)}</span>
            </div>
            <div class="text-sm">{cp.purpose}</div>
          </div>
        {/each}
      {/if}
      <div style="margin-top:16px;text-align:right;"><button class="btn btn-secondary" onclick={() => showHistory = false}>{t('close')}</button></div>
    </div>
  </div>
{/if}

<style>
  .resume-panel { display:flex; flex-direction:column; gap:0; }

  .feedback-bar { padding:8px 12px; border-radius:6px; font-size:13px; margin-bottom:8px; text-align:center; }
  .feedback-success { background:var(--success-bg,#d4edda); color:var(--success,#155724); }
  .feedback-error { background:var(--danger-bg,#f8d7da); color:var(--danger,#721c24); }

  .header-row { display:flex; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:4px; }
  .header-row h2 { font-size:16px; flex:1; margin:0; }
  .header-actions { display:flex; align-items:center; gap:4px; flex-wrap:wrap; }

  /* Slack settings */
  .slack-settings { padding:12px; margin-bottom:12px; }
  .settings-title { font-weight:600; margin-bottom:10px; padding-bottom:6px; border-bottom:1px solid var(--border-color); }
  .channel-row { display:flex; align-items:center; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--border-color); gap:8px; }
  .channel-info { display:flex; flex-direction:column; gap:2px; flex:1; min-width:0; }
  .channel-name { font-weight:500; font-size:13px; }
  .channel-url { font-size:11px; color:var(--text-muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .channel-meta { font-size:10px; color:var(--text-muted); }
  .channel-actions { display:flex; align-items:center; gap:6px; flex-shrink:0; }
  .add-channel-form { display:flex; gap:6px; margin-top:8px; }
  .channel-name-input { flex:0 0 160px; min-width:120px; }
  .channel-url-input { flex:1; min-width:200px; }
  .slack-advanced { margin-top:8px; font-size:12px; }
  .slack-advanced summary { cursor:pointer; color:var(--text-muted); }
  .advanced-fields { display:flex; flex-direction:column; gap:6px; margin-top:6px; }

  /* Section labels */
  .section-label { font-size:13px; font-weight:600; color:var(--text-muted); margin:12px 0 6px; padding-left:4px; }

  /* Task cards */
  .task-card {
    padding:12px 16px; margin-bottom:6px;
    background:var(--bg-surface); border-radius:8px;
    border:1px solid var(--border-color); transition:background 0.15s;
  }
  .task-card:hover { background:var(--bg-surface2); }
  .task-card.in-progress { border-left:3px solid var(--success); }
  .task-card.task-remote { border-left:3px solid var(--info,#4a9eff); }
  .task-card.done { opacity:0.6; }

  .task-header { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
  .priority { font-size:14px; flex-shrink:0; }
  .task-title { font-weight:600; flex:1; min-width:80px; }
  .task-title.completed { text-decoration:line-through; color:var(--text-muted); }

  .badge { font-size:11px; padding:2px 8px; border-radius:10px; background:var(--bg-surface2); white-space:nowrap; }
  .source-badge { font-size:11px; color:var(--text-muted); white-space:nowrap; }
  .progress-badge { font-family:var(--font-mono,monospace); font-size:10px; }
  .badge-critical { background:var(--danger); color:white; }
  .badge-high { background:var(--warning); color:white; }

  .task-context { margin-top:6px; margin-left:24px; font-size:13px; color:var(--text-muted); }

  .env-warning {
    margin-top:4px; margin-left:24px; padding:4px 8px;
    background:var(--bg-surface2); border-radius:4px;
    display:inline-flex; align-items:center; gap:6px; font-size:11px;
  }

  /* Resume actions — prominent */
  .resume-actions {
    display:flex; gap:6px; margin-top:10px; margin-left:24px; flex-wrap:wrap;
    padding:8px 12px; background:var(--bg-surface2); border-radius:8px;
    border:1px solid var(--border-color);
  }

  /* Handover sections */
  .handover-section {
    margin-left:24px; margin-top:8px; padding:8px 12px;
    border-left:3px solid var(--text-muted);
    background:var(--bg-surface);
  }
  .handover-section h3 { font-size:13px; margin:0 0 6px; }
  .handover-item { font-size:13px; margin-bottom:4px; line-height:1.4; }

  .task-actions { display:flex; align-items:center; gap:4px; margin-top:8px; margin-left:24px; flex-wrap:wrap; }
  .btn-done { color:var(--success); }
  .btn-delete { width:20px; height:20px; font-size:10px; color:var(--danger); }

  .export-dropdown {
    margin-top:6px; margin-left:24px; padding:8px;
    background:var(--bg-surface2); border-radius:6px;
    display:flex; align-items:center; gap:6px; flex-wrap:wrap;
  }

  .done-section { margin-top:8px; }
  .done-section summary { cursor:pointer; }

  .modal-footer { display:flex; gap:8px; margin-top:16px; justify-content:flex-end; }
</style>

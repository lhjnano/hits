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
  let checkpointData = $state<any>(null);  // project-level checkpoint (legacy)
  let handoverData = $state<any>(null);

  // Modals
  let showAddModal = $state(false);
  let showEditModal = $state<string | null>(null);
  let showSlackSettings = $state(false);
  let showExportMenu = $state<string | null>(null);
  let showHistory = $state(false);
  let checkpoints = $state<any[]>([]);

  // Add form
  let formTitle = $state('');
  let formProject = $state('');
  let formPriority = $state('medium');
  let formContext = $state('');
  let formError = $state('');

  // Edit form
  let editTitle = $state('');
  let editProject = $state('');
  let editPriority = $state('medium');
  let editContext = $state('');
  let editStatus = $state('pending');

  // Slack form
  let slackName = $state('');
  let slackUrl = $state('');
  let slackBotToken = $state('');
  let slackChannelId = $state('');

  // Section expansion
  let expandedTasks = $state<Record<string, boolean>>({});

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
    editStatus = task.status;
  }

  async function saveEdit() {
    if (!showEditModal) return;
    await api.tasks.update(showEditModal, {
      title: editTitle, project_path: editProject,
      priority: editPriority, context: editContext, status: editStatus,
    });
    showEditModal = null;
    await loadAll();
  }

  async function startTask(id: string) {
    const res = await api.tasks.start(id);
    if (res.success) {
      const action = res.data?.action;
      setFeedback(action === 'started' ? '🚀 작업을 시작합니다' : '▶ 작업을 이어합니다', 'success');
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
    if (res.success) {
      const count = res.data?.imported || 0;
      setFeedback(`✅ ${channel}에서 ${count}개 가져옴`, 'success');
    } else {
      setFeedback(`⚠️ ${res.data?.hint || res.error}`, 'error');
    }
    await loadAll();
  }

  // --- Resume prompt ---
  async function copyText(text: string) {
    try { await navigator.clipboard.writeText(text); }
    catch { const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); }
  }

  function buildTaskResumePrompt(task: any, cp?: any): string {
    const lines: string[] = [];
    lines.push(`# 작업: ${task.title}`);
    lines.push('');
    if (task.context) { lines.push(`## 내용`); lines.push(task.context); lines.push(''); }
    if (task.project_path) { lines.push(`## 프로젝트`); lines.push(task.project_path); lines.push(''); }
    if (cp) {
      lines.push(`## 진행 상태`);
      lines.push(cp.current_state || '시작 전');
      lines.push('');
      if (cp.next_steps?.length) {
        lines.push('## 다음 단계');
        for (const s of cp.next_steps) {
          lines.push(`- [${s.priority || 'medium'}] ${s.action}`);
          if (s.command) lines.push(`  → ${s.command}`);
        }
        lines.push('');
      }
      if (cp.required_context?.length) {
        lines.push('## 필수 정보');
        for (const c of cp.required_context) lines.push(`- ${c}`);
        lines.push('');
      }
    }
    if (task.source === 'slack') {
      lines.push(`## 출처`);
      lines.push(`Slack #${task.slack_channel}`);
      if (task.source_env?.hostname) lines.push(`원본 환경: ${task.source_env.hostname}`);
      lines.push('');
    }
    return lines.join('\n');
  }

  async function copyResume(task: any) {
    const cp = task._checkpoint;
    const prompt = buildTaskResumePrompt(task, cp);
    await copyText(prompt);
    copyFeedback = '✅ Copied!';
    setTimeout(() => copyFeedback = '', 3000);
  }

  // --- Helpers ---
  function priorityIcon(p: string): string {
    return { critical: '🔴', high: '🟠', medium: '🔵', low: '⚪' }[p] || '🔵';
  }

  function sourceLabel(task: any): string {
    if (task.source === 'slack') return `💬 ${task.slack_channel}`;
    return '💻 Local';
  }

  function isRemote(task: any): boolean {
    return task.source !== 'local' && task.source_env?.hostname;
  }

  function progressBar(pct: number): string {
    const filled = '█'.repeat(Math.floor(pct / 10));
    const empty = '░'.repeat(10 - Math.floor(pct / 10));
    return `${filled}${empty} ${pct}%`;
  }

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
            {#if ch.bot_token}
              <span class="channel-meta">📥 읽기 가능 (channel: {ch.channel_id || '?'})</span>
            {:else}
              <span class="channel-meta">📤 내보내기 전용</span>
            {/if}
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
          <div class="text-xs text-muted" style="margin-top:4px;">
            읽기 권한: api.slack.com/apps → OAuth & Permissions → channels:history 스코프 추가
          </div>
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
        <div class="task-card in-progress" class:task-remote={isRemote(task)}>
          <div class="task-header">
            <span class="priority">{priorityIcon(task.priority)}</span>
            <strong class="task-title">{task.title}</strong>
            {#if task.project_name}<span class="badge">📂 {task.project_name}</span>{/if}
            <span class="source-badge">{sourceLabel(task)}</span>
          </div>
          {#if task.context}<div class="task-context">{task.context}</div>{/if}
          {#if isRemote(task)}
            <div class="env-warning">⚠️ {task.source_env.hostname} {task.source_env.os || ''}</div>
          {/if}
          <div class="task-actions">
            <button class="btn btn-primary btn-sm" onclick={() => copyResume(task)}>📋 {t('resume.copy')}</button>
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

    <!-- ═══ EMPTY ═══ -->
    {#if tasks.length === 0}
      <div class="empty-state">
        <div class="icon">▶</div>
        <div class="message">{t('tasks.noTasks')}</div>
        <button class="btn btn-primary btn-sm" onclick={() => showAddModal = true}>{t('tasks.createTask')}</button>
      </div>
    {/if}

    <!-- ═══ LEGACY: Project checkpoint (if no tasks) ═══ -->
    {#if tasks.length === 0 && checkpointData?.checkpoint}
      {@const cp = checkpointData.checkpoint}
      <div class="card" style="margin-top:16px;">
        <div class="flex items-center gap-sm">
          <span style="font-size:24px;">💾</span>
          <div style="flex:1;">
            <div style="font-weight:600;">{cp.purpose || t('resume.noPurpose')}</div>
            <div class="text-sm text-muted">{cp.current_state || ''}</div>
          </div>
          <div class="badge">{progressBar(cp.completion_pct)}</div>
        </div>
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
  .resume-panel { display: flex; flex-direction: column; gap: 0; }

  /* Feedback */
  .feedback-bar { padding:8px 12px; border-radius:6px; font-size:13px; margin-bottom:8px; text-align:center; }
  .feedback-success { background:var(--success-bg,#d4edda); color:var(--success,#155724); }
  .feedback-error { background:var(--danger-bg,#f8d7da); color:var(--danger,#721c24); }

  /* Header */
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

  .task-context { margin-top:6px; margin-left:24px; font-size:13px; color:var(--text-muted); }

  .env-warning {
    margin-top:4px; margin-left:24px; padding:4px 8px;
    background:var(--bg-surface2); border-radius:4px;
    display:inline-flex; align-items:center; gap:6px; font-size:11px;
  }

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

  /* Modal */
  .modal-footer { display:flex; gap:8px; margin-top:16px; justify-content:flex-end; }
</style>

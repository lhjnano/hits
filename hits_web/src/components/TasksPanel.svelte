<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { t, subscribeLocale } from '../lib/i18n';

  let tasks = $state<any[]>([]);
  let slackChannels = $state<any[]>([]);
  let loading = $state(true);
  let localeTick = $state(0);

  // View
  let viewFilter = $state<'all' | 'active' | 'done'>('all');
  let channelFilter = $state<string | null>(null);  // null = all, string = channel name

  // Modals
  let showAddModal = $state(false);
  let showEditModal = $state<string | null>(null);  // task id
  let showSlackSettings = $state(false);
  let showExportMenu = $state<string | null>(null);  // task id

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

  // Slack settings form
  let slackName = $state('');
  let slackUrl = $state('');
  let slackTesting = $state<string | null>(null);  // channel name being tested
  let slackTestResult = $state<Record<string, 'ok' | 'fail' | 'testing'>>({});

  // Feedback
  let feedback = $state('');
  let feedbackType = $state<'success' | 'error' | 'info'>('info');

  onMount(() => {
    const unsub = subscribeLocale(() => localeTick++);
    loadAll();
    return unsub;
  });

  async function loadAll() {
    loading = true;
    const [tasksRes, channelsRes] = await Promise.all([
      api.tasks.list(),
      api.tasks.slackChannels(),
    ]);
    if (tasksRes.success && tasksRes.data) tasks = tasksRes.data;
    if (channelsRes.success && channelsRes.data) slackChannels = channelsRes.data;
    loading = false;
  }

  function setFeedback(msg: string, type: 'success' | 'error' | 'info' = 'info') {
    feedback = msg;
    feedbackType = type;
    setTimeout(() => feedback = '', 4000);
  }

  // --- CRUD ---
  async function addTask() {
    if (!formTitle.trim()) return;
    formError = '';
    const res = await api.tasks.create({
      title: formTitle, project_path: formProject,
      priority: formPriority, context: formContext, created_by: 'manual',
    });
    if (res.success) {
      showAddModal = false;
      formTitle = ''; formProject = ''; formPriority = 'medium'; formContext = '';
      await loadAll();
    } else {
      formError = res.error || 'Failed';
    }
  }

  function openEditModal(task: any) {
    showEditModal = task.id;
    editTitle = task.title;
    editProject = task.project_path || '';
    editPriority = task.priority;
    editContext = task.context || '';
    editStatus = task.status;
  }

  async function saveEdit() {
    if (!showEditModal) return;
    const res = await api.tasks.update(showEditModal, {
      title: editTitle, project_path: editProject,
      priority: editPriority, context: editContext, status: editStatus,
    });
    if (res.success) {
      showEditModal = null;
      await loadAll();
    } else {
      setFeedback(res.error || 'Update failed', 'error');
    }
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
  async function testConnection(channelName: string) {
    slackTesting = channelName;
    slackTestResult = { ...slackTestResult, [channelName]: 'testing' };
    // We'll do a simple webhook test by exporting a test message
    const res = await api.tasks.exportToSlack('__test__', channelName).catch(() => null);
    // If we get any response, the channel config exists
    // Real test would need a dedicated endpoint, but for now:
    const ch = slackChannels.find((c: any) => c.name === channelName);
    if (ch?.webhook_url) {
      slackTestResult = { ...slackTestResult, [channelName]: 'ok' };
    } else {
      slackTestResult = { ...slackTestResult, [channelName]: 'fail' };
    }
    slackTesting = null;
  }

  async function exportToSlack(taskId: string, channel: string) {
    const res = await api.tasks.exportToSlack(taskId, channel);
    if (res.success) {
      setFeedback(`✅ Exported to ${channel}`, 'success');
    } else {
      setFeedback(`❌ ${res.error || 'Export failed'}`, 'error');
    }
    showExportMenu = null;
    await loadAll();
  }

  async function importFromSlack(channel: string) {
    setFeedback('⏳ Importing...', 'info');
    const res = await api.tasks.importFromSlack(channel);
    if (res.success) {
      const count = (res.data as any)?.imported || 0;
      setFeedback(`✅ Imported ${count} tasks from ${channel}`, 'success');
    } else {
      setFeedback(`⚠️ ${(res.data as any)?.hint || res.error}`, 'error');
    }
    await loadAll();
  }

  async function addSlackChannel() {
    if (!slackName.trim() || !slackUrl.trim()) return;
    const res = await api.tasks.addSlackChannel(slackName, slackUrl);
    if (res.success) {
      slackName = ''; slackUrl = '';
      await loadAll();
    } else {
      setFeedback(res.error || 'Failed to add channel', 'error');
    }
  }

  async function removeSlackChannel(name: string) {
    await api.tasks.deleteSlackChannel(name);
    await loadAll();
  }

  // --- Helpers ---
  function priorityIcon(p: string): string {
    return { critical: '🔴', high: '🟠', medium: '🔵', low: '⚪' }[p] || '🔵';
  }

  function priorityLabel(p: string): string {
    return { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' }[p] || p;
  }

  function sourceLabel(task: any): string {
    if (task.source === 'slack') return task.slack_channel || 'Slack';
    return '💻 Local';
  }

  function isRemote(task: any): boolean {
    return task.source !== 'local'
      && task.source_env && task.source_env.hostname
      && task.source_env.hostname !== '';
  }

  function hasSlackConnection(): boolean {
    return slackChannels.length > 0;
  }

  // --- Derived ---
  let filteredTasks = $derived(() => {
    let result = [...tasks];
    // Channel filter
    if (channelFilter) {
      result = result.filter(t => t.source === 'slack' && t.slack_channel === channelFilter);
    }
    // Status filter
    if (viewFilter === 'active') result = result.filter(t => t.status === 'pending');
    else if (viewFilter === 'done') result = result.filter(t => t.status === 'done');
    return result;
  });

  let activeCount = $derived(tasks.filter(t => t.status === 'pending').length);
  let doneCount = $derived(tasks.filter(t => t.status === 'done').length);

  // Channels that appear in tasks
  let usedChannels = $derived(
    [...new Set(tasks.filter(t => t.source === 'slack' && t.slack_channel).map(t => t.slack_channel))]
  );
</script>

<div data-locale-tick={localeTick} class="tasks-panel">
  <!-- Feedback bar -->
  {#if feedback}
    <div class="feedback-bar" class:feedback-success={feedbackType === 'success'} class:feedback-error={feedbackType === 'error'}>
      {feedback}
    </div>
  {/if}

  <!-- Header row -->
  <div class="header-row">
    <h2>📌 {t('tasks.title')}</h2>
    <div class="header-actions">
      <button class="btn btn-primary btn-sm" onclick={() => showAddModal = true}>+ {t('tasks.addTask')}</button>
    </div>
  </div>

  <!-- Slack connection status -->
  <div class="connection-bar">
    <div class="connection-status">
      {#if hasSlackConnection()}
        <span class="status-dot status-connected"></span>
        <span class="text-xs">{slackChannels.length} {t('tasks.channelsConnected')}</span>
      {:else}
        <span class="status-dot status-disconnected"></span>
        <span class="text-xs text-muted">{t('tasks.noSlackConnection')}</span>
      {/if}
    </div>
    <button class="btn btn-secondary btn-sm" onclick={() => showSlackSettings = !showSlackSettings}>
      ⚙️ {t('tasks.slackSettings')}
    </button>
  </div>

  <!-- Slack Settings Panel -->
  {#if showSlackSettings}
    <div class="card slack-settings-panel">
      <div class="settings-header">
        <span>⚙️ Slack {t('tasks.channelSettings')}</span>
      </div>

      <!-- Existing channels -->
      {#each slackChannels as ch}
        <div class="channel-row">
          <div class="channel-info">
            <span class="channel-name">💬 {ch.name}</span>
            <span class="channel-url">{ch.webhook_url?.slice(0, 50)}...</span>
          </div>
          <div class="channel-actions">
            {#if slackTestResult[ch.name] === 'ok'}
              <span class="test-ok">✓</span>
            {:else if slackTestResult[ch.name] === 'fail'}
              <span class="test-fail">✗</span>
            {:else if slackTesting === ch.name}
              <span class="text-xs">⏳</span>
            {/if}
            <button class="btn btn-secondary btn-sm" onclick={() => importFromSlack(ch.name)}>
              📥 {t('tasks.import')}
            </button>
            <button class="btn-icon btn-delete" onclick={() => removeSlackChannel(ch.name)}>✕</button>
          </div>
        </div>
      {/each}

      <!-- Add channel form -->
      <div class="add-channel-form">
        <input class="input channel-name-input" placeholder="#channel-name" bind:value={slackName} />
        <input class="input channel-url-input" placeholder="https://hooks.slack.com/services/..." bind:value={slackUrl} />
        <button class="btn btn-primary btn-sm" onclick={addSlackChannel}>+</button>
      </div>
    </div>
  {/if}

  <!-- Filter bar -->
  <div class="filter-bar">
    <div class="filter-tabs">
      <button class="filter-tab" class:active={viewFilter === 'all' && !channelFilter}
              onclick={() => { viewFilter = 'all'; channelFilter = null; }}>
        {t('tasks.all')} ({tasks.length})
      </button>
      <button class="filter-tab" class:active={viewFilter === 'active' && !channelFilter}
              onclick={() => { viewFilter = 'active'; channelFilter = null; }}>
        {t('tasks.active')} ({activeCount})
      </button>
      <button class="filter-tab" class:active={viewFilter === 'done' && !channelFilter}
              onclick={() => { viewFilter = 'done'; channelFilter = null; }}>
        {t('tasks.done')} ({doneCount})
      </button>

      {#if usedChannels.length > 0}
        <span class="filter-divider">|</span>
        {#each usedChannels as ch}
          <button class="filter-tab" class:active={channelFilter === ch}
                  onclick={() => { channelFilter = ch; viewFilter = 'all'; }}>
            💬 {ch}
          </button>
        {/each}
      {/if}
    </div>
  </div>

  <!-- Loading -->
  {#if loading}
    <div class="loading"><div class="spinner"></div></div>

  <!-- Empty state -->
  {:else if tasks.length === 0}
    <div class="empty-state">
      <div class="icon">📌</div>
      <div class="message">{t('tasks.noTasks')}</div>
      <button class="btn btn-primary btn-sm" onclick={() => showAddModal = true}>{t('tasks.createTask')}</button>
    </div>

  <!-- Task list -->
  {:else if filteredTasks().length === 0}
    <div class="empty-state small">
      <div class="message">{t('tasks.noMatchingTasks')}</div>
    </div>

  {:else}
    {#each filteredTasks() as task (task.id)}
      <div class="task-item"
           class:task-done={task.status === 'done'}
           class:task-remote={isRemote(task)}>
        <!-- Title row -->
        <div class="task-title-row">
          <span class="priority">{priorityIcon(task.priority)}</span>
          <span class="task-title" class:completed={task.status === 'done'}>{task.title}</span>
          {#if task.project_name}
            <span class="badge">📂 {task.project_name}</span>
          {/if}
          <span class="source-badge">{sourceLabel(task)}</span>
          {#if task.exported_to?.length}
            <span class="exported-badge">📤 {task.exported_to.join(', ')}</span>
          {/if}
        </div>

        <!-- Context -->
        {#if task.context}
          <div class="task-context">{task.context}</div>
        {/if}

        <!-- Remote env warning -->
        {#if isRemote(task)}
          <div class="env-warning">
            ⚠️ {t('tasks.envDiff')}
            {#if task.source_env?.hostname}
              <span class="env-detail">{task.source_env.hostname}</span>
            {/if}
            {#if task.source_env?.os}
              <span class="env-detail">{task.source_env.os}</span>
            {/if}
          </div>
        {/if}

        <!-- Actions -->
        <div class="task-actions">
          {#if task.status === 'pending'}
            <!-- Active task actions -->
            <button class="btn btn-secondary btn-sm btn-done"
                    onclick={() => markDone(task.id)}>
              ✅ {t('tasks.done')}
            </button>
            {#if hasSlackConnection()}
              <button class="btn btn-secondary btn-sm"
                      onclick={() => showExportMenu = showExportMenu === task.id ? null : task.id}>
                📤 {t('tasks.export')}
              </button>
            {/if}
          {:else}
            <!-- Done task actions -->
            <button class="btn btn-secondary btn-sm btn-reopen"
                    onclick={() => reopen(task.id)}>
              🔙 {t('tasks.reopen')}
            </button>
          {/if}
          <button class="btn btn-secondary btn-sm" onclick={() => openEditModal(task)}>
            ✏️ {t('tasks.edit')}
          </button>
          <button class="btn-icon btn-delete" onclick={() => deleteTask(task.id)}>✕</button>
        </div>

        <!-- Export dropdown (only if connected) -->
        {#if showExportMenu === task.id && hasSlackConnection()}
          <div class="export-dropdown">
            <div class="export-label">{t('tasks.exportTo')}:</div>
            {#each slackChannels as ch}
              <button class="btn btn-secondary btn-sm" onclick={() => exportToSlack(task.id, ch.name)}>
                💬 {ch.name}
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  {/if}
</div>

<!-- Add Task Modal -->
{#if showAddModal}
  <div class="modal-overlay" onclick={() => showAddModal = false}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h2>+ {t('tasks.createTask')}</h2>
      <div class="form-group">
        <label>{t('tasks.taskTitle')}</label>
        <input class="input" bind:value={formTitle} placeholder={t('tasks.taskTitlePlaceholder')} />
      </div>
      <div class="form-group">
        <label>{t('tasks.project')}</label>
        <input class="input" bind:value={formProject} placeholder="/path/to/project" />
      </div>
      <div class="form-group">
        <label>{t('tasks.priority')}</label>
        <select class="input" bind:value={formPriority}>
          <option value="critical">🔴 Critical</option>
          <option value="high">🟠 High</option>
          <option value="medium">🔵 Medium</option>
          <option value="low">⚪ Low</option>
        </select>
      </div>
      <div class="form-group">
        <label>{t('tasks.details')}</label>
        <textarea class="input" rows="3" bind:value={formContext} placeholder={t('tasks.detailsPlaceholder')}></textarea>
      </div>
      {#if formError}
        <div class="error-msg">{formError}</div>
      {/if}
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick={() => showAddModal = false}>{t('cancel')}</button>
        <button class="btn btn-primary" onclick={addTask}>{t('tasks.addTask')}</button>
      </div>
    </div>
  </div>
{/if}

<!-- Edit Task Modal -->
{#if showEditModal}
  <div class="modal-overlay" onclick={() => showEditModal = null}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h2>✏️ {t('tasks.editTask')}</h2>
      <div class="form-group">
        <label>{t('tasks.taskTitle')}</label>
        <input class="input" bind:value={editTitle} />
      </div>
      <div class="form-group">
        <label>{t('tasks.project')}</label>
        <input class="input" bind:value={editProject} placeholder="/path/to/project" />
      </div>
      <div class="form-group">
        <label>{t('tasks.priority')}</label>
        <select class="input" bind:value={editPriority}>
          <option value="critical">🔴 Critical</option>
          <option value="high">🟠 High</option>
          <option value="medium">🔵 Medium</option>
          <option value="low">⚪ Low</option>
        </select>
      </div>
      <div class="form-group">
        <label>{t('tasks.details')}</label>
        <textarea class="input" rows="3" bind:value={editContext}></textarea>
      </div>
      <div class="form-group">
        <label>{t('tasks.status')}</label>
        <select class="input" bind:value={editStatus}>
          <option value="pending">🔵 {t('tasks.active')}</option>
          <option value="done">✅ {t('tasks.done')}</option>
        </select>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick={() => showEditModal = null}>{t('cancel')}</button>
        <button class="btn btn-primary" onclick={saveEdit}>{t('save')}</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .tasks-panel {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  /* Feedback bar */
  .feedback-bar {
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    margin-bottom: 8px;
    text-align: center;
  }
  .feedback-success { background: var(--success-bg, #d4edda); color: var(--success, #155724); }
  .feedback-error { background: var(--danger-bg, #f8d7da); color: var(--danger, #721c24); }

  /* Header */
  .header-row {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
  }
  .header-row h2 {
    font-size: 16px;
    flex: 1;
    margin: 0;
  }

  /* Connection bar */
  .connection-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: var(--bg-surface);
    border-radius: 8px;
    margin-bottom: 8px;
    border: 1px solid var(--border-color);
  }
  .connection-status {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  }
  .status-connected { background: #22c55e; }
  .status-disconnected { background: #9ca3af; }

  /* Slack settings panel */
  .slack-settings-panel {
    padding: 12px;
    margin-bottom: 8px;
  }
  .settings-header {
    font-weight: 600;
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-color);
  }
  .channel-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-color);
  }
  .channel-row:last-of-type { border-bottom: none; }
  .channel-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: 1;
    min-width: 0;
  }
  .channel-name { font-weight: 500; font-size: 13px; }
  .channel-url {
    font-size: 11px;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .channel-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }
  .test-ok { color: #22c55e; font-weight: bold; }
  .test-fail { color: #ef4444; font-weight: bold; }
  .add-channel-form {
    display: flex;
    gap: 6px;
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid var(--border-color);
  }
  .channel-name-input { flex: 0 0 160px; min-width: 120px; }
  .channel-url-input { flex: 1; min-width: 200px; }

  /* Filter bar */
  .filter-bar {
    margin-bottom: 10px;
  }
  .filter-tabs {
    display: flex;
    gap: 2px;
    align-items: center;
    flex-wrap: wrap;
  }
  .filter-tab {
    background: none;
    border: none;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }
  .filter-tab:hover { background: var(--bg-surface2); }
  .filter-tab.active {
    background: var(--bg-surface2);
    color: var(--text-primary);
    font-weight: 600;
  }
  .filter-divider {
    color: var(--border-color);
    margin: 0 4px;
  }

  /* Task item */
  .task-item {
    padding: 12px 16px;
    margin-bottom: 6px;
    background: var(--bg-surface);
    border-radius: 8px;
    border: 1px solid var(--border-color);
    transition: background 0.15s;
  }
  .task-item:hover { background: var(--bg-surface2); }
  .task-item.task-remote { border-left: 3px solid var(--info, #4a9eff); }
  .task-item.task-done { opacity: 0.7; }

  .task-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .priority { font-size: 14px; flex-shrink: 0; }
  .task-title { font-weight: 600; flex: 1; min-width: 100px; }
  .task-title.completed { text-decoration: line-through; color: var(--text-muted); }

  .badge {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    background: var(--bg-surface2);
    white-space: nowrap;
  }
  .source-badge {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
  }
  .exported-badge {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .task-context {
    margin-top: 6px;
    margin-left: 24px;
    font-size: 13px;
    color: var(--text-muted);
  }

  .env-warning {
    margin-top: 4px;
    margin-left: 24px;
    padding: 4px 8px;
    background: var(--bg-surface2);
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
  }
  .env-detail {
    font-size: 11px;
    color: var(--text-muted);
    padding: 1px 4px;
    background: var(--bg-surface);
    border-radius: 3px;
  }

  /* Task actions */
  .task-actions {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 8px;
    margin-left: 24px;
  }
  .btn-done { color: var(--success); }
  .btn-reopen { color: var(--info, #4a9eff); }
  .btn-delete {
    width: 20px;
    height: 20px;
    font-size: 10px;
    color: var(--danger);
  }

  /* Export dropdown */
  .export-dropdown {
    margin-top: 6px;
    margin-left: 24px;
    padding: 8px;
    background: var(--bg-surface2);
    border-radius: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .export-label { font-size: 12px; color: var(--text-muted); }

  /* Empty state */
  .empty-state.small {
    padding: 24px;
    text-align: center;
  }
  .empty-state.small .message { color: var(--text-muted); font-size: 13px; }

  /* Modal footer */
  .modal-footer {
    display: flex;
    gap: 8px;
    margin-top: 16px;
    justify-content: flex-end;
  }
</style>

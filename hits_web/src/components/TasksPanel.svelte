<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { t, subscribeLocale } from '../lib/i18n';

  let tasks = $state<any[]>([]);
  let slackChannels = $state<any[]>([]);
  let loading = $state(true);
  let localeTick = $state(0);

  // Modal states
  let showAddModal = $state(false);
  let showSlackSettings = $state(false);
  let showExportMenu = $state<string | null>(null);  // task_id
  let showImportMenu = $state(false);

  // Add form
  let formTitle = $state('');
  let formProject = $state('');
  let formPriority = $state('medium');
  let formContext = $state('');
  let formError = $state('');

  // Slack settings form
  let slackName = $state('');
  let slackUrl = $state('');

  // Feedback
  let feedback = $state('');

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

  async function addTask() {
    if (!formTitle.trim()) return;
    formError = '';
    const res = await api.tasks.create({
      title: formTitle,
      project_path: formProject,
      priority: formPriority,
      context: formContext,
      created_by: 'manual',
    });
    if (res.success) {
      showAddModal = false;
      formTitle = '';
      formProject = '';
      formPriority = 'medium';
      formContext = '';
      await loadAll();
    } else {
      formError = res.error || 'Failed';
    }
  }

  async function markDone(id: string) {
    await api.tasks.update(id, { status: 'done' });
    await loadAll();
  }

  async function deleteTask(id: string) {
    await api.tasks.delete(id);
    await loadAll();
  }

  async function exportToSlack(taskId: string, channel: string) {
    const res = await api.tasks.exportToSlack(taskId, channel);
    if (res.success) {
      feedback = `✅ Exported to ${channel}`;
      setTimeout(() => feedback = '', 3000);
    } else {
      feedback = `❌ ${res.error}`;
      setTimeout(() => feedback = '', 5000);
    }
    showExportMenu = null;
    await loadAll();
  }

  async function importFromSlack(channel: string) {
    feedback = '⏳ Importing...';
    const res = await api.tasks.importFromSlack(channel);
    if (res.success) {
      const count = (res.data as any)?.imported || 0;
      feedback = `✅ Imported ${count} tasks from ${channel}`;
    } else {
      feedback = `⚠️ ${(res.data as any)?.hint || res.error}`;
    }
    setTimeout(() => feedback = '', 5000);
    showImportMenu = false;
    await loadAll();
  }

  async function addSlackChannel() {
    if (!slackName.trim() || !slackUrl.trim()) return;
    const res = await api.tasks.addSlackChannel(slackName, slackUrl);
    if (res.success) {
      slackName = '';
      slackUrl = '';
      await loadAll();
    }
  }

  async function removeSlackChannel(name: string) {
    await api.tasks.deleteSlackChannel(name);
    await loadAll();
  }

  function priorityIcon(p: string): string {
    return { critical: '🔴', high: '🟡', medium: '🔵', low: '⚪' }[p] || '🔵';
  }

  function sourceIcon(task: any): { icon: string; label: string } {
    if (task.source === 'slack') return { icon: '💬', label: task.slack_channel || 'Slack' };
    return { icon: '💻', label: 'Local' };
  }

  function isRemote(task: any): boolean {
    return task.source !== 'local' && task.source_env && Object.keys(task.source_env).length > 0;
  }

  // Derived: split tasks into active and done
  let activeTasks = $derived(tasks.filter(t => t.status === 'pending'));
  let doneTasks = $derived(tasks.filter(t => t.status === 'done'));
</script>

<div data-locale-tick={localeTick}>
  <!-- Header -->
  <div class="flex items-center" style="margin-bottom:16px;">
    <h2 style="font-size:16px; flex:1;">📌 {t('tasks.title')}</h2>
    {#if feedback}
      <span style="color:var(--success); font-size:12px; margin-right:8px;">{feedback}</span>
    {/if}
    <button class="btn btn-secondary btn-sm" onclick={() => showImportMenu = !showImportMenu}>📥 {t('tasks.import')}</button>
    <button class="btn btn-secondary btn-sm" style="margin-left:4px;" onclick={() => showSlackSettings = !showSlackSettings}>⚙️</button>
    <button class="btn btn-primary btn-sm" style="margin-left:4px;" onclick={() => showAddModal = true}>+ {t('tasks.addTask')}</button>
  </div>

  <!-- Import menu -->
  {#if showImportMenu}
    <div class="card" style="margin-bottom:12px; padding:12px;">
      <div style="font-weight:600; margin-bottom:8px;">📥 {t('tasks.importFromSlack')}</div>
      {#if slackChannels.length === 0}
        <div class="text-sm text-muted">{t('tasks.noChannels')}</div>
      {:else}
        {#each slackChannels as ch}
          <button class="btn btn-secondary btn-sm" style="margin:2px;" onclick={() => importFromSlack(ch.name)}>
            💬 {ch.name}
          </button>
        {/each}
      {/if}
    </div>
  {/if}

  <!-- Slack settings -->
  {#if showSlackSettings}
    <div class="card" style="margin-bottom:12px; padding:12px;">
      <div style="font-weight:600; margin-bottom:8px;">⚙️ Slack {t('tasks.channelSettings')}</div>
      {#each slackChannels as ch}
        <div class="flex items-center" style="margin-bottom:4px; gap:8px;">
          <span class="text-sm">💬 {ch.name}</span>
          <span class="text-xs text-muted" style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
            {ch.webhook_url.slice(0, 40)}...
          </span>
          <button class="btn-icon" style="width:20px;height:20px;font-size:10px;color:var(--danger);" onclick={() => removeSlackChannel(ch.name)}>✕</button>
        </div>
      {/each}
      <div class="flex gap-sm" style="margin-top:8px;">
        <input class="input" style="flex:1;" placeholder="#channel-name" bind:value={slackName} />
        <input class="input" style="flex:2;" placeholder="https://hooks.slack.com/services/..." bind:value={slackUrl} />
        <button class="btn btn-primary btn-sm" onclick={addSlackChannel}>+</button>
      </div>
    </div>
  {/if}

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
  {:else}
    <!-- Active tasks -->
    {#each activeTasks as task}
      <div class="task-item" class:task-remote={isRemote(task)}>
        <div class="flex items-center gap-sm">
          <span>{priorityIcon(task.priority)}</span>
          <strong style="flex:1;">{task.title}</strong>
          {#if task.project_name}
            <span class="badge">📂 {task.project_name}</span>
          {/if}
          <span class="text-xs text-muted">{sourceIcon(task).icon} {sourceIcon(task).label}</span>
          {#if task.exported_to?.length}
            <span class="text-xs text-muted">📤 {task.exported_to.join(', ')}</span>
          {/if}
        </div>
        {#if task.context}
          <div class="text-sm text-muted" style="margin-top:4px; margin-left:24px;">{task.context}</div>
        {/if}
        {#if isRemote(task)}
          <div style="margin-top:4px; margin-left:24px; padding:4px 8px; background:var(--bg-surface2); border-radius:4px; display:inline-flex; align-items:center; gap:4px;">
            <span style="font-size:11px;">⚠️ {t('tasks.envDiff')}</span>
            {#if task.source_env?.hostname}
              <span class="text-xs text-muted">{task.source_env.hostname}</span>
            {/if}
            {#if task.environment_note}
              <span class="text-xs text-muted">{task.environment_note}</span>
            {/if}
          </div>
        {/if}
        <div class="flex gap-sm" style="margin-top:6px; margin-left:24px;">
          <button class="btn btn-secondary btn-sm" onclick={() => { showExportMenu = showExportMenu === task.id ? null : task.id; }}>
            📤 {t('tasks.export')}
          </button>
          <button class="btn btn-secondary btn-sm" style="color:var(--success);" onclick={() => markDone(task.id)}>✅ {t('tasks.done')}</button>
          <button class="btn-icon" style="width:20px;height:20px;font-size:10px;color:var(--danger);" onclick={() => deleteTask(task.id)}>✕</button>
        </div>
        <!-- Export dropdown -->
        {#if showExportMenu === task.id}
          <div style="margin-top:4px; margin-left:24px; padding:8px; background:var(--bg-surface2); border-radius:4px;">
            {#each slackChannels as ch}
              <button class="btn btn-secondary btn-sm" style="margin:2px;" onclick={() => exportToSlack(task.id, ch.name)}>
                💬 {ch.name}
              </button>
            {/each}
            {#if slackChannels.length === 0}
              <span class="text-xs text-muted">{t('tasks.noChannelsExport')}</span>
            {/if}
          </div>
        {/if}
      </div>
    {/each}

    <!-- Done tasks (collapsed) -->
    {#if doneTasks.length > 0}
      <details style="margin-top:16px;">
        <summary class="text-sm text-muted" style="cursor:pointer;">✅ {t('tasks.doneTasks')} ({doneTasks.length})</summary>
        {#each doneTasks as task}
          <div class="task-item" style="opacity:0.5;">
            <div class="flex items-center gap-sm">
              <span>✅</span>
              <span style="flex:1; text-decoration:line-through;">{task.title}</span>
              <button class="btn-icon" style="width:20px;height:20px;font-size:10px;color:var(--danger);" onclick={() => deleteTask(task.id)}>✕</button>
            </div>
          </div>
        {/each}
      </details>
    {/if}
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
          <option value="high">🟡 High</option>
          <option value="medium">🔵 Medium</option>
          <option value="low">⚪ Low</option>
        </select>
      </div>
      <div class="form-group">
        <label>{t('tasks.details')}</label>
        <textarea class="input" bind:value={formContext} placeholder={t('tasks.detailsPlaceholder')}></textarea>
      </div>
      {#if formError}
        <div class="error-msg">{formError}</div>
      {/if}
      <div class="flex gap-sm" style="margin-top:16px; justify-content:flex-end;">
        <button class="btn btn-secondary" onclick={() => showAddModal = false}>{t('cancel')}</button>
        <button class="btn btn-primary" onclick={addTask}>{t('tasks.addTask')}</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .task-item {
    padding: 12px 16px;
    margin-bottom: 8px;
    background: var(--bg-surface);
    border-radius: 8px;
    border: 1px solid var(--border-color);
  }
  .task-item:hover {
    background: var(--bg-surface2);
  }
  .task-remote {
    border-left: 3px solid var(--info, #4a9eff);
  }
</style>

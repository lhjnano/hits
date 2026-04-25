<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { uiStore, workLogsStore } from '../lib/stores';
  import { t, getLocale, subscribeLocale } from '../lib/i18n';

  let logs = $state<any[]>([]);
  let loading = $state(true);
  let searchQuery = $state('');
  let showAddModal = $state(false);
  let editingLog: any | null = $state(null);
  let expandedLogId: string | null = $state(null);

  // Form state
  let formSummary = $state('');
  let formContext = $state('');
  let formPerformedBy = $state('manual');
  let formTags = $state('');
  let formError = $state('');
  let formSubmitting = $state(false);

  // Reactive locale tick for re-rendering on language change
  let localeTick = $state(0);

  // Track selected project to reload when it changes
  let currentProject = $state(uiStore.value.selectedProject);

  onMount(() => {
    const unsub = subscribeLocale(() => localeTick++);
    loadLogs();
    return unsub;
  });

  // Watch for project selection changes and reload
  $effect(() => {
    const project = uiStore.value.selectedProject;
    if (project !== currentProject) {
      currentProject = project;
      loadLogs();
    }
  });

  async function loadLogs() {
    loading = true;
    const params: Record<string, any> = { limit: 100 };
    const project = uiStore.value.selectedProject;
    if (project) params.project_path = project;

    const res = await api.workLogs.list(params);
    if (res.success && res.data) {
      logs = res.data;
      workLogsStore.value = res.data;
    }
    loading = false;
  }

  async function handleSearch() {
    if (!searchQuery.trim()) {
      await loadLogs();
      return;
    }
    loading = true;
    const params: Record<string, string | undefined> = { q: searchQuery };
    const project = uiStore.value.selectedProject;
    if (project) params.project_path = project;

    const res = await api.workLogs.search(searchQuery, project);
    if (res.success && res.data) {
      logs = res.data;
    }
    loading = false;
  }

  function groupByDate(items: any[]): { label: string; items: any[] }[] {
    void localeTick;
    const groups: Record<string, any[]> = {};
    const today = new Date().toISOString().slice(0, 10);
    const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

    for (const item of items) {
      const date = (item.performed_at || '').slice(0, 10) || 'unknown';
      if (!groups[date]) groups[date] = [];
      groups[date].push(item);
    }

    return Object.entries(groups)
      .sort(([a], [b]) => b.localeCompare(a))
      .map(([date, items]) => ({
        label: date === today ? t('timeline.today') : date === yesterday ? t('timeline.yesterday') : date,
        items,
      }));
  }

  function formatTime(iso: string): string {
    void localeTick;
    try {
      const locale = getLocale() === 'ko' ? 'ko-KR' : 'en-US';
      return new Date(iso).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  }

  function openAddLog() {
    editingLog = null;
    formSummary = '';
    formContext = '';
    formPerformedBy = 'manual';
    formTags = '';
    formError = '';
    showAddModal = true;
  }

  function openEditLog(log: any) {
    editingLog = log;
    formSummary = log.request_text || '';
    formContext = log.context || '';
    formPerformedBy = log.performed_by || 'manual';
    formTags = (log.tags || []).join(', ');
    formError = '';
    showAddModal = true;
  }

  function toggleExpand(id: string) {
    expandedLogId = expandedLogId === id ? null : id;
  }

  async function saveLog() {
    formError = '';
    formSubmitting = true;

    const data = {
      request_text: formSummary,
      context: formContext,
      performed_by: formPerformedBy,
      source: 'manual',
      tags: formTags.split(',').map(tag => tag.trim()).filter(Boolean),
      project_path: uiStore.value.selectedProject || undefined,
    };

    let res;
    if (editingLog) {
      res = await api.workLogs.update(editingLog.id, data);
    } else {
      res = await api.workLogs.create(data);
    }

    formSubmitting = false;
    if (res.success) {
      showAddModal = false;
      await loadLogs();
    } else {
      formError = res.error || t('timeline.saveFailed');
    }
  }

  async function deleteLog(id: string) {
    if (!confirm(t('timeline.confirmDelete'))) return;
    await api.workLogs.delete(id);
    expandedLogId = null;
    await loadLogs();
  }

  let grouped = $derived((void localeTick, groupByDate(logs)));
  let projectLabel = $derived(
    (void localeTick,
    uiStore.value.selectedProject
      ? uiStore.value.selectedProject.split('/').pop()
      : t('timeline.allProjects'))
  );
</script>

<div>
  <div class="flex items-center gap-sm" style="margin-bottom:16px;">
    <h2 style="font-size:16px; flex:1;">📝 {t('timeline.title')} — {projectLabel}</h2>
    <div class="flex gap-sm" style="flex:1; max-width:300px;">
      <input
        class="input"
        type="text"
        placeholder={t('search') + '...'}
        bind:value={searchQuery}
        onkeydown={(e) => e.key === 'Enter' && handleSearch()}
      />
      <button class="btn btn-secondary btn-sm" onclick={handleSearch}>🔍</button>
    </div>
    <button class="btn btn-primary btn-sm" onclick={openAddLog}>+ {t('timeline.addLog')}</button>
  </div>

  {#if loading}
    <div class="loading"><div class="spinner"></div></div>
  {:else if logs.length === 0}
    <div class="empty-state">
      <div class="icon">📝</div>
      <div class="message">{t('timeline.noLogs')}</div>
      <button class="btn btn-primary btn-sm" onclick={openAddLog}>{t('timeline.createLog')}</button>
    </div>
  {:else}
    {#each grouped as group}
      <div class="timeline-date">{group.label}</div>
      {#each group.items as log}
        <div
          class="timeline-item"
          class:expanded={expandedLogId === log.id}
          onclick={() => toggleExpand(log.id)}
          role="button"
          tabindex="0"
          onkeydown={(e) => { if (e.key === 'Enter') toggleExpand(log.id); }}
        >
          <div class="summary">{log.request_text || log.context || `(${t('empty.noData')})`}</div>
          <div class="meta">
            <span>{formatTime(log.performed_at)}</span>
            <span>·</span>
            <span>{log.performed_by}</span>
            {#if log.project_path}
              <span>·</span>
              <span class="text-xs" style="color:var(--accent-secondary);">
                {log.project_path.split('/').pop()}
              </span>
            {/if}
          </div>
          {#if log.tags?.length}
            <div class="tags">
              {#each log.tags as tag}
                <span class="tag">{tag}</span>
              {/each}
            </div>
          {/if}

          <!-- Expanded detail view -->
          {#if expandedLogId === log.id}
            <div class="timeline-detail" onclick={(e) => e.stopPropagation()}>
              {#if log.context}
                <div class="detail-section">
                  <div class="detail-label">{t('timeline.context')}</div>
                  <div class="detail-content">{log.context}</div>
                </div>
              {/if}
              {#if log.result_data?.files_modified?.length}
                <div class="detail-section">
                  <div class="detail-label">{t('timeline.files')}</div>
                  <div class="detail-files">
                    {#each log.result_data.files_modified as file}
                      <span class="detail-file">{file}</span>
                    {/each}
                  </div>
                </div>
              {/if}
              {#if log.result_data?.commands_run?.length}
                <div class="detail-section">
                  <div class="detail-label">{t('timeline.commands')}</div>
                  <div class="detail-content" style="font-family:var(--font-mono);font-size:12px;">
                    {#each log.result_data.commands_run as cmd}
                      <div>{cmd}</div>
                    {/each}
                  </div>
                </div>
              {/if}
              <div class="detail-actions">
                <button class="btn btn-secondary btn-sm" onclick={() => openEditLog(log)}>✏ {t('edit')}</button>
                <button class="btn btn-secondary btn-sm" style="color:var(--danger);" onclick={() => deleteLog(log.id)}>✕ {t('delete')}</button>
              </div>
            </div>
          {/if}

          {#if expandedLogId !== log.id}
            <div class="timeline-actions">
              <button class="btn-icon" style="width:20px;height:20px;font-size:9px;" onclick={(e) => { e.stopPropagation(); openEditLog(log); }}>✏</button>
              <button class="btn-icon" style="width:20px;height:20px;font-size:9px;color:var(--danger);" onclick={(e) => { e.stopPropagation(); deleteLog(log.id); }}>✕</button>
            </div>
          {/if}
        </div>
      {/each}
    {/each}
  {/if}
</div>

<!-- Add/Edit Modal -->
{#if showAddModal}
  <div class="modal-overlay" onclick={() => showAddModal = false}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h2>{editingLog ? t('timeline.editLog') : t('timeline.newLog')}</h2>
      <div class="form-group">
        <label>{t('timeline.summary')}</label>
        <input class="input" bind:value={formSummary} placeholder={t('timeline.summary')} />
      </div>
      <div class="form-group">
        <label>{t('timeline.context')}</label>
        <textarea class="input" bind:value={formContext} placeholder={t('timeline.context')}></textarea>
      </div>
      <div class="form-group">
        <label>{t('timeline.performer')}</label>
        <select class="input" bind:value={formPerformedBy}>
          <option value="manual">{t('performer.manual')}</option>
          <option value="opencode">{t('performer.opencode')}</option>
          <option value="claude">{t('performer.claude')}</option>
          <option value="cursor">{t('performer.cursor')}</option>
          <option value="copilot">{t('performer.copilot')}</option>
        </select>
      </div>
      <div class="form-group">
        <label>{t('timeline.tags')}</label>
        <input class="input" bind:value={formTags} placeholder={t('timeline.tags')} />
      </div>
      {#if formError}
        <div class="error-msg">{formError}</div>
      {/if}
      <div class="flex gap-sm" style="margin-top:16px; justify-content:flex-end;">
        <button class="btn btn-secondary" onclick={() => showAddModal = false}>{t('cancel')}</button>
        <button class="btn btn-primary" onclick={saveLog} disabled={formSubmitting}>
          {formSubmitting ? t('knowledge.saving') : t('save')}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .timeline-item {
    cursor: pointer;
    position: relative;
  }
  .timeline-item:hover {
    background: var(--bg-surface2);
  }
  .timeline-item.expanded {
    background: var(--bg-surface2);
    border-left: 3px solid var(--accent-primary);
  }

  .timeline-actions {
    position: absolute;
    right: 16px;
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    gap: 2px;
    opacity: 0.3;
  }
  .timeline-item:hover .timeline-actions {
    opacity: 1;
  }

  .timeline-detail {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border-color);
  }
  .detail-section {
    margin-bottom: 10px;
  }
  .detail-label {
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
  }
  .detail-content {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .detail-files {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .detail-file {
    font-family: var(--font-mono);
    font-size: 11px;
    background: var(--bg-surface);
    padding: 2px 6px;
    border-radius: 3px;
    color: var(--text-muted);
  }
  .detail-actions {
    display: flex;
    gap: 6px;
    margin-top: 8px;
  }
</style>

<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { uiStore, workLogsStore } from '../lib/stores';
  import { t } from '../lib/i18n';

  let logs = $state<any[]>([]);
  let loading = $state(true);
  let searchQuery = $state('');
  let showAddModal = $state(false);
  let editingLog: any | null = $state(null);

  // Form state
  let formSummary = $state('');
  let formContext = $state('');
  let formPerformedBy = $state('manual');
  let formTags = $state('');
  let formError = $state('');
  let formSubmitting = $state(false);

  onMount(async () => {
    await loadLogs();
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
    try {
      return new Date(iso).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
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
      formError = res.error || 'Save failed';
    }
  }

  async function deleteLog(id: string) {
    if (!confirm(t('timeline.confirmDelete'))) return;
    await api.workLogs.delete(id);
    await loadLogs();
  }

  let grouped = $derived(groupByDate(logs));
  let projectLabel = $derived(
    uiStore.value.selectedProject
      ? uiStore.value.selectedProject.split('/').pop()
      : t('timeline.allProjects')
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
        <div class="timeline-item">
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
          <div style="position:absolute;right:16px;top:50%;transform:translateY(-50%);display:flex;gap:2px;opacity:0.3;">
            <button class="btn-icon" style="width:20px;height:20px;font-size:9px;" onclick={() => openEditLog(log)}>✏</button>
            <button class="btn-icon" style="width:20px;height:20px;font-size:9px;color:var(--danger);" onclick={() => deleteLog(log.id)}>✕</button>
          </div>
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
          <option value="manual">manual</option>
          <option value="opencode">opencode</option>
          <option value="claude">claude</option>
          <option value="cursor">cursor</option>
          <option value="copilot">copilot</option>
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

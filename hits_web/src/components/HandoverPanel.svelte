<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { uiStore } from '../lib/stores';
  import { t } from '../lib/i18n';

  let summary = $state<any>(null);
  let loading = $state(true);
  let error = $state('');
  let projectLabel = $derived(
    uiStore.value.selectedProject
      ? uiStore.value.selectedProject.split('/').pop()
      : null
  );

  onMount(async () => {
    await loadHandover();
  });

  async function loadHandover() {
    loading = true;
    error = '';
    summary = null;

    const project = uiStore.value.selectedProject;
    if (!project) {
      loading = false;
      return;
    }

    const res = await api.handover.get(project);
    if (res.success && res.data) {
      summary = res.data;
    } else {
      error = res.error || t('handover.noData');
    }
    loading = false;
  }

  function copyToClipboard() {
    if (!summary) return;
    const text = buildPlainText();
    navigator.clipboard.writeText(text).then(() => {
      alert('Copied to clipboard');
    });
  }

  function buildPlainText(): string {
    if (!summary) return '';
    const lines: string[] = [];
    lines.push(`📋 ${t('handover.title')}: ${summary.project_name}`);
    lines.push('='.repeat(40));
    lines.push(`${summary.project_path}`);
    if (summary.git_branch) {
      lines.push(`${summary.git_branch} (${summary.git_status || '?'})`);
    }
    lines.push('');

    if (summary.session_history?.length) {
      lines.push(`👥 ${t('handover.sessionHistory')}`);
      lines.push('-'.repeat(30));
      for (const s of summary.session_history) {
        lines.push(`  ${s.performed_by}: ${s.log_count} (${(s.last_activity || '').slice(0, 16)})`);
      }
      lines.push('');
    }

    if (summary.key_decisions?.length) {
      lines.push(`★ ${t('handover.keyDecisions')}`);
      lines.push('-'.repeat(30));
      for (const d of summary.key_decisions) {
        lines.push(`  • ${d}`);
      }
      lines.push('');
    }

    if (summary.pending_items?.length) {
      lines.push(`⚠ ${t('handover.pendingItems')}`);
      lines.push('-'.repeat(30));
      for (const p of summary.pending_items) {
        lines.push(`  • ${p}`);
      }
      lines.push('');
    }

    if (summary.recent_logs?.length) {
      lines.push(`📝 ${t('handover.recentWork')}`);
      lines.push('-'.repeat(30));
      for (const log of summary.recent_logs.slice(0, 10)) {
        const ts = (log.performed_at || '').slice(5, 16);
        const tool = log.performed_by;
        const text = log.request_text || `(${t('empty.noData')})`;
        lines.push(`  [${ts}] ${tool}: ${text.slice(0, 80)}`);
      }
    }

    return lines.join('\n');
  }
</script>

<div>
  <div class="flex items-center" style="margin-bottom:16px;">
    <h2 style="font-size:16px; flex:1;">🔄 {t('handover.title')} — {projectLabel || t('handover.selectProject')}</h2>
    {#if summary}
      <button class="btn btn-secondary btn-sm" onclick={copyToClipboard}>📋 {t('copy')}</button>
    {/if}
    <button class="btn btn-secondary btn-sm" onclick={loadHandover} style="margin-left:4px;">🔄</button>
  </div>

  {#if !uiStore.value.selectedProject}
    <div class="empty-state">
      <div class="icon">🔄</div>
      <div class="message">{t('handover.noProject')}</div>
    </div>
  {:else if loading}
    <div class="loading"><div class="spinner"></div></div>
  {:else if error}
    <div class="card" style="text-align:center; color:var(--danger);">{error}</div>
  {:else if !summary}
    <div class="empty-state">
      <div class="icon">🔄</div>
      <div class="message">{t('handover.noData')}</div>
    </div>
  {:else}
    <!-- Project Info -->
    <div class="card" style="margin-bottom:16px;">
      <div class="flex items-center gap-sm">
        <span style="font-size:24px;">📂</span>
        <div>
          <div style="font-weight:600;">{summary.project_name}</div>
          <div class="text-sm text-muted">{summary.project_path}</div>
        </div>
        {#if summary.git_branch}
          <div style="margin-left:auto;" class="badge badge-what">🔀 {summary.git_branch}</div>
        {/if}
      </div>
    </div>

    <!-- Session History -->
    {#if summary.session_history?.length}
      <div class="handover-section">
        <h3>👥 {t('handover.sessionHistory')}</h3>
        {#each summary.session_history as session}
          <div class="handover-item">
            <strong>{session.performed_by}</strong>: {session.log_count}
            <span class="text-xs text-muted" style="margin-left:8px;">
              {(session.last_activity || '').slice(0, 16)}
            </span>
          </div>
        {/each}
      </div>
    {/if}

    <!-- Key Decisions -->
    {#if summary.key_decisions?.length}
      <div class="handover-section">
        <h3>★ {t('handover.keyDecisions')}</h3>
        {#each summary.key_decisions as decision}
          <div class="handover-item" style="border-left-color:var(--warning);">
            {decision}
          </div>
        {/each}
      </div>
    {/if}

    <!-- Pending Items -->
    {#if summary.pending_items?.length}
      <div class="handover-section">
        <h3>⚠ {t('handover.pendingItems')}</h3>
        {#each summary.pending_items as item}
          <div class="handover-item" style="border-left-color:var(--danger);">
            {item}
          </div>
        {/each}
      </div>
    {/if}

    <!-- Files Modified -->
    {#if summary.files_modified?.length}
      <div class="handover-section">
        <h3>📄 {t('handover.filesModified')} ({summary.files_modified.length})</h3>
        {#each summary.files_modified.slice(0, 15) as file}
          <div class="handover-item" style="font-family:var(--font-mono); font-size:12px;">
            {file}
          </div>
        {/each}
        {#if summary.files_modified.length > 15}
          <div class="text-xs text-muted" style="margin-top:4px;">
            ... +{summary.files_modified.length - 15} {t('handover.more')}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Recent Logs -->
    {#if summary.recent_logs?.length}
      <div class="handover-section">
        <h3>📝 {t('handover.recentWork')}</h3>
        {#each summary.recent_logs.slice(0, 10) as log}
          <div class="handover-item">
            <span class="text-xs text-muted">{(log.performed_at || '').slice(5, 16)}</span>
            <span style="margin-left:8px;" class="badge badge-{log.performed_by === 'opencode' ? 'what' : 'how'}">
              {log.performed_by}
            </span>
            <span style="margin-left:8px;">{(log.request_text || `(${t('empty.noData')})`).slice(0, 80)}</span>
            {#if log.tags?.length}
              <div class="tags" style="display:inline-flex; margin-left:4px;">
                {#each log.tags as tag}
                  <span class="tag">{tag}</span>
                {/each}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>

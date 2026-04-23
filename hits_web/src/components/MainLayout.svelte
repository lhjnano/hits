<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { t, setLocale, getLocale, altLang, altLangLabel, subscribeLocale, type Locale } from '../lib/i18n';
  import { authStore, projectsStore, uiStore } from '../lib/stores';
  import KnowledgeTree from './KnowledgeTree.svelte';
  import Timeline from './Timeline.svelte';
  import ResumePanel from './ResumePanel.svelte';

  let { onLogout } = $props<{ onLogout: () => void }>();

  let showUserMenu = $state(false);
  let showPasswordModal = $state(false);
  let oldPassword = $state('');
  let newPassword = $state('');
  let confirmPassword = $state('');
  let passwordError = $state('');
  let passwordSuccess = $state('');
  let refreshing = $state(false);
  let activeTab: 'knowledge' | 'timeline' | 'resume' = $state('resume');
  let sidebarOpen = $state(true);
  let langLabel = $state(altLangLabel());
  let projects: any[] = $state([]);
  let selectedProject = $state('');
  // Counter to force re-render when locale changes
  let localeTick = $state(0);

  // Subscribe to locale changes so t() calls re-evaluate
  onMount(() => {
    const unsub = subscribeLocale(() => {
      localeTick++;
      langLabel = altLangLabel();
    });
    loadProjects();
    document.addEventListener('click', handleOutsideClick);
    return () => {
      unsub();
      document.removeEventListener('click', handleOutsideClick);
    };
  });

  async function loadProjects() {
    // Load from both handover (work logs) and checkpoints
    const [handoverRes, checkpointRes] = await Promise.all([
      api.handover.projects(),
      api.checkpoints.projects(),
    ]);

    const handoverProjects = (handoverRes.success && handoverRes.data) ? handoverRes.data : [];
    const checkpointProjects = (checkpointRes.success && checkpointRes.data) ? checkpointRes.data : [];

    // Merge: checkpoint projects fill in where handover has no entry
    const seen = new Set(handoverProjects.map((p: any) => p.project_path));
    for (const cp of checkpointProjects) {
      if (!seen.has(cp.project_path)) {
        handoverProjects.push({
          project_path: cp.project_path,
          project_name: cp.project_name,
          log_count: cp.checkpoint_count || 0,
          last_activity: cp.last_activity || '',
          performers: [cp.last_performer].filter(Boolean),
        });
        seen.add(cp.project_path);
      }
    }

    projectsStore.value = handoverProjects;
    projects = handoverProjects;
  }

  function handleOutsideClick(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest('.user-menu')) showUserMenu = false;
  }

  async function handleRefresh() {
    refreshing = true;
    await loadProjects();
    setTimeout(() => { refreshing = false; }, 300);
  }

  function toggleLang() {
    const next: Locale = altLang();
    setLocale(next);
    // 새 언어가 즉시 모든 컴포넌트에 적용되도록 새로고침
    window.location.reload();
  }

  function selectProject(path: string) {
    selectedProject = path;
  }

  async function handleChangePassword() {
    passwordError = '';
    passwordSuccess = '';
    if (newPassword !== confirmPassword) {
      passwordError = t('auth.passwordMismatch');
      return;
    }
    if (newPassword.length < 8) {
      passwordError = t('auth.passwordMin');
      return;
    }
    const res = await api.auth.changePassword(oldPassword, newPassword);
    if (res.success) {
      passwordSuccess = t('auth.passwordChanged');
      oldPassword = '';
      newPassword = '';
      confirmPassword = '';
      setTimeout(() => { showPasswordModal = false; passwordSuccess = ''; }, 1500);
    } else {
      passwordError = res.error || t('auth.wrongPassword');
    }
  }

  function switchTab(tab: 'knowledge' | 'timeline' | 'resume') {
    activeTab = tab;
  }
</script>

<div class="app-layout" data-locale-tick={localeTick}>
  <!-- Sidebar -->
  <div class="sidebar" class:collapsed={!sidebarOpen}>
    <div style="padding:16px; border-bottom: 1px solid var(--border-color);">
      <h2 style="font-size:14px; color:var(--text-primary);">📁 {t('header.projects')}</h2>
    </div>
    <div class="overflow-y" style="flex:1;">
      {#if projects.length === 0}
        <div class="p-md text-muted text-sm" style="text-align:center;">
          {t('sidebar.noProjects')}
        </div>
      {:else}
        {#each projects as project}
          <div
            class="project-item"
            class:selected={selectedProject === project.project_path}
            role="button"
            tabindex="0"
            onclick={() => selectProject(project.project_path)}
            onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectProject(project.project_path); } }}
          >
            <span>📂</span>
            <span style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              {project.project_path.split('/').pop() || project.project_path}
            </span>
            <span class="text-xs">{project.total_logs}</span>
          </div>
        {/each}
      {/if}
    </div>
  </div>

  <!-- Main -->
  <div class="main-content">
    <!-- Header -->
    <div class="header">
      <button
        class="btn-icon"
        onclick={() => sidebarOpen = !sidebarOpen}
        title={t('header.toggleSidebar')}
        aria-label={t('header.toggleSidebar')}
      >
        {sidebarOpen ? '◀' : '▶'}
      </button>

      <h1>HITS</h1>

      <div class="tabs" style="margin-left:12px;">
        <button class="tab" class:active={activeTab === 'resume'} onclick={() => switchTab('resume')}>
          ▶ Resume
        </button>
        <button class="tab" class:active={activeTab === 'knowledge'} onclick={() => switchTab('knowledge')}>
          📋 {t('header.knowledge')}
        </button>
        <button class="tab" class:active={activeTab === 'timeline'} onclick={() => switchTab('timeline')}>
          📝 {t('header.timeline')}
        </button>
      </div>

      <div style="flex:1;"></div>

      <!-- Language Toggle -->
      <button class="btn-icon" onclick={toggleLang} title="Switch language" aria-label="Switch language">
        🌐 {langLabel}
      </button>

      <button class="btn-icon" onclick={handleRefresh} title={t('header.refresh')} aria-label={t('header.refresh')}>
        {refreshing ? '⏳' : '🔄'}
      </button>

      <div class="user-menu">
        <button class="user-menu-toggle" onclick={() => showUserMenu = !showUserMenu}>
          👤 {authStore.value.username}
          {#if authStore.value.role === 'admin'}<span class="text-xs" style="color:var(--warning);">★</span>{/if}
          ▾
        </button>
        {#if showUserMenu}
          <div class="user-dropdown">
            <button onclick={() => { showPasswordModal = true; showUserMenu = false; }}>
              🔑 {t('auth.changePassword')}
            </button>
            <button onclick={onLogout}>
              🚪 {t('auth.logout')}
            </button>
          </div>
{/if}

<style>
  .sponsor-links {
    position: fixed;
    bottom: 12px;
    left: 12px;
    display: flex;
    gap: 12px;
    opacity: 0.4;
    transition: opacity 0.2s;
    z-index: 50;
  }
  .sponsor-links:hover {
    opacity: 0.9;
  }
  .sponsor-links a {
    display: flex;
    align-items: center;
    gap: 4px;
    color: var(--text-muted);
    text-decoration: none;
    font-size: 11px;
    padding: 4px 6px;
    border-radius: 4px;
    background: var(--bg-secondary);
    transition: color 0.15s, background 0.15s;
  }
  .sponsor-links a:hover {
    color: var(--text-primary);
    background: var(--border-color);
  }
  .sponsor-label {
    display: none;
  }
  .sponsor-links:hover .sponsor-label {
    display: inline;
  }
</style>
      </div>
    </div>

    <!-- Content -->
    <div class="content-area">
      {#if activeTab === 'resume'}
        <ResumePanel bind:selectedProject />
      {:else if activeTab === 'knowledge'}
        <KnowledgeTree />
      {:else if activeTab === 'timeline'}
        <Timeline />
      {/if}
    </div>
  </div>

  <!-- Sponsor links (bottom-left) -->
  <div class="sponsor-links">
    <a href="https://github.com/sponsors/lhjnano" target="_blank" rel="noopener noreferrer" title="GitHub Sponsors" aria-label="GitHub Sponsors">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
      <span class="sponsor-label">Sponsor</span>
    </a>
    <a href="https://ko-fi.com/lhjnano" target="_blank" rel="noopener noreferrer" title="Ko-fi" aria-label="Ko-fi">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M23.881 8.948c-.773-4.085-4.859-4.593-4.859-4.593H.723c-.604 0-.679.798-.679.798s-.082 7.324-.022 11.822c.164 2.424 2.586 2.672 2.586 2.672s8.267-.023 11.966-.049c2.438-.426 2.683-2.566 2.658-3.734 4.352.24 7.422-2.831 6.649-6.916zm-11.062 3.511c-1.246 1.453-4.011 3.976-4.011 3.976s-.121.119-.31.023c-.076-.057-.108-.09-.108-.09-.443-.441-3.368-3.049-4.034-3.954-.709-.965-1.041-2.7-.091-3.71.951-1.01 3.005-1.086 4.363.407 0 0 1.565-1.782 3.468-.963 1.904.82 1.832 3.011.723 4.311zm6.173.478c-.928.116-1.682.028-1.682.028V7.284h1.77s1.971.551 1.971 2.638c0 1.913-.985 2.667-2.059 3.015z"/></svg>
      <span class="sponsor-label">Ko-fi</span>
    </a>
  </div>
</div>

<!-- Password Modal -->
{#if showPasswordModal}
  <div class="modal-overlay" onclick={() => showPasswordModal = false}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h2>🔑 {t('auth.changePassword')}</h2>
      <div class="form-group">
        <label>{t('auth.currentPassword')}</label>
        <input class="input" type="password" bind:value={oldPassword} autocomplete="current-password" />
      </div>
      <div class="form-group">
        <label>{t('auth.newPassword')}</label>
        <input class="input" type="password" bind:value={newPassword} autocomplete="new-password" />
      </div>
      <div class="form-group">
        <label>{t('auth.newPasswordConfirm')}</label>
        <input class="input" type="password" bind:value={confirmPassword} autocomplete="new-password" />
      </div>
      {#if passwordError}
        <div class="error-msg">{passwordError}</div>
      {/if}
      {#if passwordSuccess}
        <div style="color:var(--success); font-size:12px; margin-top:8px;">{passwordSuccess}</div>
      {/if}
      <div class="flex gap-sm" style="margin-top:16px; justify-content:flex-end;">
        <button class="btn btn-secondary" onclick={() => showPasswordModal = false}>{t('cancel')}</button>
        <button class="btn btn-primary" onclick={handleChangePassword}>{t('save')}</button>
      </div>
    </div>
  </div>
{/if}

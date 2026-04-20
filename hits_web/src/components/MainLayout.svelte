<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { t, setLocale, getLocale, altLang, altLangLabel, subscribeLocale, type Locale } from '../lib/i18n';
  import { authStore, projectsStore, uiStore } from '../lib/stores';
  import KnowledgeTree from './KnowledgeTree.svelte';
  import Timeline from './Timeline.svelte';
  import HandoverPanel from './HandoverPanel.svelte';
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
  let activeTab: 'knowledge' | 'timeline' | 'handover' | 'resume' = $state('resume');
  let sidebarOpen = $state(true);
  let langLabel = $state(altLangLabel());
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
    const res = await api.handover.projects();
    if (res.success && res.data) {
      projectsStore.value = res.data;
    }
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
    uiStore.value = { ...uiStore.value, selectedProject: path };
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

  function switchTab(tab: 'knowledge' | 'timeline' | 'handover' | 'resume') {
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
      {#if projectsStore.value.length === 0}
        <div class="p-md text-muted text-sm" style="text-align:center;">
          {t('sidebar.noProjects')}
        </div>
      {:else}
        {#each projectsStore.value as project}
          <div
            class="project-item"
            class:selected={uiStore.value.selectedProject === project.project_path}
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
        <button class="tab" class:active={activeTab === 'handover'} onclick={() => switchTab('handover')}>
          🔄 {t('header.handover')}
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
      </div>
    </div>

    <!-- Content -->
    <div class="content-area">
      {#if activeTab === 'resume'}
        <ResumePanel />
      {:else if activeTab === 'knowledge'}
        <KnowledgeTree />
      {:else if activeTab === 'timeline'}
        <Timeline />
      {:else if activeTab === 'handover'}
        <HandoverPanel />
      {/if}
    </div>
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

<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { authStore, uiStore, projectsStore } from '../lib/stores';
  import KnowledgeTree from './KnowledgeTree.svelte';
  import Timeline from './Timeline.svelte';
  import HandoverPanel from './HandoverPanel.svelte';

  let { onLogout } = $props<{ onLogout: () => void }>();

  let showUserMenu = $state(false);
  let showPasswordModal = $state(false);
  let oldPassword = $state('');
  let newPassword = $state('');
  let confirmPassword = $state('');
  let passwordError = $state('');
  let passwordSuccess = $state('');
  let refreshing = $state(false);

  onMount(async () => {
    await loadProjects();
    // Click outside to close user menu
    document.addEventListener('click', handleOutsideClick);
    return () => document.removeEventListener('click', handleOutsideClick);
  });

  async function loadProjects() {
    const res = await api.handover.projects();
    if (res.success && res.data) {
      projectsStore.value = res.data;
    }
  }

  function handleOutsideClick(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest('.user-menu')) {
      showUserMenu = false;
    }
  }

  async function handleRefresh() {
    refreshing = true;
    await loadProjects();
    // Trigger child component refresh via key change
    setTimeout(() => { refreshing = false; }, 300);
  }

  async function handleChangePassword() {
    passwordError = '';
    passwordSuccess = '';

    if (newPassword !== confirmPassword) {
      passwordError = '비밀번호가 일치하지 않습니다';
      return;
    }
    if (newPassword.length < 8) {
      passwordError = '비밀번호는 8자 이상이어야 합니다';
      return;
    }

    const res = await api.auth.changePassword(oldPassword, newPassword);
    if (res.success) {
      passwordSuccess = '비밀번호가 변경되었습니다';
      oldPassword = '';
      newPassword = '';
      confirmPassword = '';
      setTimeout(() => { showPasswordModal = false; passwordSuccess = ''; }, 1500);
    } else {
      passwordError = res.error || '비밀번호 변경 실패';
    }
  }

  let activeTab: 'knowledge' | 'timeline' | 'handover' = $state('knowledge');
  let sidebarOpen = $state(true);

  function switchTab(tab: 'knowledge' | 'timeline' | 'handover') {
    activeTab = tab;
  }
</script>

<div class="app-layout">
  <!-- Sidebar -->
  <div class="sidebar" class:collapsed={!sidebarOpen}>
    <div style="padding:16px; border-bottom: 1px solid var(--border-color);">
      <h2 style="font-size:14px; color:var(--text-primary);">📁 프로젝트</h2>
    </div>
    <div class="overflow-y" style="flex:1;">
      {#if projectsStore.value.length === 0}
        <div class="p-md text-muted text-sm" style="text-align:center;">
          기록된 프로젝트가 없습니다
        </div>
      {:else}
        {#each projectsStore.value as project}
          <div
            class="project-item"
            class:active={uiStore.value.selectedProject === project.project_path}
            onclick={() => uiStore.value = { ...uiStore.value, selectedProject: project.project_path }}
            role="button"
            tabindex="0"
          >
            <span>📂</span>
            <span style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              {project.project_path.split('/').pop() || project.project_path}
            </span>
            <span class="text-xs">{project.total_logs}건</span>
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
        title="사이드바 토글"
        aria-label="사이드바 토글"
      >
        {sidebarOpen ? '◀' : '▶'}
      </button>

      <h1>HITS</h1>

      <div class="tabs" style="margin-left:12px;">
        <button class="tab" class:active={activeTab === 'knowledge'} onclick={() => switchTab('knowledge')}>
          📋 지식 트리
        </button>
        <button class="tab" class:active={activeTab === 'timeline'} onclick={() => switchTab('timeline')}>
          📝 타임라인
        </button>
        <button class="tab" class:active={activeTab === 'handover'} onclick={() => switchTab('handover')}>
          🔄 인수인계
        </button>
      </div>

      <div style="flex:1;"></div>

      <button class="btn-icon" onclick={handleRefresh} title="새로고침" aria-label="새로고침">
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
              🔑 비밀번호 변경
            </button>
            <button onclick={onLogout}>
              🚪 로그아웃
            </button>
          </div>
        {/if}
      </div>
    </div>

    <!-- Content -->
    <div class="content-area">
      {#if activeTab === 'knowledge'}
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
      <h2>🔑 비밀번호 변경</h2>
      <div class="form-group">
        <label>현재 비밀번호</label>
        <input class="input" type="password" bind:value={oldPassword} autocomplete="current-password" />
      </div>
      <div class="form-group">
        <label>새 비밀번호</label>
        <input class="input" type="password" bind:value={newPassword} autocomplete="new-password" />
      </div>
      <div class="form-group">
        <label>새 비밀번호 확인</label>
        <input class="input" type="password" bind:value={confirmPassword} autocomplete="new-password" />
      </div>
      {#if passwordError}
        <div class="error-msg">{passwordError}</div>
      {/if}
      {#if passwordSuccess}
        <div style="color:var(--success); font-size:12px; margin-top:8px;">{passwordSuccess}</div>
      {/if}
      <div class="flex gap-sm" style="margin-top:16px; justify-content:flex-end;">
        <button class="btn btn-secondary" onclick={() => showPasswordModal = false}>취소</button>
        <button class="btn btn-primary" onclick={handleChangePassword}>변경</button>
      </div>
    </div>
  </div>
{/if}

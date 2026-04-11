<script lang="ts">
  import './lib/styles.css';
  import { onMount } from 'svelte';
  import { api } from './lib/api';
  import { initLocale } from './lib/i18n';
  import { authStore } from './lib/stores';
  import Login from './components/Login.svelte';
  import MainLayout from './components/MainLayout.svelte';

  let authenticated = $state(false);
  let initialized = $state(false);
  let loading = $state(true);

  onMount(async () => {
    initLocale();
    const res = await api.auth.status();
    if (res.success && res.data) {
      initialized = res.data.initialized;
      authenticated = res.data.authenticated;
      if (authenticated) {
        authStore.value = {
          initialized: true,
          authenticated: true,
          username: res.data.username || null,
          role: res.data.role || null,
          loading: false,
        };
      }
    }
    loading = false;
  });

  function onLoginSuccess(data: { username: string; role: string }) {
    authenticated = true;
    initialized = true;
    authStore.value = {
      initialized: true,
      authenticated: true,
      username: data.username,
      role: data.role,
      loading: false,
    };
  }

  async function onLogout() {
    await api.auth.logout();
    authenticated = false;
    authStore.value = {
      initialized: true,
      authenticated: false,
      username: null,
      role: null,
      loading: false,
    };
  }
</script>

<main class="app-layout">
  {#if loading}
    <div class="login-container">
      <div class="loading">
        <div class="spinner" style="width:32px;height:32px;margin-right:12px;"></div>
        <span>HITS...</span>
      </div>
    </div>
  {:else if !authenticated}
    <Login {initialized} onLogin={onLoginSuccess} />
  {:else}
    <MainLayout onLogout={onLogout} />
  {/if}
</main>

<script lang="ts">
  import { api } from '../lib/api';
  import { t } from '../lib/i18n';

  let { initialized, onLogin } = $props<{
    initialized: boolean;
    onLogin: (data: { username: string; role: string }) => void;
  }>();

  let isRegister = $state(!initialized);
  let username = $state('');
  let password = $state('');
  let confirmPassword = $state('');
  let error = $state('');
  let submitting = $state(false);

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = '';

    if (isRegister) {
      if (password !== confirmPassword) {
        error = t('auth.passwordMismatch');
        return;
      }
      if (password.length < 8) {
        error = t('auth.passwordMin');
        return;
      }

      submitting = true;
      const res = await api.auth.register(username, password);
      submitting = false;

      if (res.success) {
        const loginRes = await api.auth.login(username, password);
        if (loginRes.success && loginRes.data) {
          onLogin(loginRes.data);
        }
      } else {
        error = res.error || t('auth.registerFailed');
      }
    } else {
      submitting = true;
      const res = await api.auth.login(username, password);
      submitting = false;

      if (res.success && res.data) {
        onLogin(res.data);
      } else {
        error = res.error || t('auth.loginFailed');
      }
    }
  }
</script>

<div class="login-container">
  <div class="login-card">
    <h1>🌳 HITS</h1>
    <p class="subtitle">{t('app.subtitle')}</p>

    <form onsubmit={handleSubmit}>
      <div class="form-group">
        <label for="username">{t('auth.username')}</label>
        <input
          id="username"
          class="input"
          type="text"
          bind:value={username}
          placeholder={t('auth.username')}
          autocomplete="username"
          required
          minlength={3}
          maxlength={32}
          disabled={submitting}
        />
      </div>

      <div class="form-group">
        <label for="password">{t('auth.password')}</label>
        <input
          id="password"
          class="input"
          type="password"
          bind:value={password}
          placeholder={t('auth.password')}
          autocomplete={isRegister ? 'new-password' : 'current-password'}
          required
          minlength={8}
          disabled={submitting}
        />
      </div>

      {#if isRegister}
        <div class="form-group">
          <label for="confirm">{t('auth.confirmPassword')}</label>
          <input
            id="confirm"
            class="input"
            type="password"
            bind:value={confirmPassword}
            placeholder={t('auth.confirmPassword')}
            autocomplete="new-password"
            required
            minlength={8}
            disabled={submitting}
          />
        </div>
      {/if}

      {#if error}
        <div class="error-msg">{error}</div>
      {/if}

      <button
        class="btn btn-primary w-full"
        type="submit"
        style="margin-top: 16px; justify-content: center;"
        disabled={submitting}
      >
        {#if submitting}
          <div class="spinner" style="width:14px;height:14px;"></div>
          {t('auth.processing')}
        {:else}
          {isRegister ? t('auth.register') : t('auth.login')}
        {/if}
      </button>
    </form>

    {#if initialized}
      <p style="text-align:center; margin-top:16px; font-size:12px;">
        {#if isRegister}
          {t('auth.hasAccount')}
          <button
            style="background:none;border:none;color:var(--accent-secondary);cursor:pointer;font-size:12px;font-family:var(--font-sans);"
            onclick={() => { isRegister = false; error = ''; }}
          >{t('auth.login')}</button>
        {:else}
          <button
            style="background:none;border:none;color:var(--accent-secondary);cursor:pointer;font-size:12px;font-family:var(--font-sans);"
            onclick={() => { isRegister = true; error = ''; }}
          >{t('auth.noAccount')}</button>
        {/if}
      </p>
    {:else}
      <p style="text-align:center; margin-top:16px; font-size:12px; color:var(--text-muted);">
        {t('auth.firstAccount')}
      </p>
    {/if}
  </div>
</div>

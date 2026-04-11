<script lang="ts">
  import { api } from '../lib/api';

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
        error = '비밀번호가 일치하지 않습니다';
        return;
      }
      if (password.length < 8) {
        error = '비밀번호는 8자 이상이어야 합니다';
        return;
      }

      submitting = true;
      const res = await api.auth.register(username, password);
      submitting = false;

      if (res.success) {
        // Auto-login after registration
        const loginRes = await api.auth.login(username, password);
        if (loginRes.success && loginRes.data) {
          onLogin(loginRes.data);
        }
      } else {
        error = res.error || '회원가입 실패';
      }
    } else {
      submitting = true;
      const res = await api.auth.login(username, password);
      submitting = false;

      if (res.success && res.data) {
        onLogin(res.data);
      } else {
        error = res.error || '로그인 실패';
      }
    }
  }
</script>

<div class="login-container">
  <div class="login-card">
    <h1>🌳 HITS</h1>
    <p class="subtitle">Hybrid Intel Trace System</p>

    <form onsubmit={handleSubmit}>
      <div class="form-group">
        <label for="username">사용자명</label>
        <input
          id="username"
          class="input"
          type="text"
          bind:value={username}
          placeholder="사용자명 입력"
          autocomplete="username"
          required
          minlength={3}
          maxlength={32}
          disabled={submitting}
        />
      </div>

      <div class="form-group">
        <label for="password">비밀번호</label>
        <input
          id="password"
          class="input"
          type="password"
          bind:value={password}
          placeholder="비밀번호 입력"
          autocomplete={isRegister ? 'new-password' : 'current-password'}
          required
          minlength={8}
          disabled={submitting}
        />
      </div>

      {#if isRegister}
        <div class="form-group">
          <label for="confirm">비밀번호 확인</label>
          <input
            id="confirm"
            class="input"
            type="password"
            bind:value={confirmPassword}
            placeholder="비밀번호 재입력"
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
          처리 중...
        {:else}
          {isRegister ? '계정 생성' : '로그인'}
        {/if}
      </button>
    </form>

    {#if initialized}
      <p style="text-align:center; margin-top:16px; font-size:12px;">
        {#if isRegister}
          이미 계정이 있으신가요?
          <button
            style="background:none;border:none;color:var(--accent-secondary);cursor:pointer;font-size:12px;font-family:var(--font-sans);"
            onclick={() => { isRegister = false; error = ''; }}
          >로그인</button>
        {:else}
          <button
            style="background:none;border:none;color:var(--accent-secondary);cursor:pointer;font-size:12px;font-family:var(--font-sans);"
            onclick={() => { isRegister = true; error = ''; }}
          >새 계정 만들기</button>
        {/if}
      </p>
    {:else}
      <p style="text-align:center; margin-top:16px; font-size:12px; color:var(--text-muted);">
        첫 번째 계정이 관리자로 설정됩니다
      </p>
    {/if}
  </div>
</div>

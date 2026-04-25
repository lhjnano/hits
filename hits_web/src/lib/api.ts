/**
 * Secure API client for HITS.
 * Uses HttpOnly cookies for authentication (set by server).
 * No token stored in localStorage/sessionStorage.
 */

const API_BASE = '/api';

interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}

async function request<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };

  // Don't set Content-Type for FormData
  if (options.body && typeof options.body === 'string') {
    headers['Content-Type'] = 'application/json';
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      credentials: 'include', // Send HttpOnly cookies
    });

    if (response.status === 401) {
      // Try refresh
      const refreshed = await refreshToken();
      if (refreshed) {
        // Retry original request
        const retry = await fetch(url, { ...options, headers, credentials: 'include' });
        return retry.json();
      }
      return { success: false, error: 'Authentication required' };
    }

    if (response.status === 429) {
      return { success: false, error: 'Too many requests. Please wait.' };
    }

    return response.json();
  } catch (err) {
    return { success: false, error: 'Network error' };
  }
}

async function refreshToken(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    });
    const data = await res.json();
    return data.success === true;
  } catch {
    return false;
  }
}

// --- Auth ---

export const api = {
  // Auth
  auth: {
    status: () => request<{ initialized: boolean; authenticated: boolean; username?: string; role?: string }>('/auth/status'),
    register: (username: string, password: string) =>
      request('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      }),
    login: (username: string, password: string) =>
      request<{ username: string; role: string }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      }),
    logout: () => request('/auth/logout', { method: 'POST' }),
    me: () => request<{ username: string; role: string }>('/auth/me'),
    changePassword: (old_password: string, new_password: string) =>
      request('/auth/password', {
        method: 'PUT',
        body: JSON.stringify({ old_password, new_password }),
      }),
  },

  // Work Logs
  workLogs: {
    list: (params?: { project_path?: string; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.project_path) q.set('project_path', params.project_path);
      if (params?.limit) q.set('limit', String(params.limit));
      const qs = q.toString();
      return request(`/work-logs${qs ? '?' + qs : ''}`);
    },
    get: (id: string) => request(`/work-log/${id}`),
    create: (data: Record<string, unknown>) =>
      request('/work-log', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Record<string, unknown>) =>
      request(`/work-log/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: string) =>
      request(`/work-log/${id}`, { method: 'DELETE' }),
    search: (query: string, project_path?: string) => {
      const q = new URLSearchParams({ q: query });
      if (project_path) q.set('project_path', project_path);
      return request(`/work-logs/search?${q}`);
    },
  },

  // Handover
  handover: {
    get: (project_path: string) =>
      request(`/handover?project_path=${encodeURIComponent(project_path)}`),
    projects: () => request('/handover/projects'),
    projectStats: (project_path: string) =>
      request(`/handover/project-stats?project_path=${encodeURIComponent(project_path)}`),
  },

  // Checkpoints
  checkpoints: {
    resume: (project_path: string, token_budget?: number, performer?: string) => {
      const q = new URLSearchParams({ project_path });
      if (token_budget) q.set('token_budget', String(token_budget));
      if (performer) q.set('performer', performer);
      return request(`/checkpoint/resume?${q}`);
    },
    latest: (project_path: string, token_budget?: number) => {
      const q = new URLSearchParams({ project_path });
      if (token_budget) q.set('token_budget', String(token_budget));
      return request(`/checkpoint/latest?${q}`);
    },
    list: (project_path: string, limit?: number) => {
      const q = new URLSearchParams({ project_path });
      if (limit) q.set('limit', String(limit));
      return request(`/checkpoint/list?${q}`);
    },
    projects: () => request('/checkpoint/projects'),
    auto: (data: Record<string, unknown>) =>
      request('/checkpoint/auto', { method: 'POST', body: JSON.stringify(data) }),
  },

  // Knowledge Categories
  knowledge: {
    list: () => request('/knowledge/categories'),
    createCategory: (name: string, icon: string) =>
      request('/knowledge/category', { method: 'POST', body: JSON.stringify({ name, icon }) }),
    updateCategory: (oldName: string, name: string, icon?: string) =>
      request(`/knowledge/category/${encodeURIComponent(oldName)}`, {
        method: 'PUT',
        body: JSON.stringify({ name, icon }),
      }),
    deleteCategory: (name: string) =>
      request(`/knowledge/category/${encodeURIComponent(name)}`, { method: 'DELETE' }),
    addNode: (category: string, node: { name: string; layer: string; type: string; action: string; negative_path: boolean }) =>
      request(`/knowledge/category/${encodeURIComponent(category)}/nodes`, {
        method: 'POST',
        body: JSON.stringify(node),
      }),
    updateNode: (category: string, index: number, node: Record<string, unknown>) =>
      request(`/knowledge/category/${encodeURIComponent(category)}/nodes/${index}`, {
        method: 'PUT',
        body: JSON.stringify(node),
      }),
    deleteNode: (category: string, index: number) =>
      request(`/knowledge/category/${encodeURIComponent(category)}/nodes/${index}`, { method: 'DELETE' }),
  },

  // Signals
  signals: {
    send: (data: Record<string, unknown>) =>
      request('/signals/send', { method: 'POST', body: JSON.stringify(data) }),
    check: (recipient?: string, project_path?: string) => {
      const q = new URLSearchParams();
      if (recipient) q.set('recipient', recipient);
      if (project_path) q.set('project_path', project_path);
      return request(`/signals/check?${q}`);
    },
  },

  // Tasks
  tasks: {
    list: (params?: { project_path?: string; status?: string }) => {
      const q = new URLSearchParams();
      if (params?.project_path) q.set('project_path', params.project_path);
      if (params?.status) q.set('status', params.status);
      const qs = q.toString();
      return request(`/tasks${qs ? '?' + qs : ''}`);
    },
    create: (data: { title: string; project_path?: string; priority?: string; context?: string; created_by?: string }) =>
      request('/tasks', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Record<string, unknown>) =>
      request(`/tasks/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: string) =>
      request(`/tasks/${id}`, { method: 'DELETE' }),
    exportToSlack: (id: string, channel: string) =>
      request(`/tasks/${id}/export`, { method: 'POST', body: JSON.stringify({ channel }) }),
    slackChannels: () =>
      request('/tasks/slack/channels'),
    addSlackChannel: (name: string, webhook_url: string) =>
      request('/tasks/slack/channels', { method: 'POST', body: JSON.stringify({ name, webhook_url }) }),
    deleteSlackChannel: (name: string) =>
      request(`/tasks/slack/channels/${encodeURIComponent(name)}`, { method: 'DELETE' }),
    importFromSlack: (channel: string, limit?: number) =>
      request('/tasks/slack/import', { method: 'POST', body: JSON.stringify({ channel, limit: limit || 10 }) }),
  },
};

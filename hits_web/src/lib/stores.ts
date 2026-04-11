/**
 * Svelte 5 runes-based stores for HITS application state.
 * Uses $state and $derived runes for reactive state management.
 */

export type { };

// --- Auth State ---
// These are imported and used directly in components as module-level state.
// In Svelte 5, we use $state rune inside .svelte.js files or
// simple reactive state in .svelte components via $state().

// For cross-component state, we use a simple observable pattern.
type Listener = () => void;

class Store<T> {
  private _value: T;
  private _listeners: Set<Listener> = new Set();

  constructor(initial: T) {
    this._value = initial;
  }

  get value(): T {
    return this._value;
  }

  set value(newValue: T) {
    this._value = newValue;
    this._listeners.forEach(fn => fn());
  }

  subscribe(fn: Listener): () => void {
    this._listeners.add(fn);
    return () => this._listeners.delete(fn);
  }

  update(fn: (current: T) => T) {
    this.value = fn(this._value);
  }
}

// --- Auth Store ---
export interface AuthState {
  initialized: boolean;
  authenticated: boolean;
  username: string | null;
  role: string | null;
  loading: boolean;
}

export const authStore = new Store<AuthState>({
  initialized: false,
  authenticated: false,
  username: null,
  role: null,
  loading: true,
});

// --- UI State ---
export interface UIState {
  activeTab: 'knowledge' | 'timeline' | 'handover';
  selectedProject: string;
  sidebarOpen: boolean;
  searchQuery: string;
  showAddDialog: boolean;
  editingItem: Record<string, unknown> | null;
}

export const uiStore = new Store<UIState>({
  activeTab: 'knowledge',
  selectedProject: '',
  sidebarOpen: true,
  searchQuery: '',
  showAddDialog: false,
  editingItem: null,
});

// --- Data Stores ---
export const projectsStore = new Store<{ project_path: string; total_logs: number; last_activity: string | null }[]>([]);
export const categoriesStore = new Store<{ name: string; icon: string; items: unknown[] }[]>([]);
export const workLogsStore = new Store<unknown[]>([]);

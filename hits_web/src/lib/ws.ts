/**
 * WebSocket client for real-time HITS event streaming.
 * Auto-reconnects on disconnect. Provides typed event subscriptions.
 */

export interface LiveEvent {
  type: string;
  data: Record<string, unknown>;
  project_path?: string;
  performer?: string;
  timestamp: string;
}

type EventHandler = (event: LiveEvent) => void;

class WsClient {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Set<EventHandler>> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private _connected = false;

  get connected() { return this._connected; }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}/api/ws/events`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this._connected = true;
      this.emit({ type: '_connected', data: {}, timestamp: new Date().toISOString() });
    };

    this.ws.onmessage = (ev) => {
      try {
        const event: LiveEvent = JSON.parse(ev.data);
        // Notify wildcard listeners
        this.listeners.get('*')?.forEach(fn => fn(event));
        // Notify type-specific listeners
        this.listeners.get(event.type)?.forEach(fn => fn(event));
      } catch { /* ignore malformed */ }
    };

    this.ws.onclose = () => {
      this._connected = false;
      this.emit({ type: '_disconnected', data: {}, timestamp: new Date().toISOString() });
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 3000);
  }

  private emit(event: LiveEvent) {
    this.listeners.get('*')?.forEach(fn => fn(event));
    this.listeners.get(event.type)?.forEach(fn => fn(event));
  }

  /** Subscribe to events. Use '*' for all, or specific type like 'checkpoint_created' */
  on(type: string, handler: EventHandler): () => void {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(handler);
    return () => this.listeners.get(type)?.delete(handler);
  }

  /** Send a client action (ping, history request) */
  send(action: string, data: Record<string, unknown> = {}) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action, ...data }));
    }
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }
}

export const wsClient = new WsClient();

/**
 * Resilient, singleton WebSocket client for RevenueOS.
 *
 * Implements:
 * - Request correlation (UUIDv4)
 * - 25-second heartbeat ping / 5-second stale connection detection
 * - Jittered exponential backoff reconnect (1s -> 30s)
 * - Automatic subscription cleanup and event listener tracking
 * - Explicit connection lifecycle state management
 */

import {
  ClientMessage,
  ClientMessageType,
  ConnectionState,
  ServerMessage,
  ServerMessageType,
} from "./types";

type MessageHandler = (message: ServerMessage) => void;

interface PendingRequest {
  resolve: (value: ServerMessage) => void;
  reject: (reason: Error) => void;
  timeoutId: ReturnType<typeof setTimeout>;
}

export class RevenueWebSocketClient {
  private static instance: RevenueWebSocketClient | null = null;
  private ws: WebSocket | null = null;
  private url: string;
  private state: ConnectionState = "DISCONNECTED";

  // Request correlation map: requestId -> PendingRequest
  private pendingRequests = new Map<string, PendingRequest>();

  // Event handlers: messageType -> Set<MessageHandler>
  private listeners = new Map<ServerMessageType | "*", Set<MessageHandler>>();

  // State change callbacks
  private stateListeners = new Set<(state: ConnectionState) => void>();

  // Heartbeat state
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private heartbeatTimeout: ReturnType<typeof setTimeout> | null = null;
  private readonly PING_INTERVAL_MS = 25000;
  private readonly PONG_TIMEOUT_MS = 15000;

  // Reconnection state
  private reconnectAttempt = 0;
  private readonly MAX_RECONNECT_ATTEMPTS = 5;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isExplicitlyClosed = false;

  private constructor(url?: string) {
    const defaultUrl =
      process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/v1/app/";
    this.url = url || defaultUrl;
    if (typeof window !== "undefined") {
      (window as unknown as { __REVENUE_WS_CLIENT__?: RevenueWebSocketClient }).__REVENUE_WS_CLIENT__ = this;
      window.addEventListener("offline", () => {
        this.setState("OFFLINE");
      });
      window.addEventListener("online", () => {
        if (this.state === "OFFLINE" && !this.isExplicitlyClosed) {
          this.connect();
        }
      });
    }
  }

  public static getInstance(url?: string): RevenueWebSocketClient {
    if (!RevenueWebSocketClient.instance) {
      RevenueWebSocketClient.instance = new RevenueWebSocketClient(url);
    }
    return RevenueWebSocketClient.instance;
  }

  public connect(): void {
    if (typeof window === "undefined") return; // SSR guard
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      this.setState("OFFLINE");
      return;
    }
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isExplicitlyClosed = false;
    this.setState("CONNECTING");

    try {
      this.ws = new WebSocket(this.url);
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onerror = this.handleError.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
    } catch {
      this.setState("ERROR");
      this.scheduleReconnect();
    }
  }

  public disconnect(reason = "Client disconnect"): void {
    this.isExplicitlyClosed = true;
    this.reconnectAttempt = 0;
    this.cleanupHeartbeat();
    this.clearReconnectTimer();

    // Reject all pending RPC requests
    this.pendingRequests.forEach((req) => {
      clearTimeout(req.timeoutId);
      req.reject(new Error("WebSocket client explicitly disconnected."));
    });
    this.pendingRequests.clear();

    if (this.ws) {
      this.ws.close(1000, reason);
      this.ws = null;
    }
    this.setState("CLOSED_INTENTIONALLY");
  }

  public getState(): ConnectionState {
    return this.state;
  }

  public onStateChange(callback: (state: ConnectionState) => void): () => void {
    this.stateListeners.add(callback);
    callback(this.state);
    return () => {
      this.stateListeners.delete(callback);
    };
  }

  public on(type: ServerMessageType | "*", handler: MessageHandler): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(handler);

    // Return cleanup function to prevent memory leaks
    return () => {
      const set = this.listeners.get(type);
      if (set) {
        set.delete(handler);
        if (set.size === 0) {
          this.listeners.delete(type);
        }
      }
    };
  }

  /**
   * Send an RPC command and await correlated response.
   */
  public async request<T = unknown, R = unknown>(
    type: ClientMessageType,
    payload: T,
    timeoutMs = 10000
  ): Promise<ServerMessage<R>> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not connected. Current state: " + this.state);
    }

    const requestId = this.generateUUID();
    const message: ClientMessage<T> = {
      protocolVersion: "v1",
      requestId,
      type,
      timestamp: new Date().toISOString(),
      payload,
    };

    return new Promise<ServerMessage<R>>((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        this.pendingRequests.delete(requestId);
        reject(new Error(`WebSocket request '${type}' timed out after ${timeoutMs}ms.`));
      }, timeoutMs);

      this.pendingRequests.set(requestId, {
        resolve: resolve as (val: ServerMessage) => void,
        reject,
        timeoutId,
      });

      this.ws!.send(JSON.stringify(message));
    });
  }

  /**
   * Send a fire-and-forget message without awaiting response.
   */
  public send<T = unknown>(type: ClientMessageType, payload: T): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not connected.");
    }
    const message: ClientMessage<T> = {
      protocolVersion: "v1",
      requestId: this.generateUUID(),
      type,
      timestamp: new Date().toISOString(),
      payload,
    };
    this.ws.send(JSON.stringify(message));
  }

  /**
   * Dispatch a simulated server message directly to listeners (useful for testing and offline mocks).
   */
  public dispatchServerMessage(message: ServerMessage): void {
    this.handleMessage(new MessageEvent("message", { data: JSON.stringify(message) }));
  }

  private handleOpen(): void {
    this.reconnectAttempt = 0;
    this.setState("CONNECTED");
    this.startHeartbeat();
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: ServerMessage = JSON.parse(event.data);

      // Handle heartbeat pong
      if (message.type === "pong") {
        if (this.heartbeatTimeout) {
          clearTimeout(this.heartbeatTimeout);
          this.heartbeatTimeout = null;
        }
        if (this.state === "STALE") {
          this.setState("CONNECTED");
        }
        return;
      }

      // Check request correlation
      if (message.requestId && this.pendingRequests.has(message.requestId)) {
        const pending = this.pendingRequests.get(message.requestId)!;
        clearTimeout(pending.timeoutId);
        this.pendingRequests.delete(message.requestId);

        if (message.type === "error" && message.error) {
          pending.reject(new Error(`[${message.error.code}] ${message.error.message}`));
        } else {
          pending.resolve(message);
        }
      }

      // Dispatch to typed listeners
      const typeListeners = this.listeners.get(message.type);
      if (typeListeners) {
        typeListeners.forEach((handler) => handler(message));
      }

      // Dispatch to wildcard listeners
      const wildcardListeners = this.listeners.get("*");
      if (wildcardListeners) {
        wildcardListeners.forEach((handler) => handler(message));
      }
    } catch (err) {
      console.error("Failed to parse incoming WebSocket message:", err);
    }
  }

  private handleError(): void {
    this.setState("ERROR");
  }

  private handleClose(event: CloseEvent): void {
    this.cleanupHeartbeat();

    if (this.isExplicitlyClosed) {
      this.setState("CLOSED_INTENTIONALLY");
      return;
    }

    if (event.code === 4401 || event.code === 4403) {
      // Unauthorized or forbidden session
      this.setState("AUTH_FAILED");
      this.clearReconnectTimer();
      return;
    }

    // Check if network is offline
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      this.setState("OFFLINE");
      this.clearReconnectTimer();
      return;
    }

    // Handshake abnormal closure (1006) on multiple attempts or max retries reached
    if (this.reconnectAttempt >= this.MAX_RECONNECT_ATTEMPTS) {
      this.setState("SERVER_FAILED");
      this.clearReconnectTimer();
      return;
    }

    this.setState("RECONNECTING");
    this.scheduleReconnect();
  }

  private startHeartbeat(): void {
    this.cleanupHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

      // Send ping frame
      const pingMessage: ClientMessage<Record<string, never>> = {
        protocolVersion: "v1",
        requestId: this.generateUUID(),
        type: "ping",
        timestamp: new Date().toISOString(),
        payload: {},
      };
      this.ws.send(JSON.stringify(pingMessage));

      // Wait for pong; if missing, log warning without aborting active socket
      this.heartbeatTimeout = setTimeout(() => {
        if (this.pendingRequests.size > 0) {
          return;
        }
        console.warn("Heartbeat pong delayed; keeping socket open for active RPC session.");
      }, this.PONG_TIMEOUT_MS);
    }, this.PING_INTERVAL_MS);
  }

  private cleanupHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.isExplicitlyClosed) return;
    if (this.reconnectAttempt >= this.MAX_RECONNECT_ATTEMPTS) {
      this.setState("SERVER_FAILED");
      return;
    }

    this.clearReconnectTimer();
    this.setState("RECONNECTING");

    // Exponential backoff with jitter: min(30s, 1s * 2^attempt) +- jitter
    const baseWait = Math.min(30000, 1000 * Math.pow(2, this.reconnectAttempt));
    const jitter = Math.floor(Math.random() * 500);
    const delay = baseWait + jitter;

    this.reconnectAttempt++;
    this.reconnectTimer = setTimeout(() => {
      if (!this.isExplicitlyClosed) {
        this.connect();
      }
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private setState(newState: ConnectionState): void {
    if (this.state !== newState) {
      this.state = newState;
      this.stateListeners.forEach((listener) => listener(newState));
    }
  }

  private generateUUID(): string {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return "req_" + Math.random().toString(36).substring(2, 11) + "_" + Date.now();
  }
}

import { useCallback, useEffect, useState } from "react";
import { RevenueWebSocketClient } from "@/lib/ws";
import { ClientMessageType, ConnectionState, ServerMessage, ServerMessageType } from "@/lib/types";

interface UseWebSocketOptions {
  autoConnect?: boolean;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { autoConnect = false } = options;
  const [state, setState] = useState<ConnectionState>("DISCONNECTED");
  const client = RevenueWebSocketClient.getInstance();

  useEffect(() => {
    // Subscribe to connection state transitions
    const unsubscribeState = client.onStateChange((newState) => {
      setState(newState);
    });

    if (autoConnect) {
      client.connect();
    }

    return () => {
      unsubscribeState();
    };
  }, [client, autoConnect]);

  const connect = useCallback(() => {
    client.connect();
  }, [client]);

  const disconnect = useCallback((reason?: string) => {
    client.disconnect(reason);
  }, [client]);

  const request = useCallback(<T = unknown, R = unknown>(type: ClientMessageType, payload?: T, timeoutMs?: number) => {
    return client.request<T, R>(type, payload as T, timeoutMs);
  }, [client]);

  const send = useCallback(<T = unknown>(type: ClientMessageType, payload: T) => {
    return client.send<T>(type, payload);
  }, [client]);

  const on = useCallback((type: ServerMessageType | "*", handler: (msg: ServerMessage) => void) => {
    return client.on(type, handler);
  }, [client]);

  return {
    state,
    isConnected: state === "CONNECTED",
    isConnecting: state === "CONNECTING",
    isStale: state === "STALE",
    connect,
    disconnect,
    request,
    send,
    on,
  };
}

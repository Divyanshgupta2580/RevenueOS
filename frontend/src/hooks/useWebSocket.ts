"use client";

import { useEffect, useState } from "react";
import { RevenueWebSocketClient } from "@/lib/ws";
import { ConnectionState, ServerMessage, ServerMessageType } from "@/lib/types";

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

  const on = (type: ServerMessageType | "*", handler: (msg: ServerMessage) => void) => {
    return client.on(type, handler);
  };

  return {
    state,
    isConnected: state === "CONNECTED",
    isConnecting: state === "CONNECTING",
    isStale: state === "STALE",
    connect: client.connect.bind(client),
    disconnect: client.disconnect.bind(client),
    request: client.request.bind(client),
    send: client.send.bind(client),
    on,
  };
}

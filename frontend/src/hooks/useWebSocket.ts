"use client";

import { useEffect, useState } from "react";
import { RevenueWebSocketClient } from "@/lib/ws";
import { ConnectionState, ServerMessage, ServerMessageType } from "@/lib/types";

export function useWebSocket() {
  const [state, setState] = useState<ConnectionState>("DISCONNECTED");
  const client = RevenueWebSocketClient.getInstance();

  useEffect(() => {
    // Subscribe to connection state transitions
    const unsubscribeState = client.onStateChange((newState) => {
      setState(newState);
    });

    // Auto-connect on client mount
    client.connect();

    return () => {
      unsubscribeState();
    };
  }, [client]);

  const on = (type: ServerMessageType | "*", handler: (msg: ServerMessage) => void) => {
    return client.on(type, handler);
  };

  return {
    state,
    isConnected: state === "CONNECTED",
    isConnecting: state === "CONNECTING",
    isStale: state === "STALE",
    request: client.request.bind(client),
    send: client.send.bind(client),
    on,
  };
}

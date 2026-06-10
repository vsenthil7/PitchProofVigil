import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { LiveEvent } from "../lib/types";

// Subscribes to the backend WebSocket and accumulates live events. Auto-
// reconnects with a short backoff so a backend restart doesn't kill the feed.
export function useLiveFeed(maxItems = 50) {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let closedByUs = false;

    const connect = () => {
      const ws = new WebSocket(api.liveSocketUrl());
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closedByUs) {
          retryRef.current = setTimeout(connect, 1500);
        }
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (msg) => {
        try {
          const event = JSON.parse(msg.data) as LiveEvent;
          setEvents((prev) => [event, ...prev].slice(0, maxItems));
        } catch {
          // ignore malformed frames
        }
      };
    };

    connect();
    return () => {
      closedByUs = true;
      if (retryRef.current) clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, [maxItems]);

  return { events, connected };
}

import { useEffect, useRef, useCallback, useState } from 'react';
import type { AgentEvent } from './types';

function resolveWebSocketUrl(url: string): string {
  if (/^wss?:\/\//i.test(url)) return url;
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${url.startsWith('/') ? url : `/${url}`}`;
}

export function useWebSocket(url: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const shouldReconnectRef = useRef(true);
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastMessageAt, setLastMessageAt] = useState<number | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const eventsRef = useRef<AgentEvent[]>([]);

  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const ws = new WebSocket(resolveWebSocketUrl(url));
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setLastError(null);
      reconnectAttemptRef.current = 0;
      setReconnectAttempts(0);
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    ws.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data) as AgentEvent;
        eventsRef.current = [...eventsRef.current.slice(-199), event];
        setEvents(eventsRef.current);
        setLastMessageAt(Date.now());
      } catch {
        setLastError('WebSocket message parse failed');
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      setConnected(false);
      if (!shouldReconnectRef.current) return;

      const attempt = reconnectAttemptRef.current;
      const delayMs = Math.min(1000 * 2 ** attempt, 10_000);
      reconnectAttemptRef.current += 1;
      setReconnectAttempts(reconnectAttemptRef.current);
      reconnectTimerRef.current = setTimeout(connect, delayMs);
    };

    ws.onerror = () => {
      setLastError('WebSocket connection error');
      ws.close();
    };
  }, [url]);

  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();

    return () => {
      shouldReconnectRef.current = false;
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current = null;
      reconnectTimerRef.current = null;
    };
  }, [connect]);

  return {
    connected,
    events,
    clearEvents: () => { eventsRef.current = []; setEvents([]); },
    diagnostics: {
      url: resolveWebSocketUrl(url),
      lastError,
      lastMessageAt,
      reconnectAttempts,
    },
  };
}

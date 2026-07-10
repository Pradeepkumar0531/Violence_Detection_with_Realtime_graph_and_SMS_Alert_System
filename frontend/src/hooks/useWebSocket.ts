import { useState, useRef, useCallback } from 'react';

export interface DetectionResult {
  timestamp: number;
  score: number;
  raw_score?: number;
  is_violence: boolean;
  scores_above_threshold?: number;
  type?: string;
  event?: string;
}

interface UseWebSocketReturn {
  bufferRef: React.MutableRefObject<DetectionResult[]>;
  latestResult: DetectionResult | null;
  isViolence: boolean;
  connected: boolean;
  status: any;
  clearBuffer: () => void;
  connect: () => void;
  disconnect: () => void;
}

const WS_URL = `ws://${window.location.hostname}:8000/ws/stream`;

export function useWebSocket(): UseWebSocketReturn {
  const bufferRef = useRef<DetectionResult[]>([]);
  const [latestResult, setLatestResult] = useState<DetectionResult | null>(null);
  const [isViolence, setIsViolence] = useState(false);
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<any>(null);

  const wsRef = useRef<WebSocket | null>(null);

  const clearBuffer = useCallback(() => {
    bufferRef.current = [];
    setLatestResult(null);
    setIsViolence(false);
    setStatus(null);
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current) return;
    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WS] Connected to backend');
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Handle status/keepalive messages — don't buffer these
          if (data.type === 'status') {
            setStatus(data);
            return;
          }
          if (data.type === 'keepalive' || data.type === 'pong') return;
          if (data.score === undefined) return;

          const result: DetectionResult = data;

          // Push every prediction to the graph buffer
          bufferRef.current.push(result);

          // Use backend's is_violence as single source of truth
          // This only fires when the smoothed score crosses the threshold
          setLatestResult(result);
          setIsViolence(result.is_violence);

          if (result.is_violence) {
            console.log('🚨 VIOLENCE DETECTED — score:', result.score);
          }
        } catch (err) {
          console.error('[WS] Failed to parse message:', err);
        }
      };

      ws.onclose = () => {
        console.log('[WS] Disconnected');
        setConnected(false);
        wsRef.current = null;
      };

      ws.onerror = (error) => {
        console.error('[WS] Error:', error);
      };
    } catch (err) {
      console.error('[WS] Failed to create WebSocket:', err);
    }
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  return { bufferRef, latestResult, isViolence, connected, status, clearBuffer, connect, disconnect };
}

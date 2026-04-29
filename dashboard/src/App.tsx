import { useState, useEffect } from 'react';
import StrategyPanel from './StrategyPanel';
import { useWebSocket } from './useWebSocket';
import type { StrategyName, HealthResponse, AgentEvent } from './types';
import { STRATEGY_CONFIG } from './types';

const STRATEGIES: StrategyName[] = ['thrive', 'swift', 'echo', 'bridge', 'flow', 'clarity', 'nurture', 'insight'];
const WS_URL = 'ws://localhost:8989/ws';
const API_BASE = 'http://localhost:8989';

function groupEventsByStrategy(events: AgentEvent[]): Record<string, AgentEvent[]> {
  const grouped: Record<string, AgentEvent[]> = {};
  for (const e of events) {
    if (!grouped[e.strategy]) grouped[e.strategy] = [];
    grouped[e.strategy].push(e);
  }
  return grouped;
}

export default function App() {
  const { connected, events, clearEvents } = useWebSocket(WS_URL);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [showVerbose, setShowVerbose] = useState(false);
  const [initialEvents, setInitialEvents] = useState<AgentEvent[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/strategies`)
      .then(r => r.json())
      .then(setHealth)
      .catch(() => {});
    fetch(`${API_BASE}/events?limit=50`)
      .then(r => r.json())
      .then(setInitialEvents)
      .catch(() => {});
  }, []);

  const allEvents = [...initialEvents, ...events];
  const grouped = groupEventsByStrategy(allEvents);

  const runningCount = health?.strategies.filter(s => s.state === 'running').length ?? 0;
  const statusLookup: Record<string, string> = {};
  if (health) {
    for (const s of health.strategies) {
      statusLookup[s.name] = s.state;
    }
  }

  return (
    <div className="app">
      <header className="top-bar">
        <div className="top-left">
          <h1>🧠 MemTune · AST Dashboard</h1>
          <span className={`conn-badge ${connected ? 'connected' : 'disconnected'}`}>
            {connected ? '● Connected' : '○ Reconnecting...'}
          </span>
        </div>
        <div className="top-center">
          <span className="stat">Balance: <strong>$10,000</strong></span>
          <span className="stat">P&L: <strong style={{ color: '#44dd66' }}>$0.00</strong></span>
          <span className="stat">Active: <strong>{runningCount}/8</strong></span>
          {health && <span className="stat">Uptime: {health.uptime_seconds}s</span>}
        </div>
        <div className="top-right">
          <button onClick={() => clearEvents()}>🗑️ Clear</button>
          <button onClick={() => setShowVerbose(!showVerbose)}>
            {showVerbose ? '📋 Hide Log' : '📋 JSON Log'}
          </button>
          <label className="auto-scroll-toggle">
            <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} />
            Auto-scroll
          </label>
        </div>
      </header>

      <main className="grid">
        {STRATEGIES.map(name => (
          <StrategyPanel
            key={name}
            name={name}
            events={grouped[name] || []}
            status={statusLookup[name] || 'stopped'}
          />
        ))}
      </main>

      {showVerbose && (
        <div className="verbose-panel">
          <div className="verbose-header">📋 Raw Event Log ({allEvents.length} events)</div>
          <pre className="verbose-content">
            {allEvents.length === 0
              ? 'No events yet...'
              : allEvents.map((e, i) => JSON.stringify(e, null, 2)).join('\n---\n')}
          </pre>
        </div>
      )}
    </div>
  );
}

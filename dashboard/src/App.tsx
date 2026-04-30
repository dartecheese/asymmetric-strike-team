import { useState, useEffect, useMemo } from 'react';
import StrategyPanel from './StrategyPanel';
import { useWebSocket } from './useWebSocket';
import type {
  StrategyName,
  HealthResponse,
  AgentEvent,
  StrategyCapabilities,
  PortfolioResponse,
  OperatorResponse,
  StrategyViewResponse,
  StrategyControlAction,
} from './types';
import { STRATEGY_CONFIG } from './types';

const STRATEGIES: StrategyName[] = ['thrive', 'swift', 'echo', 'bridge', 'flow', 'clarity', 'nurture', 'insight'];
const WS_URL = '/ws';
const API_BASE = '/api';

type ViewMode = 'dashboard' | 'troubleshooting';
type FetchStatus = 'idle' | 'ok' | 'error';

interface EndpointDiagnostic {
  name: string;
  status: FetchStatus;
  lastOkAt: number | null;
  lastError: string | null;
}

function fmtUsd(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value);
}

function fmtTime(ts: number | null): string {
  if (!ts) return '—';
  return new Date(ts).toLocaleTimeString();
}

function groupEventsByStrategy(events: AgentEvent[]): Record<string, AgentEvent[]> {
  const grouped: Record<string, AgentEvent[]> = {};
  for (const e of events) {
    if (!grouped[e.strategy]) grouped[e.strategy] = [];
    grouped[e.strategy].push(e);
  }
  return grouped;
}

function strategyEventCount(events: AgentEvent[], strategy: string): number {
  return events.filter((event) => event.strategy === strategy).length;
}

function initEndpointDiagnostics(): Record<string, EndpointDiagnostic> {
  return {
    health: { name: 'health', status: 'idle', lastOkAt: null, lastError: null },
    portfolio: { name: 'portfolio', status: 'idle', lastOkAt: null, lastError: null },
    strategies: { name: 'strategies', status: 'idle', lastOkAt: null, lastError: null },
    events: { name: 'events', status: 'idle', lastOkAt: null, lastError: null },
    capabilities: { name: 'capabilities', status: 'idle', lastOkAt: null, lastError: null },
    operator: { name: 'operator', status: 'idle', lastOkAt: null, lastError: null },
  };
}

export default function App() {
  const { connected, events, clearEvents, diagnostics: wsDiagnostics } = useWebSocket(WS_URL);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [showVerbose, setShowVerbose] = useState(false);
  const [initialEvents, setInitialEvents] = useState<AgentEvent[]>([]);
  const [capabilities, setCapabilities] = useState<StrategyCapabilities[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [operator, setOperator] = useState<OperatorResponse | null>(null);
  const [strategies, setStrategies] = useState<StrategyViewResponse[]>([]);
  const [selectedStrategies, setSelectedStrategies] = useState<StrategyName[]>([...STRATEGIES]);
  const [viewMode, setViewMode] = useState<ViewMode>('dashboard');
  const [endpointDiagnostics, setEndpointDiagnostics] = useState<Record<string, EndpointDiagnostic>>(initEndpointDiagnostics());
  const [copiedTroubleshooting, setCopiedTroubleshooting] = useState(false);

  const trackedFetch = async <T,>(name: keyof ReturnType<typeof initEndpointDiagnostics>, path: string): Promise<T | null> => {
    try {
      const response = await fetch(`${API_BASE}${path}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json() as T;
      setEndpointDiagnostics((current) => ({
        ...current,
        [name]: { ...current[name], status: 'ok', lastOkAt: Date.now(), lastError: null },
      }));
      return payload;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown fetch error';
      setEndpointDiagnostics((current) => ({
        ...current,
        [name]: { ...current[name], status: 'error', lastError: message },
      }));
      return null;
    }
  };

  const loadHealth = async () => {
    const payload = await trackedFetch<HealthResponse>('health', '/health');
    if (payload) setHealth(payload);
  };
  const loadPortfolio = async () => {
    const payload = await trackedFetch<PortfolioResponse>('portfolio', '/portfolio');
    if (payload) setPortfolio(payload);
  };
  const loadStrategies = async () => {
    const payload = await trackedFetch<StrategyViewResponse[]>('strategies', '/strategies');
    if (payload) setStrategies(payload);
  };
  const loadEvents = async () => {
    const payload = await trackedFetch<AgentEvent[]>('events', '/events');
    if (payload) setInitialEvents(payload);
  };
  const loadCapabilities = async () => {
    const payload = await trackedFetch<StrategyCapabilities[]>('capabilities', '/capabilities');
    if (payload) setCapabilities(payload);
  };
  const loadOperator = async () => {
    const payload = await trackedFetch<OperatorResponse>('operator', '/operator');
    if (payload) setOperator(payload);
  };

  useEffect(() => {
    loadHealth();
    loadEvents();
    loadCapabilities();
    loadOperator();
    loadStrategies();
    loadPortfolio();

    const interval = window.setInterval(() => {
      loadHealth();
      loadStrategies();
      loadPortfolio();
    }, 5000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (events.length === 0) return;
    loadHealth();
    loadStrategies();
    loadPortfolio();
  }, [events]);

  const handleControl = async (strategy: StrategyName, action: StrategyControlAction) => {
    try {
      await fetch(`${API_BASE}/strategies/${strategy}/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
    } catch {
      setViewMode('troubleshooting');
    }
    loadHealth();
    loadStrategies();
  };

  const toggleStrategy = (strategy: StrategyName) => {
    setSelectedStrategies((current) => {
      const has = current.includes(strategy);
      if (has) {
        const next = current.filter((item) => item !== strategy);
        return next.length === 0 ? [...STRATEGIES] : next;
      }
      return [...current, strategy];
    });
  };

  const selectAllStrategies = () => setSelectedStrategies([...STRATEGIES]);

  const allEvents = useMemo(() => [...initialEvents, ...events], [initialEvents, events]);
  const grouped = useMemo(() => groupEventsByStrategy(allEvents), [allEvents]);

  const runningCount = health?.strategies.filter(s => s.state === 'running').length ?? 0;
  const capabilitiesLookup: Record<string, StrategyCapabilities> = {};
  for (const entry of capabilities) capabilitiesLookup[entry.strategy] = entry;
  const statusLookup: Record<string, HealthResponse['strategies'][number]> = {};
  if (health) {
    for (const s of health.strategies) statusLookup[s.name] = s;
  }
  const strategyLookup: Record<string, StrategyViewResponse> = {};
  for (const strategy of strategies) strategyLookup[strategy.profile.name] = strategy;

  const visibleStrategies = selectedStrategies.length === STRATEGIES.length
    ? STRATEGIES
    : STRATEGIES.filter((name) => selectedStrategies.includes(name));

  const totalPnl = (portfolio?.realized_pnl_usd ?? 0) + (portfolio?.unrealized_pnl_usd ?? 0);
  const recentErrorEvents = allEvents.filter((event) => event.action === 'error').slice(-20).reverse();
  const pausedOrStopped = (health?.strategies ?? []).filter((s) => s.control_state === 'paused' || s.control_state === 'stopped');

  const copyTroubleshootingReport = async () => {
    const lines = [
      'AST Troubleshooting Report',
      `Generated: ${new Date().toISOString()}`,
      `WebSocket connected: ${connected}`,
      `WebSocket url: ${wsDiagnostics.url}`,
      `WebSocket last message: ${fmtTime(wsDiagnostics.lastMessageAt)}`,
      `WebSocket reconnect attempts: ${wsDiagnostics.reconnectAttempts}`,
      `WebSocket last error: ${wsDiagnostics.lastError || 'none'}`,
      '',
      'API diagnostics:',
      ...Object.values(endpointDiagnostics).map((diag) => (
        `- /${diag.name}: status=${diag.status}, last_ok=${fmtTime(diag.lastOkAt)}, error=${diag.lastError || 'none'}`
      )),
      '',
      'Paused/stopped teams:',
      ...(pausedOrStopped.length === 0
        ? ['- none']
        : pausedOrStopped.map((status) => `- ${status.name}: ${status.control_state}`)),
      '',
      'Recent error events:',
      ...(recentErrorEvents.length === 0
        ? ['- none']
        : recentErrorEvents.map((event) => `- ${new Date(event.timestamp).toLocaleTimeString()} ${event.strategy}: ${event.summary}`)),
    ];

    await navigator.clipboard.writeText(lines.join('\n'));
    setCopiedTroubleshooting(true);
    window.setTimeout(() => setCopiedTroubleshooting(false), 2000);
  };

  return (
    <div className="app">
      <header className="top-bar">
        <div className="top-left">
          <h1>🧠 MemTune · AST Dashboard</h1>
          <span className={`conn-badge ${connected ? 'connected' : 'disconnected'}`}>
            {connected ? '● Connected' : '○ Reconnecting...'}
          </span>
          {operator && (
            <span className={`mode-badge ${operator.effective_mode === 'paper' ? 'paper' : 'guarded'}`}>
              {operator.effective_mode === 'paper' ? 'Paper trading' : 'Live guarded'}
            </span>
          )}
        </div>
        <div className="top-center">
          <span className="stat">Cash: <strong>{portfolio ? fmtUsd(portfolio.cash_balance_usd) : '—'}</strong></span>
          <span className="stat">Equity: <strong>{portfolio ? fmtUsd(portfolio.equity_usd) : '—'}</strong></span>
          <span className="stat">P&L: <strong style={{ color: totalPnl >= 0 ? '#44dd66' : '#ff6666' }}>{portfolio ? fmtUsd(totalPnl) : '—'}</strong></span>
          <span className="stat">Invested: <strong>{portfolio ? fmtUsd(portfolio.invested_usd) : '—'}</strong></span>
          <span className="stat">Holdings: <strong>{portfolio?.open_positions ?? 0}</strong></span>
          <span className="stat">Active: <strong>{runningCount}/{STRATEGIES.length}</strong></span>
          <span className="stat">Events: <strong>{allEvents.length}</strong></span>
          {health && <span className="stat">Uptime: {health.uptime_seconds}s</span>}
        </div>
        <div className="top-right">
          <button onClick={() => setViewMode('dashboard')} className={viewMode === 'dashboard' ? 'nav-active' : ''}>📊 Dashboard</button>
          <button onClick={() => setViewMode('troubleshooting')} className={viewMode === 'troubleshooting' ? 'nav-active' : ''}>🛠 Troubleshooting</button>
          <button onClick={() => clearEvents()}>🗑️ Clear Stream</button>
          <button onClick={() => setShowVerbose(!showVerbose)}>
            {showVerbose ? '📋 Hide Log' : '📋 JSON Log'}
          </button>
          <label className="auto-scroll-toggle">
            <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} />
            Auto-scroll
          </label>
        </div>
      </header>

      {viewMode === 'dashboard' ? (
        <>
          <section className="control-deck">
            <div className="control-card operator-card">
              <div className="card-kicker">Operator mode</div>
              <div className="operator-row">
                <div>
                  <div className="operator-title">{operator?.selected_mode === 'live' ? 'Live requested' : 'Paper ready'}</div>
                  <div className="operator-subtitle">Effective runtime: <strong>{operator?.effective_mode ?? 'loading'}</strong></div>
                </div>
                <div className={`readiness-pill ${operator?.live_execution_ready ? 'ready' : 'blocked'}`}>
                  {operator?.live_execution_ready ? 'Live ready' : 'Live blocked'}
                </div>
              </div>
              <div className="warning-stack">
                {(operator?.warnings ?? ['Loading operator guidance...']).map((warning) => (
                  <div key={warning} className="warning-item">{warning}</div>
                ))}
              </div>
            </div>

            <div className="control-card quick-actions-card">
              <div className="card-kicker">Quick start menu</div>
              <div className="quick-actions-list">
                {(operator?.quick_actions ?? []).map((action) => (
                  <div key={action.label} className="quick-action-item">
                    <div className="quick-action-top">
                      <strong>{action.label}</strong>
                      <span className={`readiness-pill ${action.availability === 'ready' ? 'ready' : 'blocked'}`}>{action.availability}</span>
                    </div>
                    <div className="quick-action-summary">{action.summary}</div>
                    <code className="command-chip">{action.command}</code>
                  </div>
                ))}
              </div>
            </div>

            <div className="control-card session-card">
              <div className="card-kicker">Viewer controls</div>
              <div className="session-grid">
                <div>
                  <div className="session-label">Visible teams</div>
                  <code className="command-chip">{visibleStrategies.join(', ')}</code>
                </div>
                <div>
                  <div className="session-label">State dir</div>
                  <code className="command-chip">{operator?.state_dir ?? 'data'}</code>
                </div>
              </div>
              <button className="select-all-button" onClick={selectAllStrategies}>Show all teams</button>
            </div>
          </section>

          <section className="strategy-menu">
            {STRATEGIES.map((name) => {
              const profile = strategyLookup[name]?.profile;
              const selected = selectedStrategies.includes(name);
              const status = statusLookup[name];
              return (
                <button key={name} className={`strategy-menu-item ${selected ? 'selected' : ''}`} onClick={() => toggleStrategy(name)} title={STRATEGY_CONFIG[name].help}>
                  <span>{name}</span>
                  <span className="strategy-menu-meta">
                    {(status?.control_state || status?.state || 'unknown')} · {strategyEventCount(allEvents, name)} ev · {profile?.max_position_size_usd ? fmtUsd(profile.max_position_size_usd) : '—'}
                  </span>
                </button>
              );
            })}
          </section>

          <main className="grid">
            {visibleStrategies.map(name => (
              <StrategyPanel
                key={name}
                name={name}
                events={grouped[name] || []}
                status={(statusLookup[name]?.state ?? 'stopped') as any}
                controlState={(statusLookup[name]?.control_state ?? statusLookup[name]?.state ?? 'stopped') as any}
                autoScroll={autoScroll}
                capabilities={capabilitiesLookup[name]?.capabilities || []}
                holdings={portfolio?.holdings.filter((holding) => holding.strategy === name) || []}
                onControl={handleControl}
              />
            ))}
          </main>
        </>
      ) : (
        <main className="troubleshooting-page">
          <section className="control-card troubleshooting-card">
            <div className="card-kicker">Connection diagnostics</div>
            <div className="troubleshooting-actions">
              <button onClick={() => void copyTroubleshootingReport()}>
                {copiedTroubleshooting ? '✅ Copied' : '📋 Copy troubleshooting log'}
              </button>
            </div>
            <div className="diag-grid">
              <div className="diag-item">
                <strong>WebSocket</strong>
                <span>{connected ? 'Connected' : 'Disconnected / reconnecting'}</span>
                <span>URL: <code>{wsDiagnostics.url}</code></span>
                <span>Last message: {fmtTime(wsDiagnostics.lastMessageAt)}</span>
                <span>Reconnect attempts: {wsDiagnostics.reconnectAttempts}</span>
                <span className="diag-error">{wsDiagnostics.lastError || 'No websocket error'}</span>
              </div>
              {Object.values(endpointDiagnostics).map((diag) => (
                <div key={diag.name} className="diag-item">
                  <strong>API /{diag.name}</strong>
                  <span>Status: {diag.status}</span>
                  <span>Last success: {fmtTime(diag.lastOkAt)}</span>
                  <span className="diag-error">{diag.lastError || 'No fetch error'}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="control-card troubleshooting-card">
            <div className="card-kicker">Operational blockers</div>
            {pausedOrStopped.length === 0 ? (
              <div className="holdings-empty">No teams are paused or stopped.</div>
            ) : (
              <div className="warning-stack">
                {pausedOrStopped.map((status) => (
                  <div key={status.name} className="warning-item">
                    {status.name} is {status.control_state}. Use the team controls to resume it.
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="control-card troubleshooting-card">
            <div className="card-kicker">Recent error log</div>
            {recentErrorEvents.length === 0 ? (
              <div className="holdings-empty">No recent error events.</div>
            ) : (
              <div className="trouble-log-list">
                {recentErrorEvents.map((event, index) => (
                  <div key={`${event.timestamp}-${index}`} className="trouble-log-item">
                    <div><strong>{event.strategy}</strong> · {new Date(event.timestamp).toLocaleTimeString()}</div>
                    <div>{event.summary}</div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </main>
      )}

      {showVerbose && (
        <div className="verbose-panel">
          <div className="verbose-header">📋 Raw Event Log ({allEvents.length} events)</div>
          <pre className="verbose-content">
            {allEvents.length === 0 ? 'No events yet...' : allEvents.map((e) => JSON.stringify(e, null, 2)).join('\n---\n')}
          </pre>
        </div>
      )}
    </div>
  );
}

import { useMemo, useRef, useEffect, useState } from 'react';
import type { AgentEvent, StrategyName, AgentType, AgentCapability, HoldingView, StrategyControlAction, StrategyState } from './types';
import { STRATEGY_CONFIG, AGENT_LABELS, AGENT_COLORS, AGENT_HELP } from './types';

interface Props {
  name: StrategyName;
  events: AgentEvent[];
  status: StrategyState;
  controlState: StrategyState;
  autoScroll: boolean;
  capabilities: AgentCapability[];
  holdings: HoldingView[];
  onControl: (strategy: StrategyName, action: StrategyControlAction) => void;
}

type SourceTone = 'live' | 'fallback' | 'mixed' | 'neutral';
type TeamTab = 'portfolio' | 'logs';

interface AggregatedHolding {
  key: string;
  token_symbol: string;
  chain: string;
  quantity: number;
  avg_cost_usd: number;
  total_cost_usd: number;
  market_value_usd: number;
  unrealized_pnl_usd: number;
  realized_pnl_usd: number;
  states: string[];
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString();
}

function getData(event: AgentEvent): Record<string, unknown> {
  return (event.data as Record<string, unknown> | undefined) ?? {};
}

function eventExplanation(event: AgentEvent): string | null {
  const d = getData(event);
  const explanation = d.explanation;
  return typeof explanation === 'string' && explanation.length > 0 ? explanation : null;
}

function plainAgentLabel(agent: AgentType): string {
  return (AGENT_LABELS[agent] || agent).split(' ')[0];
}

function agentDeclaration(event: AgentEvent): string | null {
  const explanation = eventExplanation(event);
  if (!explanation) return null;
  return `${plainAgentLabel(event.agent as AgentType)} declares: ${explanation}`;
}

function eventSummary(event: AgentEvent): string {
  if (event.summary) return event.summary;
  const d = getData(event);
  if (event.action === 'signal_discovered') return `Signal: ${String(d.token_symbol || d.signal_type || 'N/A')} @ $${String(d.price_usd || '?')}`;
  if (event.action === 'risk_assessed') return `Risk: ${String(d.score || '?')}/100 — ${d.acceptable ? '✅ pass' : '❌ block'}`;
  if (event.action === 'order_constructed') return `Order: ${String(d.side || '?')} ${String(d.size || '?')} @ $${String(d.price || '?')}`;
  if (event.action === 'order_filled') return `Filled: ${String(d.filled_amount || '?')} @ $${String(d.fill_price || '?')}`;
  if (event.action === 'position_updated') return `Position: ${String(d.state || 'active')} · PnL $${String(d.realized_pnl_usd || '?')}`;
  if (event.action === 'intent_reflected') return `Reflection: ${d.matched_intent ? '✅ matched' : '❌ missed'} · score ${String(d.score || '?')}`;
  if (event.action === 'error') return `⚠️ ${String(d.message || '')}`;
  return event.action.replaceAll('_', ' ');
}

function sourceMeta(event: AgentEvent): { label: string; tone: SourceTone } | null {
  const d = getData(event);
  const source = String(d.source || '').toLowerCase();
  if (source === 'dexscreener') return { label: 'Live market', tone: 'live' };
  if (source === 'paper_mock') return { label: 'Fallback market', tone: 'fallback' };
  if (source) return { label: source, tone: 'neutral' };

  const summary = (event.summary || '').toLowerCase();
  if (summary.includes('live') && summary.includes('fallback')) return { label: 'Live + fallback ready', tone: 'mixed' };
  if (summary.includes('fallback')) return { label: 'Fallback path', tone: 'fallback' };
  if (summary.includes('live')) return { label: 'Live path', tone: 'live' };
  return null;
}

function actionTone(action: string): string {
  if (action === 'error') return 'error';
  if (action === 'signal_discovered') return 'signal';
  if (action === 'risk_assessed') return 'risk';
  if (action === 'order_constructed' || action === 'order_filled') return 'execution';
  if (action === 'position_updated') return 'position';
  if (action === 'intent_reflected') return 'risk';
  if (action === 'report_in') return 'report';
  return 'neutral';
}

function compactAction(action: string): string {
  return action.replaceAll('_', ' ');
}

function fmtUsd(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value);
}

function aggregateHoldings(holdings: HoldingView[]): AggregatedHolding[] {
  const aggregated = new Map<string, AggregatedHolding>();
  for (const holding of holdings) {
    const key = `${holding.chain}:${holding.token_symbol}`;
    const existing = aggregated.get(key);
    if (existing) {
      existing.quantity += holding.quantity;
      existing.total_cost_usd += holding.entry_notional_usd;
      existing.market_value_usd += holding.market_value_usd;
      existing.unrealized_pnl_usd += holding.unrealized_pnl_usd;
      existing.realized_pnl_usd += holding.realized_pnl_usd;
      if (!existing.states.includes(holding.state)) existing.states.push(holding.state);
      existing.avg_cost_usd = existing.quantity > 0 ? existing.total_cost_usd / existing.quantity : 0;
    } else {
      aggregated.set(key, {
        key,
        token_symbol: holding.token_symbol,
        chain: holding.chain,
        quantity: holding.quantity,
        avg_cost_usd: holding.quantity > 0 ? holding.entry_notional_usd / holding.quantity : 0,
        total_cost_usd: holding.entry_notional_usd,
        market_value_usd: holding.market_value_usd,
        unrealized_pnl_usd: holding.unrealized_pnl_usd,
        realized_pnl_usd: holding.realized_pnl_usd,
        states: [holding.state],
      });
    }
  }
  return [...aggregated.values()].sort((a, b) => b.market_value_usd - a.market_value_usd);
}

function statusLabel(state: StrategyState): string {
  switch (state) {
    case 'running': return '● Running';
    case 'paused': return '◐ Paused';
    case 'stopped': return '○ Stopped';
    case 'error': return '⚠ Error';
    case 'starting': return '… Starting';
    default: return '○ Unknown';
  }
}

export default function StrategyPanel({ name, events, status, controlState, autoScroll, capabilities, holdings, onControl }: Props) {
  const config = STRATEGY_CONFIG[name];
  const scrollRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<TeamTab>('portfolio');

  useEffect(() => {
    if (autoScroll && scrollRef.current && activeTab === 'logs') {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events, autoScroll, activeTab]);

  const latestByAgent = useMemo(() => {
    const latest: Partial<Record<AgentType, AgentEvent>> = {};
    for (const event of events) latest[event.agent] = event;
    return latest;
  }, [events]);

  const sourceBadges = useMemo(() => {
    const badges: Array<{ key: string; label: string; tone: SourceTone }> = [];
    const seen = new Set<string>();
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const meta = sourceMeta(events[i]);
      if (!meta) continue;
      const key = `${meta.label}-${meta.tone}`;
      if (seen.has(key)) continue;
      badges.push({ key, ...meta });
      seen.add(key);
      if (badges.length === 3) break;
    }
    return badges;
  }, [events]);

  const timeline = useMemo(() => events.slice(-12), [events]);
  const capabilityLookup = useMemo(() => {
    const next: Partial<Record<AgentType, AgentCapability>> = {};
    for (const capability of capabilities) next[capability.agent] = capability;
    return next;
  }, [capabilities]);
  const aggregatedHoldings = useMemo(() => aggregateHoldings(holdings), [holdings]);

  return (
    <section className="strategy-panel" style={{ borderLeftColor: config.color }}>
      <div className="panel-header">
        <span className="panel-emoji" title={config.help}>{config.emoji}</span>
        <span className="panel-name" title={config.help}>{config.label}</span>
        <span className={`panel-status ${status}`}>{statusLabel(status)}</span>
      </div>

      <div className="panel-controls">
        <button className={`team-action ${controlState === 'running' ? 'active' : ''}`} onClick={() => onControl(name, 'start')}>Start</button>
        <button className={`team-action ${controlState === 'paused' ? 'active' : ''}`} onClick={() => onControl(name, 'pause')}>Pause</button>
        <button className={`team-action ${controlState === 'stopped' ? 'active' : ''}`} onClick={() => onControl(name, 'stop')}>Stop</button>
      </div>

      <div className="panel-source-row">
        {sourceBadges.length === 0 ? (
          <span className="source-badge tone-neutral">Awaiting source signals</span>
        ) : sourceBadges.map((badge) => (
          <span key={badge.key} className={`source-badge tone-${badge.tone}`}>{badge.label}</span>
        ))}
      </div>

      <div className="agent-grid">
        {Object.entries(AGENT_LABELS).map(([agent, label]) => {
          const typedAgent = agent as AgentType;
          const latest = latestByAgent[typedAgent];
          return (
            <div key={agent} className="agent-card">
              <div className="agent-card-top">
                <span className="agent-dot" style={{ background: AGENT_COLORS[typedAgent] }} />
                <span className="agent-name" title={AGENT_HELP[typedAgent]}>{label}</span>
                <span className="agent-time">{latest ? formatTime(latest.timestamp) : '—'}</span>
              </div>
              <div className="agent-card-body">
                {latest ? (
                  <>
                    <span className={`mini-action tone-${actionTone(latest.action)}`}>{compactAction(latest.action)}</span>
                    <span className="agent-summary">{eventSummary(latest)}</span>
                    {agentDeclaration(latest) && <span className="agent-declaration">{agentDeclaration(latest)}</span>}
                  </>
                ) : (
                  <>
                    <span className="mini-action tone-report">ready</span>
                    <span className="agent-summary idle">{capabilityLookup[typedAgent]?.summary || 'No activity yet'}</span>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="team-tabs">
        <button className={`team-tab ${activeTab === 'portfolio' ? 'active' : ''}`} onClick={() => setActiveTab('portfolio')}>
          Portfolio {aggregatedHoldings.length > 0 ? `(${aggregatedHoldings.length})` : ''}
        </button>
        <button className={`team-tab ${activeTab === 'logs' ? 'active' : ''}`} onClick={() => setActiveTab('logs')}>
          Logs {timeline.length > 0 ? `(${timeline.length})` : ''}
        </button>
      </div>

      {activeTab === 'portfolio' ? (
        <div className="holdings-section">
          <div className="holdings-header">Trader holdings</div>
          {aggregatedHoldings.length === 0 ? (
            <div className="holdings-empty">No live holdings yet.</div>
          ) : (
            <div className="holdings-list">
              {aggregatedHoldings.slice(0, 6).map((holding) => (
                <div key={holding.key} className="holding-card">
                  <div className="holding-top">
                    <span className="holding-symbol">{holding.token_symbol}</span>
                    <span className={`mini-action tone-${holding.unrealized_pnl_usd >= 0 ? 'position' : 'error'}`}>{holding.states.join(' / ')}</span>
                  </div>
                  <div className="holding-meta">{holding.chain} · total qty {holding.quantity.toFixed(4)}</div>
                  <div className="holding-metrics">
                    <span>Total cost {fmtUsd(holding.total_cost_usd)}</span>
                    <span>Avg cost {fmtUsd(holding.avg_cost_usd)}</span>
                    <span>Value {fmtUsd(holding.market_value_usd)}</span>
                    <span style={{ color: holding.unrealized_pnl_usd >= 0 ? '#7ee787' : '#ff7b72' }}>U-PnL {fmtUsd(holding.unrealized_pnl_usd)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="timeline-header">Thought / action timeline</div>
          <div className="panel-log" ref={scrollRef}>
            {timeline.length === 0 && <div className="log-empty">Waiting for agent events...</div>}
            {timeline.map((event, i) => {
              const meta = sourceMeta(event);
              return (
                <div key={`${event.timestamp}-${event.agent}-${i}`} className="timeline-entry">
                  <div className="timeline-rail"><span className="timeline-dot" style={{ background: AGENT_COLORS[event.agent as AgentType] || '#888' }} /></div>
                  <div className="timeline-body">
                    <div className="timeline-meta">
                      <span className="log-time">{formatTime(event.timestamp)}</span>
                      <span className="log-agent" style={{ color: AGENT_COLORS[event.agent as AgentType] || '#888' }}>{AGENT_LABELS[event.agent as AgentType] || event.agent}</span>
                      <span className={`mini-action tone-${actionTone(event.action)}`}>{compactAction(event.action)}</span>
                      {meta && <span className={`source-badge small tone-${meta.tone}`}>{meta.label}</span>}
                    </div>
                    <div className="log-action">{eventSummary(event)}</div>
                    {agentDeclaration(event) && <div className="agent-declaration">{agentDeclaration(event)}</div>}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}

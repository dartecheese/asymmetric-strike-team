import { useRef, useEffect } from 'react';
import type { AgentEvent, StrategyName, AgentType } from './types';
import { STRATEGY_CONFIG, AGENT_LABELS, AGENT_COLORS } from './types';

interface Props {
  name: StrategyName;
  events: AgentEvent[];
  status: string;
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString();
}

function eventSummary(event: AgentEvent): string {
  const d = event.data as Record<string, unknown> | undefined;
  if (!d) return event.action;
  if (event.action === 'signal_discovered') return `Signal: ${d.signal_type as string || 'N/A'} @ $${String(d.price_usd || '?')}`;
  if (event.action === 'risk_assessed') return `Risk: ${String(d.score || '?')}/100 — ${d.acceptable ? '✅' : '❌'}`;
  if (event.action === 'order_constructed') return `Order: ${String(d.side || '?')} ${String(d.size || '?')} @ $${String(d.price || '?')}`;
  if (event.action === 'order_filled') return `Filled: ${String(d.filled_amount || '?')} @ $${String(d.fill_price || '?')}`;
  if (event.action === 'position_updated') return `Position: PnL $${String(d.unrealized_pnl_usd || '?')}`;
  if (event.action === 'error') return `⚠️ ${d.message as string || ''}`;
  return event.action;
}

export default function StrategyPanel({ name, events, status }: Props) {
  const config = STRATEGY_CONFIG[name];
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  const isRunning = status === 'running';

  return (
    <div className="strategy-panel" style={{ borderLeftColor: config.color }}>
      <div className="panel-header">
        <span className="panel-emoji">{config.emoji}</span>
        <span className="panel-name">{config.label}</span>
        <span className={`panel-status ${isRunning ? 'running' : 'stopped'}`}>
          {isRunning ? '●' : '○'}
        </span>
      </div>
      <div className="panel-log" ref={scrollRef}>
        {events.length === 0 && (
          <div className="log-empty">Waiting for agent events...</div>
        )}
        {events.map((event, i) => (
          <div key={i} className="log-entry">
            <span className="log-time">{formatTime(event.timestamp)}</span>
            <span className="log-agent" style={{ color: AGENT_COLORS[event.agent as AgentType] || '#888' }}>
              [{AGENT_LABELS[event.agent as AgentType] || event.agent}]
            </span>
            <span className="log-action">{eventSummary(event)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

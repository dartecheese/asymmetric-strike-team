export type AgentType = 'whisperer' | 'actuary' | 'slinger' | 'reaper';
export type StrategyName = 'thrive' | 'swift' | 'echo' | 'bridge' | 'flow' | 'clarity' | 'nurture' | 'insight';
export type StrategyState = 'running' | 'stopped' | 'error';

export interface StrategyInfo {
  name: StrategyName;
  state: StrategyState;
  last_event_timestamp: number;
  description?: string;
  max_position_size_usd?: number;
  max_slippage_bps?: number;
  scan_interval_seconds?: number;
}

export interface AgentEvent {
  strategy: StrategyName;
  agent: AgentType;
  action: string;
  data: unknown;
  timestamp: number;
}

export interface StrategyStatus {
  name: StrategyName;
  state: StrategyState;
  last_update: number;
  last_event_timestamp: number;
}

export interface HealthResponse {
  status: string;
  uptime_seconds: number;
  active_strategies: number;
  strategies: StrategyStatus[];
}

export const STRATEGY_CONFIG: Record<StrategyName, { emoji: string; color: string; label: string }> = {
  thrive:  { emoji: '🚀', color: '#ff4444', label: 'Thrive' },
  swift:   { emoji: '⚡', color: '#ffdd44', label: 'Swift' },
  echo:    { emoji: '🔮', color: '#aa66ff', label: 'Echo' },
  bridge:  { emoji: '🌉', color: '#4488ff', label: 'Bridge' },
  flow:    { emoji: '🌊', color: '#44ddbb', label: 'Flow' },
  clarity: { emoji: '👁️', color: '#8899aa', label: 'Clarity' },
  nurture: { emoji: '🌱', color: '#44dd66', label: 'Nurture' },
  insight: { emoji: '💡', color: '#ff8844', label: 'Insight' },
};

export const AGENT_LABELS: Record<AgentType, string> = {
  whisperer: 'Whisperer 🕵️',
  actuary: 'Actuary 📊',
  slinger: 'Slinger 🎯',
  reaper: 'Reaper ⚔️',
};

export const AGENT_COLORS: Record<AgentType, string> = {
  whisperer: '#44bbff',
  actuary: '#ffbb44',
  slinger: '#ff6644',
  reaper: '#ff44aa',
};

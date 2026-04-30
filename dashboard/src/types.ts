export type AgentType = 'whisperer' | 'actuary' | 'safety' | 'slinger' | 'reaper' | 'critic';
export type StrategyName = 'thrive' | 'swift' | 'echo' | 'bridge' | 'flow' | 'clarity' | 'nurture' | 'insight';
export type StrategyState = 'starting' | 'running' | 'paused' | 'stopped' | 'error' | 'unknown';
export type StrategyControlAction = 'start' | 'pause' | 'stop';

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
  summary: string;
  data: unknown;
  timestamp: number;
}

export interface StrategyStatus {
  name: StrategyName;
  state: StrategyState;
  control_state: StrategyState;
  last_event_timestamp: number | null;
}

export interface HealthResponse {
  status: string;
  uptime_seconds: number;
  active_strategies: number;
  strategies: StrategyStatus[];
}

export interface OperatorQuickAction {
  label: string;
  command: string;
  summary: string;
  availability: string;
}

export interface OperatorResponse {
  selected_mode: string;
  effective_mode: string;
  live_execution_ready: boolean;
  allow_live: boolean;
  state_dir: string;
  dashboard_url: string;
  warnings: string[];
  quick_actions: OperatorQuickAction[];
}

export interface StrategyViewResponse {
  profile: StrategyInfo;
  status: StrategyStatus;
}

export interface AgentCapability {
  agent: AgentType;
  mode: string;
  summary: string;
}

export interface StrategyCapabilities {
  strategy: StrategyName;
  capabilities: AgentCapability[];
}

export interface HoldingView {
  strategy: string;
  token_symbol: string;
  chain: string;
  quantity: number;
  entry_notional_usd: number;
  market_value_usd: number;
  realized_pnl_usd: number;
  unrealized_pnl_usd: number;
  state: string;
  updated_at_ms: number;
}

export interface PortfolioResponse {
  initial_balance_usd: number;
  cash_balance_usd: number;
  equity_usd: number;
  invested_usd: number;
  realized_pnl_usd: number;
  unrealized_pnl_usd: number;
  open_positions: number;
  holdings: HoldingView[];
}

export const STRATEGY_CONFIG: Record<StrategyName, { emoji: string; color: string; label: string; help: string }> = {
  thrive:  { emoji: '🚀', color: '#ff8f5a', label: 'Thrive', help: 'Aggressive high-growth entries. Hunts stronger upside setups with looser risk tolerance.' },
  swift:   { emoji: '⚡', color: '#ffdd44', label: 'Swift', help: 'Fast entries on new pairs. Optimized for quick reaction to fresh opportunities.' },
  echo:    { emoji: '🪞', color: '#b388ff', label: 'Echo', help: 'Mirrors smart-money style moves. Looks for trades that resemble stronger wallet behavior.' },
  bridge:  { emoji: '🌉', color: '#4488ff', label: 'Bridge', help: 'Cross-venue arbitrage focus. Prefers tighter, lower-risk relative pricing opportunities.' },
  flow:    { emoji: '🌊', color: '#44ddbb', label: 'Flow', help: 'Liquidity event plays. Watches for strong movement driven by liquidity and volume changes.' },
  clarity: { emoji: '👁️', color: '#8899aa', label: 'Clarity', help: 'Defensive, lower-risk strategy. Prefers cleaner markets and more conservative entries.' },
  nurture: { emoji: '🌱', color: '#7ee787', label: 'Nurture', help: 'Yield and slower-burn opportunities. Focuses on steadier setups over fast speculation.' },
  insight: { emoji: '🔍', color: '#ff79c6', label: 'Insight', help: 'Contract-analysis-driven opportunities. Leans into higher-conviction, research-heavy setups.' },
};

export const AGENT_LABELS: Record<AgentType, string> = {
  whisperer: 'Whisperer 🕵️',
  actuary: 'Actuary 📊',
  safety: 'Safety 🛡️',
  slinger: 'Slinger 🎯',
  reaper: 'Reaper ⚔️',
  critic: 'Critic 🧠',
};

export const AGENT_COLORS: Record<AgentType, string> = {
  whisperer: '#44bbff',
  actuary: '#ffbb44',
  safety: '#77dd77',
  slinger: '#ff6644',
  reaper: '#ff44aa',
  critic: '#8b7dff',
};

export const AGENT_HELP: Record<AgentType, string> = {
  whisperer: 'Finds trade ideas from market data feeds and surfaces candidate signals to the team.',
  actuary: 'Scores risk on each signal using security checks, taxes, liquidity, and other risk factors.',
  safety: 'Applies hard safety rules before any trade is allowed to proceed.',
  slinger: 'Builds the order and simulates execution, including fill quality, slippage, and fees in paper mode.',
  reaper: 'Tracks open positions, updates mark-to-market pricing, and manages exits and PnL state.',
  critic: 'Reviews outcomes against the original thesis so the system can learn and improve over time.',
};

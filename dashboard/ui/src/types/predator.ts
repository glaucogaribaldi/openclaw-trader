export type PredatorRegime =
  | 'ACTIVE_SCALP_MM'
  | 'AGGRESSIVE_BREAKOUT'
  | 'TOXIC_DIP_DEFENSE'
  | 'MEAN_REVERSION';

export type TokenUniverseMode = 'ACTIVE_ULTRA_LIQUID' | 'HARVEST_RETIRE';

export interface TokenTelemetry {
  inst_id: string;
  symbol: string;
  universe_mode: TokenUniverseMode;
  mid_price: number;
  micro_price: number;
  open_avg_px: number;
  cost_basis_floor_px: number;
  holding_size: number;
  holding_eq_usd: number;
  inv_weight_pct: number;
  unrealized_bps: number;
  unrealized_usd: number;
  // L2 Microstructure
  ofi_norm: number; // -1.0 to +1.0 (5-level Cont-Stoikov OFI)
  vpin_toxicity: number; // 0.0 to 1.0 (VPIN Toxicity Bucket Tracker)
  hawkes_intensity: number; // Hawkes Burst Intensity
  spread_bps: number;
  // Local Kronos-mini (4.1M) Oracle (127.0.0.1:8090)
  kronos_1h_bps: number; // 5m x 12 horizon
  kronos_2h_macro_bps: number; // 15m x 8 horizon
  kronos_high_bps: number;
  kronos_low_bps: number;
  tp_touch_prob_1h?: number;
  kronos_zscore_1h?: number;
  pred_volume_surge_ratio?: number;
  perp_basis_bps?: number;
  horizon_aligned: boolean;
  // 4-Factor Predictive Blend (core/predictor.py)
  rls_kalman_bps: number; // 45% weight
  kronos_blend_bps: number; // 35% weight (75% 5m + 25% 15m)
  llm_council_bps: number; // 12% weight
  btc_lead_lag_contrib_bps: number; // 8% weight
  predicted_return_bps: number; // Final blended prediction
  // Opportunity-Ranked Cash Sweeper
  opp_score: number;
  anti_stacking_locked: boolean; // True if token_eq >= $17.50
  // Execution & Orders
  regime: PredatorRegime;
  buy_offset_bps: number;
  sell_tp_bps: number;
  active_buy_px: number | null;
  active_sell_px: number | null;
  ratchet_subsidy_applied_usd: number;
  updated_at: string;
}

export interface FreshScalpTranche {
  trade_id: string;
  inst_id: string;
  buy_px: number;
  current_px: number;
  size: number;
  notional_usdc: number;
  target_tp_px: number;
  target_tp_bps: number;
  unrealized_bps: number;
  unrealized_usdc: number;
  profit_lock_armed: boolean; // Armed at >= +28 bps
  cl_ord_id: string;
  created_at: string;
}

export interface TradeLedgerEntry {
  trade_id: string;
  ord_id: string;
  inst_id: string;
  side: 'BUY' | 'SELL';
  price: number;
  quantity: number;
  notional_usdc: number;
  fee_usdc: number; // 0.0000 Post-Only Maker
  realized_pnl_usdc: number;
  realized_bps: number;
  binario: 'FRESH_SCALP' | 'LEGACY_RATCHET' | 'SWEEPER_ENTRY';
  created_at: string;
}

export interface NavHistoryPoint {
  timestamp: string;
  label: string;
  nav_usdc: number;
  golden_floor_usdc: number; // +0.70% / day compounding floor
  golden_ceiling_usdc: number; // +5.00% / day compounding ceiling
  realized_cum_pnl_usdc: number;
  btc_lead_lag_bps: number;
  vpin_avg: number;
  event_tag?: string;
}

export interface DailyPnLBar {
  date: string;
  realized_pnl_usdc: number;
  realized_pct: number;
  fills_count: number;
  ratchet_recycled_usdc: number;
  in_golden_channel: boolean;
}

export interface AuditAndCouncilReport {
  audit_score_100: number;
  auditor_model: string;
  maker_ratio_pct: number;
  total_fills_count: number;
  buy_fills_count: number;
  sell_fills_count: number;
  realized_pnl_usd: number;
  unrealized_mtm_usd: number;
  zero_loss_violations: number;
  executive_verdict: string;
  council_timestamp: string;
  council_models: string[];
  council_consensus: string;
  last_self_healing_actions: string[];
}

export interface PredatorSystemState {
  status: 'ok';
  vps_host: string;
  vps_ip: string;
  vps_tailnet_ip: string;
  connection_mode: 'LIVE_VPS_PUSH' | 'SOVEREIGN_REPLAY';
  last_vps_push_iso: string | null;
  vps_push_count: number;
  cycle_num: number;
  cycle_interval_sec: number;
  latency_scan_ms: number;
  kronos_http_ms: number;
  timestamp: string;
  // Capital & NAV Metrics
  genesis_baseline_usdc: number; // $253.01 (11/10/2026)
  v7_run_baseline_usdc: number; // $298.89 (22/10/2026)
  current_nav_usdc: number;
  spot_equity_usd: number;
  free_usdc: number;
  frozen_usdc: number;
  total_usdc_cash: number;
  genesis_net_pnl_usdc: number;
  genesis_growth_pct: number;
  v7_run_pnl_usdc: number;
  v7_run_growth_pct: number;
  today_realized_pnl_usdc: number;
  today_growth_pct: number;
  golden_rule_channel: string;
  golden_status: 'IN_GOLDEN_CHANNEL' | 'ABOVE_GOLDEN_CEILING' | 'ACCUMULATING_TO_FLOOR';
  // Cross-Asset & Ratchet Engine
  btc_mid_px: number;
  ofi_btc: number;
  btc_lead_lag_bps: number;
  ratchet_pool_usd: number;
  ratchet_target_inst_id: string;
  cost_basis_fixes: number;
  profit_lock_repegs: number;
  active_orders_count: number;
  // Arrays
  telemetry: TokenTelemetry[];
  fresh_tranches: FreshScalpTranche[];
  trade_ledger: TradeLedgerEntry[];
  nav_history: NavHistoryPoint[];
  daily_pnl: DailyPnLBar[];
  audit_report: AuditAndCouncilReport;
}

import React, { useState, useEffect, useMemo } from 'react';
import {
  Activity,
  Cpu,
  Layers,
  ShieldCheck,
  Search,
  ArrowUpDown,
  Download,
  RefreshCw,
  ChevronRight,
} from 'lucide-react';
import type { PredatorSystemState, TokenTelemetry } from './types/predator';
import { EquityGoldenChart } from './components/EquityGoldenChart';
import { NeuralBrainVisualizer } from './components/NeuralBrainVisualizer';
import { TokenQuantDrawer } from './components/TokenQuantDrawer';
import { VpsIntegrationPanel } from './components/VpsIntegrationPanel';

type ActiveTab = 'TERMINAL' | 'MICROSTRUCTURE' | 'SUB_LEDGER' | 'AUDIT_VPS';
type SortField = 'opp_score' | 'predicted_return_bps' | 'kronos_1h_bps' | 'ofi_norm' | 'vpin_toxicity' | 'unrealized_bps' | 'holding_eq_usd';

export default function App() {
  const [state, setState] = useState<PredatorSystemState | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('TERMINAL');
  const [selectedToken, setSelectedToken] = useState<TokenTelemetry | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [universeFilter, setUniverseFilter] = useState<'ALL' | 'ACTIVE_10' | 'HARVEST_2' | 'TOXIC_DEFENSE'>('ALL');
  const [sortField, setSortField] = useState<SortField>('opp_score');
  const [sortAsc, setSortAsc] = useState<boolean>(false);
  const [ledgerFilter, setLedgerFilter] = useState<'ALL' | 'FRESH_SCALP' | 'LEGACY_RATCHET'>('ALL');
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [sseConnected, setSseConnected] = useState<boolean>(false);

  // Initial state load + resilient 5s live telemetry sync
  useEffect(() => {
    let active = true;

    const fetchLatestState = async () => {
      try {
        const res = await fetch('/api/state');
        if (!res.ok) return;
        const data: PredatorSystemState = await res.json();
        if (active) {
          setState(data);
          setSseConnected(true);
        }
      } catch {
        if (active) setSseConnected(false);
      }
    };

    fetchLatestState();
    const timer = setInterval(fetchLatestState, 5000);

    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  // Keep selectedToken synced when state updates
  useEffect(() => {
    if (selectedToken && state) {
      const updated = state.telemetry.find((t) => t.inst_id === selectedToken.inst_id);
      if (updated) setSelectedToken(updated);
    }
  }, [state, selectedToken]);

  const handleSimulateCycle = async (scenario: 'normal' | 'toxic_btc_dump' | 'scalp_harvest') => {
    setIsSimulating(true);
    try {
      const res = await fetch('/api/vps/simulate-cycle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario }),
      });
      if (res.ok) {
        const updated = await res.json();
        setState(updated);
      }
    } finally {
      setIsSimulating(false);
    }
  };

  const filteredTelemetry = useMemo(() => {
    if (!state) return [];
    return state.telemetry
      .filter((t) => {
        if (searchQuery.trim() !== '' && !t.inst_id.toLowerCase().includes(searchQuery.toLowerCase())) {
          return false;
        }
        if (universeFilter === 'ACTIVE_10') return t.universe_mode === 'ACTIVE_ULTRA_LIQUID';
        if (universeFilter === 'HARVEST_2') return t.universe_mode === 'HARVEST_RETIRE';
        if (universeFilter === 'TOXIC_DEFENSE') return t.regime === 'TOXIC_DIP_DEFENSE' || t.vpin_toxicity >= 0.55;
        return true;
      })
      .sort((a, b) => {
        const diff = a[sortField] - b[sortField];
        return sortAsc ? diff : -diff;
      });
  }, [state, searchQuery, universeFilter, sortField, sortAsc]);

  const filteredLedger = useMemo(() => {
    if (!state) return [];
    return state.trade_ledger.filter((entry) => {
      if (ledgerFilter === 'ALL') return true;
      return entry.binario === ledgerFilter;
    });
  }, [state, ledgerFilter]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc((v) => !v);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  if (!state) {
    return (
      <div className="min-h-screen bg-[#07080A] text-[#E6E8EC] flex items-center justify-center p-6 font-mono text-xs">
        <div className="border border-[#1E2530] bg-[#0D1017] p-6 max-w-md w-full space-y-3">
          <div className="text-[#FCD34D] font-semibold">TRE OS v7.0 — SOVEREIGN PREDATOR</div>
          <div className="text-[#8A94A6]">Inizializzazione stream telemetrico L2 e Kronos-mini (4.1M)...</div>
          <div className="h-1 w-full bg-[#151A22] overflow-hidden">
            <div className="h-full w-2/3 bg-[#F59E0B]" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#07080A] text-[#E6E8EC] pb-20 md:pb-12">
      {/* STRICT 3-ZONE TOP BAR CONTRACT */}
      <header className="sticky top-0 z-30 h-13 md:h-15 bg-[#07080A]/95 backdrop-blur-xs border-b border-[#1E2530] px-4 sm:px-6 flex items-center justify-between gap-8">
        {/* Zone 1: Single text element wordmark */}
        <a
          href="#top"
          onClick={(e) => {
            e.preventDefault();
            setActiveTab('TERMINAL');
          }}
          className="font-editorial text-base sm:text-lg font-bold tracking-wider text-[#38BDF8] whitespace-nowrap shrink-0 flex items-center gap-2"
        >
          <span className="inline-block w-2 h-2 rounded-full bg-[#38BDF8] animate-pulse" />
          <span>HOLONET // TRE OS v8.8 · IG-88 PREDATOR</span>
        </a>

        {/* Zone 2: 4 clean single-line navigation links */}
        <nav className="hidden md:flex items-center gap-6 text-xs font-mono">
          <button
            type="button"
            onClick={() => setActiveTab('TERMINAL')}
            className={`py-1 transition-colors whitespace-nowrap shrink-0 border-b-2 ${
              activeTab === 'TERMINAL'
                ? 'border-[#38BDF8] text-[#38BDF8] font-semibold'
                : 'border-transparent text-[#8A94A6] hover:text-[#F3F4F6]'
            }`}
          >
            01. Imperial Command Desk
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('MICROSTRUCTURE')}
            className={`py-1 transition-colors whitespace-nowrap shrink-0 border-b-2 ${
              activeTab === 'MICROSTRUCTURE'
                ? 'border-[#38BDF8] text-[#38BDF8] font-semibold'
                : 'border-transparent text-[#8A94A6] hover:text-[#F3F4F6]'
            }`}
          >
            02. Droid Brain &amp; Kronos
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('SUB_LEDGER')}
            className={`py-1 transition-colors whitespace-nowrap shrink-0 border-b-2 ${
              activeTab === 'SUB_LEDGER'
                ? 'border-[#38BDF8] text-[#38BDF8] font-semibold'
                : 'border-transparent text-[#8A94A6] hover:text-[#F3F4F6]'
            }`}
          >
            03. Sub-Ledger &amp; Ratchet
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('AUDIT_VPS')}
            className={`py-1 transition-colors whitespace-nowrap shrink-0 border-b-2 ${
              activeTab === 'AUDIT_VPS'
                ? 'border-[#38BDF8] text-[#38BDF8] font-semibold'
                : 'border-transparent text-[#8A94A6] hover:text-[#F3F4F6]'
            }`}
          >
            04. Outpost Brody &amp; Audit
          </button>
        </nav>

        {/* Zone 3: 1 primary action */}
        <div className="flex items-center shrink-0">
          <a
            href="/api/export/ledger.csv"
            download
            className="px-3.5 py-1.5 text-xs font-mono font-semibold bg-[#0284C7] text-[#F8FAFC] border border-[#38BDF8] hover:bg-[#0369A1] transition-colors whitespace-nowrap shrink-0"
          >
            Holo-Ledger CSV
          </a>
        </div>
      </header>

      {/* MAIN CONTAINER (1440px institutional desktop presence, full touch ergonomics on mobile) */}
      <main className="max-w-[1440px] mx-auto px-3 sm:px-6 pt-4 space-y-5">
        {/* Institutional Telemetry Sub-Strip (Real SSE Connection + Cycle Stepper) */}
        <div className="border border-[#1E2530] bg-[#0D1017] px-3.5 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs font-mono tabular-nums">
          <div className="flex flex-wrap items-center gap-2 text-[#8A94A6]">
            <span className={sseConnected ? 'text-[#10B981] font-semibold' : 'text-[#F59E0B]'}>
              {state.connection_mode === 'LIVE_VPS_PUSH'
                ? 'STREAM VPS BRODY ATTIVO (15s PUSH)'
                : 'TELEMETRIA SOVRANA ATTIVA (SSE STREAM)'}
            </span>
            <span aria-hidden="true">·</span>
            <span>Ciclo #{state.cycle_num}</span>
            <span aria-hidden="true">·</span>
            <span>L2 Scan: {state.latency_scan_ms}ms (6 Thread)</span>
            <span aria-hidden="true">·</span>
            <span className="hidden sm:inline">Kronos-mini RAM Cache: 0.00ms</span>
            <span aria-hidden="true" className="hidden sm:inline">·</span>
            <span>{state.timestamp}</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={isSimulating}
              onClick={() => handleSimulateCycle('normal')}
              className="px-2.5 py-1 bg-[#07080A] border border-[#1E2530] hover:border-[#F59E0B] text-[#FCD34D] flex items-center gap-1.5 transition-colors whitespace-nowrap shrink-0 min-h-[32px]"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isSimulating ? 'animate-spin' : ''}`} />
              Ciclo +15s
            </button>
            <button
              type="button"
              disabled={isSimulating}
              onClick={() => handleSimulateCycle('scalp_harvest')}
              className="px-2.5 py-1 bg-[#07080A] border border-[#1E2530] hover:border-[#10B981] text-[#10B981] transition-colors whitespace-nowrap shrink-0 min-h-[32px] hidden sm:inline-flex"
            >
              +Fill Quick-Scalp
            </button>
          </div>
        </div>

        {/* EXECUTIVE KPI STRIP (5 Institutional Pillars) */}
        <section className="grid grid-cols-2 lg:grid-cols-5 gap-3 font-mono tabular-nums">
          {/* 1. Net Asset Value */}
          <div className="col-span-2 sm:col-span-1 border border-[#0E3A5A] bg-[#060B14] p-3.5 sm:p-4 holo-glow">
            <div className="text-[11px] text-[#38BDF8] flex items-center justify-between">
              <span>NET ASSET VALUE (LIVE)</span>
              <span className="text-[#10B981]">SPOT EEA</span>
            </div>
            <div className="text-2xl sm:text-3xl font-bold text-[#F3F4F6] mt-1">
              ${state.current_nav_usdc.toFixed(2)}
            </div>
            <div className="text-xs mt-1.5 flex items-center justify-between">
              <span
                className={`font-semibold ${
                  state.v7_run_pnl_usdc >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                }`}
              >
                {state.v7_run_pnl_usdc >= 0
                  ? `+$${state.v7_run_pnl_usdc.toFixed(2)}`
                  : `-$${Math.abs(state.v7_run_pnl_usdc).toFixed(2)}`}{' '}
                ({state.v7_run_growth_pct >= 0 ? `+${state.v7_run_growth_pct}` : state.v7_run_growth_pct}%)
              </span>
              <span className="text-[#8A94A6]">da Baseline Run</span>
            </div>
          </div>

          {/* 2. Golden Rule Daily Compounding */}
          <div className="border border-[#0E3A5A] bg-[#060B14] p-3.5 sm:p-4 holo-glow">
            <div className="text-[11px] text-[#38BDF8] flex items-center justify-between">
              <span>UTILE REALIZZATO (24H)</span>
              <span className="text-[#FCD34D]">REGOLA AUREA</span>
            </div>
            <div
              className={`text-xl sm:text-2xl font-bold mt-1 ${
                state.today_realized_pnl_usdc >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
              }`}
            >
              {state.today_realized_pnl_usdc >= 0
                ? `+$${state.today_realized_pnl_usdc.toFixed(4)}`
                : `-$${Math.abs(state.today_realized_pnl_usdc).toFixed(4)}`}{' '}
              <span className="text-sm font-normal">
                ({state.today_growth_pct >= 0 ? `+${state.today_growth_pct}` : state.today_growth_pct}%)
              </span>
            </div>
            <div className="text-[11px] text-[#8A94A6] mt-1.5">
              Target 24h: <span className="text-[#FCD34D]">{state.golden_rule_channel}</span>
            </div>
          </div>

          {/* 3. Liquidity & Maker Traps */}
          <div className="border border-[#0E3A5A] bg-[#060B14] p-3.5 sm:p-4 holo-glow">
            <div className="text-[11px] text-[#38BDF8] flex items-center justify-between">
              <span>CASSA LIQUIDA USDC</span>
              <span className="text-[#38BDF8]">{state.active_orders_count} ORDINI</span>
            </div>
            <div className="text-xl sm:text-2xl font-bold text-[#F3F4F6] mt-1">
              ${state.free_usdc.toFixed(2)} <span className="text-xs text-[#8A94A6] font-normal">liberi</span>
            </div>
            <div className="text-[11px] text-[#8A94A6] mt-1.5">
              Totale: ${state.total_usdc_cash.toFixed(2)} · Frozen: ${state.frozen_usdc.toFixed(2)}
            </div>
          </div>

          {/* 4. Cross-Asset BTC-USDC Radar */}
          <div className="border border-[#0E3A5A] bg-[#060B14] p-3.5 sm:p-4 holo-glow">
            <div className="text-[11px] text-[#38BDF8] flex items-center justify-between">
              <span>BTC-USDC LEAD-LAG RADAR</span>
              <span className={state.ofi_btc >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                OFI {state.ofi_btc >= 0 ? `+${state.ofi_btc}` : state.ofi_btc}
              </span>
            </div>
            <div
              className={`text-xl sm:text-2xl font-bold mt-1 ${
                state.btc_lead_lag_bps >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
              }`}
            >
              {state.btc_lead_lag_bps >= 0 ? '+' : ''}
              {state.btc_lead_lag_bps} bps
            </div>
            <div className="text-[11px] text-[#8A94A6] mt-1.5">
              {state.btc_lead_lag_bps < -12
                ? 'SCUDO TOXIC_DIP_DEFENSE ATTIVO'
                : 'Settore Regolare (Soglia < -12 bps)'}
            </div>
          </div>

          {/* 5. Ratchet Capital Recycler */}
          <div className="border border-[#0E3A5A] bg-[#060B14] p-3.5 sm:p-4 holo-glow">
            <div className="text-[11px] text-[#38BDF8] flex items-center justify-between">
              <span>RATCHET RECYCLER POOL</span>
              <span className="text-[#FCD34D]">20% UTILI</span>
            </div>
            <div className="text-xl sm:text-2xl font-bold text-[#FCD34D] mt-1">
              ${state.ratchet_pool_usd.toFixed(3)}
            </div>
            <div className="text-[11px] text-[#8A94A6] mt-1.5">
              Target Sblocco: <span className="text-[#E6E8EC]">{state.ratchet_target_inst_id}</span> · Re-pegs:{' '}
              {state.profit_lock_repegs}
            </div>
          </div>
        </section>

        {/* VIEW 1: EXECUTIVE TERMINAL (DEFAULT) */}
        {activeTab === 'TERMINAL' && (
          <div className="space-y-6">
            {/* Main Interactive Equity & Golden Rule Chart */}
            <EquityGoldenChart
              history={state.nav_history}
              dailyPnl={state.daily_pnl}
              genesisBaseline={state.genesis_baseline_usdc}
              v7Baseline={state.v7_run_baseline_usdc}
              currentNav={state.current_nav_usdc}
            />

            {/* Two-Column Institutional Split: 12-Pair Opportunity Matrix + Dual-Binary Live Summary */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
              {/* Left 8 Columns: 12-Pair Microstructure & Kronos Matrix */}
              <div className="lg:col-span-8 border border-[#1E2530] bg-[#0D1017] p-4 sm:p-5 flex flex-col justify-between">
                <div>
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-3 border-b border-[#181E27]">
                    <div>
                      <span className="text-xs font-mono text-[#8A94A6]">
                        02. UNIVERSO DINAMICO 12 COPPIE (10 ATTIVE + 2 HARVEST &amp; RETIRE)
                      </span>
                      <h3 className="font-editorial text-lg sm:text-xl font-semibold text-[#F3F4F6]">
                        Matrice Microstruttura L2, Oracolo Kronos-mini &amp; Opportunity Score
                      </h3>
                    </div>
                    <button
                      type="button"
                      onClick={() => setActiveTab('MICROSTRUCTURE')}
                      className="text-xs font-mono text-[#FCD34D] hover:underline self-start sm:self-auto whitespace-nowrap shrink-0"
                    >
                      Vista Completa L2 →
                    </button>
                  </div>

                  {/* Desktop High-Density Table */}
                  <div className="hidden sm:block overflow-x-auto mt-3">
                    <table className="w-full text-left border-collapse font-mono tabular-nums text-xs">
                      <thead>
                        <tr className="border-b border-[#1E2530] text-[#8A94A6] text-[11px]">
                          <th className="py-2 pr-2">PAIR / STATO</th>
                          <th className="py-2 px-2 text-right">MID / FLOOR</th>
                          <th className="py-2 px-2 text-right">UNR. BPS</th>
                          <th className="py-2 px-2 text-right">OFI / VPIN</th>
                          <th className="py-2 px-2 text-right">KRONOS 1H/2H</th>
                          <th className="py-2 px-2 text-right">PRED BPS</th>
                          <th className="py-2 px-2 text-right">OPPSCORE</th>
                          <th className="py-2 pl-2 text-right">REGIME</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#151A22]">
                        {state.telemetry.map((t) => (
                          <tr
                            key={t.inst_id}
                            onClick={() => setSelectedToken(t)}
                            className="hover:bg-[#141923] cursor-pointer transition-colors"
                          >
                            <td className="py-2.5 pr-2">
                              <div className="font-semibold text-[#F3F4F6] flex items-center gap-1.5">
                                <span>{t.symbol}</span>
                                <span className="text-[10px] text-[#8A94A6]">
                                  {t.universe_mode === 'HARVEST_RETIRE' ? '· HARVEST' : `· ${t.inv_weight_pct}%`}
                                </span>
                              </div>
                            </td>
                            <td className="py-2.5 px-2 text-right">
                              <div className="text-[#E6E8EC]">${t.mid_price}</div>
                              <div className="text-[10px] text-[#8A94A6]">Fl: ${t.cost_basis_floor_px}</div>
                            </td>
                            <td
                              className={`py-2.5 px-2 text-right font-semibold ${
                                t.unrealized_bps >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                              }`}
                            >
                              {t.unrealized_bps >= 0 ? '+' : ''}
                              {t.unrealized_bps}
                            </td>
                            <td className="py-2.5 px-2 text-right">
                              <span className={t.ofi_norm >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                                {t.ofi_norm >= 0 ? '+' : ''}
                                {t.ofi_norm.toFixed(2)}
                              </span>
                              <span className="text-[#8A94A6]"> / </span>
                              <span className={t.vpin_toxicity >= 0.55 ? 'text-[#EF4444]' : 'text-[#8A94A6]'}>
                                {t.vpin_toxicity.toFixed(2)}
                              </span>
                            </td>
                            <td className="py-2.5 px-2 text-right">
                              <span className={t.kronos_1h_bps >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                                {t.kronos_1h_bps >= 0 ? '+' : ''}
                                {t.kronos_1h_bps}
                              </span>
                              <span className="text-[#8A94A6]"> / </span>
                              <span className={t.kronos_2h_macro_bps >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                                {t.kronos_2h_macro_bps >= 0 ? '+' : ''}
                                {t.kronos_2h_macro_bps}
                              </span>
                            </td>
                            <td
                              className={`py-2.5 px-2 text-right font-semibold ${
                                t.predicted_return_bps >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                              }`}
                            >
                              {t.predicted_return_bps >= 0 ? '+' : ''}
                              {t.predicted_return_bps}
                            </td>
                            <td
                              className={`py-2.5 px-2 text-right font-semibold ${
                                t.opp_score >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                              }`}
                            >
                              {t.opp_score >= 0 ? '+' : ''}
                              {t.opp_score}
                            </td>
                            <td className="py-2.5 pl-2 text-right text-[11px]">
                              <span
                                className={
                                  t.regime === 'AGGRESSIVE_BREAKOUT'
                                    ? 'text-[#10B981]'
                                    : t.regime === 'TOXIC_DIP_DEFENSE'
                                    ? 'text-[#EF4444]'
                                    : 'text-[#E6E8EC]'
                                }
                              >
                                {t.regime}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Mobile Ergonomic Tap Rows (>=60px height) */}
                  <div className="sm:hidden divide-y divide-[#181E27] mt-2">
                    {state.telemetry.map((t) => (
                      <button
                        key={t.inst_id}
                        type="button"
                        onClick={() => setSelectedToken(t)}
                        className="w-full py-3 flex items-center justify-between text-left font-mono tabular-nums min-h-[62px]"
                      >
                        <div>
                          <div className="text-sm font-semibold text-[#F3F4F6] flex items-center gap-2">
                            <span>{t.inst_id}</span>
                            <span className="text-xs text-[#FCD34D]">Opp {t.opp_score >= 0 ? `+${t.opp_score}` : t.opp_score}</span>
                          </div>
                          <div className="text-[11px] text-[#8A94A6] mt-0.5">
                            {t.regime} · OFI {t.ofi_norm >= 0 ? `+${t.ofi_norm}` : t.ofi_norm} · VPIN {t.vpin_toxicity}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 text-right">
                          <div>
                            <div className="text-sm text-[#E6E8EC]">${t.mid_price}</div>
                            <div
                              className={`text-xs ${
                                t.predicted_return_bps >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                              }`}
                            >
                              Pred {t.predicted_return_bps >= 0 ? '+' : ''}
                              {t.predicted_return_bps} bps
                            </div>
                          </div>
                          <ChevronRight className="w-4 h-4 text-[#8A94A6]" />
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="pt-3 mt-3 border-t border-[#181E27] text-xs font-mono text-[#8A94A6] flex flex-wrap items-center justify-between gap-2">
                  <span>Clicca su qualsiasi coppia per aprire il Token Quant Inspector (4-Factor Blend + Kronos Envelope)</span>
                  <span className="text-[#10B981]">100% Inventory Coverage Attiva</span>
                </div>
              </div>

              {/* Right 4 Columns: Fresh Tranche Sub-Ledger & Self-Healing Feed */}
              <div className="lg:col-span-4 flex flex-col gap-5">
                {/* Fresh Tranches Sub-Ledger Box */}
                <div className="border border-[#1E2530] bg-[#0D1017] p-4 sm:p-5 flex-1">
                  <div className="flex items-center justify-between pb-3 border-b border-[#181E27]">
                    <div>
                      <span className="text-xs font-mono text-[#8A94A6]">BINARIO B · SUB-LEDGER</span>
                      <h3 className="font-editorial text-lg font-semibold text-[#F3F4F6]">
                        Fresh Tranche Quick-Scalp
                      </h3>
                    </div>
                    <span className="text-xs font-mono text-[#10B981]">+35..+65 bps TP</span>
                  </div>

                  <div className="space-y-2.5 mt-3 font-mono tabular-nums text-xs">
                    {state.fresh_tranches.map((tr) => (
                      <div key={tr.trade_id} className="bg-[#07080A] border border-[#1E2530] p-3">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-[#F3F4F6]">
                            {tr.inst_id} <span className="text-[#8A94A6] font-normal">({tr.trade_id})</span>
                          </span>
                          <span
                            className={`font-semibold ${
                              tr.unrealized_bps >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                            }`}
                          >
                            {tr.unrealized_bps >= 0 ? `+${tr.unrealized_bps}` : tr.unrealized_bps} bps
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-[11px] text-[#8A94A6] mt-1">
                          <span>
                            Buy ${tr.buy_px} → TP ${tr.target_tp_px}
                          </span>
                          <span>${tr.notional_usdc.toFixed(2)} USDC</span>
                        </div>
                        <div className="flex items-center justify-between text-[11px] mt-1.5 pt-1.5 border-t border-[#151A22]">
                          <span className={tr.profit_lock_armed ? 'text-[#FCD34D]' : 'text-[#8A94A6]'}>
                            {tr.profit_lock_armed ? 'PROFIT-LOCK ARMATO (+28 bps)' : 'In attesa di +28 bps Lock'}
                          </span>
                          <span className={tr.unrealized_usdc >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                            {tr.unrealized_usdc >= 0
                              ? `+$${tr.unrealized_usdc.toFixed(3)}`
                              : `-$${Math.abs(tr.unrealized_usdc).toFixed(3)}`}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Self-Healing & Execution Log */}
                <div className="border border-[#1E2530] bg-[#0D1017] p-4 sm:p-5">
                  <div className="pb-2.5 border-b border-[#181E27]">
                    <span className="text-xs font-mono text-[#8A94A6]">AUTONOMOUS GUARDRAILS</span>
                    <h3 className="font-editorial text-lg font-semibold text-[#F3F4F6]">
                      Ultime Azioni Self-Healing
                    </h3>
                  </div>
                  <div className="space-y-2 mt-3 font-mono text-[11px] text-[#E6E8EC]">
                    {state.audit_report.last_self_healing_actions.map((act, idx) => (
                      <div key={idx} className="bg-[#07080A] border border-[#1E2530] p-2.5 leading-relaxed">
                        {act}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* VIEW 2: FULL MICROSTRUCTURE L2 & KRONOS-MINI MATRIX */}
        {activeTab === 'MICROSTRUCTURE' && (
          <div className="space-y-6">
            <NeuralBrainVisualizer
              telemetry={state.telemetry}
              btcLeadLagBps={state.btc_lead_lag_bps}
            />
            <section className="border border-[#1E2530] bg-[#0D1017] p-4 sm:p-6 space-y-4">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 pb-4 border-b border-[#181E27]">
              <div>
                <div className="text-xs font-mono text-[#8A94A6]">
                  02. CONT-STOIKOV OFI (5 LIVELLI) · VPIN TOXICITY · HAWKES BURST · KRONOS-MINI (4.1M)
                </div>
                <h2 className="font-editorial text-xl sm:text-2xl font-semibold text-[#F3F4F6] mt-1">
                  Scanner Microstrutturale L2 &amp; Fusione Predittiva a 4 Fattori
                </h2>
              </div>

              {/* Search & Universe Segment Filter */}
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-[#8A94A6] absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Filtra ticker (es. HYPE, SOL)..."
                    className="bg-[#07080A] border border-[#1E2530] pl-8 pr-3 py-1.5 text-xs font-mono text-[#E6E8EC] focus:outline-none focus:border-[#F59E0B] min-h-[36px]"
                  />
                </div>

                <div className="flex items-center bg-[#07080A] border border-[#1E2530] p-0.5">
                  {(
                    [
                      { id: 'ALL', label: 'Tutti (12)' },
                      { id: 'ACTIVE_10', label: 'Attivi (10)' },
                      { id: 'HARVEST_2', label: 'Harvest (2)' },
                      { id: 'TOXIC_DEFENSE', label: 'Alert VPIN/Toxic' },
                    ] as const
                  ).map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => setUniverseFilter(f.id)}
                      className={`px-2.5 py-1.5 text-xs font-mono transition-colors whitespace-nowrap shrink-0 min-h-[34px] ${
                        universeFilter === f.id
                          ? 'bg-[#F59E0B] text-[#07080A] font-semibold'
                          : 'text-[#8A94A6] hover:text-[#E6E8EC]'
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Sortable Full Quantitative Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse font-mono tabular-nums text-xs">
                <thead>
                  <tr className="border-b border-[#1E2530] text-[#8A94A6] text-[11px]">
                    <th className="py-2.5 pr-3">STRUMENTO</th>
                    <th className="py-2.5 px-2 text-right">MID / MICRO PX</th>
                    <th className="py-2.5 px-2 text-right">
                      <button
                        type="button"
                        onClick={() => toggleSort('holding_eq_usd')}
                        className="inline-flex items-center gap-1 hover:text-[#F3F4F6]"
                      >
                        INV. USD <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    <th className="py-2.5 px-2 text-right">
                      <button
                        type="button"
                        onClick={() => toggleSort('ofi_norm')}
                        className="inline-flex items-center gap-1 hover:text-[#F3F4F6]"
                      >
                        OFI (L2) <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    <th className="py-2.5 px-2 text-right">
                      <button
                        type="button"
                        onClick={() => toggleSort('vpin_toxicity')}
                        className="inline-flex items-center gap-1 hover:text-[#F3F4F6]"
                      >
                        VPIN / HAWKES <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    <th className="py-2.5 px-2 text-right">
                      <button
                        type="button"
                        onClick={() => toggleSort('kronos_1h_bps')}
                        className="inline-flex items-center gap-1 hover:text-[#F3F4F6]"
                      >
                        KRONOS 5m/15m <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    <th className="py-2.5 px-2 text-right">RLS / LLM</th>
                    <th className="py-2.5 px-2 text-right">
                      <button
                        type="button"
                        onClick={() => toggleSort('predicted_return_bps')}
                        className="inline-flex items-center gap-1 hover:text-[#F3F4F6]"
                      >
                        BLEND BPS <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    <th className="py-2.5 px-2 text-right">
                      <button
                        type="button"
                        onClick={() => toggleSort('opp_score')}
                        className="inline-flex items-center gap-1 text-[#FCD34D]"
                      >
                        OPPSCORE <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    <th className="py-2.5 pl-2 text-right">TRAP BUY / TP SELL</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#151A22]">
                  {filteredTelemetry.map((t) => (
                    <tr
                      key={t.inst_id}
                      onClick={() => setSelectedToken(t)}
                      className="hover:bg-[#141923] cursor-pointer transition-colors"
                    >
                      <td className="py-3 pr-3">
                        <div className="font-semibold text-[#F3F4F6]">{t.inst_id}</div>
                        <div className="text-[10px] text-[#8A94A6]">
                          {t.regime} · {t.universe_mode === 'HARVEST_RETIRE' ? 'HARVEST' : 'ACTIVE'}
                        </div>
                      </td>
                      <td className="py-3 px-2 text-right">
                        <div className="text-[#E6E8EC]">${t.mid_price}</div>
                        <div className="text-[10px] text-[#8A94A6]">µPx: ${t.micro_price}</div>
                      </td>
                      <td className="py-3 px-2 text-right">
                        <div className="text-[#E6E8EC]">${t.holding_eq_usd.toFixed(2)}</div>
                        <div className="text-[10px] text-[#8A94A6]">
                          {t.inv_weight_pct}% {t.anti_stacking_locked ? '· MAX CAP' : ''}
                        </div>
                      </td>
                      <td
                        className={`py-3 px-2 text-right font-semibold ${
                          t.ofi_norm >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                        }`}
                      >
                        {t.ofi_norm >= 0 ? '+' : ''}
                        {t.ofi_norm.toFixed(2)}
                      </td>
                      <td className="py-3 px-2 text-right">
                        <span className={t.vpin_toxicity >= 0.55 ? 'text-[#EF4444] font-semibold' : 'text-[#E6E8EC]'}>
                          {t.vpin_toxicity.toFixed(2)}
                        </span>
                        <span className="text-[#8A94A6]"> · λ {t.hawkes_intensity}</span>
                      </td>
                      <td className="py-3 px-2 text-right">
                        <div className={t.kronos_1h_bps >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                          1h: {t.kronos_1h_bps >= 0 ? '+' : ''}
                          {t.kronos_1h_bps} bps
                        </div>
                        <div className="text-[10px] text-[#8A94A6]">
                          2h: {t.kronos_2h_macro_bps >= 0 ? '+' : ''}
                          {t.kronos_2h_macro_bps} ({t.horizon_aligned ? 'Aligned' : 'Div'})
                        </div>
                      </td>
                      <td className="py-3 px-2 text-right text-[#8A94A6]">
                        <div>RLS: {t.rls_kalman_bps >= 0 ? `+${t.rls_kalman_bps}` : t.rls_kalman_bps}</div>
                        <div className="text-[10px]">LLM: {t.llm_council_bps >= 0 ? `+${t.llm_council_bps}` : t.llm_council_bps}</div>
                      </td>
                      <td
                        className={`py-3 px-2 text-right font-bold ${
                          t.predicted_return_bps >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                        }`}
                      >
                        {t.predicted_return_bps >= 0 ? '+' : ''}
                        {t.predicted_return_bps} bps
                      </td>
                      <td
                        className={`py-3 px-2 text-right font-bold ${
                          t.opp_score >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                        }`}
                      >
                        {t.opp_score >= 0 ? '+' : ''}
                        {t.opp_score}
                      </td>
                      <td className="py-3 pl-2 text-right">
                        <div className="text-[#10B981]">-{t.buy_offset_bps} bps</div>
                        <div className="text-[10px] text-[#FCD34D]">+{t.sell_tp_bps} bps TP</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          </div>
        )}

        {/* VIEW 3: DUAL-BINARY SUB-LEDGER, RATCHET RECYCLER & CERTIFIED FILLS */}
        {activeTab === 'SUB_LEDGER' && (
          <div className="space-y-6">
            {/* Dual Binary Architecture Explainer & Ratchet Status */}
            <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 font-mono tabular-nums">
              <div className="border border-[#1E2530] bg-[#0D1017] p-4">
                <div className="text-xs text-[#FCD34D] font-semibold">BINARIO A · COST-BASIS FLOOR + RATCHET</div>
                <p className="text-xs text-[#8A94A6] mt-1 font-sans leading-relaxed">
                  100% dell&apos;inventario storico è coperto da ordini SELL Post-Only a prezzo{' '}
                  <code className="text-[#E6E8EC]">&gt;= openAvgPx × 1.0012</code>. Il 20% dei profitti Quick-Scalp
                  alimenta il Ratchet Pool (${state.ratchet_pool_usd.toFixed(3)}) per abbassare e sbloccare il TP più
                  vicino ({state.ratchet_target_inst_id}).
                </p>
              </div>
              <div className="border border-[#1E2530] bg-[#0D1017] p-4">
                <div className="text-xs text-[#10B981] font-semibold">BINARIO B · FRESH TRANCHE SUB-LEDGER</div>
                <p className="text-xs text-[#8A94A6] mt-1 font-sans leading-relaxed">
                  Ogni nuovo acquisto viene isolato nella tabella SQLite <code className="text-[#E6E8EC]">fresh_scalp_tranches</code>{' '}
                  e messo subito in vendita a <code className="text-[#10B981]">+35..+65 bps</code> sopra{' '}
                  <code className="text-[#E6E8EC]">buy_px</code>, con Profit-Lock automatico al Best Ask a{' '}
                  <code className="text-[#FCD34D]">+28 bps</code>.
                </p>
              </div>
              <div className="border border-[#1E2530] bg-[#0D1017] p-4">
                <div className="text-xs text-[#E6E8EC] font-semibold">BINARIO C · OPPORTUNITY CASH SWEEPER</div>
                <p className="text-xs text-[#8A94A6] mt-1 font-sans leading-relaxed">
                  Quando la cassa libera supera <code className="text-[#E6E8EC]">$8.00 USDC</code> (attuale:{' '}
                  <span className="text-[#10B981]">${state.free_usdc.toFixed(2)}</span>), il motore alloca trappole Maker
                  sulle coppie con <code className="text-[#FCD34D]">OppScore</code> massimo, bloccando l&apos;accumulo a{' '}
                  <code className="text-[#E6E8EC]">$17.50 max/token</code>.
                </p>
              </div>
            </section>

            {/* Certified Trade Ledger Table with Filter & Export */}
            <section className="border border-[#1E2530] bg-[#0D1017] p-4 sm:p-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-[#181E27]">
                <div>
                  <span className="text-xs font-mono text-[#8A94A6]">
                    03. REGISTRO CONTABILE CERTIFICATO (SQLITE TRADE_LEDGER · 0.00% MAKER FEE)
                  </span>
                  <h2 className="font-editorial text-xl sm:text-2xl font-semibold text-[#F3F4F6] mt-1">
                    Esecuzioni Storiche &amp; Attribuzione PnL Realizzato
                  </h2>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex items-center bg-[#07080A] border border-[#1E2530] p-0.5">
                    {(
                      [
                        { id: 'ALL', label: 'Tutti i Fill' },
                        { id: 'FRESH_SCALP', label: 'Fresh Scalp (Binario B)' },
                        { id: 'LEGACY_RATCHET', label: 'Ratchet Unlock (Binario A)' },
                      ] as const
                    ).map((b) => (
                      <button
                        key={b.id}
                        type="button"
                        onClick={() => setLedgerFilter(b.id)}
                        className={`px-2.5 py-1.5 text-xs font-mono transition-colors whitespace-nowrap shrink-0 min-h-[34px] ${
                          ledgerFilter === b.id
                            ? 'bg-[#F59E0B] text-[#07080A] font-semibold'
                            : 'text-[#8A94A6] hover:text-[#E6E8EC]'
                        }`}
                      >
                        {b.label}
                      </button>
                    ))}
                  </div>

                  <a
                    href="/api/export/ledger.csv"
                    download
                    className="px-3 py-1.5 text-xs font-mono border border-[#1E2530] bg-[#07080A] text-[#FCD34D] hover:border-[#F59E0B] flex items-center gap-1.5 whitespace-nowrap shrink-0 min-h-[36px]"
                  >
                    <Download className="w-3.5 h-3.5" />
                    CSV
                  </a>
                </div>
              </div>

              <div className="overflow-x-auto mt-3">
                <table className="w-full text-left border-collapse font-mono tabular-nums text-xs">
                  <thead>
                    <tr className="border-b border-[#1E2530] text-[#8A94A6] text-[11px]">
                      <th className="py-2.5 pr-3">TRADE ID / ORDINE OKX</th>
                      <th className="py-2.5 px-2">COPPIA</th>
                      <th className="py-2.5 px-2">LATO / BINARIO</th>
                      <th className="py-2.5 px-2 text-right">PREZZO ESECUZIONE</th>
                      <th className="py-2.5 px-2 text-right">QUANTITÀ / CONTROVALORE</th>
                      <th className="py-2.5 px-2 text-right">FEE MAKER</th>
                      <th className="py-2.5 px-2 text-right">PNL REALIZZATO</th>
                      <th className="py-2.5 pl-2 text-right">TIMESTAMP (CEST)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#151A22]">
                    {filteredLedger.map((row) => (
                      <tr key={row.trade_id} className="hover:bg-[#141923]">
                        <td className="py-2.5 pr-3">
                          <div className="text-[#E6E8EC] font-semibold">{row.trade_id}</div>
                          <div className="text-[10px] text-[#8A94A6]">{row.ord_id}</div>
                        </td>
                        <td className="py-2.5 px-2 font-semibold text-[#F3F4F6]">{row.inst_id}</td>
                        <td className="py-2.5 px-2">
                          <span className={row.side === 'SELL' ? 'text-[#10B981] font-semibold' : 'text-[#FCD34D]'}>
                            {row.side}
                          </span>
                          <span className="text-[#8A94A6]"> · {row.binario}</span>
                        </td>
                        <td className="py-2.5 px-2 text-right text-[#E6E8EC]">${row.price}</td>
                        <td className="py-2.5 px-2 text-right">
                          <div className="text-[#E6E8EC]">${row.notional_usdc.toFixed(2)} USDC</div>
                          <div className="text-[10px] text-[#8A94A6]">Qty: {row.quantity}</div>
                        </td>
                        <td className="py-2.5 px-2 text-right text-[#10B981]">$0.0000 (0%)</td>
                        <td className="py-2.5 px-2 text-right font-semibold">
                          {row.side === 'SELL' ? (
                            <span className={row.realized_pnl_usdc >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                              {row.realized_pnl_usdc >= 0
                                ? `+$${row.realized_pnl_usdc.toFixed(3)} (+${row.realized_bps} bps)`
                                : `-$${Math.abs(row.realized_pnl_usdc).toFixed(3)} (${row.realized_bps} bps)`}
                            </span>
                          ) : (
                            <span className="text-[#8A94A6]">Ingresso Maker</span>
                          )}
                        </td>
                        <td className="py-2.5 pl-2 text-right text-[#8A94A6]">{row.created_at}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}

        {/* VIEW 4: SCIENTIFIC AUDIT & VPS BRODY 15S PUSH INTEGRATION */}
        {activeTab === 'AUDIT_VPS' && (
          <VpsIntegrationPanel
            state={state}
            onSimulateCycle={handleSimulateCycle}
            isSimulating={isSimulating}
          />
        )}
      </main>

      {/* TOKEN QUANT INSPECTOR DRAWER / BOTTOM SHEET */}
      <TokenQuantDrawer token={selectedToken} onClose={() => setSelectedToken(null)} />

      {/* MOBILE ERGONOMIC BOTTOM TAB BAR (<768px, Natural Thumb Zone, <= 15% Sticky Cap) */}
      <nav
        aria-label="Navigazione Mobile"
        className="md:hidden fixed bottom-0 left-0 right-0 z-40 h-14 bg-[#07080A]/95 backdrop-blur-md border-t border-[#1E2530] grid grid-cols-4 items-center"
      >
        <button
          type="button"
          onClick={() => setActiveTab('TERMINAL')}
          className={`h-full flex flex-col items-center justify-center font-mono text-[10px] ${
            activeTab === 'TERMINAL' ? 'text-[#FCD34D] font-semibold' : 'text-[#8A94A6]'
          }`}
        >
          <Activity className="w-4 h-4 mb-0.5" />
          <span>NAV &amp; Desk</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('MICROSTRUCTURE')}
          className={`h-full flex flex-col items-center justify-center font-mono text-[10px] ${
            activeTab === 'MICROSTRUCTURE' ? 'text-[#FCD34D] font-semibold' : 'text-[#8A94A6]'
          }`}
        >
          <Cpu className="w-4 h-4 mb-0.5" />
          <span>Matrice L2</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('SUB_LEDGER')}
          className={`h-full flex flex-col items-center justify-center font-mono text-[10px] ${
            activeTab === 'SUB_LEDGER' ? 'text-[#FCD34D] font-semibold' : 'text-[#8A94A6]'
          }`}
        >
          <Layers className="w-4 h-4 mb-0.5" />
          <span>Sub-Ledger</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('AUDIT_VPS')}
          className={`h-full flex flex-col items-center justify-center font-mono text-[10px] ${
            activeTab === 'AUDIT_VPS' ? 'text-[#FCD34D] font-semibold' : 'text-[#8A94A6]'
          }`}
        >
          <ShieldCheck className="w-4 h-4 mb-0.5" />
          <span>VPS Brody</span>
        </button>
      </nav>
    </div>
  );
}

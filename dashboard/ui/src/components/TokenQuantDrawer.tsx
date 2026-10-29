import React from 'react';
import { X, ShieldAlert, Cpu, Layers, ArrowUpRight } from 'lucide-react';
import type { TokenTelemetry } from '../types/predator';

interface TokenQuantDrawerProps {
  token: TokenTelemetry | null;
  onClose: () => void;
}

export const TokenQuantDrawer: React.FC<TokenQuantDrawerProps> = ({ token, onClose }) => {
  if (!token) return null;

  const rlsWeighted = Number((0.45 * token.rls_kalman_bps).toFixed(2));
  const kronosWeighted = Number((0.35 * token.kronos_blend_bps).toFixed(2));
  const llmWeighted = Number((0.12 * token.llm_council_bps).toFixed(2));
  const btcWeighted = Number((0.08 * token.btc_lead_lag_contrib_bps).toFixed(2));

  const factors = [
    {
      label: '45% Online RLS (λ=0.985) + Kalman Velocity',
      rawBps: token.rls_kalman_bps,
      weightedBps: rlsWeighted,
      desc: 'Regressione lineare ricorsiva su micro-variazioni L2 in tempo reale',
    },
    {
      label: '35% NeoQuasar/Kronos-mini (75% 5m + 25% 15m)',
      rawBps: token.kronos_blend_bps,
      weightedBps: kronosWeighted,
      desc: `Oracolo locale 4.1M parametri su 127.0.0.1:8090 (${token.horizon_aligned ? 'Orizzonti Allineati' : 'Orizzonti Divergenti'})`,
    },
    {
      label: '12% Multi-Model Free OpenRouter Council',
      rawBps: token.llm_council_bps,
      weightedBps: llmWeighted,
      desc: 'Consenso avversario Nemotron-253B + DeepSeek-R1 + Llama-3.3-70B',
    },
    {
      label: '8% Cross-Asset BTC-USDC Lead-Lag Radar',
      rawBps: token.btc_lead_lag_contrib_bps,
      weightedBps: btcWeighted,
      desc: 'Protezione sistemica da scarichi improvvisi sul leader di mercato',
    },
  ];

  const liqBonus = token.universe_mode === 'ACTIVE_ULTRA_LIQUID' ? 4.5 : -25.0;
  const ofiTerm = Number((15 * token.ofi_norm).toFixed(2));
  const vpinPenalty = Number((-20 * token.vpin_toxicity).toFixed(2));
  const invPenalty = Number((-50 * (token.inv_weight_pct / 100)).toFixed(2));

  return (
    <div
      className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-end sm:items-center justify-center p-0 sm:p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl max-h-[90vh] overflow-y-auto bg-[#0D1017] border-t sm:border border-[#F59E0B]/50 text-[#E6E8EC] p-4 sm:p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Mobile Drag Handle */}
        <div className="w-10 h-1 bg-[#2A3241] mx-auto mb-3 sm:hidden" />

        {/* Drawer Header */}
        <div className="flex items-start justify-between gap-4 pb-4 border-b border-[#1E2530]">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-[#8A94A6]">
              <span>QUANTITATIVE MICROSTRUCTURE INSPECTOR</span>
              <span aria-hidden="true">·</span>
              <span className={token.universe_mode === 'ACTIVE_ULTRA_LIQUID' ? 'text-[#10B981]' : 'text-[#F59E0B]'}>
                {token.universe_mode === 'ACTIVE_ULTRA_LIQUID' ? 'ACTIVE 10 UNIVERSE' : 'HARVEST & RETIRE (SOLO VENDITA IN PROFITTO)'}
              </span>
              <span aria-hidden="true">·</span>
              <span>REGIME: {token.regime}</span>
            </div>
            <h3 className="font-editorial text-2xl sm:text-3xl font-bold text-[#F3F4F6] mt-1">
              {token.inst_id} — Mid ${token.mid_price} USDC
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="min-h-[44px] min-w-[44px] flex items-center justify-center border border-[#1E2530] bg-[#07080A] text-[#8A94A6] hover:text-[#F3F4F6] hover:border-[#F59E0B]"
            aria-label="Chiudi Inspector"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Top KPI Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-4 border-b border-[#1E2530] font-mono tabular-nums text-xs">
          <div className="bg-[#07080A] border border-[#1E2530] p-3">
            <span className="text-[#8A94A6] block">STOIKOV MICRO-PRICE</span>
            <span className="text-base font-semibold text-[#F3F4F6]">${token.micro_price}</span>
            <span className="block text-[11px] text-[#8A94A6] mt-0.5">Spread: {token.spread_bps} bps</span>
          </div>
          <div className="bg-[#07080A] border border-[#1E2530] p-3">
            <span className="text-[#8A94A6] block">COST-BASIS FLOOR</span>
            <span className="text-base font-semibold text-[#FCD34D]">${token.cost_basis_floor_px}</span>
            <span className="block text-[11px] text-[#8A94A6] mt-0.5">AvgPx: ${token.open_avg_px}</span>
          </div>
          <div className="bg-[#07080A] border border-[#1E2530] p-3">
            <span className="text-[#8A94A6] block">PREDICTED RETURN</span>
            <span
              className={`text-base font-semibold ${
                token.predicted_return_bps >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
              }`}
            >
              {token.predicted_return_bps >= 0 ? '+' : ''}
              {token.predicted_return_bps} bps
            </span>
            <span className="block text-[11px] text-[#8A94A6] mt-0.5">
              Kronos 1h: {token.kronos_1h_bps >= 0 ? '+' : ''}
              {token.kronos_1h_bps} bps
            </span>
          </div>
          <div className="bg-[#07080A] border border-[#1E2530] p-3">
            <span className="text-[#8A94A6] block">OPPORTUNITY SCORE</span>
            <span className="text-base font-semibold text-[#FCD34D]">
              {token.opp_score >= 0 ? '+' : ''}
              {token.opp_score}
            </span>
            <span className="block text-[11px] text-[#8A94A6] mt-0.5">
              Peso Inv: {token.inv_weight_pct}% (${token.holding_eq_usd})
            </span>
          </div>
        </div>

        {/* Section 1: 4-Factor Predictive Blend (core/predictor.py) */}
        <div className="py-4 border-b border-[#1E2530]">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-[#FCD34D] flex items-center gap-1.5">
              <Cpu className="w-4 h-4" />
              01. FUSIONE PREDITTIVA A 4 FATTORI (core/predictor.py)
            </span>
            <span className="text-xs font-mono tabular-nums text-[#E6E8EC]">
              Somma Pesata: {token.predicted_return_bps >= 0 ? '+' : ''}
              {token.predicted_return_bps} bps
            </span>
          </div>

          <div className="space-y-2.5">
            {factors.map((f) => {
              const barPct = Math.min(100, Math.max(8, Math.abs(f.rawBps) * 3.8));
              const isPos = f.weightedBps >= 0;
              return (
                <div key={f.label} className="bg-[#07080A] border border-[#1E2530] p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-mono tabular-nums">
                    <span className="text-[#E6E8EC] font-medium">{f.label}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-[#8A94A6]">
                        Segnale Grezzo: {f.rawBps >= 0 ? '+' : ''}
                        {f.rawBps} bps
                      </span>
                      <span className={isPos ? 'text-[#10B981] font-semibold' : 'text-[#EF4444] font-semibold'}>
                        Contributo: {isPos ? '+' : ''}
                        {f.weightedBps} bps
                      </span>
                    </div>
                  </div>
                  <div className="w-full h-1.5 bg-[#151A22] mt-2 overflow-hidden">
                    <div
                      className={`h-full ${isPos ? 'bg-[#10B981]' : 'bg-[#EF4444]'}`}
                      style={{ width: `${barPct}%` }}
                    />
                  </div>
                  <p className="text-[11px] text-[#8A94A6] mt-1.5">{f.desc}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Section 2: Kronos-mini Multi-Horizon & OrderBook Price Ladder */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 py-4 border-b border-[#1E2530]">
          <div className="bg-[#07080A] border border-[#1E2530] p-3.5 font-mono tabular-nums text-xs space-y-2">
            <div className="text-[#FCD34D] font-semibold flex items-center gap-1.5">
              <Layers className="w-4 h-4" />
              ORACOLO LOCALE KRONOS-MINI (4.1M)
            </div>
            <div className="flex justify-between pt-1">
              <span className="text-[#8A94A6]">Micro Forecast 1h (180×5m):</span>
              <span className={token.kronos_1h_bps >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                {token.kronos_1h_bps >= 0 ? '+' : ''}
                {token.kronos_1h_bps} bps
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#8A94A6]">Macro Forecast 2h (120×15m):</span>
              <span className={token.kronos_2h_macro_bps >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                {token.kronos_2h_macro_bps >= 0 ? '+' : ''}
                {token.kronos_2h_macro_bps} bps
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#8A94A6]">Envelope High / Low (1h):</span>
              <span className="text-[#E6E8EC]">
                +{token.kronos_high_bps} bps / {token.kronos_low_bps} bps
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#8A94A6]">Allineamento Multi-Orizzonte:</span>
              <span className={token.horizon_aligned ? 'text-[#10B981]' : 'text-[#F59E0B]'}>
                {token.horizon_aligned ? 'ALLINEATO (Turbo-Scalp +20%)' : 'NON ALLINEATO'}
              </span>
            </div>
          </div>

          <div className="bg-[#07080A] border border-[#1E2530] p-3.5 font-mono tabular-nums text-xs space-y-2">
            <div className="text-[#FCD34D] font-semibold flex items-center gap-1.5">
              <ShieldAlert className="w-4 h-4" />
              SCALA ESECUZIONE POST-ONLY MAKER
            </div>
            <div className="flex justify-between pt-1">
              <span className="text-[#8A94A6]">Trappola BUY (-{token.buy_offset_bps} bps):</span>
              <span className="text-[#10B981]">
                {token.active_buy_px ? `$${token.active_buy_px} USDC` : 'SOSPESO (Guardia Attiva)'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#8A94A6]">Target SELL (+{token.sell_tp_bps} bps):</span>
              <span className="text-[#FCD34D]">
                {token.active_sell_px ? `$${token.active_sell_px} USDC` : 'N/A'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#8A94A6]">Sussidio Ratchet Applicato:</span>
              <span className="text-[#10B981]">${token.ratchet_subsidy_applied_usd.toFixed(2)} USDC</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#8A94A6]">Anti-Stacking Guard ($17.50 max):</span>
              <span className={token.anti_stacking_locked ? 'text-[#F59E0B]' : 'text-[#10B981]'}>
                {token.anti_stacking_locked ? 'TETTO RAGGIUNTO ($17.50+)' : 'CAPACITÀ LIBERA'}
              </span>
            </div>
          </div>
        </div>

        {/* Section 3: Opportunity-Ranked Cash Sweeper Formula Breakdown */}
        <div className="pt-4 font-mono tabular-nums text-xs">
          <div className="flex items-center justify-between text-[#8A94A6] mb-2">
            <span>FORMULA OPPORTUNITY SCORE (CASH SWEEPER BINARIO C)</span>
            <span className="text-[#FCD34D] font-semibold flex items-center gap-1">
              OppScore = {token.opp_score >= 0 ? '+' : ''}
              {token.opp_score}
              <ArrowUpRight className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="bg-[#07080A] border border-[#1E2530] p-3 text-[11px] text-[#E6E8EC] leading-relaxed">
            OppScore = Pred_bps ({token.predicted_return_bps >= 0 ? '+' : ''}
            {token.predicted_return_bps}) + 15·OFI ({ofiTerm >= 0 ? '+' : ''}
            {ofiTerm}) + LiqBonus ({liqBonus >= 0 ? '+' : ''}
            {liqBonus}) + Aligned ({token.horizon_aligned ? '+5.0' : '0.0'}) − 20·VPIN ({vpinPenalty}) − 50·InvWeight (
            {invPenalty}) = <strong className="text-[#FCD34D]">{token.opp_score}</strong>
          </div>
        </div>
      </div>
    </div>
  );
};

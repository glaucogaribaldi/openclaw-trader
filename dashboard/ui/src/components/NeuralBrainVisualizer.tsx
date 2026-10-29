import React, { useState } from 'react';
import type { TokenTelemetry } from '../types/predator';

interface Props {
  telemetry: TokenTelemetry[];
  btcLeadLagBps: number;
}

type DroidSubsystem = 'CRANIAL_KRONOS' | 'OPTIC_L2_VISOR' | 'VOCAL_BSQ' | 'THORACIC_RLS' | 'ACTUATOR_ARMS';

export const NeuralBrainVisualizer: React.FC<Props> = ({ telemetry, btcLeadLagBps }) => {
  const sorted = [...telemetry].sort((a, b) => b.opp_score - a.opp_score);
  const [selectedPair, setSelectedPair] = useState<string>(sorted[0]?.inst_id || 'SUI-USDC');
  const [selectedSub, setSelectedSub] = useState<DroidSubsystem>('CRANIAL_KRONOS');

  const activeToken = telemetry.find((t) => t.inst_id === selectedPair) || sorted[0];
  if (!activeToken) return null;

  const tpProb = activeToken.tp_touch_prob_1h ?? (activeToken.kronos_high_bps >= 26 ? 0.67 : 0.33);
  const zScore = activeToken.kronos_zscore_1h ?? Number((activeToken.kronos_1h_bps / 32).toFixed(2));
  const volSurge = activeToken.pred_volume_surge_ratio ?? 1.05;
  const perpBasis = activeToken.perp_basis_bps ?? 0.0;

  const isBullish = activeToken.opp_score >= 0;
  const isToxic = activeToken.vpin_toxicity >= 0.65 || activeToken.regime === 'TOXIC_DIP_DEFENSE';
  const primaryGlow = isBullish ? '#10B981' : isToxic ? '#EF4444' : '#38BDF8';
  const visorColor = activeToken.ofi_norm >= 0 ? '#10B981' : '#EF4444';
  const cortexColor = activeToken.kronos_1h_bps >= 0 ? '#38BDF8' : '#F59E0B';

  const fmtSigned = (val: number, decimals = 2, suffix = '') => {
    const abs = Math.abs(val).toFixed(decimals);
    return `${val >= 0 ? '+' : '-'}${abs}${suffix}`;
  };

  const SUBSYSTEM_INFO: Record<
    DroidSubsystem,
    { code: string; title: string; spec: string; desc: string }
  > = {
    CRANIAL_KRONOS: {
      code: 'SYS-01 // CRANIAL POSITRONIC CORTEX',
      title: 'KRONOS-MINI (4.1M) PRE-MEAN TRAJECTORY CORTEX',
      spec: 'Tsinghua arXiv:2508.02739v1 · 4× Transformer Blocks (d=256, RoPE, SwiGLU) · Tensor (3, 12, 6)',
      desc: `Il lobo superiore del droide elabora 300×5m + 160×15m + 80×1H candele per ${activeToken.inst_id}: estrae il tensore pre-media (3, 12, 6) calcolando Kronos 1h (${fmtSigned(
        activeToken.kronos_1h_bps,
        1,
        ' bps'
      )}), Kronos 2h (${fmtSigned(
        activeToken.kronos_2h_macro_bps,
        1,
        ' bps'
      )}), Probabilità Tocco TP ≥+26bps (${(tpProb * 100).toFixed(0)}%), Z-Score (${fmtSigned(
        zScore,
        2
      )}) e Allineamento a 3 Orizzonti (${activeToken.horizon_aligned ? 'CONFERMATO' : 'VETO DIFENSIVO'}).`,
    },
    OPTIC_L2_VISOR: {
      code: 'SYS-02 // PHOTORECEPTOR L2 & PERP VISOR',
      title: 'SENSORE OTTICO ORDERBOOK L2 & RADAR PERPETUAL SWAP',
      spec: '5-Level Cont-Stoikov OFI · Easley VPIN Toxicity · Hawkes λ Burst · 524 USDT-SWAP Basis Radar',
      desc: `Il visore ottico del droide scansiona ogni 15s il book L2 di ${activeToken.inst_id}: Mid $${
        activeToken.mid_price
      } (µPx $${activeToken.micro_price}), OFI L2 ${fmtSigned(
        activeToken.ofi_norm,
        2
      )}, Tossicità VPIN ${activeToken.vpin_toxicity.toFixed(2)}, Hawkes λ ${
        activeToken.hawkes_intensity
      }, Basis Perpetual-Spot ${fmtSigned(perpBasis, 1, ' bps')} e Radar BTC ${fmtSigned(
        btcLeadLagBps,
        2,
        ' bps'
      )}.`,
    },
    VOCAL_BSQ: {
      code: 'SYS-03 // CERVICAL BSQ QUANTIZER (2²⁰)',
      title: 'TOKENIZZATORE SFERICO BINARIO (BSQ HYPERPLANE CODEC)',
      spec: 's1_bits=10 (1.024 Coarse Sub-Tokens) × s2_bits=10 (1.024 Fine Sub-Tokens) · .eval() Deterministic Lock',
      desc: `La giunzione cervicale traduce il linguaggio continuo del mercato [Open, High, Low, Close, Volume, Amount] normalizzato in Z-Score [-5, +5] in 1.048.576 sub-token sferici (s1, s2), alimentando il cervello Transformer senza rumore stocastico.`,
    },
    THORACIC_RLS: {
      code: 'SYS-04 // THORACIC KYBER REACTOR (ONLINE RLS + KALMAN)',
      title: 'REATTORE TORACICO STREAMING RLS (λ=0.985) & FILTRO DI KALMAN',
      spec: 'Matrice Covarianza P_t (6×6) Persistente · Vincoli Positività w[OBI,OFI,α] ≥ +0.5 · Intercetta [-2.5, +2.5]',
      desc: `Il cuore cibernetico nel torace aggiorna in O(d²) i pesi predittivi ad ogni movimento ≥ 1.2 bps: contributo istantaneo RLS/Kalman per ${
        activeToken.inst_id
      } = ${fmtSigned(activeToken.rls_kalman_bps, 2, ' bps')} | LLM Council = ${fmtSigned(
        activeToken.llm_council_bps,
        2,
        ' bps'
      )} | Previsione Fusa = ${fmtSigned(activeToken.predicted_return_bps, 2, ' bps')}.`,
    },
    ACTUATOR_ARMS: {
      code: 'SYS-05 // TACTICAL MAKER ACTUATORS (OKX SPOT EEA)',
      title: 'BRACCI ESECUTORI 100% POST-ONLY MAKER & SCUDO FEE-SAFE',
      spec: '_ceil_px() Floor ≥ +24/+25 bps (> 20 bps Maker Fee) · clOrdId Idempotency · Dec 31 Cashout Engine',
      desc: `I bracci operativi piazzano ordini esclusivamente Post-Only Maker: OppScore = ${fmtSigned(
        activeToken.opp_score,
        2
      )} (${activeToken.regime}) | Cost-Basis Floor = $${
        activeToken.cost_basis_floor_px
      } | Ordine SELL Attivo = ${
        activeToken.active_sell_px ? '$' + activeToken.active_sell_px : 'In Attesa'
      } | Trap BUY Offset = -${activeToken.buy_offset_bps} bps.`,
    },
  };

  const activeSpec = SUBSYSTEM_INFO[selectedSub];

  return (
    <div className="border border-[#0E3A5A] bg-[#060B14] p-4 sm:p-6 space-y-5 font-mono holo-glow relative overflow-hidden">
      {/* Corner Star Wars Tactical Brackets */}
      <div className="pointer-events-none absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-[#38BDF8]" />
      <div className="pointer-events-none absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 border-[#38BDF8]" />
      <div className="pointer-events-none absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2 border-[#38BDF8]" />
      <div className="pointer-events-none absolute bottom-0 right-0 w-4 h-4 border-b-2 border-r-2 border-[#38BDF8]" />

      {/* Top HoloNet Command Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 pb-3 border-b border-[#0E3A5A]">
        <div>
          <div className="text-[11px] text-[#38BDF8] flex items-center gap-2 tracking-wider">
            <span className="inline-block w-2 h-2 rounded-full bg-[#38BDF8] animate-ping" />
            <span>HOLONET BIOMECHANICAL SCAN // DROID UNIT: IG-88 QUANT PREDATOR v8.8</span>
          </div>
          <h3 className="font-editorial text-lg sm:text-xl font-bold text-[#E2F1FF] mt-1 tracking-wide">
            androide quantitativo &amp; corteccia neurale realtime — bersaglio attivo:{' '}
            <span className="text-[#38BDF8]">{activeToken.inst_id}</span>
          </h3>
        </div>

        {/* 12 Target Sector Selector Pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          {sorted.map((t) => {
            const isSel = selectedPair === t.inst_id;
            const pos = t.opp_score >= 0;
            return (
              <button
                key={t.inst_id}
                type="button"
                onClick={() => setSelectedPair(t.inst_id)}
                className={`px-2.5 py-1 text-[11px] border transition-all cursor-pointer ${
                  isSel
                    ? 'bg-[#0284C7] text-[#F8FAFC] border-[#38BDF8] font-bold shadow-[0_0_12px_rgba(56,189,248,0.5)]'
                    : 'bg-[#04070D] text-[#94A3B8] border-[#0E3A5A] hover:border-[#38BDF8] hover:text-[#E2F1FF]'
                }`}
              >
                <span>{t.symbol}</span>{' '}
                <span className={isSel ? 'text-[#A7F3D0]' : pos ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                  {t.opp_score >= 0 ? `+${t.opp_score}` : t.opp_score}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* MAIN STAR WARS HUMANOID DROID + REALTIME CORTEX HUD */}
      <div className="w-full overflow-x-auto bg-[#04070D] border border-[#0E3A5A] p-3">
        <svg viewBox="0 0 1060 540" className="w-full min-w-[860px] h-auto block select-none">
          <defs>
            <radialGradient id="holoCoreGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor={primaryGlow} stopOpacity="0.45" />
              <stop offset="65%" stopColor="#0284C7" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#04070D" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="droidArmor" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0B192C" />
              <stop offset="100%" stopColor="#050C16" />
            </linearGradient>
            <linearGradient id="brainCortexGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#0EA5E9" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#6366F1" stopOpacity="0.2" />
            </linearGradient>
          </defs>

          {/* Holographic Floor Projection Rings */}
          <ellipse cx="530" cy="505" rx="220" ry="20" fill="none" stroke="#0E3A5A" strokeWidth="1.5" strokeDasharray="8 4" />
          <ellipse cx="530" cy="505" rx="155" ry="12" fill="none" stroke="#38BDF8" strokeWidth="1" opacity="0.5" />
          <circle cx="530" cy="240" r="210" fill="url(#holoCoreGlow)" />

          {/* ===================================================================== */}
          {/* LEFT CALLOUT HUD PANELS (CONNECTED TO DROID HEAD, EYES & NECK)        */}
          {/* ===================================================================== */}

          {/* Left Callout 1: Cranial Kronos Cortex */}
          <g onClick={() => setSelectedSub('CRANIAL_KRONOS')} className="cursor-pointer">
            <rect
              x="16"
              y="22"
              width="290"
              height="142"
              rx="4"
              fill="#06101E"
              stroke={selectedSub === 'CRANIAL_KRONOS' ? '#38BDF8' : '#0E3A5A'}
              strokeWidth={selectedSub === 'CRANIAL_KRONOS' ? '2.2' : '1.2'}
            />
            <text x="28" y="43" fill="#38BDF8" fontSize="11" fontWeight="bold">
              [01] CORTECCIA KRONOS-MINI (4.1M)
            </text>
            <text x="28" y="60" fill="#64748B" fontSize="9.5">
              PRE-MEAN TENSOR (3, 12, 6) · TSINGHUA MODEL
            </text>
            <text
              x="28"
              y="81"
              fill={activeToken.kronos_1h_bps >= 0 ? '#10B981' : '#EF4444'}
              fontSize="11"
              fontWeight="bold"
            >
              • Previsione 1h (5m×12): {fmtSigned(activeToken.kronos_1h_bps, 2, ' bps')}
            </text>
            <text
              x="28"
              y="99"
              fill={activeToken.kronos_2h_macro_bps >= 0 ? '#10B981' : '#EF4444'}
              fontSize="10.5"
            >
              • Orizzonte 2h (15m×8): {fmtSigned(activeToken.kronos_2h_macro_bps, 2, ' bps')}
            </text>
            <text x="28" y="117" fill="#FCD34D" fontSize="10.5">
              • Probabilità Tocco TP: {(tpProb * 100).toFixed(0)}% (Z-Score: {fmtSigned(zScore, 2)})
            </text>
            <text
              x="28"
              y="135"
              fill={activeToken.horizon_aligned ? '#10B981' : '#F59E0B'}
              fontSize="10"
              fontWeight="bold"
            >
              • 3-Orizzonti (1h/2h/12h): {activeToken.horizon_aligned ? 'ALLINEATI ✓' : 'GUARDIA ATTIVA ⚡'}
            </text>
            {/* Leader Line to Droid Brain */}
            <polyline
              points="306,82 395,82 478,90"
              fill="none"
              stroke="#38BDF8"
              strokeWidth="1.6"
              className="holo-synapse"
            />
            <circle cx="478" cy="90" r="4" fill="#38BDF8" />
          </g>

          {/* Left Callout 2: Optic L2 & Perp Visor */}
          <g onClick={() => setSelectedSub('OPTIC_L2_VISOR')} className="cursor-pointer">
            <rect
              x="16"
              y="182"
              width="290"
              height="152"
              rx="4"
              fill="#06101E"
              stroke={selectedSub === 'OPTIC_L2_VISOR' ? '#38BDF8' : '#0E3A5A'}
              strokeWidth={selectedSub === 'OPTIC_L2_VISOR' ? '2.2' : '1.2'}
            />
            <text x="28" y="203" fill="#38BDF8" fontSize="11" fontWeight="bold">
              [02] VISORE OTTICO L2 &amp; PERP RADAR
            </text>
            <text x="28" y="220" fill="#64748B" fontSize="9.5">
              CONT-STOIKOV OFI · VPIN · 524 SWAP TICKERS
            </text>
            <text x="28" y="240" fill="#E2F1FF" fontSize="10.5">
              • Mid Price: ${activeToken.mid_price} (µPx: ${activeToken.micro_price})
            </text>
            <text
              x="28"
              y="258"
              fill={activeToken.ofi_norm >= 0 ? '#10B981' : '#EF4444'}
              fontSize="11"
              fontWeight="bold"
            >
              • Flusso Ordini L2 (OFI): {fmtSigned(activeToken.ofi_norm, 2)}
            </text>
            <text
              x="28"
              y="276"
              fill={activeToken.vpin_toxicity >= 0.55 ? '#EF4444' : '#10B981'}
              fontSize="10.5"
            >
              • Tossicità VPIN: {activeToken.vpin_toxicity.toFixed(2)} · Hawkes λ: {activeToken.hawkes_intensity}
            </text>
            <text
              x="28"
              y="294"
              fill={perpBasis >= 0 ? '#FCD34D' : '#38BDF8'}
              fontSize="10.5"
            >
              • Basis Perp-Spot: {fmtSigned(perpBasis, 1, ' bps')} · VolSurge: {volSurge}x
            </text>
            <text
              x="28"
              y="312"
              fill={btcLeadLagBps >= 0 ? '#10B981' : '#EF4444'}
              fontSize="10.5"
            >
              • Radar BTC-USDC: {fmtSigned(btcLeadLagBps, 2, ' bps')}
            </text>
            {/* Leader Line to Droid Optic Visor */}
            <polyline
              points="306,245 415,245 488,136"
              fill="none"
              stroke={visorColor}
              strokeWidth="1.6"
              className="holo-synapse"
            />
            <circle cx="488" cy="136" r="4" fill={visorColor} />
          </g>

          {/* Left Callout 3: Cervical BSQ Tokenizer */}
          <g onClick={() => setSelectedSub('VOCAL_BSQ')} className="cursor-pointer">
            <rect
              x="16"
              y="352"
              width="290"
              height="128"
              rx="4"
              fill="#06101E"
              stroke={selectedSub === 'VOCAL_BSQ' ? '#38BDF8' : '#0E3A5A'}
              strokeWidth={selectedSub === 'VOCAL_BSQ' ? '2.2' : '1.2'}
            />
            <text x="28" y="373" fill="#38BDF8" fontSize="11" fontWeight="bold">
              [03] VOCODER SFERICO BSQ (2²⁰ TOKEN)
            </text>
            <text x="28" y="390" fill="#64748B" fontSize="9.5">
              BINARY SPHERICAL QUANTIZER · .EVAL() DETERMINISTICO
            </text>
            <text x="28" y="410" fill="#E2F1FF" fontSize="10.5">
              • Input: 300×5m + 160×15m + 80×1H Candele
            </text>
            <text x="28" y="428" fill="#E2F1FF" fontSize="10.5">
              • Sub-Token Coarse s1: 1.024 stati (10-bit)
            </text>
            <text x="28" y="446" fill="#E2F1FF" fontSize="10.5">
              • Sub-Token Fine s2: 1.024 stati (10-bit)
            </text>
            <text x="28" y="464" fill="#10B981" fontSize="10">
              • Envelope 1h: +{activeToken.kronos_high_bps} / -{activeToken.kronos_low_bps} bps
            </text>
            {/* Leader Line to Droid Neck Vocoder */}
            <polyline
              points="306,405 425,405 508,184"
              fill="none"
              stroke="#818CF8"
              strokeWidth="1.6"
              className="holo-synapse"
            />
            <circle cx="508" cy="184" r="4" fill="#818CF8" />
          </g>

          {/* ===================================================================== */}
          {/* CENTER: HUMANOID QUANT DROID ANATOMY & REALTIME NEURAL CORTEX         */}
          {/* ===================================================================== */}

          {/* DROID HEAD / TRANSPARENT CRANIAL DOME (KRONOS CORTEX) */}
          <g onClick={() => setSelectedSub('CRANIAL_KRONOS')} className="cursor-pointer">
            {/* Outer Cranial Armor & Dome */}
            <path
              d="M 472 115 C 472 52, 588 52, 588 115 L 582 168 L 555 182 L 505 182 L 478 168 Z"
              fill="url(#droidArmor)"
              stroke="#38BDF8"
              strokeWidth="2.2"
            />
            {/* Transparent Glowing Neural Brain Hemisphere */}
            <path
              d="M 482 112 C 482 64, 578 64, 578 112 Z"
              fill="url(#brainCortexGrad)"
              stroke={cortexColor}
              strokeWidth="1.5"
            />
            {/* Neural Nodes & Synapses Inside the Brain */}
            <line x1="498" y1="98" x2="518" y2="80" stroke="#38BDF8" strokeWidth="1.4" />
            <line x1="518" y1="80" x2="542" y2="80" stroke="#38BDF8" strokeWidth="1.4" />
            <line x1="542" y1="80" x2="562" y2="98" stroke="#38BDF8" strokeWidth="1.4" />
            <line x1="518" y1="80" x2="530" y2="102" stroke={primaryGlow} strokeWidth="1.6" />
            <line x1="542" y1="80" x2="530" y2="102" stroke={primaryGlow} strokeWidth="1.6" />
            <line x1="498" y1="98" x2="530" y2="102" stroke="#38BDF8" strokeWidth="1.3" />
            <line x1="562" y1="98" x2="530" y2="102" stroke="#38BDF8" strokeWidth="1.3" />

            <circle cx="498" cy="98" r="4" fill="#38BDF8" />
            <circle cx="518" cy="80" r="4.5" fill={cortexColor} />
            <circle cx="542" cy="80" r="4.5" fill={cortexColor} />
            <circle cx="562" cy="98" r="4" fill="#38BDF8" />
            <circle cx="530" cy="102" r="6" fill={primaryGlow} />

            {/* Telemetry Antenna (Left Ear) */}
            <line x1="466" y1="125" x2="466" y2="62" stroke="#38BDF8" strokeWidth="2" />
            <circle cx="466" cy="58" r="4" fill="#EF4444" />
          </g>

          {/* DROID OPTIC VISOR (L2 ORDERBOOK & VPIN SCANNER) */}
          <g onClick={() => setSelectedSub('OPTIC_L2_VISOR')} className="cursor-pointer">
            <polygon
              points="484,126 576,126 568,144 492,144"
              fill="#04070D"
              stroke={visorColor}
              strokeWidth="2"
            />
            {/* Glowing Cybernetic Eyes */}
            <rect x="494" y="131" width="26" height="8" rx="2" fill={visorColor} />
            <rect x="540" y="131" width="26" height="8" rx="2" fill={visorColor} />
            <circle cx="530" cy="135" r="3" fill="#FCD34D" />
          </g>

          {/* DROID VOCODER & CERVICAL SPINE (BSQ 2^20 QUANTIZER) */}
          <g onClick={() => setSelectedSub('VOCAL_BSQ')} className="cursor-pointer">
            <rect x="506" y="154" width="48" height="16" rx="2" fill="#091526" stroke="#818CF8" strokeWidth="1.4" />
            <line x1="514" y1="157" x2="514" y2="167" stroke="#818CF8" strokeWidth="1.5" />
            <line x1="522" y1="157" x2="522" y2="167" stroke="#38BDF8" strokeWidth="1.5" />
            <line x1="530" y1="157" x2="530" y2="167" stroke="#818CF8" strokeWidth="1.5" />
            <line x1="538" y1="157" x2="538" y2="167" stroke="#38BDF8" strokeWidth="1.5" />
            <line x1="546" y1="157" x2="546" y2="167" stroke="#818CF8" strokeWidth="1.5" />
            {/* Neck Pistons */}
            <rect x="508" y="182" width="44" height="22" fill="#0B192C" stroke="#38BDF8" strokeWidth="1.5" />
            <line x1="530" y1="108" x2="530" y2="265" stroke={primaryGlow} strokeWidth="2.5" className="holo-synapse" />
          </g>

          {/* DROID THORACIC CHEST ARMOR & KYBER RLS/KALMAN REACTOR */}
          <g onClick={() => setSelectedSub('THORACIC_RLS')} className="cursor-pointer">
            {/* Shoulder Pauldrons */}
            <polygon points="418,212 465,204 455,252 410,242" fill="#0B192C" stroke="#38BDF8" strokeWidth="1.8" />
            <polygon points="642,212 595,204 605,252 650,242" fill="#0B192C" stroke="#38BDF8" strokeWidth="1.8" />

            {/* Main Torso Chassis */}
            <polygon
              points="455,204 605,204 588,348 472,348"
              fill="url(#droidArmor)"
              stroke="#38BDF8"
              strokeWidth="2.2"
            />
            {/* Internal Rib Circuitry */}
            <line x1="468" y1="235" x2="495" y2="250" stroke="#0E3A5A" strokeWidth="2" />
            <line x1="592" y1="235" x2="565" y2="250" stroke="#0E3A5A" strokeWidth="2" />
            <line x1="474" y1="295" x2="498" y2="285" stroke="#0E3A5A" strokeWidth="2" />
            <line x1="586" y1="295" x2="562" y2="285" stroke="#0E3A5A" strokeWidth="2" />

            {/* Glowing Thoracic Kyber Core (RLS + Kalman Fusion) */}
            <circle cx="530" cy="268" r="34" fill="#04070D" stroke={primaryGlow} strokeWidth="2.5" />
            <circle cx="530" cy="268" r="24" fill="none" stroke="#38BDF8" strokeWidth="1.5" strokeDasharray="6 4" />
            <circle cx="530" cy="268" r="12" fill={primaryGlow} opacity="0.85" />
            <text x="530" y="272" textAnchor="middle" fill="#04070D" fontSize="9.5" fontWeight="bold">
              RLS
            </text>
            <text x="530" y="325" textAnchor="middle" fill="#38BDF8" fontSize="10" fontWeight="bold">
              {activeToken.symbol} {fmtSigned(activeToken.opp_score, 1)}
            </text>
          </g>

          {/* DROID ARMS, WAIST & PELVIC STABILIZER (ACTUATORS & RISK SHIELD) */}
          <g onClick={() => setSelectedSub('ACTUATOR_ARMS')} className="cursor-pointer">
            {/* Left Arm (BUY Trap Actuator) */}
            <rect x="415" y="252" width="28" height="82" rx="6" fill="#091526" stroke="#10B981" strokeWidth="1.8" />
            <circle cx="429" cy="342" r="10" fill="#04070D" stroke="#10B981" strokeWidth="2" />
            <rect x="408" y="354" width="34" height="65" rx="5" fill="#0B192C" stroke="#10B981" strokeWidth="1.8" />
            <text x="425" y="390" textAnchor="middle" fill="#10B981" fontSize="8.5" fontWeight="bold">
              BUY
            </text>

            {/* Right Arm (SELL TP Floor Actuator) */}
            <rect x="617" y="252" width="28" height="82" rx="6" fill="#091526" stroke="#38BDF8" strokeWidth="1.8" />
            <circle cx="631" cy="342" r="10" fill="#04070D" stroke="#38BDF8" strokeWidth="2" />
            <rect x="618" y="354" width="34" height="65" rx="5" fill="#0B192C" stroke="#38BDF8" strokeWidth="1.8" />
            <text x="635" y="390" textAnchor="middle" fill="#38BDF8" fontSize="8.5" fontWeight="bold">
              SELL
            </text>

            {/* Waist & Pelvic Gyroscope */}
            <polygon points="478,354 582,354 568,402 492,402" fill="#091526" stroke="#0E3A5A" strokeWidth="1.8" />
            {/* Upper Legs */}
            <rect x="484" y="406" width="34" height="88" rx="4" fill="#0B192C" stroke="#38BDF8" strokeWidth="1.6" />
            <rect x="542" y="406" width="34" height="88" rx="4" fill="#0B192C" stroke="#38BDF8" strokeWidth="1.6" />
          </g>

          {/* ===================================================================== */}
          {/* RIGHT CALLOUT HUD PANELS (CONNECTED TO TORSO CORE & ARMS)             */}
          {/* ===================================================================== */}

          {/* Right Callout 1: Thoracic RLS + Kalman Core */}
          <g onClick={() => setSelectedSub('THORACIC_RLS')} className="cursor-pointer">
            <rect
              x="748"
              y="32"
              width="296"
              height="168"
              rx="4"
              fill="#06101E"
              stroke={selectedSub === 'THORACIC_RLS' ? '#38BDF8' : '#0E3A5A'}
              strokeWidth={selectedSub === 'THORACIC_RLS' ? '2.2' : '1.2'}
            />
            <text x="760" y="53" fill="#38BDF8" fontSize="11" fontWeight="bold">
              [04] REATTORE TORACICO RLS + KALMAN
            </text>
            <text x="760" y="70" fill="#64748B" fontSize="9.5">
              ONLINE LEARNING O(d²) · MATRICE P_t SALVATA
            </text>
            <text
              x="760"
              y="92"
              fill={activeToken.rls_kalman_bps >= 0 ? '#10B981' : '#EF4444'}
              fontSize="11"
              fontWeight="bold"
            >
              • Impulso RLS + Kalman (45%): {fmtSigned(activeToken.rls_kalman_bps, 2, ' bps')}
            </text>
            <text
              x="760"
              y="110"
              fill={activeToken.kronos_blend_bps >= 0 ? '#10B981' : '#EF4444'}
              fontSize="10.5"
            >
              • Impulso Kronos 3H (35%): {fmtSigned(activeToken.kronos_blend_bps, 2, ' bps')}
            </text>
            <text x="760" y="128" fill="#E2F1FF" fontSize="10.5">
              • Council + BTC Radar (20%): {fmtSigned(activeToken.llm_council_bps + activeToken.btc_lead_lag_contrib_bps, 2, ' bps')}
            </text>
            <text
              x="760"
              y="148"
              fill={activeToken.predicted_return_bps >= 0 ? '#10B981' : '#EF4444'}
              fontSize="11.5"
              fontWeight="bold"
            >
              • RENDIMENTO ATTESO FUSO: {fmtSigned(activeToken.predicted_return_bps, 2, ' bps')}
            </text>
            <text x="760" y="168" fill="#38BDF8" fontSize="10">
              • Vincoli Pesi: w[OBI,OFI,α] ≥ +0.5 · Bias ∈ [-2.5,+2.5]
            </text>
            <polyline
              points="748,135 660,135 564,268"
              fill="none"
              stroke={primaryGlow}
              strokeWidth="1.8"
              className="holo-synapse"
            />
            <circle cx="564" cy="268" r="4" fill={primaryGlow} />
          </g>

          {/* Right Callout 2: Maker Tactical Actuator Arms */}
          <g onClick={() => setSelectedSub('ACTUATOR_ARMS')} className="cursor-pointer">
            <rect
              x="748"
              y="222"
              width="296"
              height="252"
              rx="4"
              fill="#06101E"
              stroke={selectedSub === 'ACTUATOR_ARMS' ? '#38BDF8' : '#0E3A5A'}
              strokeWidth={selectedSub === 'ACTUATOR_ARMS' ? '2.2' : '1.2'}
            />
            <text x="760" y="243" fill="#38BDF8" fontSize="11" fontWeight="bold">
              [05] ATTUATORI MAKER &amp; SCUDO FEE-SAFE
            </text>
            <text x="760" y="260" fill="#64748B" fontSize="9.5">
              100% POST-ONLY MAKER · ZERO VENDITE IN PERDITA
            </text>
            <text
              x="760"
              y="283"
              fill={activeToken.opp_score >= 0 ? '#10B981' : '#EF4444'}
              fontSize="12"
              fontWeight="bold"
            >
              • OPPSCORE FINALE: {fmtSigned(activeToken.opp_score, 2)}
            </text>
            <text x="760" y="303" fill="#E2F1FF" fontSize="10.5">
              • Regime Tattico: {activeToken.regime}
            </text>
            <text x="760" y="323" fill="#E2F1FF" fontSize="10.5">
              • Prezzo Medio Carico: ${activeToken.open_avg_px}
            </text>
            <text x="760" y="343" fill="#FCD34D" fontSize="10.5" fontWeight="bold">
              • Floor Anti-Perdita (_ceil_px): ${activeToken.cost_basis_floor_px}
            </text>
            <text x="760" y="363" fill="#10B981" fontSize="11" fontWeight="bold">
              • Braccio SELL Attivo: {activeToken.active_sell_px ? `$${activeToken.active_sell_px}` : 'Nessuno'}
            </text>
            <text x="760" y="383" fill="#38BDF8" fontSize="10.5">
              • Braccio BUY Offset: -{activeToken.buy_offset_bps} bps (TP +{activeToken.sell_tp_bps} bps)
            </text>
            <text
              x="760"
              y="403"
              fill={activeToken.unrealized_usd >= 0 ? '#10B981' : '#EF4444'}
              fontSize="10.5"
            >
              • Posizione Inv.: ${activeToken.holding_eq_usd.toFixed(2)} ({activeToken.inv_weight_pct}% NAV)
            </text>
            <text x="760" y="425" fill="#94A3B8" fontSize="9.5">
              • clOrdId Idempotente · Cap 22% Post-Fill Attivo
            </text>
            <text x="760" y="445" fill="#10B981" fontSize="9.5" fontWeight="bold">
              • Cashout Automatico: 25/12 ➔ 31/12/2026 (100% USDC)
            </text>
            <polyline
              points="748,360 685,360 652,380"
              fill="none"
              stroke="#38BDF8"
              strokeWidth="1.8"
              className="holo-synapse"
            />
            <circle cx="652" cy="380" r="4" fill="#38BDF8" />
          </g>
        </svg>
      </div>

      {/* Bottom Interactive Subsystem Diagnostic Console */}
      <div className="bg-[#04070D] border border-[#0E3A5A] p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="text-[11px] text-[#38BDF8] font-bold tracking-wider">{activeSpec.code}</div>
          <div className="text-sm font-bold text-[#E2F1FF]">{activeSpec.title}</div>
          <div className="text-[11px] text-[#64748B]">{activeSpec.spec}</div>
          <p className="text-xs text-[#CBD5E1] font-sans leading-relaxed pt-1">{activeSpec.desc}</p>
        </div>

        <div className="flex flex-wrap lg:flex-col gap-1.5 shrink-0">
          {(
            [
              { id: 'CRANIAL_KRONOS', label: '01. Corteccia Kronos' },
              { id: 'OPTIC_L2_VISOR', label: '02. Visore L2/Perp' },
              { id: 'VOCAL_BSQ', label: '03. Vocoder BSQ' },
              { id: 'THORACIC_RLS', label: '04. Reattore RLS' },
              { id: 'ACTUATOR_ARMS', label: '05. Bracci Maker' },
            ] as const
          ).map((b) => (
            <button
              key={b.id}
              type="button"
              onClick={() => setSelectedSub(b.id)}
              className={`px-3 py-1.5 text-[11px] border text-left transition-all cursor-pointer ${
                selectedSub === b.id
                  ? 'bg-[#0284C7] text-[#F8FAFC] border-[#38BDF8] font-bold'
                  : 'bg-[#06101E] text-[#94A3B8] border-[#0E3A5A] hover:text-[#E2F1FF]'
              }`}
            >
              {b.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

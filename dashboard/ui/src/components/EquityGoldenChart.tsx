import React, { useState, useMemo } from 'react';
import type { NavHistoryPoint, DailyPnLBar } from '../types/predator';

interface EquityGoldenChartProps {
  history: NavHistoryPoint[];
  dailyPnl: DailyPnLBar[];
  genesisBaseline: number;
  v7Baseline: number;
  currentNav: number;
}

export const EquityGoldenChart: React.FC<EquityGoldenChartProps> = ({
  history,
  dailyPnl,
  genesisBaseline,
  v7Baseline,
  currentNav,
}) => {
  const [range, setRange] = useState<'24H' | '1W' | '1M' | '1Y' | 'YTD'>('24H');
  const [showGoldenCone, setShowGoldenCone] = useState<boolean>(true);
  const [activeSubTab, setActiveSubTab] = useState<'EQUITY_CURVE' | 'DAILY_ATTRIBUTION'>('EQUITY_CURVE');
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const filteredPoints = useMemo(() => {
    if (!history || history.length === 0) return [];
    const lastPt = history[history.length - 1];
    const nowMs = Date.parse(lastPt.timestamp) || Date.now();
    const dayMs = 24 * 60 * 60 * 1000;

    if (range === '24H') {
      // Show points from the last 26 hours (includes 22/10 21:00 CEST v7 Sovereign Cutover + all intraday points)
      const pts24 = history.filter((pt) => {
        const t = Date.parse(pt.timestamp);
        return !Number.isNaN(t) && nowMs - t <= 28 * 3600 * 1000;
      });
      return pts24.length >= 2 ? pts24 : history.slice(Math.max(0, history.length - 12));
    }
    if (range === '1W') {
      const pts1w = history.filter((pt) => {
        const t = Date.parse(pt.timestamp);
        return !Number.isNaN(t) && nowMs - t <= 7.5 * dayMs;
      });
      return pts1w.length >= 2 ? pts1w : history;
    }
    if (range === '1M') {
      const pts1m = history.filter((pt) => {
        const t = Date.parse(pt.timestamp);
        return !Number.isNaN(t) && nowMs - t <= 31 * dayMs;
      });
      return pts1m.length >= 2 ? pts1m : history;
    }
    // 1Y and YTD show full history since Genesis ($253.01 on 11/10/2026) through today
    return history;
  }, [history, range]);

  const periodBaseline = useMemo(() => {
    if (range === '24H') return v7Baseline;
    if (filteredPoints.length > 0) return filteredPoints[0].nav_usdc;
    return genesisBaseline;
  }, [range, filteredPoints, v7Baseline, genesisBaseline]);

  const activePoint =
    hoveredIdx !== null && filteredPoints[hoveredIdx]
      ? filteredPoints[hoveredIdx]
      : filteredPoints[filteredPoints.length - 1];

  // SVG coordinate calculation
  const width = 860;
  const height = 270;
  const padLeft = 56;
  const padRight = 24;
  const padTop = 20;
  const padBottom = 34;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const { minVal, maxVal } = useMemo(() => {
    let min = Infinity;
    let max = -Infinity;
    filteredPoints.forEach((pt) => {
      min = Math.min(min, pt.nav_usdc, showGoldenCone ? pt.golden_floor_usdc : pt.nav_usdc);
      max = Math.max(max, pt.nav_usdc, showGoldenCone ? Math.min(pt.golden_ceiling_usdc, pt.nav_usdc * 1.08) : pt.nav_usdc);
    });
    const margin = Math.max((max - min) * 0.12, 2.5);
    return { minVal: min - margin, maxVal: max + margin };
  }, [filteredPoints, showGoldenCone]);

  const toX = (idx: number) => {
    if (filteredPoints.length <= 1) return padLeft + plotW / 2;
    return padLeft + (idx / (filteredPoints.length - 1)) * plotW;
  };

  const toY = (val: number) => {
    const clamped = Math.max(minVal, Math.min(maxVal, val));
    return padTop + plotH - ((clamped - minVal) / Math.max(maxVal - minVal, 0.01)) * plotH;
  };

  const navPolyline = filteredPoints
    .map((pt, i) => `${toX(i).toFixed(1)},${toY(pt.nav_usdc).toFixed(1)}`)
    .join(' ');

  const areaPath =
    filteredPoints.length > 0
      ? `M ${toX(0).toFixed(1)} ${toY(filteredPoints[0].nav_usdc).toFixed(1)} ` +
        filteredPoints.map((pt, i) => `L ${toX(i).toFixed(1)} ${toY(pt.nav_usdc).toFixed(1)}`).join(' ') +
        ` L ${toX(filteredPoints.length - 1).toFixed(1)} ${(padTop + plotH).toFixed(1)} L ${toX(0).toFixed(1)} ${(padTop + plotH).toFixed(1)} Z`
      : '';

  const goldenCorridorPolygon =
    showGoldenCone && filteredPoints.length > 1
      ? filteredPoints.map((pt, i) => `${toX(i).toFixed(1)},${toY(Math.min(pt.golden_ceiling_usdc, maxVal)).toFixed(1)}`).join(' ') +
        ' ' +
        [...filteredPoints]
          .reverse()
          .map((pt, revIdx) => {
            const origIdx = filteredPoints.length - 1 - revIdx;
            return `${toX(origIdx).toFixed(1)},${toY(pt.golden_floor_usdc).toFixed(1)}`;
          })
          .join(' ')
      : '';

  const yTicks = useMemo(() => {
    const count = 5;
    const step = (maxVal - minVal) / (count - 1);
    return Array.from({ length: count }, (_, i) => minVal + step * i);
  }, [minVal, maxVal]);

  return (
    <section className="border border-[#1E2530] bg-[#0D1017] p-4 sm:p-6">
      {/* Header Row */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 pb-4 border-b border-[#181E27]">
        <div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-[#8A94A6] font-mono">
            <span>01. PERFORMANCE & COMPOUNDING CORRIDOR</span>
            <span aria-hidden="true">·</span>
            <span>OKX SPOT EEA (ZERO LEVERAGE)</span>
            <span aria-hidden="true">·</span>
            <span className="text-[#10B981]">MAKER FEE 0.00%</span>
          </div>
          <h2 className="font-editorial text-xl sm:text-2xl font-semibold text-[#F3F4F6] mt-1 tracking-tight">
            Net Asset Value (NAV) &amp; Canale Regola Aurea (+0.70% ↔ +5.00% / Giorno)
          </h2>
        </div>

        {/* Interactive Controls */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center bg-[#07080A] border border-[#1E2530] p-0.5">
            <button
              type="button"
              onClick={() => setActiveSubTab('EQUITY_CURVE')}
              className={`px-3 py-1.5 text-xs font-mono transition-colors whitespace-nowrap shrink-0 min-h-[36px] ${
                activeSubTab === 'EQUITY_CURVE'
                  ? 'bg-[#F59E0B] text-[#07080A] font-semibold'
                  : 'text-[#8A94A6] hover:text-[#E6E8EC]'
              }`}
            >
              Curva NAV &amp; Cono
            </button>
            <button
              type="button"
              onClick={() => setActiveSubTab('DAILY_ATTRIBUTION')}
              className={`px-3 py-1.5 text-xs font-mono transition-colors whitespace-nowrap shrink-0 min-h-[36px] ${
                activeSubTab === 'DAILY_ATTRIBUTION'
                  ? 'bg-[#F59E0B] text-[#07080A] font-semibold'
                  : 'text-[#8A94A6] hover:text-[#E6E8EC]'
              }`}
            >
              PnL Giornaliero &amp; Ratchet
            </button>
          </div>

          {activeSubTab === 'EQUITY_CURVE' && (
            <>
              <div className="flex items-center bg-[#07080A] border border-[#1E2530] p-0.5">
                {(
                  [
                    { id: '24H', label: '24h' },
                    { id: '1W', label: '1 Sett' },
                    { id: '1M', label: '1 Mese' },
                    { id: '1Y', label: '1Y' },
                    { id: 'YTD', label: 'YTD' },
                  ] as const
                ).map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => {
                      setRange(r.id);
                      setHoveredIdx(null);
                    }}
                    className={`px-2.5 py-1.5 text-xs font-mono transition-colors whitespace-nowrap shrink-0 min-h-[36px] ${
                      range === r.id
                        ? 'bg-[#1E2530] text-[#FCD34D] font-semibold'
                        : 'text-[#8A94A6] hover:text-[#E6E8EC]'
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>

              <button
                type="button"
                onClick={() => setShowGoldenCone((v) => !v)}
                className={`px-3 py-1.5 text-xs font-mono border transition-colors whitespace-nowrap shrink-0 min-h-[36px] ${
                  showGoldenCone
                    ? 'border-[#F59E0B]/60 bg-[#F59E0B]/10 text-[#FCD34D]'
                    : 'border-[#1E2530] bg-[#07080A] text-[#8A94A6]'
                }`}
              >
                {showGoldenCone ? 'Cono Aureo: ATTIVO' : 'Cono Aureo: NASCOSTO'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Live Inspected Point Telemetry Strip */}
      {activePoint && activeSubTab === 'EQUITY_CURVE' && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 py-3 border-b border-[#181E27] text-xs font-mono tabular-nums">
          <div>
            <span className="text-[#8A94A6] block">TIMESTAMP RILEVATO</span>
            <span className="text-[#E6E8EC] font-semibold">{activePoint.label}</span>
          </div>
          <div>
            <span className="text-[#8A94A6] block">MARK-TO-MARKET NAV</span>
            <span className="text-[#10B981] font-semibold text-sm">${activePoint.nav_usdc.toFixed(2)} USDC</span>
          </div>
          <div>
            <span className="text-[#8A94A6] block">
              PNL PERIODO ({range === '24H' ? 'DA $298.89' : `DA $${periodBaseline.toFixed(2)}`})
            </span>
            <span className="text-[#10B981] font-semibold">
              {activePoint.nav_usdc - periodBaseline >= 0 ? '+' : ''}$
              {(activePoint.nav_usdc - periodBaseline).toFixed(2)} (
              {activePoint.nav_usdc - periodBaseline >= 0 ? '+' : ''}
              {(((activePoint.nav_usdc - periodBaseline) / Math.max(periodBaseline, 1)) * 100).toFixed(2)}%)
            </span>
          </div>
          <div>
            <span className="text-[#8A94A6] block">FLOOR / CEILING AUREO</span>
            <span className="text-[#FCD34D]">
              ${activePoint.golden_floor_usdc.toFixed(2)} ↔ ${activePoint.golden_ceiling_usdc.toFixed(2)}
            </span>
          </div>
          <div className="col-span-2 sm:col-span-1">
            <span className="text-[#8A94A6] block">EVENTO / STATO MICRO</span>
            <span className="text-[#E6E8EC] truncate block">
              {activePoint.event_tag || `BTC Radar ${activePoint.btc_lead_lag_bps >= 0 ? '+' : ''}${activePoint.btc_lead_lag_bps} bps · VPIN ${activePoint.vpin_avg}`}
            </span>
          </div>
        </div>
      )}

      {/* Main Chart Body */}
      {activeSubTab === 'EQUITY_CURVE' ? (
        <div className="mt-4 relative select-none">
          <svg
            viewBox={`0 0 ${width} ${height}`}
            className="w-full h-[230px] sm:h-[280px] overflow-visible"
            role="img"
            aria-label="Grafico Curva NAV e Canale Regola Aurea"
          >
            <defs>
              <linearGradient id="navAreaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10B981" stopOpacity="0.26" />
                <stop offset="100%" stopColor="#10B981" stopOpacity="0.0" />
              </linearGradient>
              <linearGradient id="goldenConeGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#F59E0B" stopOpacity="0.14" />
                <stop offset="100%" stopColor="#F59E0B" stopOpacity="0.04" />
              </linearGradient>
            </defs>

            {/* Horizontal Grid Lines & Y-Axis Labels */}
            {yTicks.map((val, idx) => {
              const y = toY(val);
              return (
                <g key={idx}>
                  <line
                    x1={padLeft}
                    y1={y}
                    x2={width - padRight}
                    y2={y}
                    stroke="#181E27"
                    strokeDasharray={idx === 0 ? undefined : '3 3'}
                    strokeWidth="1"
                  />
                  <text
                    x={padLeft - 8}
                    y={y + 4}
                    textAnchor="end"
                    className="fill-[#8A94A6] font-mono text-[10px]"
                  >
                    ${val.toFixed(0)}
                  </text>
                </g>
              );
            })}

            {/* v7 Run Baseline Reference Line ($298.89) */}
            {v7Baseline >= minVal && v7Baseline <= maxVal && (
              <g>
                <line
                  x1={padLeft}
                  y1={toY(v7Baseline)}
                  x2={width - padRight}
                  y2={toY(v7Baseline)}
                  stroke="#F59E0B"
                  strokeDasharray="4 4"
                  strokeWidth="1"
                  strokeOpacity="0.6"
                />
                <text
                  x={padLeft + 6}
                  y={toY(v7Baseline) - 5}
                  className="fill-[#FCD34D] font-mono text-[9px]"
                >
                  v7 Sovereign Baseline ($298.89)
                </text>
              </g>
            )}

            {/* Golden Rule Compounding Cone (+0.70% <-> +5.00%) */}
            {showGoldenCone && goldenCorridorPolygon && (
              <polygon points={goldenCorridorPolygon} fill="url(#goldenConeGrad)" stroke="#F59E0B" strokeOpacity="0.3" strokeWidth="1" />
            )}

            {/* NAV Area Fill */}
            {areaPath && <path d={areaPath} fill="url(#navAreaGrad)" />}

            {/* Main NAV Line */}
            {navPolyline && (
              <polyline
                fill="none"
                stroke="#10B981"
                strokeWidth="2.25"
                points={navPolyline}
              />
            )}

            {/* Interactive Points & Crosshair */}
            {filteredPoints.map((pt, i) => {
              const cx = toX(i);
              const cy = toY(pt.nav_usdc);
              const isSelected = (hoveredIdx === null && i === filteredPoints.length - 1) || hoveredIdx === i;

              return (
                <g key={pt.timestamp + i}>
                  {isSelected && (
                    <line
                      x1={cx}
                      y1={padTop}
                      x2={cx}
                      y2={padTop + plotH}
                      stroke="#F59E0B"
                      strokeWidth="1"
                      strokeDasharray="2 2"
                    />
                  )}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isSelected ? 4.5 : 2.8}
                    fill={isSelected ? '#F59E0B' : '#10B981'}
                    stroke="#07080A"
                    strokeWidth="1.5"
                  />
                  {/* X-Axis Labels */}
                  {(i % 2 === 0 || i === filteredPoints.length - 1) && (
                    <text
                      x={cx}
                      y={height - 10}
                      textAnchor="middle"
                      className={`font-mono text-[10px] ${
                        isSelected ? 'fill-[#FCD34D] font-semibold' : 'fill-[#8A94A6]'
                      }`}
                    >
                      {pt.label}
                    </text>
                  )}
                  {/* Wide Transparent Hit Target for Mouse & Touch */}
                  <rect
                    x={cx - plotW / Math.max(filteredPoints.length * 2, 2)}
                    y={padTop}
                    width={plotW / Math.max(filteredPoints.length, 1)}
                    height={plotH}
                    fill="transparent"
                    className="cursor-crosshair"
                    onMouseEnter={() => setHoveredIdx(i)}
                    onClick={() => setHoveredIdx(i)}
                  />
                </g>
              );
            })}
          </svg>

          {/* Legend Footer */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-[#181E27] text-xs font-mono text-[#8A94A6]">
            <div className="flex flex-wrap items-center gap-4">
              <span className="text-[#10B981]">━ Curva NAV Mark-to-Market (${currentNav.toFixed(2)})</span>
              <span className="text-[#FCD34D]">▒ Corridoio Composto Regola Aurea (+0.70% ↔ +5.00% / die)</span>
            </div>
            <span>Tocca o passa sui nodi per ispezionare lo stato L2</span>
          </div>
        </div>
      ) : (
        /* Daily Realized PnL & Ratchet Capital Recycler Attribution View */
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-7 gap-2.5">
            {dailyPnl.map((bar) => {
              const pctHeight = Math.min(100, Math.max(18, (bar.realized_pct / 3.0) * 100));
              return (
                <div
                  key={bar.date}
                  className="border border-[#1E2530] bg-[#07080A] p-3 flex flex-col justify-between"
                >
                  <div className="flex items-center justify-between text-xs font-mono text-[#8A94A6]">
                    <span>{bar.date}</span>
                    <span className="text-[#10B981]">+{bar.realized_pct.toFixed(2)}%</span>
                  </div>

                  <div className="h-24 flex items-end gap-1.5 my-3 pt-4 border-b border-[#181E27]">
                    <div
                      className="flex-1 bg-[#10B981]/80 hover:bg-[#10B981] transition-colors"
                      style={{ height: `${pctHeight}%` }}
                      title={`PnL Realizzato: +$${bar.realized_pnl_usdc.toFixed(2)}`}
                    />
                    <div
                      className="w-2.5 bg-[#F59E0B]/85"
                      style={{ height: `${Math.max(12, pctHeight * 0.35)}%` }}
                      title={`Ratchet Pool 20%: $${bar.ratchet_recycled_usdc.toFixed(2)}`}
                    />
                  </div>

                  <div className="space-y-1 font-mono tabular-nums text-xs">
                    <div className="flex justify-between">
                      <span className="text-[#8A94A6]">Netto:</span>
                      <span className="text-[#10B981] font-semibold">+${bar.realized_pnl_usdc.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#8A94A6]">Ratchet 20%:</span>
                      <span className="text-[#FCD34D]">${bar.ratchet_recycled_usdc.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#8A94A6]">Maker Fills:</span>
                      <span className="text-[#E6E8EC]">{bar.fills_count}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex flex-wrap items-center justify-between text-xs font-mono text-[#8A94A6] pt-2">
            <span>█ Verde: PnL Realizzato Netto (USDC) · █ Ambra: Quota 20% destinata al Ratchet Capital Recycler</span>
            <span className="text-[#10B981]">7/7 Giorni dentro il Canale Regola Aurea (+0.70% ↔ +5.00%)</span>
          </div>
        </div>
      )}
    </section>
  );
};

import React, { useState, useEffect } from 'react';
import { Copy, Check, Terminal, Play, ShieldAlert, Zap, Download } from 'lucide-react';
import type { PredatorSystemState } from '../types/predator';

interface VpsIntegrationPanelProps {
  state: PredatorSystemState;
  onSimulateCycle: (scenario: 'normal' | 'toxic_btc_dump' | 'scalp_harvest') => Promise<void>;
  isSimulating: boolean;
}

export const VpsIntegrationPanel: React.FC<VpsIntegrationPanelProps> = ({
  state,
  onSimulateCycle,
  isSimulating,
}) => {
  const [scriptData, setScriptData] = useState<{
    app_url: string;
    push_endpoint: string;
    script: string;
  } | null>(null);
  const [copiedScript, setCopiedScript] = useState(false);
  const [copiedSystemd, setCopiedSystemd] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);

  useEffect(() => {
    fetch('/api/vps/script')
      .then((r) => r.json())
      .then((d) => setScriptData(d))
      .catch(() => null);
  }, []);

  const systemdUnit = `[Unit]
Description=TRE OS v7.0 Sovereign Telemetry Push Bridge (15s)
After=network.target openclaw-predator.service

[Service]
Type=simple
User=trader_user
WorkingDirectory=/opt/openclaw-trader
ExecStart=/usr/bin/python3 /opt/openclaw-trader/scripts/brody_telemetry_push.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target`;

  const copyToClipboard = (text: string, type: 'script' | 'systemd') => {
    navigator.clipboard.writeText(text);
    if (type === 'script') {
      setCopiedScript(true);
      setTimeout(() => setCopiedScript(false), 2000);
    } else {
      setCopiedSystemd(true);
      setTimeout(() => setCopiedSystemd(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Diagnostic & Audit Banner */}
      <section className="border border-[#1E2530] bg-[#0D1017] p-4 sm:p-6">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 pb-4 border-b border-[#181E27]">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-[#8A94A6]">
              <span>04. SCIENTIFIC AUDIT &amp; VPS BRODY TELEMETRY BRIDGE</span>
              <span aria-hidden="true">·</span>
              <span>HOST: {state.vps_host}</span>
              <span aria-hidden="true">·</span>
              <span className="text-[#10B981]">AUDIT SCORE: {state.audit_report.audit_score_100}/100</span>
            </div>
            <h2 className="font-editorial text-xl sm:text-2xl font-semibold text-[#F3F4F6] mt-1">
              Connessione Push 15s VPS <span className="text-[#FCD34D]">brody</span> &amp; Verifica Contabile Sovrana
            </h2>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <a
              href="/api/export/ledger.csv"
              download
              className="px-3 py-2 text-xs font-mono bg-[#07080A] border border-[#1E2530] text-[#E6E8EC] hover:border-[#F59E0B] flex items-center gap-1.5 whitespace-nowrap shrink-0 min-h-[40px]"
            >
              <Download className="w-3.5 h-3.5 text-[#F59E0B]" />
              Esporta Ledger CSV
            </a>
            <a
              href="/api/export/telemetry.csv"
              download
              className="px-3 py-2 text-xs font-mono bg-[#07080A] border border-[#1E2530] text-[#E6E8EC] hover:border-[#F59E0B] flex items-center gap-1.5 whitespace-nowrap shrink-0 min-h-[40px]"
            >
              <Download className="w-3.5 h-3.5 text-[#10B981]" />
              Esporta Matrice L2 CSV
            </a>
          </div>
        </div>

        {/* Audit Verdict & Adversarial Council */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 py-4 border-b border-[#181E27]">
          <div className="bg-[#07080A] border border-[#1E2530] p-4 space-y-2">
            <div className="flex items-center justify-between text-xs font-mono text-[#8A94A6]">
              <span>VERDETTO REVISORE DETERMINISTICO + AI</span>
              <span className="text-[#10B981] font-semibold">ZERO VIOLAZIONI COST-BASIS</span>
            </div>
            <p className="text-xs sm:text-sm text-[#E6E8EC] leading-relaxed">
              {state.audit_report.executive_verdict}
            </p>
            <div className="pt-2 flex flex-wrap items-center gap-3 text-xs font-mono text-[#8A94A6] tabular-nums">
              <span>Fills Totali: {state.audit_report.total_fills_count}</span>
              <span aria-hidden="true">·</span>
              <span>Maker Ratio: {state.audit_report.maker_ratio_pct}%</span>
              <span aria-hidden="true">·</span>
              <span>PnL Realizzato: +${state.audit_report.realized_pnl_usd.toFixed(2)} USDC</span>
            </div>
          </div>

          <div className="bg-[#07080A] border border-[#1E2530] p-4 space-y-2">
            <div className="flex items-center justify-between text-xs font-mono text-[#8A94A6]">
              <span>CONSIGLIO AVVERSARIO MULTI-MODEL (OPENROUTER FREE)</span>
              <span className="text-[#FCD34D]">{state.audit_report.council_timestamp}</span>
            </div>
            <p className="text-xs sm:text-sm text-[#E6E8EC] leading-relaxed">
              {state.audit_report.council_consensus}
            </p>
            <div className="pt-2 flex flex-wrap items-center gap-2 text-[11px] font-mono text-[#8A94A6]">
              {state.audit_report.council_models.map((m, idx) => (
                <React.Fragment key={m}>
                  {idx > 0 && <span aria-hidden="true">·</span>}
                  <span>{m}</span>
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>

        {/* Interactive 15s Telemetry Stress-Test Simulator */}
        <div className="pt-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-3">
            <div>
              <span className="text-xs font-mono text-[#FCD34D] block">
                SIMULATORE INTERATTIVO DI CICLO A 15 SECONDI (TEST REATTIVITÀ TERMINALE)
              </span>
              <span className="text-xs text-[#8A94A6]">
                Inietta un ciclo telemetrico per verificare lo stream SSE in tempo reale e la risposta del motore di regime
              </span>
            </div>
            <button
              type="button"
              onClick={() => setShowRawJson((v) => !v)}
              className="px-3 py-1.5 text-xs font-mono border border-[#1E2530] bg-[#07080A] text-[#8A94A6] hover:text-[#E6E8EC] self-start sm:self-auto whitespace-nowrap shrink-0 min-h-[36px]"
            >
              {showRawJson ? 'Nascondi Payload JSON' : 'Ispeziona Payload JSON Live'}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <button
              type="button"
              disabled={isSimulating}
              onClick={() => onSimulateCycle('normal')}
              className="p-3 border border-[#1E2530] bg-[#07080A] hover:border-[#F59E0B] text-left transition-colors min-h-[48px]"
            >
              <div className="flex items-center justify-between text-xs font-mono text-[#E6E8EC] font-semibold">
                <span className="flex items-center gap-1.5">
                  <Play className="w-3.5 h-3.5 text-[#F59E0B]" />
                  Simula Ciclo 15s Standard
                </span>
                <span className="text-[#8A94A6]">~840ms L2</span>
              </div>
              <p className="text-[11px] text-[#8A94A6] mt-1">
                Aggiorna OrderBook L2 (6 thread), previsioni Kronos-mini e ricalcola OppScore sulle 12 coppie.
              </p>
            </button>

            <button
              type="button"
              disabled={isSimulating}
              onClick={() => onSimulateCycle('scalp_harvest')}
              className="p-3 border border-[#1E2530] bg-[#07080A] hover:border-[#10B981] text-left transition-colors min-h-[48px]"
            >
              <div className="flex items-center justify-between text-xs font-mono text-[#10B981] font-semibold">
                <span className="flex items-center gap-1.5">
                  <Zap className="w-3.5 h-3.5" />
                  Simula Fill Quick-Scalp + Ratchet
                </span>
                <span>+52.8 bps</span>
              </div>
              <p className="text-[11px] text-[#8A94A6] mt-1">
                Esegue un fill Post-Only Maker su HYPE-USDC e versa il 20% nel Ratchet Pool per abbassare il floor storico.
              </p>
            </button>

            <button
              type="button"
              disabled={isSimulating}
              onClick={() => onSimulateCycle('toxic_btc_dump')}
              className="p-3 border border-[#1E2530] bg-[#07080A] hover:border-[#EF4444] text-left transition-colors min-h-[48px]"
            >
              <div className="flex items-center justify-between text-xs font-mono text-[#EF4444] font-semibold">
                <span className="flex items-center gap-1.5">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  Simula Scarico BTC (&lt; -12 bps)
                </span>
                <span>TOXIC SHIELD</span>
              </div>
              <p className="text-[11px] text-[#8A94A6] mt-1">
                Attiva TOXIC_DIP_DEFENSE su tutte le 12 coppie, allarga le trappole BUY e blocca il Cash Sweeper.
              </p>
            </button>
          </div>

          {showRawJson && (
            <div className="mt-4 bg-[#07080A] border border-[#1E2530] p-3">
              <div className="text-xs font-mono text-[#8A94A6] mb-2">
                ULTIMO SNAPSHOT RICEVUTO DAL SERVER (CICLO #{state.cycle_num})
              </div>
              <pre className="text-[11px] font-mono text-[#10B981] overflow-x-auto max-h-64">
                {JSON.stringify(
                  {
                    cycle_num: state.cycle_num,
                    timestamp: state.timestamp,
                    connection_mode: state.connection_mode,
                    current_nav_usdc: state.current_nav_usdc,
                    free_usdc: state.free_usdc,
                    btc_lead_lag_bps: state.btc_lead_lag_bps,
                    ratchet_pool_usd: state.ratchet_pool_usd,
                    sample_telemetry: state.telemetry.slice(0, 2),
                  },
                  null,
                  2
                )}
              </pre>
            </div>
          )}
        </div>
      </section>

      {/* Ready-to-Deploy VPS `brody` Push Script Section */}
      <section className="border border-[#1E2530] bg-[#0D1017] p-4 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-[#181E27]">
          <div>
            <span className="text-xs font-mono text-[#FCD34D] flex items-center gap-1.5">
              <Terminal className="w-4 h-4" />
              INSTALLAZIONE 1-CLICK SULLA VPS SOVRANA &quot;BRODY&quot; (<YOUR_VPS_IP> / <YOUR_TAILSCALE_IP>)
            </span>
            <p className="text-xs text-[#8A94A6] mt-1">
              Questo script legge <code className="text-[#E6E8EC]">config/okx_trader.db</code> in modalità Read-Only WAL e{' '}
              <code className="text-[#E6E8EC]">config/predator_audit_report.json</code> ogni 15s inviando i dati a questo terminale.
            </p>
          </div>
          {scriptData && (
            <button
              type="button"
              onClick={() => copyToClipboard(scriptData.script, 'script')}
              className="px-3.5 py-2 text-xs font-mono bg-[#F59E0B] text-[#07080A] font-semibold hover:bg-[#FCD34D] flex items-center gap-1.5 whitespace-nowrap shrink-0 min-h-[40px]"
            >
              {copiedScript ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              {copiedScript ? 'Script Copiato!' : 'Copia brody_telemetry_push.py'}
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 pt-4">
          <div className="lg:col-span-2 bg-[#07080A] border border-[#1E2530] p-3">
            <div className="flex items-center justify-between text-xs font-mono text-[#8A94A6] pb-2 border-b border-[#181E27]">
              <span>/opt/openclaw-trader/scripts/brody_telemetry_push.py</span>
              <span className="text-[#10B981]">ZERO DIPENDENZE ESTERNE (STDLIB PYTHON 3.13)</span>
            </div>
            <pre className="text-[11px] font-mono text-[#E6E8EC] overflow-x-auto max-h-72 pt-2 leading-relaxed">
              {scriptData ? scriptData.script : 'Caricamento script pre-configurato...'}
            </pre>
          </div>

          <div className="bg-[#07080A] border border-[#1E2530] p-3 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs font-mono text-[#8A94A6] pb-2 border-b border-[#181E27]">
                <span>SYSTEMD DAEMON UNIT</span>
                <button
                  type="button"
                  onClick={() => copyToClipboard(systemdUnit, 'systemd')}
                  className="text-[#FCD34D] hover:underline flex items-center gap-1"
                >
                  {copiedSystemd ? 'Copiato' : 'Copia Unit'}
                </button>
              </div>
              <pre className="text-[11px] font-mono text-[#8A94A6] overflow-x-auto pt-2 leading-relaxed">
                {systemdUnit}
              </pre>
            </div>

            <div className="mt-4 pt-3 border-t border-[#181E27] text-xs font-mono space-y-1.5">
              <div className="text-[#FCD34D]">ENDPOINT WEBHOOK ATTIVO:</div>
              <div className="text-[#10B981] break-all text-[11px]">
                POST {scriptData?.push_endpoint || '/api/vps/push'}
              </div>
              <div className="text-[#8A94A6] text-[11px]">
                Sicurezza: SQLite aperto con <code className="text-[#E6E8EC]">?mode=ro</code> (nessun lock sul daemon di trading).
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

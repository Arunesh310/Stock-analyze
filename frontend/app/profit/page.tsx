"use client";
import * as React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell as RCell,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { api } from "@/lib/api";
import type {
  EquityCurvePoint,
  PortfolioMetrics,
  RegimePerformance,
  SectorPerformance,
} from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { fmtINR, fmtPct, pctClass } from "@/lib/utils";

type Mode = "all" | "intraday" | "swing" | "positional";

export default function ProfitPage() {
  const [mode, setMode] = React.useState<Mode>("all");
  const [eq, setEq] = React.useState<EquityCurvePoint[]>([]);
  const [bySector, setBySector] = React.useState<SectorPerformance[]>([]);
  const [byRegime, setByRegime] = React.useState<RegimePerformance[]>([]);
  const [summary, setSummary] = React.useState<any>(null);
  const [metrics, setMetrics] = React.useState<PortfolioMetrics | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [err, setErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    (async () => {
      try {
        const m = mode === "all" ? undefined : mode;
        const [e, s, r, sm, pm] = await Promise.all([
          api.simulated.equityCurve(720, m),
          api.simulated.bySector(m),
          api.simulated.byRegime(m),
          api.simulated.summary({ mode: m }),
          api.simulated.portfolioMetrics({ mode: m }).catch(() => null),
        ]);
        if (!cancelled) {
          setEq(e);
          setBySector(s);
          setByRegime(r);
          setSummary(sm);
          setMetrics(pm);
        }
      } catch (e: any) {
        if (!cancelled) setErr(String(e?.message || e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode]);

  if (loading && eq.length === 0) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-16" />
        <Skeleton className="h-72" />
        <Skeleton className="h-72" />
      </div>
    );
  }

  const lastPoint = eq[eq.length - 1];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Simulated Profit Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            What ₹10,000 per signal would have done — based on objective
            replay of historical OHLC after each prediction.
          </p>
        </div>
        <Tabs value={mode} onValueChange={(v) => setMode(v as Mode)}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="intraday">Intraday</TabsTrigger>
            <TabsTrigger value="swing">Swing</TabsTrigger>
            <TabsTrigger value="positional">Positional</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {err && (
        <Card>
          <CardContent className="p-4 text-xs text-bear">{err}</CardContent>
        </Card>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi
          label="Cumulative P&L"
          value={fmtINR(summary?.total_simulated_pnl ?? 0)}
          accent={(summary?.total_simulated_pnl ?? 0) >= 0 ? "text-bull" : "text-bear"}
        />
        <Kpi
          label="Cumulative return"
          value={fmtPct(summary?.cumulative_return_pct ?? 0)}
          accent={(summary?.cumulative_return_pct ?? 0) >= 0 ? "text-bull" : "text-bear"}
        />
        <Kpi
          label="Closed trades"
          value={summary?.closed_predictions ?? 0}
        />
        <Kpi
          label="Capital deployed"
          value={fmtINR(summary?.total_simulated_capital ?? 0)}
        />
      </div>

      {metrics && metrics.trades > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Portfolio risk metrics</CardTitle>
            <p className="text-[11px] text-muted-foreground">
              Trade-by-trade statistics on {metrics.trades} closed simulated trades.
              Computed from realised PnL — assumes ₹10,000 per signal.
            </p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
              <MiniMetric label="CAGR" value={`${metrics.cagr_pct.toFixed(2)}%`} accent={metrics.cagr_pct >= 0 ? "text-bull" : "text-bear"} />
              <MiniMetric label="Sharpe (per-trade)" value={metrics.sharpe.toFixed(2)} />
              <MiniMetric
                label="Max drawdown"
                value={`${fmtINR(metrics.max_drawdown_inr)} (${metrics.max_drawdown_pct.toFixed(2)}%)`}
                accent="text-bear"
              />
              <MiniMetric
                label="Profit factor"
                value={metrics.profit_factor == null ? "∞" : metrics.profit_factor.toFixed(2)}
                accent={(metrics.profit_factor ?? 1) >= 1 ? "text-bull" : "text-bear"}
              />
              <MiniMetric
                label="Expectancy / trade"
                value={fmtINR(metrics.expectancy_inr)}
                accent={metrics.expectancy_inr >= 0 ? "text-bull" : "text-bear"}
              />
              <MiniMetric label="Avg win" value={`${metrics.avg_win_pct.toFixed(2)}%`} accent="text-bull" />
              <MiniMetric label="Avg loss" value={`${metrics.avg_loss_pct.toFixed(2)}%`} accent="text-bear" />
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Cumulative simulated P&L</CardTitle>
          {lastPoint && (
            <div className="text-xs text-muted-foreground">
              Last:{" "}
              <span className={`font-mono ${pctClass(lastPoint.cumulative_pnl)}`}>
                {fmtINR(lastPoint.cumulative_pnl)} · {fmtPct(lastPoint.cumulative_pct)}
              </span>
            </div>
          )}
        </CardHeader>
        <CardContent style={{ height: 320 }}>
          {eq.length === 0 ? (
            <EmptyHint />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={eq}>
                <defs>
                  <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.5} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" stroke="#9ca3af" fontSize={10} />
                <YAxis stroke="#9ca3af" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    fontSize: 12,
                  }}
                  formatter={(v: any, name: string) => {
                    if (name === "cumulative_pnl") return [fmtINR(v as number), "P&L"];
                    if (name === "cumulative_pct") return [fmtPct(v as number), "Return"];
                    return [v, name];
                  }}
                />
                <ReferenceLine y={0} stroke="#475569" strokeDasharray="3 3" />
                <Area
                  type="monotone"
                  dataKey="cumulative_pnl"
                  stroke="#22c55e"
                  fill="url(#profitGradient)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>P&L by sector</CardTitle>
          </CardHeader>
          <CardContent style={{ height: 320 }}>
            {bySector.length === 0 ? (
              <EmptyHint />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bySector}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    dataKey="sector"
                    stroke="#9ca3af"
                    fontSize={10}
                    angle={-25}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis stroke="#9ca3af" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(var(--popover))",
                      border: "1px solid hsl(var(--border))",
                      fontSize: 12,
                    }}
                    formatter={(v: any, name: string) =>
                      name === "pnl" ? [fmtINR(v as number), "P&L"] : [v, name]
                    }
                  />
                  <ReferenceLine y={0} stroke="#475569" />
                  <Bar dataKey="pnl" name="pnl">
                    {bySector.map((s, i) => (
                      <RCell key={i} fill={(s.pnl || 0) >= 0 ? "#22c55e" : "#ef4444"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>P&L by regime</CardTitle>
          </CardHeader>
          <CardContent style={{ height: 320 }}>
            {byRegime.length === 0 ? (
              <EmptyHint />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byRegime}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="regime" stroke="#9ca3af" fontSize={10} angle={-25} textAnchor="end" height={60} />
                  <YAxis stroke="#9ca3af" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(var(--popover))",
                      border: "1px solid hsl(var(--border))",
                      fontSize: 12,
                    }}
                    formatter={(v: any) => [fmtINR(v as number), "P&L"]}
                  />
                  <ReferenceLine y={0} stroke="#475569" />
                  <Bar dataKey="pnl">
                    {byRegime.map((r, i) => (
                      <RCell key={i} fill={(r.pnl || 0) >= 0 ? "#22c55e" : "#ef4444"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <p className="text-[10px] text-muted-foreground text-center">
        Simulated returns assume ₹10,000 invested per signal and exit at
        target or stoploss as defined by the model. Slippage, taxes and
        liquidity are not modelled. Educational only — not financial advice.
      </p>
    </div>
  );
}

function Kpi({
  label,
  value,
  accent,
}: {
  label: string;
  value: React.ReactNode;
  accent?: string;
}) {
  return (
    <Card>
      <CardContent className="p-3">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div className={`text-xl font-mono font-semibold ${accent || ""}`}>{value}</div>
      </CardContent>
    </Card>
  );
}

function MiniMetric({
  label,
  value,
  accent,
}: {
  label: string;
  value: React.ReactNode;
  accent?: string;
}) {
  return (
    <div className="space-y-0.5">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className={`text-sm font-mono font-semibold ${accent || ""}`}>
        {value}
      </div>
    </div>
  );
}

function EmptyHint() {
  return (
    <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
      No closed trades yet — let the validation cycle run for a while.
    </div>
  );
}

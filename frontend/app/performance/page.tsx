"use client";
import * as React from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { api } from "@/lib/api";
import type {
  AccuracyTrendPoint,
  PerformanceSummary,
  PredictionFull,
  SectorPerformance,
  SetupQuality,
  HeatmapCell,
} from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { fmtINR, fmtPct, pctClass } from "@/lib/utils";

type Mode = "all" | "intraday" | "swing" | "positional";

export default function PerformancePage() {
  const [mode, setMode] = React.useState<Mode>("all");
  const [summary, setSummary] = React.useState<PerformanceSummary | null>(null);
  const [trend, setTrend] = React.useState<AccuracyTrendPoint[]>([]);
  const [sectors, setSectors] = React.useState<SectorPerformance[]>([]);
  const [setups, setSetups] = React.useState<SetupQuality[]>([]);
  const [recent, setRecent] = React.useState<PredictionFull[]>([]);
  const [heatmap, setHeatmap] = React.useState<HeatmapCell[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const m = mode === "all" ? undefined : mode;
      const [s, t, sec, sp, r, hm] = await Promise.all([
        api.performance.summary({ mode: m }),
        api.performance.accuracyTrend("month", m),
        api.performance.sectorBreakdown(m),
        api.performance.setups(m),
        api.performance.recent({ limit: 25, mode: m }),
        api.performance.heatmapSectorRegime(),
      ]);
      setSummary(s);
      setTrend(t);
      setSectors(sec);
      setSetups(sp);
      setRecent(r);
      setHeatmap(hm);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [mode]);

  React.useEffect(() => {
    load();
  }, [load]);

  const runValidation = async () => {
    setBusy(true);
    try {
      await api.validate.run(200);
      await load();
    } finally {
      setBusy(false);
    }
  };

  if (loading && !summary) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI Performance Analytics</h1>
          <p className="text-sm text-muted-foreground">
            How well the engine has actually performed on its own past
            predictions. Educational only — not financial advice.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Tabs value={mode} onValueChange={(v) => setMode(v as Mode)}>
            <TabsList>
              <TabsTrigger value="all">All</TabsTrigger>
              <TabsTrigger value="intraday">Intraday</TabsTrigger>
              <TabsTrigger value="swing">Swing</TabsTrigger>
              <TabsTrigger value="positional">Positional</TabsTrigger>
            </TabsList>
          </Tabs>
          <Button onClick={runValidation} disabled={busy}>
            {busy ? "Validating…" : "Run validation"}
          </Button>
        </div>
      </div>

      {err && (
        <Card>
          <CardContent className="p-4 text-xs text-bear">{err}</CardContent>
        </Card>
      )}

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi
          label="Total predictions"
          value={summary?.total_predictions ?? 0}
        />
        <Kpi
          label="Win rate"
          value={`${(summary?.win_rate ?? 0).toFixed(1)}%`}
          accent={(summary?.win_rate ?? 0) >= 50 ? "text-bull" : "text-bear"}
        />
        <Kpi
          label="Simulated P&L"
          value={fmtINR(summary?.total_simulated_pnl ?? 0)}
          accent={(summary?.total_simulated_pnl ?? 0) >= 0 ? "text-bull" : "text-bear"}
        />
        <Kpi
          label="Cumulative return"
          value={fmtPct(summary?.cumulative_return_pct ?? 0)}
          accent={(summary?.cumulative_return_pct ?? 0) >= 0 ? "text-bull" : "text-bear"}
        />
        <Kpi label="Open predictions" value={summary?.open_predictions ?? 0} />
        <Kpi label="Closed" value={summary?.closed_predictions ?? 0} />
        <Kpi label="Avg holding (d)" value={(summary?.avg_holding_days ?? 0).toFixed(1)} />
        <Kpi
          label="Calibration gap"
          value={`${(summary?.confidence_calibration_gap ?? 0).toFixed(1)} pp`}
        />
      </div>

      {/* Accuracy trend */}
      <Card>
        <CardHeader>
          <CardTitle>Accuracy trend (monthly)</CardTitle>
        </CardHeader>
        <CardContent style={{ height: 280 }}>
          {trend.length === 0 ? (
            <EmptyHint />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="bucket" stroke="#9ca3af" fontSize={11} />
                <YAxis stroke="#9ca3af" fontSize={11} domain={[0, 100]} unit="%" />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    fontSize: 12,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line
                  type="monotone"
                  dataKey="win_rate"
                  stroke="#22c55e"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  name="Win rate"
                />
                <Line
                  type="monotone"
                  dataKey="avg_return_pct"
                  stroke="#38bdf8"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  name="Avg return %"
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Sector performance */}
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Sector performance</CardTitle>
            <span className="text-[10px] text-muted-foreground">
              Best: {summary?.best_sector || "—"} · Worst: {summary?.worst_sector || "—"}
            </span>
          </CardHeader>
          <CardContent style={{ height: 280 }}>
            {sectors.length === 0 ? (
              <EmptyHint />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sectors}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="sector" stroke="#9ca3af" fontSize={10} angle={-25} textAnchor="end" height={50} />
                  <YAxis stroke="#9ca3af" fontSize={11} unit="%" />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(var(--popover))",
                      border: "1px solid hsl(var(--border))",
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="win_rate" fill="#38bdf8" name="Win rate %" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Setup quality */}
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Setup quality</CardTitle>
            <span className="text-[10px] text-muted-foreground">
              Best: {summary?.best_setup || "—"} · Worst: {summary?.worst_setup || "—"}
            </span>
          </CardHeader>
          <CardContent className="space-y-2 max-h-72 overflow-y-auto">
            {setups.length === 0 ? (
              <EmptyHint />
            ) : (
              setups.slice(0, 15).map((s) => (
                <div
                  key={s.setup_name + s.mode}
                  className="flex items-center justify-between border border-border rounded-md px-3 py-2"
                >
                  <div>
                    <div className="text-sm font-medium">{s.setup_name}</div>
                    <div className="text-[10px] text-muted-foreground uppercase">
                      {s.mode} · {s.sample_size} samples · weight ×{s.weight_multiplier.toFixed(2)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div
                      className={`text-sm font-mono ${
                        s.win_rate >= 50 ? "text-bull" : "text-bear"
                      }`}
                    >
                      {s.win_rate.toFixed(1)}%
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                      Q{s.quality_score.toFixed(0)}
                    </div>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Sector × regime heatmap */}
      <Card>
        <CardHeader>
          <CardTitle>Sector × Regime — win rate heatmap</CardTitle>
        </CardHeader>
        <CardContent>
          <HeatmapTable cells={heatmap} />
        </CardContent>
      </Card>

      {/* Recent predictions */}
      <Card>
        <CardHeader>
          <CardTitle>Recent predictions</CardTitle>
        </CardHeader>
        <CardContent>
          {recent.length === 0 ? (
            <EmptyHint hint="No tracked predictions yet — generate some signals from /signals first." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-muted-foreground">
                  <tr className="text-left">
                    <th className="py-2 pr-3">Symbol</th>
                    <th className="py-2 pr-3">Action</th>
                    <th className="py-2 pr-3">Mode</th>
                    <th className="py-2 pr-3">Conf</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3">Outcome</th>
                    <th className="py-2 pr-3">Return</th>
                    <th className="py-2 pr-3">P&L (₹10k)</th>
                    <th className="py-2 pr-3">Regime</th>
                    <th className="py-2 pr-3">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((row) => {
                    const p = row.prediction;
                    const o = row.outcome;
                    const s = row.simulated;
                    const isWin = o?.outcome === "WIN" || o?.outcome === "PARTIAL_WIN";
                    const isLoss = o?.outcome === "LOSS";
                    return (
                      <tr key={p.id} className="border-t border-border/40">
                        <td className="py-2 pr-3 font-semibold">
                          {p.symbol.replace(".NS", "")}
                        </td>
                        <td className="py-2 pr-3">
                          <Badge
                            variant={
                              p.action === "BUY"
                                ? "bull"
                                : p.action === "SELL"
                                ? "bear"
                                : "neutral"
                            }
                          >
                            {p.action}
                          </Badge>
                        </td>
                        <td className="py-2 pr-3 uppercase text-[10px] text-muted-foreground">
                          {p.mode}
                        </td>
                        <td className="py-2 pr-3 font-mono">{p.confidence.toFixed(0)}%</td>
                        <td className="py-2 pr-3 font-mono text-[10px]">{p.status}</td>
                        <td className="py-2 pr-3">
                          {o ? (
                            <span className={isWin ? "text-bull" : isLoss ? "text-bear" : ""}>
                              {o.outcome}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className={`py-2 pr-3 font-mono ${pctClass(o?.realized_pct)}`}>
                          {o?.realized_pct !== undefined ? fmtPct(o.realized_pct) : "—"}
                        </td>
                        <td className={`py-2 pr-3 font-mono ${pctClass(s?.realized_pnl)}`}>
                          {s ? fmtINR((s.realized_pnl || 0) + (s.unrealized_pnl || 0)) : "—"}
                        </td>
                        <td className="py-2 pr-3 text-[10px] text-muted-foreground">
                          {p.market_regime || "—"}
                        </td>
                        <td className="py-2 pr-3 text-[10px] text-muted-foreground">
                          {new Date(p.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <p className="text-[10px] text-muted-foreground text-center">
        All P&L is simulated against historical OHLC. Educational only — not financial advice.
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

function EmptyHint({ hint }: { hint?: string }) {
  return (
    <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
      {hint || "No data yet. Predictions appear here after the engine validates them."}
    </div>
  );
}

function HeatmapTable({ cells }: { cells: HeatmapCell[] }) {
  if (!cells.length) return <EmptyHint />;
  const rows = Array.from(new Set(cells.map((c) => c.row))).sort();
  const cols = Array.from(new Set(cells.map((c) => c.col))).sort();
  const lookup = new Map<string, HeatmapCell>();
  cells.forEach((c) => lookup.set(`${c.row}::${c.col}`, c));
  return (
    <div className="overflow-x-auto">
      <table className="text-[11px]">
        <thead>
          <tr>
            <th className="px-2 py-1"></th>
            {cols.map((c) => (
              <th key={c} className="px-2 py-1 text-muted-foreground font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r}>
              <th className="px-2 py-1 text-left text-muted-foreground font-medium">
                {r}
              </th>
              {cols.map((c) => {
                const cell = lookup.get(`${r}::${c}`);
                if (!cell) {
                  return (
                    <td key={c} className="px-2 py-1 text-center text-muted-foreground">
                      —
                    </td>
                  );
                }
                const v = cell.value;
                const bg =
                  v >= 70
                    ? "rgba(34,197,94,0.55)"
                    : v >= 55
                    ? "rgba(34,197,94,0.30)"
                    : v >= 45
                    ? "rgba(148,163,184,0.30)"
                    : v >= 30
                    ? "rgba(239,68,68,0.30)"
                    : "rgba(239,68,68,0.55)";
                return (
                  <td
                    key={c}
                    className="px-2 py-1 text-center font-mono"
                    style={{ background: bg }}
                    title={`${cell.sample_size} samples`}
                  >
                    {v.toFixed(0)}%
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

"use client";
import * as React from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
  Legend,
} from "recharts";
import { api } from "@/lib/api";
import type { MarketRegimeSnapshot, RegimePerformance } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";

const REGIME_LABELS: Record<string, { label: string; color: string }> = {
  bullish_trend: { label: "Bullish trend", color: "text-bull" },
  bearish_trend: { label: "Bearish trend", color: "text-bear" },
  sideways: { label: "Sideways", color: "text-neutral" },
  high_volatility: { label: "High volatility", color: "text-bear" },
  risk_on: { label: "Risk-on", color: "text-bull" },
  risk_off: { label: "Risk-off", color: "text-bear" },
  unknown: { label: "Unknown", color: "text-muted-foreground" },
};

export default function RegimePage() {
  const [current, setCurrent] = React.useState<MarketRegimeSnapshot | null>(null);
  const [history, setHistory] = React.useState<MarketRegimeSnapshot[]>([]);
  const [perRegime, setPerRegime] = React.useState<RegimePerformance[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [c, h, p] = await Promise.all([
        api.regime.current(),
        api.regime.recent(120),
        api.performance.regimeBreakdown(),
      ]);
      setCurrent(c);
      setHistory(h.reverse());
      setPerRegime(p);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const refresh = async () => {
    setBusy(true);
    try {
      const r = await api.regime.refresh();
      setCurrent(r);
      await load();
    } finally {
      setBusy(false);
    }
  };

  if (loading && !current) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24" />
        <Skeleton className="h-72" />
      </div>
    );
  }

  const meta = REGIME_LABELS[current?.regime || "unknown"] || REGIME_LABELS.unknown;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Market Regime</h1>
          <p className="text-sm text-muted-foreground">
            Coarse classification of the current Indian-market environment.
            Used to bucket prediction outcomes and weight indicators.
          </p>
        </div>
        <Button onClick={refresh} disabled={busy}>
          {busy ? "Refreshing…" : "Refresh regime"}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Current regime</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className={`text-3xl font-bold ${meta.color}`}>{meta.label}</div>
              <p className="text-xs text-muted-foreground mt-1">
                {current?.description || "No regime snapshot yet."}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Stat
                label="Nifty trend"
                value={current?.nifty_trend?.toUpperCase() || "—"}
              />
              <Stat
                label="Nifty 20d return"
                value={
                  current?.nifty_return_20d !== undefined
                    ? `${current.nifty_return_20d.toFixed(2)}%`
                    : "—"
                }
                accent={
                  (current?.nifty_return_20d || 0) >= 0 ? "text-bull" : "text-bear"
                }
              />
              <Stat
                label="Breadth"
                value={
                  current?.breadth_score !== undefined
                    ? `${current.breadth_score.toFixed(1)}`
                    : "—"
                }
                accent={
                  (current?.breadth_score || 0) >= 0 ? "text-bull" : "text-bear"
                }
              />
              <Stat
                label="India VIX"
                value={
                  current?.volatility_index !== undefined && current?.volatility_index !== null
                    ? current!.volatility_index!.toFixed(2)
                    : "—"
                }
              />
              <Stat
                label="A/D ratio"
                value={
                  current?.advance_decline_ratio !== undefined
                    ? current.advance_decline_ratio.toFixed(2)
                    : "—"
                }
              />
              <Stat
                label="News sentiment"
                value={
                  current?.avg_news_sentiment !== undefined
                    ? current.avg_news_sentiment.toFixed(2)
                    : "—"
                }
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Regime history</CardTitle>
        </CardHeader>
        <CardContent style={{ height: 320 }}>
          {history.length === 0 ? (
            <EmptyHint />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis
                  dataKey="created_at"
                  stroke="#9ca3af"
                  fontSize={10}
                  tickFormatter={(v) => new Date(v).toLocaleDateString()}
                />
                <YAxis stroke="#9ca3af" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    fontSize: 12,
                  }}
                  labelFormatter={(v) => new Date(v).toLocaleString()}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <ReferenceLine y={0} stroke="#475569" />
                <Line
                  type="monotone"
                  dataKey="breadth_score"
                  stroke="#38bdf8"
                  strokeWidth={2}
                  dot={false}
                  name="Breadth"
                />
                <Line
                  type="monotone"
                  dataKey="nifty_return_20d"
                  stroke="#22c55e"
                  strokeWidth={2}
                  dot={false}
                  name="Nifty 20d %"
                />
                <Line
                  type="monotone"
                  dataKey="volatility_index"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={false}
                  name="VIX"
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>AI performance by regime</CardTitle>
        </CardHeader>
        <CardContent>
          {perRegime.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Not enough closed trades per regime yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-muted-foreground">
                  <tr className="text-left">
                    <th className="py-2 pr-3">Regime</th>
                    <th className="py-2 pr-3">Trades</th>
                    <th className="py-2 pr-3">Win rate</th>
                    <th className="py-2 pr-3">P&L</th>
                    <th className="py-2 pr-3">Return %</th>
                  </tr>
                </thead>
                <tbody>
                  {perRegime.map((r) => {
                    const reg = REGIME_LABELS[r.regime] || {
                      label: r.regime,
                      color: "text-muted-foreground",
                    };
                    return (
                      <tr key={r.regime} className="border-t border-border/40">
                        <td className={`py-2 pr-3 font-semibold ${reg.color}`}>
                          {reg.label}
                        </td>
                        <td className="py-2 pr-3 font-mono">{r.trades}</td>
                        <td
                          className={`py-2 pr-3 font-mono ${
                            r.win_rate >= 50 ? "text-bull" : "text-bear"
                          }`}
                        >
                          {r.win_rate.toFixed(1)}%
                        </td>
                        <td
                          className={`py-2 pr-3 font-mono ${
                            r.pnl >= 0 ? "text-bull" : "text-bear"
                          }`}
                        >
                          ₹{r.pnl.toFixed(0)}
                        </td>
                        <td
                          className={`py-2 pr-3 font-mono ${
                            r.return_pct >= 0 ? "text-bull" : "text-bear"
                          }`}
                        >
                          {r.return_pct.toFixed(2)}%
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
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: React.ReactNode;
  accent?: string;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className={`text-base font-mono font-semibold ${accent || ""}`}>{value}</div>
    </div>
  );
}

function EmptyHint() {
  return (
    <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
      No regime snapshots yet. They are recorded every 30 minutes.
    </div>
  );
}

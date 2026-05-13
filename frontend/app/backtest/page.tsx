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
} from "recharts";
import { api } from "@/lib/api";
import type { BacktestResponse } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

const STRATEGIES = [
  { v: "sma_crossover", l: "SMA Crossover" },
  { v: "rsi_reversal", l: "RSI Reversal" },
  { v: "breakout", l: "Donchian Breakout" },
  { v: "volume_breakout", l: "Volume Breakout" },
];

export default function BacktestPage() {
  const [symbol, setSymbol] = React.useState("RELIANCE.NS");
  const [strategy, setStrategy] = React.useState("sma_crossover");
  const [period, setPeriod] = React.useState("1y");
  const [fast, setFast] = React.useState(20);
  const [slow, setSlow] = React.useState(50);
  const [res, setRes] = React.useState<BacktestResponse | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.backtest({
        symbol,
        strategy,
        period,
        interval: "1d",
        fast,
        slow,
        rsi_low: 30,
        rsi_high: 70,
      });
      setRes(r);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  };

  const chartData = (res?.equity_curve || []).map((v, i) => ({ i, v }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Backtesting</h1>
        <p className="text-sm text-muted-foreground">
          Quick vectorised backtests. Long-only, daily bars.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Parameters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            <Field label="Symbol">
              <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} />
            </Field>
            <Field label="Strategy">
              <Select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
                {STRATEGIES.map((s) => (
                  <option value={s.v} key={s.v}>{s.l}</option>
                ))}
              </Select>
            </Field>
            <Field label="Period">
              <Select value={period} onChange={(e) => setPeriod(e.target.value)}>
                <option value="6mo">6mo</option>
                <option value="1y">1y</option>
                <option value="2y">2y</option>
                <option value="5y">5y</option>
              </Select>
            </Field>
            <Field label="Fast">
              <Input type="number" value={fast} onChange={(e) => setFast(Number(e.target.value))} />
            </Field>
            <Field label="Slow">
              <Input type="number" value={slow} onChange={(e) => setSlow(Number(e.target.value))} />
            </Field>
            <div className="self-end">
              <Button className="w-full" onClick={run} disabled={busy}>
                {busy ? "Running…" : "Run backtest"}
              </Button>
            </div>
          </div>
          {err && <p className="text-xs text-bear mt-2">{err}</p>}
        </CardContent>
      </Card>

      {res && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card className="lg:col-span-2">
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Equity Curve — {res.symbol}</CardTitle>
              <Badge variant="outline">{res.strategy}</Badge>
            </CardHeader>
            <CardContent style={{ height: 320 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="i" hide />
                  <YAxis stroke="#9ca3af" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(var(--popover))",
                      border: "1px solid hsl(var(--border))",
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "#9ca3af" }}
                  />
                  <Line type="monotone" dataKey="v" stroke="#38bdf8" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Stats</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Stat label="Trades" value={res.trades} />
              <Stat label="Win rate" value={`${res.win_rate.toFixed(1)}%`} />
              <Stat
                label="Total return"
                value={`${res.total_return_pct.toFixed(2)}%`}
                accent={res.total_return_pct >= 0 ? "text-bull" : "text-bear"}
              />
              <Stat
                label="Max drawdown"
                value={`${res.max_drawdown_pct.toFixed(2)}%`}
                accent="text-bear"
              />
              <Stat label="Avg R:R" value={res.avg_rr.toFixed(2)} />
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="space-y-1">
      <span className="block text-[11px] uppercase text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}
function Stat({ label, value, accent }: { label: string; value: React.ReactNode; accent?: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={`font-mono font-semibold ${accent || ""}`}>{value}</span>
    </div>
  );
}

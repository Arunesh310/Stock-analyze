"use client";
import * as React from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
  Legend,
} from "recharts";
import { api } from "@/lib/api";
import type { ConfidenceBucket } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs";

type Mode = "swing" | "intraday" | "positional";

export default function ConfidencePage() {
  const [mode, setMode] = React.useState<Mode>("swing");
  const [buckets, setBuckets] = React.useState<ConfidenceBucket[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const all = await api.confidence.buckets();
      setBuckets(all);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const recalibrate = async () => {
    setBusy(true);
    try {
      const all = await api.confidence.recalibrate();
      setBuckets(all);
    } finally {
      setBusy(false);
    }
  };

  if (loading && buckets.length === 0) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-16" />
        <Skeleton className="h-72" />
      </div>
    );
  }

  const data = buckets
    .filter((b) => b.mode === mode)
    .sort((a, b) => a.bucket_low - b.bucket_low)
    .map((b) => ({
      label: `${b.bucket_low}-${Math.min(b.bucket_high - 1, 99)}%`,
      midpoint: (b.bucket_low + Math.min(b.bucket_high, 100)) / 2,
      sample_size: b.sample_size,
      win_rate: b.win_rate,
      avg_return_pct: b.avg_return_pct,
      calibration_gap: b.calibration_gap,
    }));

  const overall = buckets
    .filter((b) => b.sample_size > 0)
    .reduce(
      (acc, b) => {
        acc.n += b.sample_size;
        acc.gap += b.calibration_gap * b.sample_size;
        return acc;
      },
      { n: 0, gap: 0 }
    );
  const overallGap = overall.n > 0 ? overall.gap / overall.n : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Confidence Reliability
          </h1>
          <p className="text-sm text-muted-foreground">
            Are our high-confidence signals actually winning more often than
            our low-confidence ones? A well-calibrated engine has zero gap
            between confidence and realised win-rate.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Tabs value={mode} onValueChange={(v) => setMode(v as Mode)}>
            <TabsList>
              <TabsTrigger value="intraday">Intraday</TabsTrigger>
              <TabsTrigger value="swing">Swing</TabsTrigger>
              <TabsTrigger value="positional">Positional</TabsTrigger>
            </TabsList>
          </Tabs>
          <Button onClick={recalibrate} disabled={busy}>
            {busy ? "Recalibrating…" : "Recalibrate"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Kpi
          label="Overall calibration gap"
          value={`${overallGap >= 0 ? "+" : ""}${overallGap.toFixed(2)} pp`}
          accent={Math.abs(overallGap) < 10 ? "text-bull" : "text-bear"}
          hint={
            overallGap > 0
              ? "Engine is overconfident."
              : overallGap < 0
              ? "Engine is underconfident."
              : "Perfectly calibrated."
          }
        />
        <Kpi
          label="Buckets in use"
          value={String(data.filter((d) => d.sample_size > 0).length)}
        />
        <Kpi
          label="Samples (this mode)"
          value={String(data.reduce((a, b) => a + b.sample_size, 0))}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Confidence vs realised win rate</CardTitle>
        </CardHeader>
        <CardContent style={{ height: 360 }}>
          {data.length === 0 ? (
            <EmptyHint />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="label" stroke="#9ca3af" fontSize={11} />
                <YAxis stroke="#9ca3af" fontSize={11} domain={[0, 100]} unit="%" />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    fontSize: 12,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <ReferenceLine y={50} stroke="#475569" strokeDasharray="3 3" />
                <Bar dataKey="sample_size" fill="#475569" name="Samples" />
                <Line
                  type="monotone"
                  dataKey="win_rate"
                  stroke="#22c55e"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  name="Win rate %"
                />
                <Line
                  type="monotone"
                  dataKey="midpoint"
                  stroke="#38bdf8"
                  strokeDasharray="4 4"
                  dot={false}
                  name="Expected (bucket midpoint)"
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Bucket details ({mode})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-muted-foreground">
                <tr className="text-left">
                  <th className="py-2 pr-3">Bucket</th>
                  <th className="py-2 pr-3">Samples</th>
                  <th className="py-2 pr-3">Wins</th>
                  <th className="py-2 pr-3">Losses</th>
                  <th className="py-2 pr-3">Win rate</th>
                  <th className="py-2 pr-3">Avg return</th>
                  <th className="py-2 pr-3">Gap</th>
                </tr>
              </thead>
              <tbody>
                {data.map((d, i) => (
                  <tr key={i} className="border-t border-border/40">
                    <td className="py-2 pr-3 font-medium">{d.label}</td>
                    <td className="py-2 pr-3 font-mono">{d.sample_size}</td>
                    <td className="py-2 pr-3 font-mono">{buckets[i]?.wins ?? 0}</td>
                    <td className="py-2 pr-3 font-mono">{buckets[i]?.losses ?? 0}</td>
                    <td
                      className={`py-2 pr-3 font-mono ${
                        d.win_rate >= 50 ? "text-bull" : "text-bear"
                      }`}
                    >
                      {d.win_rate.toFixed(1)}%
                    </td>
                    <td className="py-2 pr-3 font-mono">
                      {d.avg_return_pct.toFixed(2)}%
                    </td>
                    <td
                      className={`py-2 pr-3 font-mono ${
                        Math.abs(d.calibration_gap) < 10
                          ? "text-bull"
                          : "text-bear"
                      }`}
                    >
                      {d.calibration_gap >= 0 ? "+" : ""}
                      {d.calibration_gap.toFixed(1)} pp
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <p className="text-[10px] text-muted-foreground text-center">
        A positive gap means the engine claims more confidence than it has
        earned; a negative gap means it is too humble. The engine corrects
        future confidence using these numbers automatically.
      </p>
    </div>
  );
}

function Kpi({
  label,
  value,
  accent,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  accent?: string;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className="p-3">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div className={`text-2xl font-mono font-semibold ${accent || ""}`}>
          {value}
        </div>
        {hint && <p className="text-[10px] text-muted-foreground mt-1">{hint}</p>}
      </CardContent>
    </Card>
  );
}

function EmptyHint() {
  return (
    <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
      No confidence data yet — wait for predictions to be validated.
    </div>
  );
}

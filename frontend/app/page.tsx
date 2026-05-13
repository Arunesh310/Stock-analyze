"use client";
import * as React from "react";
import { api } from "@/lib/api";
import type { AIRollup, DashboardData, Signal } from "@/lib/types";
import { IndexStrip } from "@/components/market/IndexStrip";
import { QuoteCard } from "@/components/market/QuoteCard";
import { MoversList } from "@/components/market/MoversList";
import { SectorHeatmap } from "@/components/market/SectorHeatmap";
import { BreadthBar } from "@/components/market/BreadthBar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Badge } from "@/components/ui/Badge";
import { fmtINR, fmtPct, pctClass } from "@/lib/utils";
import Link from "next/link";

export default function HomePage() {
  const [data, setData] = React.useState<DashboardData | null>(null);
  const [picks, setPicks] = React.useState<Signal[]>([]);
  const [aiPerf, setAiPerf] = React.useState<AIRollup | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [err, setErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setErr(null);
      try {
        const [d, p, a] = await Promise.all([
          api.dashboard(),
          api.topPicks("swing", 6).catch(() => [] as Signal[]),
          api.aiPerformance().catch(() => null),
        ]);
        if (!cancelled) {
          setData(d);
          setPicks(p);
          setAiPerf(a);
        }
      } catch (e: any) {
        if (!cancelled) setErr(String(e?.message || e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    const t = setInterval(async () => {
      try {
        const [d, a] = await Promise.all([
          api.dashboard(),
          api.aiPerformance().catch(() => null),
        ]);
        setData(d);
        if (a) setAiPerf(a);
      } catch {}
    }, 30000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-16 w-full" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      </div>
    );
  }

  if (err && !data) {
    return (
      <Card>
        <CardContent className="p-6">
          <p className="text-sm text-bear">Failed to load dashboard: {err}</p>
          <p className="text-xs text-muted-foreground mt-2">
            Make sure the FastAPI backend is running on{" "}
            <code className="text-foreground">http://localhost:8000</code>.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Market Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Live snapshot of Indian markets, sector strength and AI top picks.
        </p>
      </div>

      <IndexStrip items={data.indices} />

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Top Movers
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {data.gainers.slice(0, 4).map((q) => (
            <QuoteCard key={q.symbol} q={q} />
          ))}
          {data.losers.slice(0, 4).map((q) => (
            <QuoteCard key={q.symbol} q={q} />
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <SectorHeatmap sectors={data.sectors} />
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>AI Top Picks (swing)</CardTitle>
              <Link href="/signals" className="text-xs text-primary hover:underline">
                View all →
              </Link>
            </CardHeader>
            <CardContent className="space-y-2">
              {picks.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  No high-conviction picks right now.
                </p>
              )}
              {picks.map((s) => (
                <Link
                  key={s.symbol}
                  href={`/stocks/${encodeURIComponent(s.symbol)}`}
                  className="flex items-center justify-between rounded-md border border-border p-3 hover:bg-secondary/50"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge variant={s.action === "BUY" ? "bull" : s.action === "SELL" ? "bear" : "neutral"}>
                        {s.action}
                      </Badge>
                      <span className="font-semibold">{s.symbol.replace(".NS", "")}</span>
                      <span className="text-xs text-muted-foreground">{s.confidence.toFixed(0)}% conf</span>
                    </div>
                    <p className="text-[11px] text-muted-foreground line-clamp-1 mt-1">
                      {s.reasoning}
                    </p>
                  </div>
                  <div className="text-right text-xs">
                    <div className="text-muted-foreground">SL {s.stoploss ?? "—"}</div>
                    <div className="text-muted-foreground">T1 {s.target1 ?? "—"}</div>
                  </div>
                </Link>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <BreadthBar breadth={data.breadth} fii={data.fii_dii} />
          {aiPerf && <AIPerformanceWidget rollup={aiPerf} />}
          <MoversList title="Top Gainers" items={data.gainers} />
          <MoversList title="Top Losers" items={data.losers} />
          <MoversList title="Most Active" items={data.most_active} />
        </div>
      </div>

      <p className="text-[10px] text-muted-foreground text-center">{data.disclaimer}</p>
    </div>
  );
}

function AIPerformanceWidget({ rollup }: { rollup: AIRollup }) {
  const wr = rollup.summary.win_rate;
  const pnl = rollup.summary.total_simulated_pnl;
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="text-sm">AI Engine Health</CardTitle>
        <Link
          href="/performance"
          className="text-[11px] text-primary hover:underline"
        >
          Details →
        </Link>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Regime</span>
          <Badge variant="outline">{rollup.regime.regime}</Badge>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Win rate</span>
          <span className={`font-mono font-semibold ${wr >= 50 ? "text-bull" : "text-bear"}`}>
            {wr.toFixed(1)}%
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Simulated P&L</span>
          <span className={`font-mono font-semibold ${pctClass(pnl)}`}>{fmtINR(pnl)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Cumulative return</span>
          <span className={`font-mono font-semibold ${pctClass(rollup.summary.cumulative_return_pct)}`}>
            {fmtPct(rollup.summary.cumulative_return_pct)}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Calibration gap</span>
          <span
            className={`font-mono font-semibold ${
              Math.abs(rollup.calibration_gap) < 10 ? "text-bull" : "text-bear"
            }`}
          >
            {rollup.calibration_gap >= 0 ? "+" : ""}
            {rollup.calibration_gap.toFixed(1)} pp
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Open / closed</span>
          <span className="font-mono">
            {rollup.summary.open_predictions} / {rollup.summary.closed_predictions}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

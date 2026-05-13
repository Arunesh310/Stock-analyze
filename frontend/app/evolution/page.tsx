"use client";
import * as React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Minus,
  RefreshCw,
  Sparkles,
  TrendingDown,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  ImprovementScore,
  LearningChange,
  RegimeStrategyCell,
  RollingWindows,
  SignalConversion,
  SignalOutcomeRow,
  StrategyPerformance,
} from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { FailureAnalysisSection } from "@/components/evolution/FailureAnalysis";
import { MLConfidenceSection } from "@/components/evolution/MLConfidence";
import { cn, fmtPct, pctClass } from "@/lib/utils";

type Mode = "all" | "intraday" | "swing" | "positional";

export default function EvolutionPage() {
  const [mode, setMode] = React.useState<Mode>("all");
  const [improvement, setImprovement] = React.useState<ImprovementScore | null>(null);
  const [rolling, setRolling] = React.useState<RollingWindows | null>(null);
  const [conversion, setConversion] = React.useState<SignalConversion | null>(null);
  const [changes, setChanges] = React.useState<LearningChange[]>([]);
  const [strategies, setStrategies] = React.useState<StrategyPerformance[]>([]);
  const [regimeMatrix, setRegimeMatrix] = React.useState<RegimeStrategyCell[]>([]);
  const [outcomes, setOutcomes] = React.useState<SignalOutcomeRow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);
  const [refreshSignal, setRefreshSignal] = React.useState(0);

  const load = React.useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const m = mode === "all" ? undefined : mode;
      const [imp, roll, conv, chg, strat, reg, out] = await Promise.all([
        api.evolution.improvementScore(m),
        api.evolution.rolling(m),
        api.evolution.signalConversion(m),
        api.evolution.recentChanges(40),
        api.evolution.strategyPerformance(m),
        api.evolution.regimeStrategyMatrix(m),
        api.evolution.recentOutcomes(60),
      ]);
      setImprovement(imp);
      setRolling(roll);
      setConversion(conv);
      setChanges(chg);
      setStrategies(strat);
      setRegimeMatrix(reg);
      setOutcomes(out);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [mode]);

  React.useEffect(() => {
    load();
  }, [load]);

  const refresh = async () => {
    setBusy(true);
    try {
      await api.learning.runCycle();
      await api.validate.run(200);
      await load();
      setRefreshSignal((n) => n + 1);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  };

  if (loading && !improvement) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-72" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-primary" />
            AI Evolution Dashboard
          </h1>
          <p className="text-sm text-muted-foreground max-w-2xl">
            Transparent view of how the prediction engine is learning. Every
            weight adjustment, every win, every failure — fully visible.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Tabs value={mode} onValueChange={(v: string) => setMode(v as Mode)}>
            <TabsList>
              <TabsTrigger value="all">All</TabsTrigger>
              <TabsTrigger value="intraday">Intraday</TabsTrigger>
              <TabsTrigger value="swing">Swing</TabsTrigger>
              <TabsTrigger value="positional">Positional</TabsTrigger>
            </TabsList>
          </Tabs>
          <Button onClick={refresh} disabled={busy} variant="secondary" size="sm">
            <RefreshCw className={cn("h-4 w-4 mr-1", busy && "animate-spin")} />
            {busy ? "Learning..." : "Run learning cycle"}
          </Button>
        </div>
      </div>

      {err && (
        <div className="rounded-md border border-bear/40 bg-bear-soft px-4 py-2 text-sm text-bear">
          {err}
        </div>
      )}

      {/* ---- Headline: improvement score + rolling windows ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <ImprovementCard score={improvement} />
        <RollingCard rolling={rolling} />
      </div>

      {/* ---- Signal conversion ---- */}
      <ConversionCard conversion={conversion} />

      {/* ---- XGBoost ML confidence model ---- */}
      <MLConfidenceSection
        refreshSignal={refreshSignal}
        onRetrained={() => setRefreshSignal((n) => n + 1)}
      />

      {/* ---- Failure Analysis Reports (what failed + what AI learned) ---- */}
      <FailureAnalysisSection
        mode={mode === "all" ? undefined : mode}
        refreshSignal={refreshSignal}
      />

      {/* ---- Strategy leaderboard + regime matrix ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <StrategyCard strategies={strategies} />
        <RegimeMatrixCard cells={regimeMatrix} />
      </div>

      {/* ---- Learning changes log ---- */}
      <ChangesCard changes={changes} />

      {/* ---- Recent signal outcomes ---- */}
      <OutcomesCard outcomes={outcomes} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Improvement score card
// ---------------------------------------------------------------------------

function ImprovementCard({ score }: { score: ImprovementScore | null }) {
  if (!score) {
    return (
      <Card className="lg:col-span-1">
        <CardHeader>
          <CardTitle>AI Improvement Score</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No data yet.</p>
        </CardContent>
      </Card>
    );
  }
  const s = score.score;
  const tone = s >= 60 ? "text-bull" : s >= 40 ? "text-amber-400" : "text-bear";
  const arrow =
    s >= 55 ? <TrendingUp className="h-5 w-5" /> :
    s <= 45 ? <TrendingDown className="h-5 w-5" /> :
    <Minus className="h-5 w-5" />;
  return (
    <Card className="lg:col-span-1">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          AI Improvement Score
          <Badge variant="outline" className="text-[10px]">
            Last 30d vs prior 30d
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className={cn("flex items-end gap-2 text-5xl font-bold", tone)}>
          {s.toFixed(0)}
          <span className="text-base text-muted-foreground font-medium pb-1">
            / 100
          </span>
          <span className={cn("ml-auto", tone)}>{arrow}</span>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          {score.narrative}
        </p>
        <div className="grid grid-cols-2 gap-2 text-xs pt-1">
          <DeltaPill label="Win-rate" v={score.deltas.win_rate_pp} suffix=" pp" />
          <DeltaPill label="Avg return" v={score.deltas.avg_return_pct} suffix=" %" />
          <DeltaPill label="Calibration" v={score.deltas.calibration_pp} suffix=" pp" />
          <DeltaPill
            label="Stoploss hits"
            v={score.deltas.stoploss_rate_pp}
            suffix=" pp"
            invertGoodBad
          />
        </div>
      </CardContent>
    </Card>
  );
}

function DeltaPill({
  label,
  v,
  suffix,
  invertGoodBad,
}: {
  label: string;
  v: number;
  suffix?: string;
  invertGoodBad?: boolean;
}) {
  const positive = invertGoodBad ? v >= 0 : v >= 0;
  const tone = positive ? "text-bull" : "text-bear";
  return (
    <div className="rounded-md border border-border bg-background/40 px-2 py-1.5">
      <div className="text-[10px] uppercase text-muted-foreground tracking-wider">
        {label}
      </div>
      <div className={cn("text-sm font-semibold flex items-center gap-1", tone)}>
        {v >= 0 ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
        {v >= 0 ? "+" : ""}
        {v.toFixed(2)}
        {suffix || ""}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rolling windows
// ---------------------------------------------------------------------------

function RollingCard({ rolling }: { rolling: RollingWindows | null }) {
  if (!rolling) {
    return (
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Rolling-window accuracy</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No closed trades yet.</p>
        </CardContent>
      </Card>
    );
  }
  const order: (keyof RollingWindows)[] = ["7d", "30d", "90d", "all_time"];
  const rows = order.map((k) => ({
    window: k === "all_time" ? "All-time" : k,
    ...rolling[k],
  }));
  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle>Rolling-window accuracy</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          {rows.map((r) => (
            <div
              key={r.window}
              className="rounded-md border border-border bg-background/40 p-3"
            >
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                {r.window}
              </div>
              <div className="mt-1 text-2xl font-bold tabular-nums">
                {r.win_rate.toFixed(1)}%
              </div>
              <div className="text-[11px] text-muted-foreground">
                {r.trades} trades · avg {fmtPct(r.avg_return_pct)}
              </div>
            </div>
          ))}
        </div>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 10, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
              <XAxis dataKey="window" stroke="#9ca3af" fontSize={11} />
              <YAxis stroke="#9ca3af" fontSize={11} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                contentStyle={{
                  background: "rgba(15,15,15,0.95)",
                  border: "1px solid #374151",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(v: number) => `${v.toFixed(1)}%`}
              />
              <Bar dataKey="win_rate" fill="#22c55e" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Signal conversion (BUY vs SELL vs target/stop)
// ---------------------------------------------------------------------------

function ConversionCard({ conversion }: { conversion: SignalConversion | null }) {
  if (!conversion) return null;
  const c = conversion;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Signal conversion</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <ConvTile
            title="BUY success"
            value={`${c.buy.win_rate.toFixed(1)}%`}
            sub={`${c.buy.wins} / ${c.buy.wins + c.buy.losses} decided`}
            tone="bull"
          />
          <ConvTile
            title="SELL success"
            value={`${c.sell.win_rate.toFixed(1)}%`}
            sub={`${c.sell.wins} / ${c.sell.wins + c.sell.losses} decided`}
            tone="bear"
          />
          <ConvTile
            title="Target 1 hit"
            value={`${c.target1_hit_rate.toFixed(1)}%`}
            sub="across all signals"
          />
          <ConvTile
            title="Target 2 hit"
            value={`${c.target2_hit_rate.toFixed(1)}%`}
            sub="extended target"
          />
          <ConvTile
            title="Stoploss hit"
            value={`${c.stoploss_hit_rate.toFixed(1)}%`}
            sub="risk discipline"
            tone={c.stoploss_hit_rate > 25 ? "bear" : undefined}
          />
          <ConvTile
            title="False breakouts"
            value={`${c.false_breakout_rate.toFixed(1)}%`}
            sub="ran then reversed"
            tone={c.false_breakout_rate > 15 ? "bear" : undefined}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function ConvTile({
  title,
  value,
  sub,
  tone,
}: {
  title: string;
  value: string;
  sub: string;
  tone?: "bull" | "bear";
}) {
  const toneClass =
    tone === "bull" ? "text-bull" : tone === "bear" ? "text-bear" : "text-foreground";
  return (
    <div className="rounded-md border border-border bg-background/40 p-3">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {title}
      </div>
      <div className={cn("mt-1 text-xl font-bold tabular-nums", toneClass)}>
        {value}
      </div>
      <div className="text-[10px] text-muted-foreground mt-0.5">{sub}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Strategy leaderboard
// ---------------------------------------------------------------------------

function StrategyCard({ strategies }: { strategies: StrategyPerformance[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Strategy leaderboard</CardTitle>
      </CardHeader>
      <CardContent>
        {strategies.length === 0 ? (
          <p className="text-sm text-muted-foreground">No closed trades yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-2 font-medium">Strategy</th>
                  <th className="text-right py-2 px-2 font-medium">Trades</th>
                  <th className="text-right py-2 px-2 font-medium">Win rate</th>
                  <th className="text-right py-2 px-2 font-medium">Avg return</th>
                  <th className="text-right py-2 px-2 font-medium">PF</th>
                </tr>
              </thead>
              <tbody>
                {strategies.map((s) => (
                  <tr key={s.strategy} className="border-b border-border/50">
                    <td className="py-2 px-2 font-medium">{s.strategy}</td>
                    <td className="py-2 px-2 text-right tabular-nums">{s.trades}</td>
                    <td className="py-2 px-2 text-right tabular-nums font-semibold">
                      {s.win_rate.toFixed(1)}%
                    </td>
                    <td
                      className={cn(
                        "py-2 px-2 text-right tabular-nums",
                        pctClass(s.avg_return_pct)
                      )}
                    >
                      {fmtPct(s.avg_return_pct)}
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums">
                      {s.profit_factor === null ? "∞" : s.profit_factor.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Regime × strategy matrix
// ---------------------------------------------------------------------------

function RegimeMatrixCard({ cells }: { cells: RegimeStrategyCell[] }) {
  // Pivot into rows = regime, cols = strategy
  const regimes = Array.from(new Set(cells.map((c) => c.regime)));
  const strategies = Array.from(new Set(cells.map((c) => c.strategy)));
  const lookup: Record<string, RegimeStrategyCell> = {};
  cells.forEach((c) => {
    lookup[`${c.regime}::${c.strategy}`] = c;
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Regime × strategy heatmap</CardTitle>
      </CardHeader>
      <CardContent>
        {cells.length === 0 ? (
          <p className="text-sm text-muted-foreground">No data yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="text-left py-1 px-1 font-medium">Regime</th>
                  {strategies.map((s) => (
                    <th key={s} className="text-center py-1 px-1 font-medium">
                      {s}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {regimes.map((r) => (
                  <tr key={r}>
                    <td className="py-1 px-1 font-medium capitalize">
                      {r.replace(/_/g, " ")}
                    </td>
                    {strategies.map((s) => {
                      const cell = lookup[`${r}::${s}`];
                      if (!cell || cell.trades === 0) {
                        return (
                          <td
                            key={s}
                            className="py-1 px-1 text-center text-muted-foreground/60"
                          >
                            —
                          </td>
                        );
                      }
                      const bg =
                        cell.win_rate >= 60
                          ? "bg-bull/30 text-bull"
                          : cell.win_rate >= 45
                          ? "bg-amber-500/20 text-amber-400"
                          : "bg-bear/30 text-bear";
                      return (
                        <td key={s} className="py-1 px-1">
                          <div
                            className={cn(
                              "rounded text-center py-1 px-1 font-semibold tabular-nums",
                              bg
                            )}
                            title={`${cell.wins}/${cell.trades} wins`}
                          >
                            {cell.win_rate.toFixed(0)}%
                            <div className="text-[9px] opacity-75 font-normal">
                              n={cell.trades}
                            </div>
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Learning change log
// ---------------------------------------------------------------------------

function ChangesCard({ changes }: { changes: LearningChange[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>What the AI changed</CardTitle>
      </CardHeader>
      <CardContent>
        {changes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No learning cycles run yet. Click <em>Run learning cycle</em> at the top.
          </p>
        ) : (
          <ul className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {changes.map((c) => {
              const isDelta = c.event === "weight_changed";
              const after = c.details?.after as number | undefined;
              const before = c.details?.before as number | undefined;
              const direction =
                after !== undefined && before !== undefined
                  ? after > before
                    ? "up"
                    : "down"
                  : null;
              return (
                <li
                  key={c.id}
                  className="rounded-md border border-border bg-background/40 px-3 py-2 flex items-start gap-2"
                >
                  <div className="mt-0.5">
                    {direction === "up" ? (
                      <TrendingUp className="h-4 w-4 text-bull" />
                    ) : direction === "down" ? (
                      <TrendingDown className="h-4 w-4 text-bear" />
                    ) : (
                      <Sparkles className="h-4 w-4 text-primary" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium leading-snug">
                      {c.summary}
                    </div>
                    <div className="flex flex-wrap items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                      <Badge variant="outline" className="text-[10px]">
                        {isDelta ? "Weight changed" : c.event.replace(/_/g, " ")}
                      </Badge>
                      <span>
                        {c.created_at
                          ? new Date(c.created_at).toLocaleString("en-IN", {
                              dateStyle: "medium",
                              timeStyle: "short",
                            })
                          : "—"}
                      </span>
                      {c.impact_score > 0 && (
                        <span>impact {c.impact_score.toFixed(2)}</span>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Recent signal outcomes
// ---------------------------------------------------------------------------

function OutcomesCard({ outcomes }: { outcomes: SignalOutcomeRow[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent predictions: outcome timeline</CardTitle>
      </CardHeader>
      <CardContent>
        {outcomes.length === 0 ? (
          <p className="text-sm text-muted-foreground">No predictions yet.</p>
        ) : (
          <div className="overflow-x-auto max-h-[480px]">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted-foreground sticky top-0 bg-background">
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-2 font-medium">Date</th>
                  <th className="text-left py-2 px-2 font-medium">Symbol</th>
                  <th className="text-left py-2 px-2 font-medium">Signal</th>
                  <th className="text-right py-2 px-2 font-medium">Conf</th>
                  <th className="text-left py-2 px-2 font-medium">Outcome</th>
                  <th className="text-right py-2 px-2 font-medium">Return</th>
                  <th className="text-left py-2 px-2 font-medium">T1 / T2 / SL</th>
                  <th className="text-right py-2 px-2 font-medium">Hold (d)</th>
                </tr>
              </thead>
              <tbody>
                {outcomes.map((o) => (
                  <tr key={o.id} className="border-b border-border/50">
                    <td className="py-2 px-2 text-xs text-muted-foreground">
                      {o.created_at
                        ? new Date(o.created_at).toLocaleDateString("en-IN", {
                            month: "short",
                            day: "numeric",
                          })
                        : "—"}
                    </td>
                    <td className="py-2 px-2 font-medium">{o.symbol.replace(".NS", "")}</td>
                    <td className="py-2 px-2">
                      <Badge
                        variant={
                          o.action === "BUY"
                            ? "bull"
                            : o.action === "SELL"
                            ? "bear"
                            : "outline"
                        }
                      >
                        {o.action}
                      </Badge>
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums">
                      {o.confidence?.toFixed(0) ?? "—"}
                    </td>
                    <td className="py-2 px-2">
                      <VerdictBadge verdict={o.verdict} />
                    </td>
                    <td
                      className={cn(
                        "py-2 px-2 text-right tabular-nums font-semibold",
                        pctClass(o.return_pct ?? 0)
                      )}
                    >
                      {o.return_pct !== null ? fmtPct(o.return_pct) : "—"}
                    </td>
                    <td className="py-2 px-2">
                      <span className="inline-flex items-center gap-1 text-xs">
                        <HitIcon hit={o.target1_hit} />
                        <HitIcon hit={o.target2_hit} />
                        <HitIcon hit={o.stoploss_hit} bear />
                      </span>
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums text-xs text-muted-foreground">
                      {o.holding_days !== null ? o.holding_days.toFixed(1) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function VerdictBadge({ verdict }: { verdict: SignalOutcomeRow["verdict"] }) {
  if (verdict === "SUCCESS")
    return (
      <Badge variant="bull">
        <CheckCircle2 className="h-3 w-3 mr-1" />
        Success
      </Badge>
    );
  if (verdict === "FAILED")
    return (
      <Badge variant="bear">
        <XCircle className="h-3 w-3 mr-1" />
        Failed
      </Badge>
    );
  if (verdict === "EXPIRED")
    return <Badge variant="outline">Expired</Badge>;
  if (verdict === "NO ENTRY")
    return <Badge variant="outline">No entry</Badge>;
  return <Badge variant="outline">Open</Badge>;
}

function HitIcon({ hit, bear }: { hit: boolean | null; bear?: boolean }) {
  if (hit === null || hit === undefined)
    return <span className="text-muted-foreground/40">·</span>;
  if (hit)
    return (
      <CheckCircle2
        className={cn("h-3.5 w-3.5", bear ? "text-bear" : "text-bull")}
      />
    );
  return <Minus className="h-3.5 w-3.5 text-muted-foreground/40" />;
}

"use client";
import * as React from "react";
import {
  AlertOctagon,
  Brain,
  ChevronDown,
  ChevronUp,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { api } from "@/lib/api";
import type { FailureReport, TopFailureReason } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn, fmtPct, pctClass } from "@/lib/utils";

type Props = {
  mode?: "intraday" | "swing" | "positional";
  refreshSignal?: number;
};

export function FailureAnalysisSection({ mode, refreshSignal }: Props) {
  const [failures, setFailures] = React.useState<FailureReport[] | null>(null);
  const [topReasons, setTopReasons] = React.useState<TopFailureReason[] | null>(
    null
  );
  const [err, setErr] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try {
      const [recent, top] = await Promise.all([
        api.failures.recent({ limit: 12, mode }),
        api.failures.topReasons({ limit: 8, days: 60, mode }),
      ]);
      setFailures(recent);
      setTopReasons(top);
      setErr(null);
    } catch (e: any) {
      setErr(String(e?.message || e));
    }
  }, [mode]);

  React.useEffect(() => {
    load();
  }, [load, refreshSignal]);

  return (
    <div className="space-y-3">
      <TopFailureReasonsCard reasons={topReasons} />
      <RecentFailuresCard failures={failures} error={err} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Top failure reasons aggregate
// ---------------------------------------------------------------------------

function TopFailureReasonsCard({
  reasons,
}: {
  reasons: TopFailureReason[] | null;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertOctagon className="h-5 w-5 text-bear" />
          Top failure reasons (60 days)
          <span className="text-xs font-normal text-muted-foreground">
            Where the AI keeps getting it wrong — and the regimes where it happens.
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {reasons === null ? (
          <Skeleton className="h-32 w-full" />
        ) : reasons.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No closed losing trades in the last 60 days — either the filter is
            tight or we have not validated enough trades yet.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {reasons.map((r) => (
              <div
                key={r.category}
                className="rounded-md border border-bear/30 bg-bear/5 p-3 flex flex-col gap-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="text-sm font-semibold leading-tight">
                    {r.title}
                  </div>
                  <Badge variant="bear" className="shrink-0">
                    {r.count}
                  </Badge>
                </div>
                <p className="text-[11px] text-muted-foreground line-clamp-2">
                  e.g. {r.example}
                </p>
                <div className="flex items-center justify-between text-[10px] text-muted-foreground border-t border-bear/20 pt-1">
                  <span>
                    Avg conf{" "}
                    <span className="font-semibold text-foreground">
                      {r.avg_confidence_at_signal.toFixed(0)}%
                    </span>
                  </span>
                  <span className="truncate">
                    {Object.keys(r.regime_breakdown || {})
                      .slice(0, 2)
                      .map((reg) => reg.replace(/_/g, " "))
                      .join(", ")}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Recent failures with full why+learning
// ---------------------------------------------------------------------------

function RecentFailuresCard({
  failures,
  error,
}: {
  failures: FailureReport[] | null;
  error: string | null;
}) {
  const [openIds, setOpenIds] = React.useState<Set<number>>(new Set());

  const toggle = (id: number) => {
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent failure analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-bear">Failed to load: {error}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-primary" />
          Failure analysis reports
          <span className="text-xs font-normal text-muted-foreground">
            Every closed losing trade — what we predicted, what happened, why it
            failed, and what the AI changed in response.
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {failures === null ? (
          <Skeleton className="h-72 w-full" />
        ) : failures.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No closed losing trades yet. Either the filter is doing its job, or
            we need more validated trades — run a learning cycle from the top.
          </p>
        ) : (
          <ul className="space-y-2">
            {failures.map((f) => {
              const isOpen = openIds.has(f.prediction_id);
              return (
                <li
                  key={f.prediction_id}
                  className="rounded-md border border-border bg-background/40 overflow-hidden"
                >
                  <button
                    type="button"
                    onClick={() => toggle(f.prediction_id)}
                    className="w-full px-3 py-2 flex items-center justify-between gap-3 hover:bg-secondary/30 transition-colors text-left"
                  >
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <Badge variant={f.action === "BUY" ? "bull" : "bear"}>
                        {f.action}
                      </Badge>
                      <span className="font-medium truncate">
                        {f.symbol.replace(".NS", "")}
                      </span>
                      <span className="text-xs text-muted-foreground truncate">
                        @ {f.confidence_at_signal.toFixed(0)}% confidence ·{" "}
                        {f.category_title}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span
                        className={cn(
                          "text-sm font-semibold tabular-nums",
                          pctClass(f.realized_pct ?? 0)
                        )}
                      >
                        {f.realized_pct !== null && f.realized_pct !== undefined
                          ? fmtPct(f.realized_pct)
                          : "—"}
                      </span>
                      <Badge variant="outline" className="text-[10px]">
                        {f.outcome}
                      </Badge>
                      {isOpen ? (
                        <ChevronUp className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      )}
                    </div>
                  </button>
                  {isOpen && <FailureDetail f={f} />}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function FailureDetail({ f }: { f: FailureReport }) {
  return (
    <div className="border-t border-border bg-card/40 p-3 grid grid-cols-1 lg:grid-cols-2 gap-3">
      {/* WHY it failed */}
      <div className="space-y-2">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
          Why it failed
        </div>
        {f.narrative && (
          <p className="text-sm text-muted-foreground italic leading-relaxed border-l-2 border-bear/40 pl-2">
            {f.narrative}
          </p>
        )}
        <ul className="space-y-1.5">
          {f.contributing_factors.map((bullet, i) => (
            <li key={i} className="flex items-start gap-2 text-sm">
              <TrendingDown className="h-3.5 w-3.5 text-bear mt-0.5 shrink-0" />
              <span className="leading-snug">{bullet}</span>
            </li>
          ))}
        </ul>

        <div className="grid grid-cols-2 gap-2 pt-2 text-[11px]">
          <Stat
            label="Entry zone"
            value={
              f.entry_ref
                ? `₹${f.entry_ref.toFixed(2)}${
                    f.entry_triggered ? " · triggered" : " · not triggered"
                  }`
                : "—"
            }
          />
          <Stat
            label="Plan SL / T1"
            value={
              f.stoploss && f.target1
                ? `₹${f.stoploss.toFixed(2)} / ₹${f.target1.toFixed(2)}`
                : "—"
            }
          />
          <Stat
            label="Max favourable"
            value={
              f.max_favorable_pct !== null && f.max_favorable_pct !== undefined
                ? `+${f.max_favorable_pct.toFixed(2)}%`
                : "—"
            }
          />
          <Stat
            label="Max adverse"
            value={
              f.max_adverse_pct !== null && f.max_adverse_pct !== undefined
                ? `${f.max_adverse_pct.toFixed(2)}%`
                : "—"
            }
          />
          <Stat
            label="Regime"
            value={f.market_regime?.replace(/_/g, " ") || "—"}
          />
          <Stat
            label="Held"
            value={
              f.holding_days !== null && f.holding_days !== undefined
                ? `${f.holding_days.toFixed(1)} days`
                : "—"
            }
          />
        </div>
      </div>

      {/* AI response */}
      <div className="space-y-2">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          AI response — weight adjustments applied
        </div>
        {f.learning_applied.length === 0 ? (
          <p className="text-xs text-muted-foreground italic">
            No related weight changes were logged within 24h of validation. The
            AI may still be gathering samples on this failure pattern (it needs
            ≥4–5 instances before downgrading a setup).
          </p>
        ) : (
          <ul className="space-y-1.5">
            {f.learning_applied.map((l) => {
              const up =
                l.after !== null &&
                l.after !== undefined &&
                l.before !== null &&
                l.before !== undefined &&
                l.after > l.before;
              return (
                <li
                  key={l.log_id}
                  className="rounded-md border border-border bg-background/40 px-2 py-1.5 flex items-start gap-2"
                >
                  {up ? (
                    <TrendingUp className="h-3.5 w-3.5 text-bull mt-0.5 shrink-0" />
                  ) : (
                    <TrendingDown className="h-3.5 w-3.5 text-bear mt-0.5 shrink-0" />
                  )}
                  <div className="flex-1 min-w-0 text-xs leading-snug">
                    {l.summary}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <p className="text-[10px] text-muted-foreground pt-2 leading-relaxed">
          Confidence calibration also self-corrects — if {Math.round(
            f.confidence_at_signal / 10
          ) * 10}
          %-bucket signals keep failing, future signals in that bucket get
          damped automatically.
        </p>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="border border-border rounded px-2 py-1 bg-background/40">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="text-xs font-medium tabular-nums truncate">{value}</div>
    </div>
  );
}

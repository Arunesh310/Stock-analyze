"use client";
import * as React from "react";
import { api } from "@/lib/api";
import type {
  FeedbackCategoryCount,
  IndicatorPerformanceRow,
  LearningFeedbackRow,
  LearningLog,
  SetupQuality,
} from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs";

type Tab = "failures" | "successes" | "indicators" | "setups" | "log";

export default function LearningPage() {
  const [tab, setTab] = React.useState<Tab>("failures");
  const [failures, setFailures] = React.useState<FeedbackCategoryCount[]>([]);
  const [successes, setSuccesses] = React.useState<FeedbackCategoryCount[]>([]);
  const [indicators, setIndicators] = React.useState<IndicatorPerformanceRow[]>([]);
  const [setups, setSetups] = React.useState<SetupQuality[]>([]);
  const [recent, setRecent] = React.useState<LearningFeedbackRow[]>([]);
  const [logs, setLogs] = React.useState<LearningLog[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [f, s, ind, sp, r, l] = await Promise.all([
        api.learning.topFailures(15),
        api.learning.topSuccesses(15),
        api.learning.indicators(),
        api.learning.setups(),
        api.learning.recent(50),
        api.learning.logs(50),
      ]);
      setFailures(f);
      setSuccesses(s);
      setIndicators(ind);
      setSetups(sp);
      setRecent(r);
      setLogs(l);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const runCycle = async () => {
    setBusy(true);
    try {
      await api.learning.runCycle();
      await load();
    } finally {
      setBusy(false);
    }
  };

  if (loading && failures.length === 0) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-16" />
        <Skeleton className="h-60" />
        <Skeleton className="h-60" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Learning Feedback</h1>
          <p className="text-sm text-muted-foreground">
            What the AI has learned from past wins and losses — and how it
            adjusts indicator weights and setup quality scores.
          </p>
        </div>
        <Button onClick={runCycle} disabled={busy}>
          {busy ? "Running…" : "Run learning cycle"}
        </Button>
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="failures">Failure reasons</TabsTrigger>
          <TabsTrigger value="successes">Success drivers</TabsTrigger>
          <TabsTrigger value="indicators">Indicator edge</TabsTrigger>
          <TabsTrigger value="setups">Setup quality</TabsTrigger>
          <TabsTrigger value="log">Learning log</TabsTrigger>
        </TabsList>
      </Tabs>

      {tab === "failures" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <CategoryList
            title="Why trades fail"
            items={failures}
            color="text-bear"
            empty="No failures recorded yet."
          />
          <RecentFeedback
            items={recent.filter((r) => r.outcome === "LOSS")}
            color="text-bear"
            title="Recent loss feedback"
          />
        </div>
      )}

      {tab === "successes" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <CategoryList
            title="Why trades succeed"
            items={successes}
            color="text-bull"
            empty="No wins recorded yet."
          />
          <RecentFeedback
            items={recent.filter((r) => r.outcome === "WIN")}
            color="text-bull"
            title="Recent win feedback"
          />
        </div>
      )}

      {tab === "indicators" && <IndicatorTable rows={indicators} />}
      {tab === "setups" && <SetupTable rows={setups} />}
      {tab === "log" && <LogList items={logs} />}

      <p className="text-[10px] text-muted-foreground text-center">
        The AI continuously rebalances weights based on what has actually
        worked. Lower weights ≠ worthless — it just means insufficient edge
        observed so far. Educational only — not financial advice.
      </p>
    </div>
  );
}

function CategoryList({
  title,
  items,
  color,
  empty,
}: {
  title: string;
  items: FeedbackCategoryCount[];
  color: string;
  empty: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 max-h-[480px] overflow-y-auto">
        {items.length === 0 ? (
          <p className="text-xs text-muted-foreground">{empty}</p>
        ) : (
          items.map((c) => (
            <div
              key={c.category}
              className="rounded-md border border-border p-3"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-sm capitalize">
                  {c.category.replace(/_/g, " ")}
                </span>
                <span className={`text-sm font-mono font-semibold ${color}`}>
                  {c.count}
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground mt-1 line-clamp-2">
                {c.example}
              </p>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function RecentFeedback({
  items,
  color,
  title,
}: {
  items: LearningFeedbackRow[];
  color: string;
  title: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 max-h-[480px] overflow-y-auto">
        {items.length === 0 ? (
          <p className="text-xs text-muted-foreground">No items yet.</p>
        ) : (
          items.slice(0, 30).map((r) => (
            <div key={r.id} className="rounded-md border border-border p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant={r.outcome === "WIN" ? "bull" : "bear"}>
                    {r.outcome}
                  </Badge>
                  <span className="text-[11px] text-muted-foreground uppercase">
                    #{r.prediction_id}
                  </span>
                  <span className="text-xs font-medium capitalize">
                    {r.category.replace(/_/g, " ")}
                  </span>
                </div>
                <span className="text-[10px] text-muted-foreground">
                  {new Date(r.created_at).toLocaleDateString()}
                </span>
              </div>
              <p className={`text-[11px] mt-1 ${color}`}>{r.reason}</p>
              <div className="mt-1 text-[10px] text-muted-foreground">
                {r.market_condition && `regime: ${r.market_condition}`}{" "}
                {r.sector_condition && `· sector: ${r.sector_condition}`}{" "}
                {r.confidence_at_signal && `· conf: ${r.confidence_at_signal.toFixed(0)}%`}
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function IndicatorTable({ rows }: { rows: IndicatorPerformanceRow[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Indicator edge per regime</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Not enough validated trades yet to score indicators.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-muted-foreground">
                <tr className="text-left">
                  <th className="py-2 pr-3">Indicator</th>
                  <th className="py-2 pr-3">Regime</th>
                  <th className="py-2 pr-3">Mode</th>
                  <th className="py-2 pr-3">Samples</th>
                  <th className="py-2 pr-3">Win rate</th>
                  <th className="py-2 pr-3">Edge</th>
                  <th className="py-2 pr-3">Weight</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-t border-border/40">
                    <td className="py-2 pr-3 font-medium">{r.indicator}</td>
                    <td className="py-2 pr-3 text-muted-foreground">{r.regime}</td>
                    <td className="py-2 pr-3 uppercase text-[10px] text-muted-foreground">
                      {r.mode}
                    </td>
                    <td className="py-2 pr-3 font-mono">{r.sample_size}</td>
                    <td
                      className={`py-2 pr-3 font-mono ${
                        r.win_rate >= 50 ? "text-bull" : "text-bear"
                      }`}
                    >
                      {r.win_rate.toFixed(1)}%
                    </td>
                    <td
                      className={`py-2 pr-3 font-mono ${
                        r.edge_score >= 0 ? "text-bull" : "text-bear"
                      }`}
                    >
                      {r.edge_score >= 0 ? "+" : ""}
                      {r.edge_score.toFixed(2)}
                    </td>
                    <td className="py-2 pr-3 font-mono">×{r.weight.toFixed(2)}</td>
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

function SetupTable({ rows }: { rows: SetupQuality[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Setup quality scores</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Quality scoring kicks in after a few closed trades per setup.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-muted-foreground">
                <tr className="text-left">
                  <th className="py-2 pr-3">Setup</th>
                  <th className="py-2 pr-3">Mode</th>
                  <th className="py-2 pr-3">Samples</th>
                  <th className="py-2 pr-3">Win rate</th>
                  <th className="py-2 pr-3">Avg return</th>
                  <th className="py-2 pr-3">Quality</th>
                  <th className="py-2 pr-3">Weight</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-t border-border/40">
                    <td className="py-2 pr-3 font-medium">{r.setup_name}</td>
                    <td className="py-2 pr-3 uppercase text-[10px] text-muted-foreground">
                      {r.mode}
                    </td>
                    <td className="py-2 pr-3 font-mono">{r.sample_size}</td>
                    <td
                      className={`py-2 pr-3 font-mono ${
                        r.win_rate >= 50 ? "text-bull" : "text-bear"
                      }`}
                    >
                      {r.win_rate.toFixed(1)}%
                    </td>
                    <td className="py-2 pr-3 font-mono">
                      {r.avg_return_pct.toFixed(2)}%
                    </td>
                    <td className="py-2 pr-3 font-mono">
                      Q{r.quality_score.toFixed(0)}
                    </td>
                    <td className="py-2 pr-3 font-mono">
                      ×{r.weight_multiplier.toFixed(2)}
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

function LogList({ items }: { items: LearningLog[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>AI learning log</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 max-h-[640px] overflow-y-auto">
        {items.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            The learning engine has not run yet.
          </p>
        ) : (
          items.map((l) => (
            <div key={l.id} className="rounded-md border border-border p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider">
                  {l.event}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {new Date(l.created_at).toLocaleString()}
                </span>
              </div>
              <p className="text-[12px] text-muted-foreground mt-1">{l.summary}</p>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

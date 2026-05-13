"use client";
import * as React from "react";
import Link from "next/link";
import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Compass,
  Globe2,
  Loader2,
  Moon,
  RefreshCw,
  Sunrise,
  TrendingDown,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  OvernightStatus,
  PreMarketBrief,
  PreMarketReadiness,
} from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn, fmtPct, pctClass } from "@/lib/utils";

const VERDICT_TONE: Record<PreMarketReadiness["verdict"], string> = {
  FAVORABLE: "bg-bull/15 text-bull border-bull/40",
  NEUTRAL: "bg-amber-500/15 text-amber-400 border-amber-500/40",
  RISKY: "bg-bear/15 text-bear border-bear/40",
  UNKNOWN: "bg-muted/20 text-muted-foreground border-border",
};

const VERDICT_ICON: Record<PreMarketReadiness["verdict"], React.ReactNode> = {
  FAVORABLE: <CheckCircle2 className="h-5 w-5" />,
  NEUTRAL: <Compass className="h-5 w-5" />,
  RISKY: <XCircle className="h-5 w-5" />,
  UNKNOWN: <Moon className="h-5 w-5" />,
};

export default function PreMarketPage() {
  const [brief, setBrief] = React.useState<PreMarketBrief | null>(null);
  const [overnight, setOvernight] = React.useState<OvernightStatus | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [refreshing, setRefreshing] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [b, o] = await Promise.all([
        api.preMarket.brief(),
        api.overnight.status(),
      ]);
      setBrief(b);
      setOvernight(o);
      setErr(null);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      const b = await api.preMarket.refresh();
      setBrief(b);
      setErr(null);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setRefreshing(false);
    }
  };

  if (loading && !brief) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-28 w-full" />
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  const isStaleBrief =
    !brief?.generated_at ||
    brief.readiness?.verdict === "UNKNOWN";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Sunrise className="h-6 w-6 text-primary" />
            Pre-Market Brief
          </h1>
          <p className="text-sm text-muted-foreground max-w-2xl">
            Global cues, India VIX, sector pulse and the AI&apos;s structured
            verdict on whether tomorrow&apos;s session looks favourable. Auto-
            refreshes daily at 08:30 IST; trigger manually any time.
          </p>
        </div>
        <Button onClick={refresh} disabled={refreshing} size="sm" variant="secondary">
          <RefreshCw className={cn("h-4 w-4 mr-1", refreshing && "animate-spin")} />
          {refreshing ? "Computing…" : "Refresh now"}
        </Button>
      </div>

      {err && (
        <div className="rounded-md border border-bear/40 bg-bear-soft px-4 py-2 text-sm text-bear">
          {err}
        </div>
      )}

      {/* Verdict + overnight summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <VerdictCard
          readiness={brief?.readiness ?? null}
          generatedAt={brief?.generated_at ?? null}
          isStale={isStaleBrief}
        />
        <OvernightCard status={overnight} />
      </div>

      {/* Global cues */}
      <GlobalCuesCard brief={brief} />

      {/* Sector pulse + India VIX */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <VixCard brief={brief} />
        <SectorsCard
          title="Top sectors (yesterday)"
          rows={brief?.top_sectors ?? []}
          tone="bull"
        />
        <SectorsCard
          title="Weak sectors (yesterday)"
          rows={brief?.weak_sectors ?? []}
          tone="bear"
        />
      </div>

      {/* Gap candidates */}
      <GapCandidatesCard brief={brief} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Verdict
// ---------------------------------------------------------------------------

function VerdictCard({
  readiness,
  generatedAt,
  isStale,
}: {
  readiness: PreMarketReadiness | null;
  generatedAt: string | null;
  isStale: boolean;
}) {
  const verdict = readiness?.verdict ?? "UNKNOWN";
  const tone = VERDICT_TONE[verdict];

  return (
    <Card className={cn("lg:col-span-2 border", tone.split(" ").filter((c) => c.startsWith("border-"))[0])}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2">
            {VERDICT_ICON[verdict]}
            Next-day readiness:&nbsp;
            <span className="uppercase">{verdict}</span>
          </span>
          <Badge variant="outline" className="text-[10px]">
            score {readiness?.score ?? 0 >= 0 ? "+" : ""}
            {readiness?.score ?? 0}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {readiness && readiness.bullets.length > 0 ? (
          <ul className="space-y-1.5">
            {readiness.bullets.map((b, i) => (
              <li
                key={i}
                className="text-sm text-foreground/90 flex items-start gap-2 leading-snug"
              >
                <span
                  className={cn(
                    "mt-1 h-1.5 w-1.5 rounded-full shrink-0",
                    verdict === "FAVORABLE"
                      ? "bg-bull"
                      : verdict === "RISKY"
                      ? "bg-bear"
                      : "bg-amber-400"
                  )}
                />
                <span>{b}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            Pre-market brief has not been generated yet. The scheduler runs at
            08:30 IST on weekdays, or click <em>Refresh now</em> at the top.
          </p>
        )}
        <p className="text-[11px] text-muted-foreground italic">
          Markets are uncertain. This is a probabilistic read on conditions — not
          a guarantee of direction. The verdict prefers NEUTRAL when signals
          conflict.
        </p>
        {generatedAt && (
          <p className="text-[10px] text-muted-foreground/80">
            Generated {new Date(generatedAt).toLocaleString("en-IN", {
              dateStyle: "medium",
              timeStyle: "short",
            })}{" "}
            {isStale && <span className="text-bear">· may be stale</span>}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function OvernightCard({ status }: { status: OvernightStatus | null }) {
  const d = status?.details ?? {};
  const validation = d.validation ?? {};
  const learning = d.learning ?? {};
  const hasRun = !!status?.created_at;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Moon className="h-5 w-5 text-primary" />
          Overnight cycle
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {!hasRun ? (
          <p className="text-sm text-muted-foreground">
            The overnight cycle has not run yet on this server. It is scheduled
            for 15:40 IST on weekdays after the NSE close.
          </p>
        ) : (
          <>
            <p className="text-sm leading-snug">{status?.summary}</p>
            <div className="grid grid-cols-2 gap-2 pt-1">
              <Mini
                label="Trades validated"
                value={`${validation.scanned ?? 0}`}
                sub={`${validation.closed ?? 0} closed`}
              />
              <Mini
                label="W / L"
                value={`${validation.new_wins ?? 0} / ${validation.new_losses ?? 0}`}
                sub="post-close batch"
              />
              <Mini
                label="Weight changes"
                value={`${learning.weight_changes ?? 0}`}
                sub={`${learning.setups_updated ?? 0} setups · ${learning.indicators_updated ?? 0} indicators`}
              />
              <Mini
                label="Closing regime"
                value={(d.closing_regime || "—").replace(/_/g, " ")}
                sub="market_regime classifier"
              />
            </div>
            <p className="text-[10px] text-muted-foreground pt-1">
              {status?.created_at
                ? `Ran ${new Date(status.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}`
                : ""}{" "}
              {d.duration_seconds ? `· ${d.duration_seconds}s` : ""}
            </p>
          </>
        )}
        <Link
          href="/evolution"
          className="text-xs text-primary hover:underline inline-block"
        >
          See full failure analysis →
        </Link>
      </CardContent>
    </Card>
  );
}

function Mini({
  label,
  value,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
}) {
  return (
    <div className="rounded-md border border-border bg-background/40 px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="text-sm font-semibold tabular-nums capitalize">{value}</div>
      {sub && <div className="text-[10px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Global cues
// ---------------------------------------------------------------------------

function GlobalCuesCard({ brief }: { brief: PreMarketBrief | null }) {
  const cues = brief?.global_cues ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Globe2 className="h-5 w-5 text-primary" />
          Global cues
          <span className="text-xs font-normal text-muted-foreground">
            Overnight % change in major indices, FX and commodities.
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {cues.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Global cues unavailable — generate the brief to populate.
          </p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {cues.map((c) => {
              const v = c.change_pct;
              return (
                <div
                  key={c.symbol}
                  className="rounded-md border border-border bg-background/40 p-2"
                >
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    {c.label}
                  </div>
                  <div className="mt-0.5 text-base font-semibold tabular-nums">
                    {c.last !== null ? c.last.toFixed(2) : "—"}
                  </div>
                  <div
                    className={cn(
                      "text-xs font-medium tabular-nums flex items-center gap-0.5",
                      pctClass(v ?? 0)
                    )}
                  >
                    {v !== null && v !== undefined ? (
                      v >= 0 ? (
                        <ArrowUp className="h-3 w-3" />
                      ) : (
                        <ArrowDown className="h-3 w-3" />
                      )
                    ) : null}
                    {v !== null && v !== undefined ? fmtPct(v) : "—"}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// India VIX + sectors
// ---------------------------------------------------------------------------

function VixCard({ brief }: { brief: PreMarketBrief | null }) {
  const vix = brief?.india_vix;
  const chg = brief?.india_vix_change_pct;
  const tone =
    vix === null || vix === undefined
      ? "text-muted-foreground"
      : vix > 20
      ? "text-bear"
      : vix > 16
      ? "text-amber-400"
      : "text-bull";

  return (
    <Card>
      <CardHeader>
        <CardTitle>India VIX</CardTitle>
      </CardHeader>
      <CardContent>
        <div className={cn("text-4xl font-bold tabular-nums", tone)}>
          {vix !== null && vix !== undefined ? vix.toFixed(2) : "—"}
        </div>
        <div
          className={cn(
            "text-sm font-medium tabular-nums mt-1",
            pctClass(chg ?? 0)
          )}
        >
          {chg !== null && chg !== undefined ? fmtPct(chg) + " yesterday" : ""}
        </div>
        <p className="text-xs text-muted-foreground pt-3 leading-relaxed">
          Lower VIX = calmer regime, tighter ranges, trend-friendly. Above 20 =
          intraday whipsaw likely, wider stops needed.
        </p>
      </CardContent>
    </Card>
  );
}

function SectorsCard({
  title,
  rows,
  tone,
}: {
  title: string;
  rows: { sector: string; avg_change_pct: number; sample_size: number; direction: string }[];
  tone: "bull" | "bear";
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No sector data yet.</p>
        ) : (
          <ul className="space-y-1.5">
            {rows.map((r) => (
              <li
                key={r.sector}
                className="flex items-center justify-between gap-2 text-sm border-b border-border/40 py-1.5 last:border-0"
              >
                <span className="flex items-center gap-1.5">
                  {tone === "bull" ? (
                    <TrendingUp className="h-3.5 w-3.5 text-bull" />
                  ) : (
                    <TrendingDown className="h-3.5 w-3.5 text-bear" />
                  )}
                  <span className="truncate">{r.sector}</span>
                </span>
                <span
                  className={cn(
                    "tabular-nums font-semibold",
                    pctClass(r.avg_change_pct)
                  )}
                >
                  {fmtPct(r.avg_change_pct)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Gap candidates
// ---------------------------------------------------------------------------

function GapCandidatesCard({ brief }: { brief: PreMarketBrief | null }) {
  const rows = brief?.gap_candidates ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          High-probability gap-up watchlist
          <span className="ml-2 text-xs font-normal text-muted-foreground">
            Stocks with strong day-prior + 5-day momentum. Confirm in the open;
            no setup is guaranteed.
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No qualifying candidates today — either nothing met the +1.5%
            yesterday and +3% 5-day momentum threshold, or the universe sample
            failed to fetch.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-2 font-medium">Symbol</th>
                  <th className="text-left py-2 px-2 font-medium">Sector</th>
                  <th className="text-right py-2 px-2 font-medium">Last close</th>
                  <th className="text-right py-2 px-2 font-medium">1-day</th>
                  <th className="text-right py-2 px-2 font-medium">5-day</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.symbol} className="border-b border-border/40">
                    <td className="py-2 px-2 font-medium">
                      <Link
                        href={`/stocks?symbol=${encodeURIComponent(r.symbol)}`}
                        className="hover:text-primary"
                      >
                        {r.symbol.replace(".NS", "")}
                      </Link>
                      <div className="text-[10px] text-muted-foreground truncate max-w-[180px]">
                        {r.name}
                      </div>
                    </td>
                    <td className="py-2 px-2 text-xs text-muted-foreground">
                      {r.sector}
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums">
                      ₹{r.last_close.toFixed(2)}
                    </td>
                    <td
                      className={cn(
                        "py-2 px-2 text-right tabular-nums font-semibold",
                        pctClass(r.change_pct_1d)
                      )}
                    >
                      {fmtPct(r.change_pct_1d)}
                    </td>
                    <td
                      className={cn(
                        "py-2 px-2 text-right tabular-nums",
                        pctClass(r.change_pct_5d)
                      )}
                    >
                      {fmtPct(r.change_pct_5d)}
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

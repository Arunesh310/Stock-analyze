"use client";
import * as React from "react";
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Loader2,
  ShieldAlert,
  Sparkles,
  Wallet,
} from "lucide-react";
import { api } from "@/lib/api";
import type { PlannerPick, PlannerRequest, PlannerResponse } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { cn, fmtINR, fmtPct } from "@/lib/utils";

const TIMEFRAMES: { v: PlannerRequest["timeframe"]; l: string }[] = [
  { v: "1m", l: "1 min" },
  { v: "5m", l: "5 min" },
  { v: "10m", l: "10 min" },
  { v: "15m", l: "15 min" },
  { v: "30m", l: "30 min" },
  { v: "1h", l: "1 hour" },
  { v: "1d", l: "1 day" },
  { v: "1w", l: "1 week" },
  { v: "1mo", l: "1 month" },
];

const VERDICT_TONE: Record<string, string> = {
  REALISTIC: "border-bull/40 bg-bull/5 text-bull",
  SPECULATIVE: "border-amber-500/40 bg-amber-500/5 text-amber-400",
  UNREALISTIC: "border-bear/40 bg-bear/5 text-bear",
  INVALID: "border-muted bg-muted/10 text-muted-foreground",
};

const VERDICT_ICON: Record<string, React.ReactNode> = {
  REALISTIC: <CheckCircle2 className="h-5 w-5" />,
  SPECULATIVE: <AlertTriangle className="h-5 w-5" />,
  UNREALISTIC: <AlertOctagon className="h-5 w-5" />,
  INVALID: <HelpCircle className="h-5 w-5" />,
};

export default function PlannerPage() {
  const [req, setReq] = React.useState<PlannerRequest>({
    capital: 50000,
    target_amount: 750,
    timeframe: "1d",
    risk_tolerance: "balanced",
    mode: "swing",
    max_picks: 6,
  });
  const [resp, setResp] = React.useState<PlannerResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setErr(null);
    try {
      const r = await api.planner(req);
      setResp(r);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  const targetPct = (req.target_amount / req.capital) * 100;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Wallet className="h-6 w-6 text-primary" />
          Capital Planner
        </h1>
        <p className="text-sm text-muted-foreground max-w-2xl">
          Set your capital, profit target, timeframe, and risk tolerance. The AI
          will tell you whether the goal is realistic and match you with the
          highest-quality liquid stocks — or refuse the trade if conditions
          don&rsquo;t justify the risk.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Goal inputs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="text-xs uppercase tracking-wider text-muted-foreground">
                Capital (INR)
              </label>
              <Input
                type="number"
                min={500}
                value={req.capital}
                onChange={(e) =>
                  setReq({ ...req, capital: Number(e.target.value) || 0 })
                }
              />
            </div>
            <div>
              <label className="text-xs uppercase tracking-wider text-muted-foreground">
                Target profit (INR)
              </label>
              <Input
                type="number"
                min={1}
                value={req.target_amount}
                onChange={(e) =>
                  setReq({ ...req, target_amount: Number(e.target.value) || 0 })
                }
              />
              <div className="text-[10px] text-muted-foreground mt-1">
                = {targetPct.toFixed(2)}% of capital
              </div>
            </div>
            <div>
              <label className="text-xs uppercase tracking-wider text-muted-foreground block mb-1">
                Timeframe
              </label>
              <select
                value={req.timeframe}
                onChange={(e) =>
                  setReq({ ...req, timeframe: e.target.value as PlannerRequest["timeframe"] })
                }
                className="h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
              >
                {TIMEFRAMES.map((t) => (
                  <option key={t.v} value={t.v}>
                    {t.l}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs uppercase tracking-wider text-muted-foreground block mb-1">
                Risk tolerance
              </label>
              <Tabs
                value={req.risk_tolerance}
                onValueChange={(v: string) =>
                  setReq({ ...req, risk_tolerance: v as PlannerRequest["risk_tolerance"] })
                }
              >
                <TabsList className="w-full">
                  <TabsTrigger value="conservative">0.5%</TabsTrigger>
                  <TabsTrigger value="balanced">1%</TabsTrigger>
                  <TabsTrigger value="aggressive">2%</TabsTrigger>
                </TabsList>
              </Tabs>
              <div className="text-[10px] text-muted-foreground mt-1">
                Per-trade capital at risk
              </div>
            </div>
            <div className="md:col-span-2">
              <label className="text-xs uppercase tracking-wider text-muted-foreground block mb-1">
                Mode
              </label>
              <Tabs
                value={req.mode}
                onValueChange={(v: string) =>
                  setReq({ ...req, mode: v as PlannerRequest["mode"] })
                }
              >
                <TabsList>
                  <TabsTrigger value="intraday">Intraday</TabsTrigger>
                  <TabsTrigger value="swing">Swing</TabsTrigger>
                  <TabsTrigger value="positional">Positional</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
            <div className="md:col-span-2 flex items-end">
              <Button onClick={run} disabled={loading} className="w-full md:w-auto">
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Scanning the market...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4 mr-2" />
                    Find opportunities
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {err && (
        <div className="rounded-md border border-bear/40 bg-bear/10 px-4 py-2 text-sm text-bear">
          {err}
        </div>
      )}

      {resp && <VerdictCard resp={resp} />}
      {resp && resp.picks.length > 0 && (
        <PicksTable picks={resp.picks} verdict={resp.verdict} />
      )}
      {resp && resp.picks.length === 0 && resp.verdict !== "UNREALISTIC" && resp.verdict !== "INVALID" && (
        <Card>
          <CardContent className="p-6 flex items-start gap-3">
            <ShieldAlert className="h-5 w-5 text-amber-400 mt-0.5" />
            <div>
              <div className="font-semibold mb-1">No high-quality setups match this goal right now.</div>
              <p className="text-sm text-muted-foreground">
                The disciplined move is to wait. Forcing a trade under these
                conditions is how capital gets lost. Try a longer timeframe or a
                smaller target.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function VerdictCard({ resp }: { resp: PlannerResponse }) {
  const tone = VERDICT_TONE[resp.verdict] || VERDICT_TONE.INVALID;
  const icon = VERDICT_ICON[resp.verdict] || VERDICT_ICON.INVALID;
  return (
    <Card className={cn("border", tone)}>
      <CardContent className="p-4 space-y-2">
        <div className="flex items-start gap-3">
          <div className="mt-0.5">{icon}</div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-bold uppercase tracking-wider">
                {resp.verdict}
              </span>
              <Badge variant="outline" className="text-[10px]">
                Target {resp.target_pct.toFixed(2)}% · {resp.timeframe} · {resp.mode}
              </Badge>
            </div>
            <p className="text-sm leading-relaxed">{resp.message}</p>
          </div>
        </div>
        {resp.suggestions.length > 0 && (
          <div className="ml-8 mt-2">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
              Suggestions
            </div>
            <ul className="space-y-1 text-xs">
              {resp.suggestions.map((s, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-muted-foreground">•</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PicksTable({
  picks,
  verdict,
}: {
  picks: PlannerPick[];
  verdict: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Matched opportunities
          {verdict === "SPECULATIVE" && (
            <span className="text-xs font-normal text-amber-400 ml-2">
              (HIGH_CONVICTION / STRONG only — speculative target)
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="text-left py-2 px-2 font-medium">Stock</th>
                <th className="text-left py-2 px-2 font-medium">Action</th>
                <th className="text-left py-2 px-2 font-medium">Grade</th>
                <th className="text-right py-2 px-2 font-medium">Quality</th>
                <th className="text-right py-2 px-2 font-medium">Prob (hit)</th>
                <th className="text-right py-2 px-2 font-medium">Entry</th>
                <th className="text-right py-2 px-2 font-medium">SL</th>
                <th className="text-right py-2 px-2 font-medium">T1</th>
                <th className="text-right py-2 px-2 font-medium">R:R</th>
                <th className="text-right py-2 px-2 font-medium">Qty</th>
                <th className="text-right py-2 px-2 font-medium">At risk</th>
                <th className="text-right py-2 px-2 font-medium">Exp gain</th>
              </tr>
            </thead>
            <tbody>
              {picks.map((p) => (
                <tr key={p.symbol} className="border-b border-border/40 hover:bg-secondary/30">
                  <td className="py-2 px-2">
                    <div className="font-medium">{p.symbol.replace(".NS", "")}</div>
                    <div className="text-[10px] text-muted-foreground line-clamp-1">
                      {p.sector}
                    </div>
                  </td>
                  <td className="py-2 px-2">
                    <Badge variant={p.action === "BUY" ? "bull" : "bear"}>
                      {p.action}
                    </Badge>
                  </td>
                  <td className="py-2 px-2">
                    <GradeBadge grade={p.quality_grade} />
                  </td>
                  <td className="py-2 px-2 text-right tabular-nums font-semibold">
                    {p.quality_score.toFixed(0)}
                  </td>
                  <td className="py-2 px-2 text-right tabular-nums">
                    {(p.probability_target_hit * 100).toFixed(0)}%
                  </td>
                  <td className="py-2 px-2 text-right tabular-nums">
                    {p.entry_low && p.entry_high
                      ? `${p.entry_low.toFixed(2)}–${p.entry_high.toFixed(2)}`
                      : fmtINR(p.last_close)}
                  </td>
                  <td className="py-2 px-2 text-right tabular-nums text-bear">
                    {p.stoploss?.toFixed(2) ?? "—"}
                  </td>
                  <td className="py-2 px-2 text-right tabular-nums text-bull">
                    {p.target1?.toFixed(2) ?? "—"}
                  </td>
                  <td className="py-2 px-2 text-right tabular-nums">
                    {p.rr?.toFixed(2) ?? "—"}
                  </td>
                  <td className="py-2 px-2 text-right tabular-nums">
                    {p.quantity}
                  </td>
                  <td className="py-2 px-2 text-right tabular-nums text-bear">
                    {fmtINR(p.capital_at_risk)}
                  </td>
                  <td className="py-2 px-2 text-right tabular-nums font-semibold text-bull">
                    {fmtINR(p.expected_gain_inr)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[10px] text-muted-foreground mt-3">
          Quantities are sized so the stoploss caps your loss at the configured
          risk-per-trade percentage of capital. Probabilities are heuristics
          combining the symbol&rsquo;s expected move with the AI&rsquo;s
          composite quality score, not guarantees.
        </p>
      </CardContent>
    </Card>
  );
}

const GRADE_TONE: Record<string, string> = {
  HIGH_CONVICTION: "bg-bull/25 text-bull border-bull/40",
  STRONG: "bg-bull/15 text-bull border-bull/30",
  MODERATE: "bg-primary/15 text-primary border-primary/30",
  WEAK: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  AVOID: "bg-bear/15 text-bear border-bear/30",
  NO_TRADE: "bg-bear/25 text-bear border-bear/40",
};

function GradeBadge({ grade }: { grade: string }) {
  return (
    <span
      className={cn(
        "inline-block rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        GRADE_TONE[grade] || GRADE_TONE.MODERATE
      )}
    >
      {grade.replace("_", " ")}
    </span>
  );
}

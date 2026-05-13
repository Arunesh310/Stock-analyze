"use client";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import type { Signal } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn, fmtNumber } from "@/lib/utils";

const GRADE_TONE: Record<string, string> = {
  HIGH_CONVICTION: "bg-bull/25 text-bull border-bull/40",
  STRONG: "bg-bull/15 text-bull border-bull/30",
  MODERATE: "bg-primary/15 text-primary border-primary/30",
  WEAK: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  AVOID: "bg-bear/15 text-bear border-bear/30",
  NO_TRADE: "bg-bear/25 text-bear border-bear/40",
};

export function SignalCard({ signal }: { signal: Signal }) {
  const variant =
    signal.action === "BUY" ? "bull" : signal.action === "SELL" ? "bear" : "neutral";
  const grade = signal.quality_grade;
  const qScore = signal.quality_score ?? 0;
  const noTrade = signal.no_trade_reasons ?? [];
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <CardTitle>AI Signal</CardTitle>
          {grade && (
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                GRADE_TONE[grade] || GRADE_TONE.MODERATE
              )}
              title="Composite quality grade"
            >
              <ShieldCheck className="h-3 w-3" />
              {grade.replace("_", " ")} · {qScore.toFixed(0)}
            </span>
          )}
        </div>
        <Badge variant={variant}>
          {signal.action} · {signal.confidence.toFixed(0)}%
        </Badge>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <Stat label="Entry" value={`${fmtNumber(signal.entry_low)} – ${fmtNumber(signal.entry_high)}`} />
          <Stat label="Stoploss" value={fmtNumber(signal.stoploss)} accent="text-bear" />
          <Stat label="Target 1" value={fmtNumber(signal.target1)} accent="text-bull" />
          <Stat label="Target 2" value={fmtNumber(signal.target2)} accent="text-bull" />
          <Stat label="R : R" value={signal.rr ? `1 : ${signal.rr}` : "—"} />
          <Stat label="Probability" value={`${(signal.probability * 100).toFixed(0)}%`} />
          <Stat label="Mode" value={signal.mode} />
          <Stat label="Quality" value={qScore ? `${qScore.toFixed(0)} / 100` : "—"} />
        </div>

        {noTrade.length > 0 && (
          <div className="mt-4 rounded-md border border-bear/40 bg-bear/5 p-3">
            <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-bear font-semibold mb-1">
              <AlertTriangle className="h-3.5 w-3.5" />
              NO-TRADE — capital preservation veto
            </div>
            <ul className="text-xs space-y-0.5 text-bear/90">
              {noTrade.map((r, i) => (
                <li key={i}>• {r}</li>
              ))}
            </ul>
          </div>
        )}

        {signal.quality_breakdown && Object.keys(signal.quality_breakdown).length > 0 && (
          <div className="mt-4">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
              Quality breakdown
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
              {(["technical", "market", "sentiment", "historical", "risk"] as const).map((k) => {
                const v = signal.quality_breakdown?.[k];
                if (v === undefined) return null;
                return (
                  <div
                    key={k}
                    className="rounded-md border border-border bg-secondary/40 px-2 py-1.5"
                  >
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      {k}
                    </div>
                    <div className="font-semibold tabular-nums">{Number(v).toFixed(1)}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {signal.detected_patterns?.length > 0 && (
          <div className="mt-4">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
              Detected Patterns
            </div>
            <div className="flex flex-wrap gap-1.5">
              {signal.detected_patterns.map((p) => (
                <Badge key={p} variant="outline" className="text-[10px]">
                  {p}
                </Badge>
              ))}
            </div>
          </div>
        )}

        <div className="mt-4 rounded-md border border-border bg-secondary/30 p-3">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
            AI Reasoning
          </div>
          <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
            {signal.reasoning || "—"}
          </pre>
        </div>
      </CardContent>
    </Card>
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
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={`font-mono text-sm font-semibold ${accent || ""}`}>{value}</div>
    </div>
  );
}

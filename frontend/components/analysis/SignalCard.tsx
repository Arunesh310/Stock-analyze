"use client";
import type { Signal } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { fmtNumber } from "@/lib/utils";

export function SignalCard({ signal }: { signal: Signal }) {
  const variant =
    signal.action === "BUY" ? "bull" : signal.action === "SELL" ? "bear" : "neutral";
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>AI Signal</CardTitle>
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
          <Stat label="Score" value={signal.score.toFixed(1)} />
        </div>

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

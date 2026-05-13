"use client";
import type { Indicators } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";

const ROWS: { key: keyof Indicators; label: string; fmt?: (v: any) => string }[] = [
  { key: "rsi", label: "RSI(14)" },
  { key: "macd", label: "MACD" },
  { key: "macd_signal", label: "MACD Signal" },
  { key: "ema20", label: "EMA 20" },
  { key: "ema50", label: "EMA 50" },
  { key: "ema200", label: "EMA 200" },
  { key: "vwap", label: "VWAP" },
  { key: "atr", label: "ATR(14)" },
  { key: "adx", label: "ADX(14)" },
  { key: "bb_upper", label: "BB Upper" },
  { key: "bb_lower", label: "BB Lower" },
  { key: "support", label: "Support" },
  { key: "resistance", label: "Resistance" },
  { key: "volatility_pct", label: "Volatility %" },
];

function fmt(v: any) {
  if (v === null || v === undefined || isNaN(Number(v))) return "—";
  const n = Number(v);
  if (Math.abs(n) > 1e6) return n.toExponential(2);
  return n.toFixed(2);
}

export function IndicatorTable({ ind }: { ind: Indicators }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Technical Indicators</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-2">
          {ROWS.map((r) => (
            <div key={r.key as string} className="flex justify-between text-sm border-b border-border/50 py-1">
              <span className="text-muted-foreground">{r.label}</span>
              <span className="font-mono">{fmt(ind[r.key])}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

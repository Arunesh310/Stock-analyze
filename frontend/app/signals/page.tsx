"use client";
import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Signal } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { fmtNumber } from "@/lib/utils";

type Mode = "intraday" | "swing" | "positional";

export default function SignalsPage() {
  const [mode, setMode] = React.useState<Mode>("swing");
  const [minConf, setMinConf] = React.useState(60);
  const [signals, setSignals] = React.useState<Signal[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .signals({ mode, min_conf: minConf, limit: 50 })
      .then((s) => !cancelled && setSignals(s))
      .catch(() => !cancelled && setSignals([]))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [mode, minConf]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI Signals</h1>
          <p className="text-sm text-muted-foreground">
            Ranked BUY/SELL signals across the curated NSE universe.
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
          <Select value={String(minConf)} onChange={(e) => setMinConf(Number(e.target.value))}>
            <option value="40">≥ 40% confidence</option>
            <option value="55">≥ 55% confidence</option>
            <option value="65">≥ 65% confidence</option>
            <option value="75">≥ 75% confidence</option>
          </Select>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : signals.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            No signals match the filters. Try lowering the confidence threshold.
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {signals.map((s) => (
            <Link key={s.symbol + s.action} href={`/stocks/${encodeURIComponent(s.symbol)}`}>
              <Card className="hover:border-primary/50">
                <CardHeader className="flex-row items-center justify-between">
                  <CardTitle className="text-base">{s.symbol.replace(".NS", "")}</CardTitle>
                  <Badge variant={s.action === "BUY" ? "bull" : s.action === "SELL" ? "bear" : "neutral"}>
                    {s.action} · {s.confidence.toFixed(0)}%
                  </Badge>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground line-clamp-2">{s.reasoning}</p>
                  <div className="mt-3 grid grid-cols-4 gap-2 text-xs font-mono">
                    <Stat label="Entry" value={`${fmtNumber(s.entry_low)}-${fmtNumber(s.entry_high)}`} />
                    <Stat label="SL" value={fmtNumber(s.stoploss)} accent="text-bear" />
                    <Stat label="T1" value={fmtNumber(s.target1)} accent="text-bull" />
                    <Stat label="R:R" value={s.rr ? `1:${s.rr}` : "—"} />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: React.ReactNode; accent?: string }) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={`text-xs font-mono ${accent || ""}`}>{value}</div>
    </div>
  );
}

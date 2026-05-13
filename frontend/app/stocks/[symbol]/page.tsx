"use client";
import * as React from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { AnalysisResponse, NewsItem, OhlcRow } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { fmtNumber, fmtPct, pctClass } from "@/lib/utils";
import { PriceChart, type Overlay } from "@/components/charts/PriceChart";
import { SignalCard } from "@/components/analysis/SignalCard";
import { IndicatorTable } from "@/components/analysis/IndicatorTable";
import { RiskCalculator } from "@/components/analysis/RiskCalculator";
import { DataQualityBadge } from "@/components/market/DataQualityBadge";
import { formatIST } from "@/hooks/useMarketStatus";

type Mode = "intraday" | "swing" | "positional";

export default function StockPage() {
  const params = useParams<{ symbol: string }>();
  const symbol = decodeURIComponent(params.symbol as string);
  const [analysis, setAnalysis] = React.useState<AnalysisResponse | null>(null);
  const [ohlc, setOhlc] = React.useState<OhlcRow[]>([]);
  const [news, setNews] = React.useState<NewsItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [mode, setMode] = React.useState<Mode>("swing");
  const [err, setErr] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const [a, o, n] = await Promise.all([
        api.analyze(symbol, mode),
        api.ohlc(symbol, mode === "intraday" ? "5d" : mode === "positional" ? "2y" : "1y",
                 mode === "intraday" ? "15m" : "1d"),
        api.news(15, undefined, symbol).catch(() => [] as NewsItem[]),
      ]);
      setAnalysis(a);
      setOhlc(o);
      setNews(n);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [symbol, mode]);

  React.useEffect(() => {
    load();
  }, [load]);

  const overlays: Overlay[] = React.useMemo(() => {
    if (!analysis || ohlc.length === 0) return [];
    const ind = analysis.indicators;
    const ovs: Overlay[] = [];
    const close = ohlc.map((d) => d.close);

    function ema(period: number) {
      const k = 2 / (period + 1);
      let prev: number | null = null;
      return ohlc.map((row, i) => {
        const c = close[i];
        const v = prev === null ? c : c * k + prev * (1 - k);
        prev = v;
        return { time: row.time, value: v };
      });
    }
    if (ind.ema20 && ohlc.length > 20)
      ovs.push({ label: "EMA20", color: "#60a5fa", values: ema(20) });
    if (ind.ema50 && ohlc.length > 50)
      ovs.push({ label: "EMA50", color: "#a78bfa", values: ema(50) });
    if (ind.ema200 && ohlc.length > 200)
      ovs.push({ label: "EMA200", color: "#f59e0b", values: ema(200) });
    return ovs;
  }, [analysis, ohlc]);

  const markers = React.useMemo(() => {
    if (!analysis) return [];
    const s = analysis.signal;
    const m: { label: string; price: number; color: string }[] = [];
    if (s.entry_low && s.entry_high) {
      m.push({ label: "Entry", price: (s.entry_low + s.entry_high) / 2, color: "#60a5fa" });
    }
    if (s.stoploss) m.push({ label: "SL", price: s.stoploss, color: "#ef4444" });
    if (s.target1) m.push({ label: "T1", price: s.target1, color: "#22c55e" });
    if (s.target2) m.push({ label: "T2", price: s.target2, color: "#16a34a" });
    return m;
  }, [analysis]);

  if (loading && !analysis) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-[420px] w-full" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (err && !analysis) {
    return (
      <Card>
        <CardContent className="p-6 space-y-2">
          <p className="text-sm text-bear">Failed to analyse {symbol}: {err}</p>
          <Button onClick={load} variant="outline" size="sm">Retry</Button>
        </CardContent>
      </Card>
    );
  }

  if (!analysis) return null;
  const q = analysis.quote;
  const positive = q.change_pct >= 0;
  const dq = analysis.data_quality;
  const quoteAt = q.timestamp ? new Date(q.timestamp) : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs text-muted-foreground">{analysis.sector || "—"}</div>
          <h1 className="text-2xl font-bold tracking-tight">
            {q.name || symbol}{" "}
            <span className="text-base font-normal text-muted-foreground">{symbol}</span>
          </h1>
          <div className="flex items-baseline gap-3 mt-1">
            <span className="font-mono text-3xl font-semibold">{fmtNumber(q.price)}</span>
            <span className={`font-mono text-sm ${pctClass(q.change_pct)}`}>
              {positive ? "+" : ""}
              {fmtNumber(q.change)} ({fmtPct(q.change_pct)})
            </span>
            {analysis.relative_strength !== undefined && (
              <Badge variant="outline">
                RS vs Nifty:{" "}
                <span className={pctClass(analysis.relative_strength)}>
                  {analysis.relative_strength >= 0 ? "+" : ""}
                  {analysis.relative_strength}pp
                </span>
              </Badge>
            )}
            <DataQualityBadge quality={dq} />
          </div>
          {quoteAt && (
            <div className="text-[10px] text-muted-foreground mt-1 font-mono">
              Last updated: {formatIST(quoteAt)} IST
            </div>
          )}
        </div>
        <div className="flex gap-2">
          <Tabs value={mode} onValueChange={(v) => setMode(v as Mode)}>
            <TabsList>
              <TabsTrigger value="intraday">Intraday</TabsTrigger>
              <TabsTrigger value="swing">Swing</TabsTrigger>
              <TabsTrigger value="positional">Positional</TabsTrigger>
            </TabsList>
          </Tabs>
          <Button variant="outline" onClick={load}>Refresh</Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-2">
          <PriceChart data={ohlc} overlays={overlays} markerLevels={markers} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <SignalCard signal={analysis.signal} />
          <IndicatorTable ind={analysis.indicators} />
        </div>
        <div className="space-y-4">
          <RiskCalculator
            defaults={{
              entry: analysis.signal.entry_high ?? q.price,
              stoploss: analysis.signal.stoploss ?? undefined,
              target: analysis.signal.target1 ?? undefined,
            }}
          />
          <Card>
            <CardHeader>
              <CardTitle>News mentioning {symbol.replace(".NS", "")}</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <ul className="divide-y divide-border max-h-96 overflow-auto">
                {news.length === 0 && (
                  <li className="px-4 py-3 text-xs text-muted-foreground">
                    No recent news matched.
                  </li>
                )}
                {news.map((n, i) => (
                  <li key={i} className="px-4 py-2.5">
                    <a href={n.link} target="_blank" rel="noreferrer" className="block">
                      <div className="text-sm font-medium line-clamp-2">{n.title}</div>
                      <div className="text-[10px] text-muted-foreground mt-1 flex items-center gap-2">
                        <span>{n.source}</span>
                        <span
                          className={
                            n.sentiment > 0 ? "text-bull" : n.sentiment < 0 ? "text-bear" : ""
                          }
                        >
                          sent {n.sentiment.toFixed(2)}
                        </span>
                      </div>
                    </a>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>

      <ul className="space-y-1">
        {analysis.notes.map((n, i) => (
          <li key={i} className="text-[11px] text-muted-foreground">• {n}</li>
        ))}
      </ul>
    </div>
  );
}

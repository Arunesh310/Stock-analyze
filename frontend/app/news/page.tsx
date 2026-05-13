"use client";
import * as React from "react";
import { api } from "@/lib/api";
import type { NewsItem } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";

export default function NewsPage() {
  const [items, setItems] = React.useState<NewsItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [q, setQ] = React.useState("");

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.news(80).then((it) => {
      if (!cancelled) {
        setItems(it);
        setLoading(false);
      }
    }).catch(() => setLoading(false));
    return () => { cancelled = true; };
  }, []);

  const filtered = React.useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return items;
    return items.filter(
      (n) =>
        n.title.toLowerCase().includes(t) ||
        n.summary?.toLowerCase().includes(t) ||
        n.impacted_sectors.join(",").toLowerCase().includes(t)
    );
  }, [items, q]);

  const sectorAgg = React.useMemo(() => {
    const m: Record<string, { sum: number; n: number }> = {};
    items.forEach((n) =>
      n.impacted_sectors.forEach((sec) => {
        m[sec] = m[sec] || { sum: 0, n: 0 };
        m[sec].sum += n.sentiment;
        m[sec].n += 1;
      })
    );
    return Object.entries(m)
      .map(([sec, v]) => ({ sec, avg: v.sum / v.n, n: v.n }))
      .sort((a, b) => b.n - a.n);
  }, [items]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">News & Sentiment</h1>
        <p className="text-sm text-muted-foreground">
          Aggregated from free RSS feeds, scored offline via lexicon sentiment.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <Input
            placeholder="Filter news…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.map((n, i) => (
                <a
                  key={i}
                  href={n.link}
                  target="_blank"
                  rel="noreferrer"
                  className="block rounded-md border border-border p-3 hover:bg-secondary/50"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold line-clamp-2">{n.title}</div>
                      {n.summary && (
                        <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                          {n.summary}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-1 mt-2">
                        {n.impacted_sectors.map((s) => (
                          <Badge key={s} variant="outline" className="text-[10px]">
                            {s}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <Badge
                        variant={n.sentiment > 0 ? "bull" : n.sentiment < 0 ? "bear" : "neutral"}
                        className="text-[10px]"
                      >
                        sent {n.sentiment.toFixed(2)}
                      </Badge>
                      <div className="text-[10px] text-muted-foreground mt-1">
                        impact {n.impact_score.toFixed(2)}
                      </div>
                      <div className="text-[10px] text-muted-foreground">{n.source}</div>
                    </div>
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Sector Mentions</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="divide-y divide-border">
                {sectorAgg.map((s) => (
                  <li key={s.sec} className="flex items-center justify-between py-2 text-sm">
                    <span>{s.sec}</span>
                    <span className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{s.n}</span>
                      <Badge
                        variant={s.avg > 0 ? "bull" : s.avg < 0 ? "bear" : "neutral"}
                        className="text-[10px]"
                      >
                        {s.avg.toFixed(2)}
                      </Badge>
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

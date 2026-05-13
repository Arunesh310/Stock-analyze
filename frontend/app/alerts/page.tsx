"use client";
import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { AlertOut } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";

export default function AlertsPage() {
  const [items, setItems] = React.useState<AlertOut[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      setItems(await api.alerts(200));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const scan = async () => {
    setBusy(true);
    try {
      await api.scanAlerts();
      await load();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Alerts</h1>
          <p className="text-sm text-muted-foreground">
            Breakouts, volume spikes, MACD crossovers, RSI reversals…
          </p>
        </div>
        <Button onClick={scan} disabled={busy}>
          {busy ? "Scanning…" : "Run scan now"}
        </Button>
      </div>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            No alerts yet. Click <em>Run scan now</em> to check the universe.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {items.map((a) => (
            <Link
              key={a.id}
              href={`/stocks/${encodeURIComponent(a.symbol)}`}
              className="block rounded-md border border-border p-3 hover:bg-secondary/40"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge
                      variant={
                        a.severity === "critical"
                          ? "bear"
                          : a.severity === "warn"
                          ? "neutral"
                          : "bull"
                      }
                    >
                      {a.kind}
                    </Badge>
                    <span className="font-semibold text-sm">{a.title}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{a.message}</p>
                </div>
                <div className="text-right text-xs text-muted-foreground shrink-0">
                  <div>{new Date(a.created_at).toLocaleString()}</div>
                  {a.price && <div className="font-mono">@ {a.price.toFixed(2)}</div>}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

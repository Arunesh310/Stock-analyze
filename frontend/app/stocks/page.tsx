"use client";
import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";

export default function StocksIndexPage() {
  const [items, setItems] = React.useState<{ symbol: string; name: string; sector: string }[]>([]);
  const [q, setQ] = React.useState("");

  React.useEffect(() => {
    api.universe().then(setItems).catch(() => setItems([]));
  }, []);

  const filtered = React.useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return items;
    return items.filter(
      (i) =>
        i.symbol.toLowerCase().includes(t) ||
        i.name.toLowerCase().includes(t) ||
        i.sector.toLowerCase().includes(t)
    );
  }, [items, q]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Stock Universe</h1>
        <p className="text-sm text-muted-foreground">
          Click any symbol for the full AI-powered analysis.
        </p>
      </div>
      <Input
        placeholder="Filter by symbol / name / sector"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <Card>
        <CardHeader>
          <CardTitle>{filtered.length} symbols</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {filtered.map((i) => (
              <Link
                key={i.symbol}
                href={`/stocks/${encodeURIComponent(i.symbol)}`}
                className="flex items-center justify-between rounded-md border border-border px-3 py-2 hover:bg-secondary/50"
              >
                <div className="min-w-0">
                  <div className="font-semibold text-sm truncate">{i.symbol.replace(".NS", "")}</div>
                  <div className="text-[11px] text-muted-foreground truncate">{i.name}</div>
                </div>
                <Badge variant="outline" className="text-[10px]">{i.sector}</Badge>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

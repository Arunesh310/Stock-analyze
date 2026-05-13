"use client";
import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Quote, WatchlistOut } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { fmtNumber, fmtPct, pctClass } from "@/lib/utils";
import { Trash2, Plus } from "lucide-react";

export default function WatchlistPage() {
  const [lists, setLists] = React.useState<WatchlistOut[]>([]);
  const [activeId, setActiveId] = React.useState<number | null>(null);
  const [name, setName] = React.useState("");
  const [symbol, setSymbol] = React.useState("");
  const [quotes, setQuotes] = React.useState<Record<string, Quote>>({});

  const refresh = React.useCallback(async () => {
    const ws = await api.watchlists();
    setLists(ws);
    if (!activeId && ws[0]) setActiveId(ws[0].id);
  }, [activeId]);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  const active = lists.find((w) => w.id === activeId) || null;

  React.useEffect(() => {
    if (!active || active.symbols.length === 0) {
      setQuotes({});
      return;
    }
    api.batchQuotes(active.symbols).then((qs) => {
      const m: Record<string, Quote> = {};
      qs.forEach((q) => (m[q.symbol] = q));
      setQuotes(m);
    });
  }, [active?.id, active?.symbols.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const create = async () => {
    if (!name.trim()) return;
    await api.createWatchlist(name.trim());
    setName("");
    await refresh();
  };
  const addSym = async () => {
    if (!active || !symbol.trim()) return;
    await api.addSymbol(active.id, symbol.trim().toUpperCase());
    setSymbol("");
    await refresh();
  };
  const removeSym = async (s: string) => {
    if (!active) return;
    await api.removeSymbol(active.id, s);
    await refresh();
  };
  const removeList = async (id: number) => {
    await api.deleteWatchlist(id);
    setActiveId(null);
    await refresh();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Watchlists</h1>
          <p className="text-sm text-muted-foreground">
            Track your conviction list with live quotes & AI signals.
          </p>
        </div>
        <div className="flex gap-2">
          <Input
            placeholder="New watchlist name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-64"
          />
          <Button onClick={create}>
            <Plus className="h-4 w-4 mr-1" /> Create
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Lists</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ul className="divide-y divide-border">
              {lists.map((w) => (
                <li
                  key={w.id}
                  className={`flex items-center justify-between px-4 py-2 cursor-pointer ${
                    w.id === activeId ? "bg-primary/10" : "hover:bg-secondary/50"
                  }`}
                  onClick={() => setActiveId(w.id)}
                >
                  <div>
                    <div className="text-sm font-medium">{w.name}</div>
                    <div className="text-[10px] text-muted-foreground">
                      {w.symbols.length} symbols
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeList(w.id);
                    }}
                    className="text-muted-foreground hover:text-bear"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
              {lists.length === 0 && (
                <li className="px-4 py-3 text-xs text-muted-foreground">
                  No watchlists yet. Run the seed script or create one above.
                </li>
              )}
            </ul>
          </CardContent>
        </Card>

        <Card className="lg:col-span-3">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>{active ? active.name : "Select a watchlist"}</CardTitle>
            {active && (
              <div className="flex items-center gap-2">
                <Input
                  className="w-48"
                  placeholder="Add symbol e.g. RELIANCE.NS"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                />
                <Button size="sm" onClick={addSym}>Add</Button>
              </div>
            )}
          </CardHeader>
          <CardContent className="p-0">
            {!active ? (
              <p className="px-4 py-3 text-sm text-muted-foreground">No list selected.</p>
            ) : active.symbols.length === 0 ? (
              <p className="px-4 py-3 text-sm text-muted-foreground">
                Empty list — add symbols to track them.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-secondary/40 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="text-left px-4 py-2">Symbol</th>
                    <th className="text-right px-4 py-2">Price</th>
                    <th className="text-right px-4 py-2">Change</th>
                    <th className="text-right px-4 py-2">%</th>
                    <th className="text-right px-4 py-2">Volume</th>
                    <th className="text-right px-4 py-2"> </th>
                  </tr>
                </thead>
                <tbody>
                  {active.symbols.map((s) => {
                    const q = quotes[s];
                    return (
                      <tr key={s} className="border-t border-border hover:bg-secondary/30">
                        <td className="px-4 py-2">
                          <Link href={`/stocks/${encodeURIComponent(s)}`} className="font-medium">
                            {s.replace(".NS", "")}
                          </Link>
                          <div className="text-[10px] text-muted-foreground">{q?.name || s}</div>
                        </td>
                        <td className="px-4 py-2 text-right font-mono">{q ? fmtNumber(q.price) : "…"}</td>
                        <td className={`px-4 py-2 text-right font-mono ${q ? pctClass(q.change) : ""}`}>
                          {q ? fmtNumber(q.change) : "…"}
                        </td>
                        <td className={`px-4 py-2 text-right font-mono ${q ? pctClass(q.change_pct) : ""}`}>
                          {q ? fmtPct(q.change_pct) : "…"}
                        </td>
                        <td className="px-4 py-2 text-right text-xs text-muted-foreground">
                          {q?.volume ? Intl.NumberFormat("en-IN").format(q.volume) : "—"}
                        </td>
                        <td className="px-4 py-2 text-right">
                          <button
                            onClick={() => removeSym(s)}
                            className="text-muted-foreground hover:text-bear"
                            type="button"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

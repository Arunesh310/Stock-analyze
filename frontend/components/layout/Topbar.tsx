"use client";
import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  AlertCircle,
  Clock,
  History,
  Loader2,
  Search,
  Sparkles,
  TrendingUp,
  Wifi,
  WifiOff,
} from "lucide-react";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { useLiveTicks } from "@/hooks/useLiveTicks";
import { useMarketStatus, formatIST } from "@/hooks/useMarketStatus";
import { api } from "@/lib/api";
import type { ResolveResult, SearchHit } from "@/lib/types";
import { cn, fmtNumber, fmtPct, pctClass } from "@/lib/utils";

const RECENT_KEY = "bq.recentSearches";
const RECENT_MAX = 8;

function readRecent(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    return raw ? (JSON.parse(raw) as string[]).slice(0, RECENT_MAX) : [];
  } catch {
    return [];
  }
}

function writeRecent(sym: string): void {
  if (typeof window === "undefined") return;
  const existing = readRecent().filter((s) => s !== sym);
  existing.unshift(sym);
  window.localStorage.setItem(
    RECENT_KEY,
    JSON.stringify(existing.slice(0, RECENT_MAX))
  );
}

function statusColor(state?: string): string {
  switch (state) {
    case "regular":
      return "text-bull";
    case "preopen":
      return "text-blue-400";
    case "afterhours":
      return "text-amber-400";
    default:
      return "text-muted-foreground";
  }
}

function statusDot(state?: string): string {
  switch (state) {
    case "regular":
      return "bg-bull animate-pulse";
    case "preopen":
      return "bg-blue-400";
    case "afterhours":
      return "bg-amber-400";
    default:
      return "bg-muted-foreground";
  }
}

export function Topbar() {
  const router = useRouter();
  const { connected, lastTickAt } = useLiveTicks();
  const { status, istNow } = useMarketStatus();

  const [q, setQ] = React.useState("");
  const [hits, setHits] = React.useState<SearchHit[]>([]);
  const [trending, setTrending] = React.useState<SearchHit[]>([]);
  const [recent, setRecent] = React.useState<string[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  const [activeIdx, setActiveIdx] = React.useState(0);
  const [unlisted, setUnlisted] = React.useState<ResolveResult | null>(null);

  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
    setRecent(readRecent());
    api.trending(8).then(setTrending).catch(() => setTrending([]));
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    if (!q) {
      setHits([]);
      setUnlisted(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        // with_prices=true is expensive — keep limit small (top 5 only).
        const r = await api.search(q, { limit: 5, with_prices: true });
        if (cancelled) return;
        setHits(r);
        setActiveIdx(0);
        // Zero matches → check if it's a known unlisted/private company
        if (r.length === 0) {
          try {
            const res = await api.resolve(q);
            if (!cancelled && res.listed === false) setUnlisted(res);
            else if (!cancelled) setUnlisted(null);
          } catch {
            if (!cancelled) setUnlisted(null);
          }
        } else {
          setUnlisted(null);
        }
      } catch {
        if (!cancelled) {
          setHits([]);
          setUnlisted(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [q]);

  const visible: SearchHit[] = React.useMemo(() => {
    if (q) return hits;
    const recentHits: SearchHit[] = recent.map((s) => ({
      symbol: s,
      name: s,
      sector: "Recent",
      exchange: "NSE",
      match_confidence: 1,
      match_source: "recent",
    }));
    return [...recentHits, ...trending];
  }, [q, hits, recent, trending]);

  const goto = (symbol: string) => {
    if (!symbol) return;
    writeRecent(symbol);
    setRecent(readRecent());
    router.push(`/stocks/${encodeURIComponent(symbol)}`);
    setQ("");
    setHits([]);
    setOpen(false);
    inputRef.current?.blur();
  };

  const submit = async () => {
    const first = visible[activeIdx] ?? visible[0];
    if (first) {
      goto(first.symbol);
      return;
    }
    if (!q.trim()) return;
    try {
      const r = await api.resolve(q.trim());
      if (r.symbol) goto(r.symbol);
    } catch {
      /* ignore */
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(visible.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      submit();
    } else if (e.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
    }
  };

  const showRecent = !q && recent.length > 0;
  const showTrending = !q && trending.length > 0;
  const groupBreak = showRecent ? recent.length : 0;

  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-border bg-card/60 backdrop-blur px-4 md:px-6">
      <div className="md:hidden font-semibold text-sm">BharatQuant</div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="relative flex-1 max-w-2xl"
      >
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        {loading && (
          <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 animate-spin text-muted-foreground" />
        )}
        <Input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 180)}
          onKeyDown={onKeyDown}
          placeholder="Search stocks: RELIANCE, hal, hdfc bank, tata mototrs…"
          aria-label="Search stocks"
          className="pl-8 pr-8 bg-background/60"
        />
        {open && (visible.length > 0 || (q && !loading)) && (
          <div className="absolute mt-1 w-full rounded-lg border border-border bg-popover/95 backdrop-blur shadow-2xl overflow-hidden z-50">
            {q && visible.length === 0 && !loading && unlisted && (
              <div className="px-3 py-3 text-xs space-y-1.5">
                <div className="flex items-start gap-2 text-amber-300">
                  <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                  <span>{unlisted.message}</span>
                </div>
                {(unlisted.suggestions?.length ?? 0) > 0 && (
                  <div className="pt-1 text-muted-foreground">
                    Did you mean:{" "}
                    {unlisted.suggestions!.slice(0, 5).map((s, i) => (
                      <button
                        key={s}
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          goto(s);
                        }}
                        className="underline underline-offset-2 hover:text-foreground"
                      >
                        {s.replace(".NS", "")}
                        {i < (unlisted.suggestions!.length - 1) ? ", " : ""}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            {q && visible.length === 0 && !loading && !unlisted && (
              <div className="px-3 py-6 text-center text-xs text-muted-foreground">
                No matches for &ldquo;{q}&rdquo;.
              </div>
            )}

            {showRecent && (
              <div className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                <History className="h-3 w-3" /> Recent
              </div>
            )}

            {visible.map((r, idx) => {
              const isRecentSection = !q && idx < groupBreak;
              const isTrendingHeader = !q && idx === groupBreak && showTrending;
              return (
                <React.Fragment key={`${r.symbol}-${idx}`}>
                  {isTrendingHeader && (
                    <div className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-wider text-muted-foreground flex items-center gap-1 border-t border-border/60">
                      <TrendingUp className="h-3 w-3" /> Trending today
                    </div>
                  )}
                  <button
                    type="button"
                    onMouseEnter={() => setActiveIdx(idx)}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      goto(r.symbol);
                    }}
                    className={cn(
                      "flex w-full items-center justify-between px-3 py-2 text-left text-sm",
                      idx === activeIdx ? "bg-secondary" : "hover:bg-secondary/60"
                    )}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="font-semibold mr-2">
                        {r.symbol.replace(".NS", "")}
                      </span>
                      <span className="text-muted-foreground text-xs">
                        {isRecentSection ? "Recently viewed" : r.name}
                      </span>
                    </span>
                    <span className="flex items-center gap-2 shrink-0">
                      {!isRecentSection && r.price !== undefined && (
                        <span className="font-mono text-xs">
                          {fmtNumber(r.price)}
                          {r.change_pct !== undefined && (
                            <span className={cn("ml-1", pctClass(r.change_pct))}>
                              {fmtPct(r.change_pct)}
                            </span>
                          )}
                        </span>
                      )}
                      {!isRecentSection && (
                        <Badge variant="outline" className="text-[10px]">
                          {r.sector}
                        </Badge>
                      )}
                      {!isRecentSection && r.match_source === "fuzzy" && (
                        <Badge variant="outline" className="text-[9px] uppercase text-amber-400">
                          fuzzy
                        </Badge>
                      )}
                    </span>
                  </button>
                </React.Fragment>
              );
            })}

            <div className="px-3 py-1.5 text-[10px] text-muted-foreground border-t border-border/60 flex items-center justify-between">
              <span className="flex items-center gap-1">
                <Sparkles className="h-3 w-3" /> Press Enter to open
              </span>
              <span>↑ ↓ navigate · Esc close</span>
            </div>
          </div>
        )}
      </form>

      <div className="ml-auto flex items-center gap-3">
        <Link
          href="/chat"
          className="hidden md:inline text-xs text-muted-foreground hover:text-foreground"
        >
          Ask the AI →
        </Link>

        {/* Market status */}
        <div
          className={cn(
            "hidden md:flex items-center gap-1.5 text-[11px]",
            statusColor(status?.state)
          )}
          title={
            status
              ? `Next: ${
                  status.next_open_at ?? status.next_close_at ?? ""
                }`
              : "Loading…"
          }
        >
          <span className={cn("h-2 w-2 rounded-full", statusDot(status?.state))} />
          {status ? status.label : "Loading…"}
        </div>

        {/* IST clock (client-only — avoid SSR hydration mismatch) */}
        <div
          className="hidden md:flex items-center gap-1 text-[11px] text-muted-foreground font-mono min-w-[88px]"
          suppressHydrationWarning
        >
          <Clock className="h-3 w-3" />
          {mounted ? `${formatIST(istNow)} IST` : "—"}
        </div>

        {/* Live tick state */}
        <div
          className="flex items-center gap-1.5 text-[11px] text-muted-foreground"
          suppressHydrationWarning
        >
          {connected ? (
            <Wifi className="h-3.5 w-3.5 text-bull" />
          ) : (
            <WifiOff className="h-3.5 w-3.5 text-bear" />
          )}
          {connected
            ? `Live${mounted && lastTickAt ? ` · ${formatIST(lastTickAt)}` : ""}`
            : "Offline"}
        </div>
      </div>
    </header>
  );
}

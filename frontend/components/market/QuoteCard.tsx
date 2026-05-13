"use client";
import Link from "next/link";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import type { Quote } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/Card";
import { fmtNumber, fmtPct, pctClass } from "@/lib/utils";

export function QuoteCard({ q, hrefBase = "/stocks" }: { q: Quote; hrefBase?: string }) {
  const positive = q.change_pct >= 0;
  return (
    <Link href={`${hrefBase}/${encodeURIComponent(q.symbol)}`}>
      <Card className="transition-colors hover:border-primary/50 hover:bg-card/80">
        <CardContent className="p-3">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <div className="text-xs text-muted-foreground truncate">{q.name || q.symbol}</div>
              <div className="font-semibold text-sm truncate">{q.symbol}</div>
            </div>
            <div className={`flex items-center gap-1 text-xs font-semibold ${pctClass(q.change_pct)}`}>
              {positive ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
              {fmtPct(q.change_pct)}
            </div>
          </div>
          <div className="mt-2 flex items-end justify-between">
            <div className="text-lg font-mono font-semibold">{fmtNumber(q.price)}</div>
            <div className={`text-xs font-mono ${pctClass(q.change)}`}>{fmtNumber(q.change)}</div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

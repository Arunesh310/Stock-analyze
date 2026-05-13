"use client";
import type { Quote } from "@/lib/types";
import { fmtNumber, fmtPct, pctClass } from "@/lib/utils";

export function IndexStrip({ items }: { items: Quote[] }) {
  return (
    <div className="overflow-x-auto rounded-md border border-border bg-card/40">
      <div className="flex divide-x divide-border min-w-max">
        {items.map((q) => (
          <div key={q.symbol} className="px-4 py-3 min-w-[180px]">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {q.name || q.symbol}
            </div>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="font-mono text-lg font-semibold">{fmtNumber(q.price)}</span>
              <span className={`text-xs font-medium ${pctClass(q.change_pct)}`}>
                {fmtPct(q.change_pct)}
              </span>
            </div>
            <div className={`text-[11px] font-mono ${pctClass(q.change)}`}>
              {q.change >= 0 ? "+" : ""}
              {fmtNumber(q.change)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

"use client";
import Link from "next/link";
import type { Quote } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { fmtNumber, fmtPct, pctClass } from "@/lib/utils";

export function MoversList({
  title,
  items,
}: {
  title: string;
  items: Quote[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ul className="divide-y divide-border">
          {items.map((q) => (
            <li key={q.symbol}>
              <Link
                href={`/stocks/${encodeURIComponent(q.symbol)}`}
                className="flex items-center justify-between px-4 py-2.5 hover:bg-secondary/50"
              >
                <div className="min-w-0">
                  <div className="font-medium text-sm truncate">{q.symbol.replace(".NS", "")}</div>
                  <div className="text-[11px] text-muted-foreground truncate">
                    {q.name || ""}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-sm">{fmtNumber(q.price)}</div>
                  <div className={`text-xs font-semibold ${pctClass(q.change_pct)}`}>
                    {fmtPct(q.change_pct)}
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";

export function BreadthBar({
  breadth,
  fii,
}: {
  breadth: { advancers: number; decliners: number; unchanged: number };
  fii: {
    fii_proxy_cr: number;
    dii_proxy_cr: number;
    nifty_change_pct: number;
    news_sentiment: number;
    samples: number;
  };
}) {
  const total = breadth.advancers + breadth.decliners + breadth.unchanged || 1;
  const advPct = (breadth.advancers / total) * 100;
  const decPct = (breadth.decliners / total) * 100;
  const flatPct = 100 - advPct - decPct;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Market Breadth & Flow Proxy</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div>
            <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
              <span>
                Advancers <span className="text-bull">{breadth.advancers}</span>
              </span>
              <span>
                Decliners <span className="text-bear">{breadth.decliners}</span>
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
              <div className="flex h-full">
                <div className="bg-bull" style={{ width: `${advPct}%` }} />
                <div className="bg-neutral/60" style={{ width: `${flatPct}%` }} />
                <div className="bg-bear" style={{ width: `${decPct}%` }} />
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 pt-2 border-t border-border">
            <div>
              <div className="text-[10px] uppercase text-muted-foreground">FII Proxy</div>
              <div
                className={`font-mono text-sm font-semibold ${
                  fii.fii_proxy_cr >= 0 ? "text-bull" : "text-bear"
                }`}
              >
                ₹{fii.fii_proxy_cr.toFixed(0)} Cr
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase text-muted-foreground">DII Proxy</div>
              <div
                className={`font-mono text-sm font-semibold ${
                  fii.dii_proxy_cr >= 0 ? "text-bull" : "text-bear"
                }`}
              >
                ₹{fii.dii_proxy_cr.toFixed(0)} Cr
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase text-muted-foreground">News Sentiment</div>
              <div
                className={`font-mono text-sm font-semibold ${
                  fii.news_sentiment >= 0 ? "text-bull" : "text-bear"
                }`}
              >
                {fii.news_sentiment.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase text-muted-foreground">Nifty</div>
              <div
                className={`font-mono text-sm font-semibold ${
                  fii.nifty_change_pct >= 0 ? "text-bull" : "text-bear"
                }`}
              >
                {fii.nifty_change_pct >= 0 ? "+" : ""}
                {fii.nifty_change_pct.toFixed(2)}%
              </div>
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground">
            FII/DII shown as a proxy blend of news sentiment & Nifty change. Real
            flows are released after market close on NSE.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

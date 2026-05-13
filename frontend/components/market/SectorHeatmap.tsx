"use client";
import type { SectorStrength } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { fmtPct } from "@/lib/utils";

function colorFor(strength: number) {
  // -10..+10 -> red..green
  const clamped = Math.max(-10, Math.min(10, strength));
  if (clamped >= 0) {
    const a = 0.15 + (clamped / 10) * 0.45;
    return `hsl(142 71% 45% / ${a})`;
  }
  const a = 0.15 + (Math.abs(clamped) / 10) * 0.45;
  return `hsl(0 84% 60% / ${a})`;
}

export function SectorHeatmap({ sectors }: { sectors: SectorStrength[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Sector Strength (1M)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {sectors.map((s) => (
            <div
              key={s.sector}
              className="rounded-md border border-border p-3"
              style={{ backgroundColor: colorFor(s.strength) }}
              title={`Leaders: ${s.leaders.join(", ")}`}
            >
              <div className="text-xs font-medium">{s.sector}</div>
              <div className="text-lg font-mono font-semibold">{fmtPct(s.strength)}</div>
              <div className="mt-1 text-[10px] text-muted-foreground truncate">
                ⬆ {s.leaders[0]?.replace(".NS", "") || "—"} · ⬇{" "}
                {s.laggards[s.laggards.length - 1]?.replace(".NS", "") || "—"}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

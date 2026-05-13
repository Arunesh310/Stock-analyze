"use client";
import * as React from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleSlash,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import type { SyncPipeline, SyncStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const TONE: Record<SyncPipeline["status"], string> = {
  fresh: "bg-bull/15 text-bull border-bull/30",
  ok: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  stale: "bg-bear/15 text-bear border-bear/30",
  offline: "bg-muted/20 text-muted-foreground border-border",
};

const ICON: Record<SyncPipeline["status"], React.ReactNode> = {
  fresh: <CheckCircle2 className="h-3.5 w-3.5" />,
  ok: <Loader2 className="h-3.5 w-3.5" />,
  stale: <AlertTriangle className="h-3.5 w-3.5" />,
  offline: <CircleSlash className="h-3.5 w-3.5" />,
};

export function SyncStatusPanel() {
  const [status, setStatus] = React.useState<SyncStatus | null>(null);
  const [err, setErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const s = await api.syncStatus();
        if (!cancelled) {
          setStatus(s);
          setErr(null);
        }
      } catch (e: any) {
        if (!cancelled) setErr(String(e?.message || e));
      }
    }
    load();
    const id = setInterval(load, 15_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (!status && !err) {
    return (
      <div className="rounded-md border border-border bg-card/40 px-3 py-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Connecting to sync engine...
        </div>
      </div>
    );
  }
  if (err || !status) {
    return (
      <div className="rounded-md border border-bear/40 bg-bear/10 px-3 py-2 text-xs text-bear">
        Sync status unavailable: {err}
      </div>
    );
  }

  const overallTone =
    status.overall_status === "healthy"
      ? "text-bull"
      : status.overall_status === "degraded"
      ? "text-amber-400"
      : "text-bear";

  return (
    <div className="rounded-md border border-border bg-card/40 px-3 py-2">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Activity className={cn("h-4 w-4", overallTone)} />
          <span className="text-xs font-semibold tracking-wide uppercase text-muted-foreground">
            System sync
          </span>
          <span className={cn("text-xs font-semibold uppercase", overallTone)}>
            {status.overall_status}
          </span>
        </div>
        <span className="text-[10px] text-muted-foreground">
          Uptime {Math.floor(status.uptime_seconds / 60)}m ·{" "}
          {status.predictions.validated}/{status.predictions.total_predictions} validated
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
        {status.pipelines.map((p) => (
          <div
            key={p.key}
            className={cn(
              "rounded-md border px-2 py-1.5 flex flex-col gap-0.5",
              TONE[p.status]
            )}
            title={p.detail}
          >
            <div className="flex items-center gap-1 text-[10px] uppercase tracking-wide opacity-80">
              {ICON[p.status]}
              {p.label}
            </div>
            <div className="text-xs font-semibold capitalize">
              {p.status} · {p.relative}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

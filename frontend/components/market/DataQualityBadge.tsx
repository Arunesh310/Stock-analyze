"use client";
import * as React from "react";
import { ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";
import type { DataQuality } from "@/lib/types";
import { cn } from "@/lib/utils";
import { formatIST } from "@/hooks/useMarketStatus";

type Props = {
  quality?: DataQuality | null;
  size?: "sm" | "md";
};

function tone(score: number, synth: boolean, stale: boolean) {
  if (synth) return "border-bear/40 text-bear bg-bear/10";
  if (stale) return "border-amber-400/40 text-amber-400 bg-amber-400/10";
  if (score >= 85) return "border-bull/40 text-bull bg-bull/10";
  if (score >= 60) return "border-amber-400/40 text-amber-400 bg-amber-400/10";
  return "border-bear/40 text-bear bg-bear/10";
}

export function DataQualityBadge({ quality, size = "sm" }: Props) {
  if (!quality) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px]",
          "border-border text-muted-foreground bg-muted/30"
        )}
      >
        <ShieldQuestion className="h-3 w-3" /> Data: unknown
      </span>
    );
  }
  const score = Math.round(quality.score);
  const cls = tone(score, quality.is_synthetic, quality.is_stale);
  const Icon = quality.is_synthetic || quality.is_stale ? ShieldAlert : ShieldCheck;
  const label =
    quality.is_synthetic
      ? "Synthetic"
      : quality.is_stale
      ? "Stale"
      : `${score}/100`;
  const updatedAt = quality.last_bar_at
    ? new Date(quality.last_bar_at)
    : null;
  return (
    <span
      title={(quality.issues || []).join(" · ") || "All checks passed"}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5",
        size === "sm" ? "text-[10px]" : "text-xs",
        cls
      )}
    >
      <Icon className="h-3 w-3" /> {quality.source.toUpperCase()} · {label}
      {updatedAt && (
        <span className="ml-1 text-muted-foreground font-mono">
          {formatIST(updatedAt)}
        </span>
      )}
    </span>
  );
}

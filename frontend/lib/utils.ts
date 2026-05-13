import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmtNumber(n: number | null | undefined, opts?: Intl.NumberFormatOptions) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2, ...opts }).format(n);
}

export function fmtINR(n: number | null | undefined) {
  if (n === null || n === undefined) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(n);
}

export function pctClass(v: number | null | undefined) {
  if (v === null || v === undefined || isNaN(v)) return "text-muted-foreground";
  if (v > 0) return "text-bull";
  if (v < 0) return "text-bear";
  return "text-muted-foreground";
}

export function fmtPct(v: number | null | undefined, digits = 2) {
  if (v === null || v === undefined || isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(digits)}%`;
}

export function fmtCompactNum(n: number | null | undefined) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return new Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(n);
}

export function classifySignal(action: string) {
  if (action === "BUY") return { color: "text-bull", bg: "bg-bull-soft", border: "border-bull/40" };
  if (action === "SELL") return { color: "text-bear", bg: "bg-bear-soft", border: "border-bear/40" };
  return { color: "text-neutral", bg: "bg-secondary", border: "border-border" };
}

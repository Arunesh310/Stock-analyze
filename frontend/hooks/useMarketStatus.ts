"use client";
import * as React from "react";
import { api } from "@/lib/api";
import type { MarketStatus } from "@/lib/types";

const REFRESH_MS = 30_000;

export function useMarketStatus() {
  const [status, setStatus] = React.useState<MarketStatus | null>(null);
  const [istNow, setIstNow] = React.useState<Date>(new Date());

  React.useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const s = await api.marketStatus();
        if (alive) setStatus(s);
      } catch {
        /* ignore */
      }
    };
    load();
    const t = setInterval(load, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  React.useEffect(() => {
    const t = setInterval(() => setIstNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return { status, istNow };
}

export function formatIST(d: Date): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }).format(d);
}

export function formatISTLong(d: Date): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).format(d);
}

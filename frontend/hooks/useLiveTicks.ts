"use client";
import * as React from "react";
import { wsUrl } from "@/lib/api";
import type { MarketStatus, Quote } from "@/lib/types";
import { notify } from "@/components/ui/Toaster";

type TickMsg = { type: "ticks"; data: Quote[] };
type StatusMsg = { type: "status"; data: MarketStatus };
type AlertMsg = {
  type: "alerts";
  data: {
    id: number;
    symbol: string;
    title: string;
    message: string;
    severity: string;
    kind: string;
  }[];
};
type Msg = TickMsg | AlertMsg | StatusMsg | { type: "hello" | "ping" };

export function useLiveTicks() {
  const [connected, setConnected] = React.useState(false);
  const [ticks, setTicks] = React.useState<Record<string, Quote>>({});
  const [lastTickAt, setLastTickAt] = React.useState<Date | null>(null);
  const [statusMsg, setStatusMsg] = React.useState<MarketStatus | null>(null);

  React.useEffect(() => {
    let ws: WebSocket | null = null;
    let retryTimer: any;
    let stop = false;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);
      } catch {
        retry();
        return;
      }
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!stop) retry();
      };
      ws.onerror = () => {
        try {
          ws?.close();
        } catch {}
      };
      ws.onmessage = (ev) => {
        try {
          const msg: Msg = JSON.parse(ev.data);
          if (msg.type === "ticks") {
            setTicks((prev) => {
              const next = { ...prev };
              msg.data.forEach((q) => (next[q.symbol] = q));
              return next;
            });
            setLastTickAt(new Date());
          } else if (msg.type === "status") {
            setStatusMsg(msg.data);
          } else if (msg.type === "alerts") {
            msg.data.forEach((a) => {
              notify({
                title: a.title,
                description: a.message,
                variant:
                  a.severity === "critical"
                    ? "destructive"
                    : a.severity === "warn"
                    ? "warn"
                    : "success",
              });
            });
          }
        } catch {
          /* ignore */
        }
      };
    };

    const retry = () => {
      retryTimer = setTimeout(connect, 2500);
    };

    connect();
    return () => {
      stop = true;
      clearTimeout(retryTimer);
      try {
        ws?.close();
      } catch {}
    };
  }, []);

  return { connected, ticks, lastTickAt, statusMsg };
}

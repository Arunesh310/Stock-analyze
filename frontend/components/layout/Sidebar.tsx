"use client";
import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  LineChart,
  Newspaper,
  Bell,
  Star,
  Beaker,
  MessageSquare,
  Activity,
  TrendingUp,
  Target,
  Wallet,
  Brain,
  Compass,
  Gauge,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV: {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  group?: string;
}[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/signals", label: "AI Signals", icon: TrendingUp },
  { href: "/stocks", label: "Stock Analysis", icon: LineChart },
  { href: "/news", label: "News & Sentiment", icon: Newspaper },
  { href: "/watchlist", label: "Watchlists", icon: Star },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/backtest", label: "Backtest", icon: Beaker },
  { href: "/chat", label: "AI Assistant", icon: MessageSquare },

  { href: "/performance", label: "AI Accuracy", icon: Target, group: "AI Brain" },
  { href: "/profit", label: "Simulated Profit", icon: Wallet, group: "AI Brain" },
  { href: "/learning", label: "Learning Feedback", icon: Brain, group: "AI Brain" },
  { href: "/regime", label: "Market Regime", icon: Compass, group: "AI Brain" },
  { href: "/confidence", label: "Confidence Reliability", icon: Gauge, group: "AI Brain" },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-border bg-card/40">
      <div className="flex items-center gap-2 px-5 py-5 border-b border-border">
        <div className="rounded-md bg-primary/15 p-1.5">
          <Activity className="h-5 w-5 text-primary" />
        </div>
        <div className="leading-tight">
          <div className="font-semibold text-sm">BharatQuant</div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
            AI · NSE / BSE
          </div>
        </div>
      </div>
      <nav className="flex-1 px-2 py-3 space-y-1 overflow-y-auto">
        {NAV.map((item, idx) => {
          const Icon = item.icon;
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          const prev = NAV[idx - 1];
          const showHeader = item.group && (!prev || prev.group !== item.group);
          return (
            <React.Fragment key={item.href}>
              {showHeader && (
                <div className="px-3 pt-4 pb-1 text-[10px] uppercase tracking-wider text-muted-foreground/80">
                  {item.group}
                </div>
              )}
              <Link
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            </React.Fragment>
          );
        })}
      </nav>
      <div className="px-4 py-3 border-t border-border text-[10px] text-muted-foreground">
        <p>
          Educational only — not financial advice. Markets carry risk.
        </p>
      </div>
    </aside>
  );
}

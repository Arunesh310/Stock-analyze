"use client";
import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { fmtINR, fmtNumber } from "@/lib/utils";

type Plan = {
  capital: number;
  risk_per_trade_pct: number;
  max_loss: number;
  qty: number;
  notional: number;
  stoploss_pct: number;
  rr: number | null;
  portfolio_heat_pct: number;
};

export function RiskCalculator({
  defaults,
}: {
  defaults?: { entry?: number; stoploss?: number; target?: number };
}) {
  const [capital, setCapital] = React.useState(100000);
  const [riskPct, setRiskPct] = React.useState(1);
  const [entry, setEntry] = React.useState<number | undefined>(defaults?.entry);
  const [sl, setSl] = React.useState<number | undefined>(defaults?.stoploss);
  const [target, setTarget] = React.useState<number | undefined>(defaults?.target);
  const [plan, setPlan] = React.useState<Plan | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (defaults?.entry) setEntry(defaults.entry);
    if (defaults?.stoploss) setSl(defaults.stoploss);
    if (defaults?.target) setTarget(defaults.target);
  }, [defaults?.entry, defaults?.stoploss, defaults?.target]);

  const calc = async () => {
    if (!entry || !sl) return;
    setBusy(true);
    setErr(null);
    try {
      const res = (await api.risk({
        capital,
        entry,
        stoploss: sl,
        target,
        risk_per_trade_pct: riskPct,
      })) as Plan;
      setPlan(res);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Risk Manager</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <Field label="Capital (₹)">
            <Input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
            />
          </Field>
          <Field label="Risk per trade (%)">
            <Input
              type="number"
              step="0.1"
              value={riskPct}
              onChange={(e) => setRiskPct(Number(e.target.value))}
            />
          </Field>
          <Field label="Entry">
            <Input
              type="number"
              step="0.05"
              value={entry ?? ""}
              onChange={(e) => setEntry(Number(e.target.value))}
            />
          </Field>
          <Field label="Stoploss">
            <Input
              type="number"
              step="0.05"
              value={sl ?? ""}
              onChange={(e) => setSl(Number(e.target.value))}
            />
          </Field>
          <Field label="Target (optional)">
            <Input
              type="number"
              step="0.05"
              value={target ?? ""}
              onChange={(e) => setTarget(Number(e.target.value))}
            />
          </Field>
        </div>
        <Button onClick={calc} disabled={busy || !entry || !sl} className="w-full">
          {busy ? "Calculating…" : "Calculate position"}
        </Button>
        {err && <p className="text-xs text-bear">{err}</p>}
        {plan && (
          <div className="grid grid-cols-2 gap-3 pt-2 border-t border-border text-sm">
            <Stat label="Quantity" value={fmtNumber(plan.qty)} accent="text-primary" />
            <Stat label="Notional" value={fmtINR(plan.notional)} />
            <Stat label="Max loss" value={fmtINR(plan.max_loss)} accent="text-bear" />
            <Stat label="SL %" value={`${plan.stoploss_pct}%`} />
            <Stat label="R : R" value={plan.rr ? `1 : ${plan.rr}` : "—"} />
            <Stat label="Portfolio heat" value={`${plan.portfolio_heat_pct}%`} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="space-y-1">
      <span className="block text-[11px] uppercase text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}
function Stat({ label, value, accent }: { label: string; value: React.ReactNode; accent?: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={`font-mono text-sm font-semibold ${accent || ""}`}>{value}</div>
    </div>
  );
}

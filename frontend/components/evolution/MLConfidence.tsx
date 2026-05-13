"use client";
import * as React from "react";
import {
  Brain,
  Cpu,
  Loader2,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import type { MLModelStatus, MLRetrainResult } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/utils";

const FRIENDLY_FEATURES: Record<string, string> = {
  rule_confidence: "Rule-based confidence (the older heuristic score)",
  rule_score: "Rule-based raw score",
  rr: "Risk / reward ratio",
  sl_pct: "Stoploss distance (% of entry)",
  t1_pct: "Target-1 distance (% of entry)",
  atr_pct: "ATR / entry price (volatility scale)",
  news_sentiment: "News sentiment at signal",
  sector_strength: "Sector relative strength",
  breadth_ratio: "Market breadth (advancers / total)",
  rsi: "RSI",
  macd: "MACD",
  macd_signal: "MACD signal line",
  macd_hist: "MACD histogram",
  adx: "ADX (trend strength)",
  macd_bull: "MACD bullish (above signal)",
  ema_bull_stack: "EMA stack 20>50>200 (uptrend)",
  ema_bear_stack: "EMA stack 20<50<200 (downtrend)",
  volatility_pct: "Volatility (annualised %)",
  bb_position: "Bollinger position (0 lower → 1 upper)",
  pattern_count: "Number of detected patterns",
  regime__bullish_trend: "Regime is bullish trend",
  regime__bearish_trend: "Regime is bearish trend",
  regime__sideways: "Regime is sideways",
  regime__high_volatility: "Regime is high volatility",
  regime__risk_off: "Regime is risk-off",
  regime__risk_on: "Regime is risk-on",
  regime__unknown: "Regime not classified",
  mode__intraday: "Intraday mode",
  mode__swing: "Swing mode",
  mode__positional: "Positional mode",
  action__BUY: "Action is BUY",
  action__SELL: "Action is SELL",
};

function friendly(name: string): string {
  return FRIENDLY_FEATURES[name] || name.replace(/_/g, " ");
}

type Props = {
  refreshSignal?: number;
  onRetrained?: () => void;
};

export function MLConfidenceSection({ refreshSignal, onRetrained }: Props) {
  const [model, setModel] = React.useState<MLModelStatus | null>(null);
  const [retraining, setRetraining] = React.useState(false);
  const [retrainMessage, setRetrainMessage] = React.useState<string | null>(null);
  const [err, setErr] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try {
      const s = await api.ml.status();
      setModel(s);
      setErr(null);
    } catch (e: any) {
      setErr(String(e?.message || e));
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load, refreshSignal]);

  const retrain = async () => {
    setRetraining(true);
    setRetrainMessage(null);
    try {
      const res: MLRetrainResult = await api.ml.retrain();
      if (res.trained === false) {
        setRetrainMessage(`Could not train: ${res.message}`);
      } else if (res.trained === true) {
        setRetrainMessage(
          `Retrained on ${res.samples} trades · CV AUC ${(res.cv_auc ?? 0).toFixed(
            3
          )} · accuracy ${((res.cv_accuracy ?? 0) * 100).toFixed(1)}%`
        );
      }
      await load();
      onRetrained?.();
    } catch (e: any) {
      setRetrainMessage(`Retrain failed: ${String(e?.message || e)}`);
    } finally {
      setRetraining(false);
    }
  };

  if (model === null && err === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>ML Confidence Model</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2">
            <Cpu className="h-5 w-5 text-primary" />
            ML Confidence Model
            <Badge variant={model?.ready ? "bull" : "outline"} className="text-[10px]">
              {model?.ready ? "active" : "warming up"}
            </Badge>
          </span>
          <Button onClick={retrain} disabled={retraining} size="sm" variant="secondary">
            {retraining ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-1" />
            )}
            {retraining ? "Retraining…" : "Retrain now"}
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {err && (
          <div className="rounded-md border border-bear/40 bg-bear-soft px-3 py-2 text-sm text-bear">
            {err}
          </div>
        )}
        {retrainMessage && (
          <div
            className={cn(
              "rounded-md border px-3 py-2 text-sm",
              retrainMessage.startsWith("Could not") || retrainMessage.startsWith("Retrain failed")
                ? "border-amber-400/40 bg-amber-500/10 text-amber-300"
                : "border-bull/40 bg-bull/10 text-bull"
            )}
          >
            {retrainMessage}
          </div>
        )}

        {!model?.ready ? (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground leading-relaxed">
              The XGBoost classifier hasn&apos;t been trained yet — it needs at
              least{" "}
              <span className="font-semibold text-foreground">
                {model?.min_required_samples ?? 30}
              </span>{" "}
              validated trades to learn from.{" "}
              {model?.train_samples ? (
                <>You currently have <span className="font-semibold text-foreground">{model.train_samples}</span> in the database.</>
              ) : (
                <>You currently have <span className="font-semibold text-foreground">0</span>.</>
              )}
            </p>
            <p className="text-xs text-muted-foreground">
              Until then signals fall back to the deterministic rule-based
              confidence — which is still adaptive (it self-calibrates per
              confidence bucket and adjusts setup weights from outcomes).
            </p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <Metric
                label="CV AUC"
                value={
                  model.cv_auc !== null && model.cv_auc !== undefined
                    ? model.cv_auc.toFixed(3)
                    : "—"
                }
                hint={
                  model.cv_auc !== null && model.cv_auc !== undefined
                    ? model.cv_auc > 0.6
                      ? "good"
                      : model.cv_auc > 0.55
                      ? "weak edge"
                      : "near random"
                    : ""
                }
                tone={
                  model.cv_auc !== null && model.cv_auc !== undefined
                    ? model.cv_auc > 0.6
                      ? "bull"
                      : model.cv_auc > 0.55
                      ? "neutral"
                      : "bear"
                    : "neutral"
                }
              />
              <Metric
                label="CV accuracy"
                value={
                  model.cv_accuracy !== null && model.cv_accuracy !== undefined
                    ? `${(model.cv_accuracy * 100).toFixed(1)}%`
                    : "—"
                }
                hint={`${model.cv_folds} folds`}
              />
              <Metric
                label="Trained on"
                value={`${model.train_samples}`}
                hint="validated trades"
              />
              <Metric
                label="Blend weight"
                value={`${(model.ml_blend_weight * 100).toFixed(0)}%`}
                hint="ML weight in final confidence"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              <div className="space-y-1">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1">
                  <Sparkles className="h-3.5 w-3.5 text-primary" />
                  What the model is leaning on
                </div>
                <ul className="space-y-1">
                  {model.top_features.slice(0, 8).map(([name, importance]) => (
                    <li
                      key={name}
                      className="flex items-center justify-between gap-2 text-sm border-b border-border/40 py-1 last:border-0"
                    >
                      <span className="truncate">{friendly(name)}</span>
                      <ImportanceBar
                        value={importance}
                        max={model.top_features[0]?.[1] || 1}
                      />
                    </li>
                  ))}
                </ul>
              </div>
              <div className="space-y-2">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1">
                  <Brain className="h-3.5 w-3.5 text-primary" />
                  What this means for signals
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Every actionable BUY / SELL signal is now scored by two
                  brains: the deterministic rule engine and this XGBoost model
                  trained on past outcomes. The final confidence is a
                  {" "}
                  <span className="font-semibold text-foreground">
                    {(model.ml_blend_weight * 100).toFixed(0)}% ML +{" "}
                    {(100 - model.ml_blend_weight * 100).toFixed(0)}% rule
                  </span>{" "}
                  blend.
                </p>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Out-of-sample (walk-forward) AUC is the honest number — it
                  measures performance only on data the model hadn&apos;t seen
                  during training. An AUC above 0.55 is a real edge for noisy
                  daily-bar equity data.
                </p>
                {model.win_rate_in_sample !== null && (
                  <p className="text-[10px] text-muted-foreground">
                    Win rate in training set:{" "}
                    {(model.win_rate_in_sample * 100).toFixed(1)}%
                  </p>
                )}
                {model.trained_at && (
                  <p className="text-[10px] text-muted-foreground">
                    Last retrained{" "}
                    {new Date(model.trained_at).toLocaleString("en-IN", {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </p>
                )}
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "bull" | "bear" | "neutral";
}) {
  const toneClass =
    tone === "bull" ? "text-bull" : tone === "bear" ? "text-bear" : "";
  return (
    <div className="rounded-md border border-border bg-background/40 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className={cn("text-xl font-semibold tabular-nums", toneClass)}>
        {value}
      </div>
      {hint && (
        <div className="text-[10px] text-muted-foreground capitalize">{hint}</div>
      )}
    </div>
  );
}

function ImportanceBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="w-24 h-1.5 rounded-full bg-border overflow-hidden shrink-0">
      <div
        className="h-full bg-primary"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

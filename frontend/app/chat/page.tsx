"use client";
import * as React from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

type Msg = {
  id: number;
  role: "user" | "ai";
  content: string;
  meta?: { used_news_count?: number; used_memories?: number; used_symbols?: string[] };
};

const SUGGESTIONS = [
  "Which Indian stocks benefit from rising crude oil?",
  "Why might Bank Nifty fall this week?",
  "Find bullish railway stocks today.",
  "Which sectors look strongest right now?",
  "Should I avoid IT if USD weakens?",
  "Which defence stocks have the best AI signal?",
];

export default function ChatPage() {
  const [msgs, setMsgs] = React.useState<Msg[]>([]);
  const [input, setInput] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [symbols, setSymbols] = React.useState("");
  const endRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs.length, busy]);

  const ask = async (q?: string) => {
    const question = (q ?? input).trim();
    if (!question) return;
    const id = Date.now();
    setMsgs((m) => [...m, { id, role: "user", content: question }]);
    setInput("");
    setBusy(true);
    try {
      const syms = symbols
        .split(",")
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean);
      const r = await api.chat(question, syms, true);
      setMsgs((m) => [
        ...m,
        {
          id: id + 1,
          role: "ai",
          content: r.answer,
          meta: {
            used_news_count: r.used_news_count,
            used_memories: r.used_memories,
            used_symbols: r.used_symbols,
          },
        },
      ]);
    } catch (e: any) {
      setMsgs((m) => [
        ...m,
        { id: id + 1, role: "ai", content: `Error: ${e?.message || e}` },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto w-full">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">AI Assistant</h1>
        <p className="text-sm text-muted-foreground">
          Grounded in live quotes, news sentiment & historical event memory (ChromaDB).
        </p>
      </div>

      {msgs.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Try a question</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => ask(s)}
                className="rounded-full border border-border bg-secondary/40 px-3 py-1.5 text-xs hover:bg-secondary"
              >
                {s}
              </button>
            ))}
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {msgs.map((m) => (
          <div
            key={m.id}
            className={`rounded-md border p-3 ${
              m.role === "user"
                ? "border-primary/30 bg-primary/10"
                : "border-border bg-card"
            }`}
          >
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
              {m.role === "user" ? "You" : "AI"}
            </div>
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
              {m.content}
            </pre>
            {m.meta && (
              <div className="mt-2 flex flex-wrap gap-2 text-[10px]">
                {m.meta.used_symbols && m.meta.used_symbols.length > 0 && (
                  <Badge variant="outline">syms: {m.meta.used_symbols.join(", ")}</Badge>
                )}
                <Badge variant="outline">news ctx: {m.meta.used_news_count}</Badge>
                <Badge variant="outline">memories: {m.meta.used_memories}</Badge>
              </div>
            )}
          </div>
        ))}
        {busy && (
          <div className="rounded-md border border-border bg-card p-3 animate-pulse-soft">
            <div className="text-[10px] uppercase text-muted-foreground mb-1">AI</div>
            <div className="text-sm text-muted-foreground">Thinking…</div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="sticky bottom-2">
        <Card>
          <CardContent className="p-3 space-y-2">
            <Input
              placeholder="Ground in symbols (comma separated, e.g. RELIANCE.NS, HAL.NS)"
              value={symbols}
              onChange={(e) => setSymbols(e.target.value)}
              className="text-xs"
            />
            <form
              onSubmit={(e) => {
                e.preventDefault();
                ask();
              }}
              className="flex gap-2"
            >
              <Input
                placeholder="Ask anything about Indian markets…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={busy}
              />
              <Button type="submit" disabled={busy || !input.trim()}>
                Send
              </Button>
            </form>
            <p className="text-[10px] text-muted-foreground">
              Educational only — not financial advice. Powered by your local Ollama
              install. If the LLM is down the assistant gracefully falls back.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

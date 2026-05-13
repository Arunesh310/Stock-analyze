"use client";
import * as React from "react";
import * as ToastPrimitive from "@radix-ui/react-toast";
import { cn } from "@/lib/utils";

type Toast = {
  id: number;
  title: string;
  description?: string;
  variant?: "default" | "success" | "warn" | "destructive";
};

type ToastContextValue = {
  push: (t: Omit<Toast, "id">) => void;
};

const Ctx = React.createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = React.useContext(Ctx);
  if (!ctx) {
    return { push: () => undefined };
  }
  return ctx;
}

let idSeq = 0;

export function Toaster() {
  const [toasts, setToasts] = React.useState<Toast[]>([]);

  const push = React.useCallback((t: Omit<Toast, "id">) => {
    setToasts((cur) => [...cur, { ...t, id: ++idSeq }]);
  }, []);

  React.useEffect(() => {
    (window as any).__push_toast = push;
  }, [push]);

  return (
    <Ctx.Provider value={{ push }}>
      <ToastPrimitive.Provider duration={4500}>
        {toasts.map((t) => (
          <ToastPrimitive.Root
            key={t.id}
            onOpenChange={(open) => {
              if (!open) setToasts((cur) => cur.filter((x) => x.id !== t.id));
            }}
            className={cn(
              "group pointer-events-auto relative flex w-full items-start justify-between space-x-2 overflow-hidden rounded-md border p-3 pr-6 shadow-lg",
              t.variant === "destructive" && "border-bear/40 bg-bear-soft text-bear",
              t.variant === "warn" && "border-neutral/40 bg-neutral/10 text-neutral",
              t.variant === "success" && "border-bull/40 bg-bull-soft text-bull",
              (!t.variant || t.variant === "default") && "bg-card border-border"
            )}
          >
            <div className="flex-1 space-y-1">
              <ToastPrimitive.Title className="text-sm font-semibold">
                {t.title}
              </ToastPrimitive.Title>
              {t.description && (
                <ToastPrimitive.Description className="text-xs opacity-90">
                  {t.description}
                </ToastPrimitive.Description>
              )}
            </div>
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-[60] flex max-h-screen w-96 flex-col gap-2" />
      </ToastPrimitive.Provider>
    </Ctx.Provider>
  );
}

export function notify(t: Omit<Toast, "id">) {
  if (typeof window !== "undefined" && (window as any).__push_toast) {
    (window as any).__push_toast(t);
  }
}

import { Bike, Clock3 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Day } from "./api";
import { BottomNav, type Tab } from "./components/BottomNav";
import { fmtTime } from "./lib/format";
import { CompareScreen } from "./screens/CompareScreen";
import { NextStopScreen } from "./screens/NextStopScreen";
import { RouteScreen } from "./screens/RouteScreen";
import { TodayScreen } from "./screens/TodayScreen";

type Toast = { text: string; kind: "good" | "bad" | "info" };

export function RiderApp() {
  const [day, setDay] = useState<Day | null>(null);
  const [tab, setTab] = useState<Tab>("today");
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lastEvents = useRef(0);

  const show = useCallback((t: Toast) => {
    setToast(t);
    window.setTimeout(() => setToast((cur) => (cur === t ? null : cur)), 4500);
  }, []);

  const accept = useCallback(
    (d: Day, announceReplies = false) => {
      if (announceReplies && lastEvents.current && d.events.length > lastEvents.current) {
        const fresh = d.events.slice(lastEvents.current - d.events.length);
        const reply = fresh.find((e) => e.kind === "reply");
        if (reply) show({ text: `${reply.text}. Route updated (plan v${d.plan?.version ?? 0}).`, kind: "info" });
      }
      lastEvents.current = d.events.length;
      setDay(d);
    },
    [show],
  );

  useEffect(() => {
    api.day().then((d) => accept(d)).catch((e: Error) => setError(e.message));
  }, [accept]);

  // Pick up customer replies sent from another phone or tab.
  useEffect(() => {
    if (tab === "compare") return;
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") api.day().then((d) => accept(d, true)).catch(() => undefined);
    }, 4000);
    return () => window.clearInterval(id);
  }, [tab, accept]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      show({ text: (e as Error).message, kind: "bad" });
    } finally {
      setBusy(false);
    }
  };

  const plan = () =>
    run(async () => {
      const d = await api.plan();
      accept(d);
      show({ text: `Plan v${d.plan?.version} ready: finish around ${fmtTime(d.plan?.finish_min)}`, kind: "good" });
      setTab("route");
    });

  const reset = () =>
    run(async () => {
      const d = await api.reset();
      accept(d);
      setSelected(null);
      setTab("today");
      show({ text: "Demo day reset: 16 parcels, nothing planned yet", kind: "info" });
    });

  const outcome = (stopId: string, status: "delivered" | "failed", reason?: string) =>
    run(async () => {
      const r = await api.outcome(stopId, status, reason);
      accept(r.day);
      setSelected(null);
      show({ text: r.message, kind: status === "delivered" ? "good" : "bad" });
    });

  const openStop = (id: string) => {
    setSelected(id);
    setTab("next");
  };

  return (
    <div className="mx-auto min-h-full max-w-md pb-28">
      <header
        className="sticky top-0 z-[1000] flex items-center justify-between gap-3 border-b border-line bg-canvas/95 px-4 py-3 backdrop-blur"
        style={{ paddingTop: "max(0.75rem, env(safe-area-inset-top, 0px))" }}
      >
        <div className="flex items-center gap-2">
          <img src="/icon.svg" alt="" className="h-8 w-8" />
          <div className="leading-tight">
            <p className="font-bold">RouteSense</p>
            {day && (
              <p className="flex items-center gap-1 text-xs text-muted">
                <Bike size={13} /> {day.rider.name} · Klang Valley
              </p>
            )}
          </div>
        </div>
        {day && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-sm font-semibold shadow-sm" title="Demo clock: moves forward as you deliver">
            <Clock3 size={15} className="text-brand" /> {day.clock_label}
          </span>
        )}
      </header>

      <main className="px-4 pt-4">
        {error && <p className="rounded-2xl bg-bad-soft px-4 py-3 text-bad">Cannot reach the RouteSense server: {error}</p>}
        {day && tab === "today" && <TodayScreen day={day} busy={busy} onPlan={plan} onReset={reset} />}
        {day && tab === "route" && <RouteScreen day={day} onOpenStop={openStop} />}
        {day && tab === "next" && <NextStopScreen day={day} stopId={selected} busy={busy} onOutcome={outcome} />}
        {tab === "compare" && <CompareScreen />}
      </main>

      {toast && (
        <div className="fixed inset-x-0 bottom-20 z-[1100] flex justify-center px-4" role="status">
          <p
            className={`rise max-w-md rounded-2xl px-4 py-3 text-sm font-medium text-white shadow-lg ${
              toast.kind === "good" ? "bg-ok" : toast.kind === "bad" ? "bg-bad" : "bg-ink"
            }`}
          >
            {toast.text}
          </p>
        </div>
      )}

      <BottomNav
        tab={tab}
        onChange={(t) => {
          if (t === "next") setSelected(null);
          setTab(t);
        }}
      />
    </div>
  );
}

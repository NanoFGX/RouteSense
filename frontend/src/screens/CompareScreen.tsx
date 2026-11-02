import { CheckCircle2, Loader2, Play, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type CompareResult, type Metrics, type ModelInfo, type SimulateResult } from "../api";
import { fmtTime } from "../lib/format";

const ORDER = ["nearest", "time_optimal", "routesense", "routesense_replies"] as const;
const TABLE = ["time_optimal", "routesense_replies"] as const;
const SHORT: Record<string, string> = {
  nearest: "Rider's usual way",
  time_optimal: "Normal route app",
  routesense: "RouteSense, no replies",
  routesense_replies: "RouteSense + replies",
};
const COLOR: Record<string, string> = {
  nearest: "#b9b0b4",
  time_optimal: "#6a5f65",
  routesense: "#c48aa0",
  routesense_replies: "#8a1538",
};

function Bars({ title, data, unit = "", better }: { title: string; data: Record<string, number>; unit?: string; better: "high" | "low" }) {
  const max = Math.max(...Object.values(data), 1);
  const best = better === "high" ? Math.max(...Object.values(data)) : Math.min(...Object.values(data));
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-semibold">{title}</p>
      {ORDER.map((k) => (
        <div key={k} className="flex items-center gap-2 text-sm">
          <span className="w-36 shrink-0 text-muted">{SHORT[k]}</span>
          <div className="h-6 flex-1 overflow-hidden rounded-md bg-canvas">
            <div className="h-full rounded-md" style={{ width: `${(data[k] / max) * 100}%`, background: COLOR[k] }} />
          </div>
          <span className={`w-12 text-right tabular-nums ${data[k] === best ? "font-bold" : ""}`}>
            {data[k].toFixed(1)}
            {unit}
          </span>
        </div>
      ))}
    </div>
  );
}

function SimDay() {
  const [strategy, setStrategy] = useState<"time_optimal" | "routesense_replies">("routesense_replies");
  const [result, setResult] = useState<SimulateResult | null>(null);
  const [shown, setShown] = useState(0);
  const [loading, setLoading] = useState(false);
  const timer = useRef<number | null>(null);

  const run = async () => {
    setLoading(true);
    setShown(0);
    if (timer.current) window.clearInterval(timer.current);
    try {
      const r = await api.simulate(strategy, 3);
      setResult(r);
      timer.current = window.setInterval(() => {
        setShown((n) => {
          if (n >= r.events.length) {
            if (timer.current) window.clearInterval(timer.current);
            return n;
          }
          return n + 1;
        });
      }, 350);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => () => {
    if (timer.current) window.clearInterval(timer.current);
  }, []);

  return (
    <section className="rounded-2xl border border-line bg-white px-4 py-4">
      <h2 className="font-semibold">Watch one simulated day</h2>
      <p className="text-sm text-muted">The same day and the same customers, played out minute by minute.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {(["time_optimal", "routesense_replies"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStrategy(s)}
            className={`rounded-full border px-3 py-1.5 text-sm font-medium ${strategy === s ? "border-brand bg-brand text-white" : "border-line"}`}
          >
            {SHORT[s]}
          </button>
        ))}
        <button onClick={run} disabled={loading} className="inline-flex items-center gap-1.5 rounded-full bg-ink px-3 py-1.5 text-sm font-semibold text-white">
          {loading ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />} Play
        </button>
      </div>
      {result && (
        <>
          <ul className="mt-3 flex flex-col gap-1.5 text-sm">
            {result.events.slice(0, shown).map((e, i) => (
              <li key={i} className="rise flex items-start gap-2">
                <span className="w-16 shrink-0 tabular-nums text-muted">{fmtTime(e.t)}</span>
                {e.event === "delivered" ? (
                  <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-ok" />
                ) : (
                  <XCircle size={16} className="mt-0.5 shrink-0 text-bad" />
                )}
                <span>
                  {e.customer}
                  {e.event === "failed" ? `: ${e.reason?.toLowerCase()}${e.retry ? ", retry later" : ", back tomorrow"}` : e.attempt > 1 ? " (second try)" : ""}
                </span>
              </li>
            ))}
          </ul>
          {shown >= result.events.length && (
            <p className="rise mt-3 rounded-xl bg-canvas px-3 py-2 text-sm">
              <b>{result.delivered}</b> of {result.parcels} delivered, <b>{result.failed_attempts}</b> failed trips,{" "}
              <b>{result.carried_over}</b> back tomorrow{result.replies ? `, ${result.replies} customers replied` : ""}.
            </p>
          )}
        </>
      )}
    </section>
  );
}

function ModelPanel() {
  const [m, setM] = useState<ModelInfo | null>(null);
  useEffect(() => {
    api.model().then(setM).catch(() => setM(null));
  }, []);
  if (!m) return null;
  const lr = m.metrics.logistic_regression;
  const xg = m.metrics.xgboost;
  return (
    <section className="rounded-2xl border border-line bg-white px-4 py-4 text-sm">
      <h2 className="font-semibold">Under the hood: the failure-risk model</h2>
      <p className="mt-1 text-muted">
        Trained on {m.metrics.train_rows.toLocaleString()} synthetic attempts, tested on {m.metrics.test_rows.toLocaleString()} from{" "}
        {m.metrics.test_routes} unseen routes.
      </p>
      <table className="mt-3 w-full text-left tabular-nums">
        <thead className="text-xs uppercase tracking-wider text-muted">
          <tr>
            <th className="py-1 font-semibold">Measure</th>
            <th className="py-1 font-semibold">Logistic reg.</th>
            <th className="py-1 font-semibold">XGBoost</th>
          </tr>
        </thead>
        <tbody>
          {[
            ["PR-AUC", "pr_auc"],
            ["ROC-AUC", "roc_auc"],
            ["Brier score (lower is better)", "brier"],
            ["Recall on failures (high band)", "recall_high_band"],
          ].map(([label, key]) => (
            <tr key={key} className="border-t border-line">
              <td className="py-1.5">{label}</td>
              <td className="py-1.5">{lr[key]}</td>
              <td className="py-1.5">{xg[key]}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 font-medium">Synthetic data checks</p>
      <ul className="mt-1 flex flex-wrap gap-2">
        {Object.entries(m.data_checks).map(([k, v]) => (
          <li key={k} className={`rounded-full px-2.5 py-1 text-xs font-semibold ${v.passed ? "bg-ok-soft text-ok" : "bg-bad-soft text-bad"}`}>
            {k}: {v.passed ? "passed" : "failed"}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-muted">
        {m.logged_outcomes} {m.logged_outcomes === 1 ? "outcome" : "outcomes"} logged from the app so far; the retraining
        script runs once there are {m.retrain_threshold}.
      </p>
    </section>
  );
}

export function CompareScreen() {
  const [rate, setRate] = useState(0.6);
  const [res, setRes] = useState<CompareResult | null>(null);

  useEffect(() => {
    let alive = true;
    let handle: number | undefined;
    const poll = async () => {
      try {
        const r = await api.compare(rate);
        if (!alive) return;
        setRes(r);
        if (r.status === "computing") handle = window.setTimeout(poll, 2000);
      } catch {
        if (alive) handle = window.setTimeout(poll, 4000);
      }
    };
    setRes(null);
    poll();
    return () => {
      alive = false;
      if (handle) window.clearTimeout(handle);
    };
  }, [rate]);

  const s = res?.status === "ready" ? res.strategies! : null;
  const pick = (key: keyof Metrics) => Object.fromEntries(ORDER.map((k) => [k, s ? (s[k].mean[key] as number) : 0]));
  const app = s?.time_optimal.mean;
  const rs = s?.routesense_replies.mean;

  return (
    <div className="flex flex-col gap-4">
      <section>
        <h1 className="text-xl font-bold">RouteSense against a normal route app</h1>
        <p className="mt-1 text-sm text-muted">
          The same 16 parcels, the same traffic and the same customers, replayed {res?.replays ?? 8} times per strategy.
          What happens at each door comes from hidden customer profiles that the planner never sees.
        </p>
      </section>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted">Customers who reply:</span>
        {[0.3, 0.6, 0.9].map((r) => (
          <button
            key={r}
            onClick={() => setRate(r)}
            className={`rounded-full border px-3 py-1 font-medium ${rate === r ? "border-brand bg-brand text-white" : "border-line bg-white"}`}
          >
            {Math.round(r * 100)}%
          </button>
        ))}
      </div>

      {!s && (
        <div className="flex items-center gap-3 rounded-2xl border border-line bg-white px-4 py-6 text-sm">
          <Loader2 className="animate-spin text-brand" size={20} /> Simulating 32 delivery days. About 30 seconds the first time.
        </div>
      )}

      {s && app && rs && (
        <>
          <section className="grid grid-cols-3 gap-2">
            {[
              { v: rs.delivered - app.delivered, label: "more parcels delivered today" },
              { v: app.failed_attempts - rs.failed_attempts, label: "fewer failed trips" },
              { v: app.carried_over - rs.carried_over, label: "fewer parcels left for tomorrow" },
            ].map((c) => (
              <div key={c.label} className="rounded-2xl bg-brand px-3 py-3 text-white">
                <p className="text-2xl font-bold tabular-nums">{c.v.toFixed(1)}</p>
                <p className="text-xs text-white/85">{c.label}</p>
              </div>
            ))}
          </section>

          <section className="flex flex-col gap-5 rounded-2xl border border-line bg-white px-4 py-4">
            <Bars title="Delivered today (of 16)" data={pick("delivered")} better="high" />
            <Bars title="Delivered on the first try" data={pick("delivered_first_try")} better="high" />
            <Bars title="Failed trips" data={pick("failed_attempts")} better="low" />
            <Bars title="Unpaid minutes on failed trips" data={pick("unpaid_min")} better="low" />
          </section>

          <section className="overflow-x-auto rounded-2xl border border-line bg-white">
            <table className="w-full text-left text-sm tabular-nums">
              <thead className="bg-canvas text-xs uppercase tracking-wider text-muted">
                <tr>
                  <th className="px-3 py-2 font-semibold">Average day</th>
                  {TABLE.map((k) => (
                    <th key={k} className="px-3 py-2 font-semibold">
                      {SHORT[k]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ["Kilometres", "km", (v: number) => v.toFixed(1)],
                    ["Finish time", "finish_min", (v: number) => fmtTime(v)],
                    ["Riding and door time", "active_min", (v: number) => `${Math.round(v)} min`],
                    ["Parcels per working hour", "parcels_per_active_hour", (v: number) => v.toFixed(2)],
                    ["Free time between waves", "free_min", (v: number) => `${Math.round(v)} min`],
                  ] as [string, keyof Metrics, (v: number) => string][]
                ).map(([label, key, f]) => (
                  <tr key={key} className="border-t border-line">
                    <td className="px-3 py-2">{label}</td>
                    {TABLE.map((k) => (
                      <td key={k} className="px-3 py-2">
                        {f(s[k].mean[key] as number)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <p className="text-xs text-muted">
            RouteSense trades a later finish for fewer wasted trips: customers who are out in the day get an evening slot,
            and the time between waves is the rider's own.
          </p>
        </>
      )}

      <SimDay />
      <ModelPanel />
    </div>
  );
}

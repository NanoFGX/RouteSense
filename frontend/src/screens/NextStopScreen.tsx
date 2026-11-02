import { ArrowDown, ArrowUp, CheckCircle2, MessageCircle, Navigation, PackageCheck, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Day, type Stop } from "../api";
import { bandColor, RiskChip } from "../components/RiskChip";
import { fmtDuration, fmtTime, googleMapsLink, isOpen, propertyLabel, replySummary, wazeLink, whatsappLink } from "../lib/format";

const FAIL_REASONS = ["Customer not home", "COD cash not ready", "Stopped at guardhouse", "Wrong or unclear address", "No answer"];

function RiskCurve({ stop }: { stop: Stop }) {
  const [points, setPoints] = useState<{ minute: number; risk: number }[]>([]);
  useEffect(() => {
    api.riskCurve(stop.id).then((r) => setPoints(r.points)).catch(() => setPoints([]));
  }, [stop.id, stop.reply, stop.failed_attempts_today]);
  if (points.length === 0) return null;

  const W = 320, H = 96, pad = 4;
  const lo = points[0].minute, hi = points[points.length - 1].minute;
  const x = (m: number) => pad + ((m - lo) / (hi - lo)) * (W - 2 * pad);
  const maxR = Math.max(0.5, ...points.map((p) => p.risk));
  const y = (r: number) => H - 18 - (r / maxR) * (H - 30);
  const bw = (W - 2 * pad) / points.length - 2;
  const planned = stop.planned?.start_min;
  const best = points.reduce((a, b) => (b.risk < a.risk ? b : a));
  const band = (r: number) => (r < 0.15 ? bandColor.low : r < 0.35 ? bandColor.medium : bandColor.high);

  return (
    <figure className="flex flex-col gap-1">
      <figcaption className="text-sm font-semibold">Risk through the day</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`Lowest risk around ${fmtTime(best.minute)}`}>
        {points.map((p) => (
          <rect
            key={p.minute}
            x={x(p.minute) - bw / 2}
            y={y(p.risk)}
            width={bw}
            height={H - 18 - y(p.risk)}
            rx={2}
            fill={band(p.risk)}
            opacity={0.75}
          />
        ))}
        {planned !== undefined && (
          <line x1={x(planned)} x2={x(planned)} y1={6} y2={H - 18} stroke="#1f1a1d" strokeWidth={1.5} strokeDasharray="3 3" />
        )}
        {[540, 720, 900, 1080, 1260].map((m) => (
          <text key={m} x={x(m)} y={H - 4} fontSize={10} textAnchor={m === 540 ? "start" : m === 1260 ? "end" : "middle"} fill="#6a5f65">
            {fmtTime(m).replace(":00", "")}
          </text>
        ))}
      </svg>
      <p className="text-xs text-muted">
        Dashed line: planned time. Lowest risk around {fmtTime(best.minute)} ({Math.round(best.risk * 100)}%).
      </p>
    </figure>
  );
}

export function NextStopScreen({
  day,
  stopId,
  busy,
  onOutcome,
}: {
  day: Day;
  stopId: string | null;
  busy: boolean;
  onOutcome: (stopId: string, status: "delivered" | "failed", reason?: string) => void;
}) {
  const [failing, setFailing] = useState(false);
  const stop = day.stops.find((s) => s.id === (stopId ?? day.next_stop_id));

  useEffect(() => setFailing(false), [stop?.id]);

  if (!stop) {
    const c = day.counts;
    return (
      <div className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-white p-6 text-center">
        <PackageCheck size={40} className="text-ok" />
        <p className="text-lg font-semibold">{day.plan ? "No stop selected" : "Day complete"}</p>
        <p className="text-sm text-muted">
          {c.delivered} delivered · {c.carried} for tomorrow · {c.self_collect} self-collect
        </p>
      </div>
    );
  }

  const p = stop.planned;
  const reply = replySummary(stop.reply);
  const isNext = stop.id === day.next_stop_id;
  const raises = stop.reasons.filter((r) => r.effect === "raises");
  const lowers = stop.reasons.filter((r) => r.effect === "lowers");

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-2xl border border-line bg-white px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-brand">{isNext ? "Next stop" : "Stop"}</p>
        <div className="mt-1 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-xl font-bold">{stop.customer}</h2>
            <p className="text-sm text-muted">{stop.address}</p>
            <p className="text-sm text-muted">
              {stop.area} · {propertyLabel[stop.property_type]}
              {stop.guardhouse ? " · guardhouse" : ""}
            </p>
          </div>
          {stop.cod && (
            <span className="shrink-0 rounded-xl bg-warn-soft px-2.5 py-1.5 text-center text-xs font-semibold text-warn">
              COD
              <br />
              RM{stop.cod_amount.toFixed(0)}
            </span>
          )}
        </div>

        {isOpen(stop) && p && (
          <div className="mt-4 flex items-end justify-between gap-3">
            <div>
              <p className="text-xs text-muted">Arrive around</p>
              <p className="text-4xl font-bold tabular-nums tracking-tight">{fmtTime(p.start_min)}</p>
              <p className="text-sm text-muted">
                Window {fmtTime(stop.tw_start)} to {fmtTime(stop.tw_end)} · about {stop.service_min} min at the door
              </p>
            </div>
            <RiskChip band={stop.risk_band} risk={stop.risk} />
          </div>
        )}
        {!isOpen(stop) && <p className="mt-3 text-sm font-semibold">This parcel is {stop.status.replace("_", " ")}.</p>}
        {reply && <p className="mt-3 rounded-xl bg-brand-soft px-3 py-2 text-sm font-medium text-brand">{reply}</p>}
        {p && p.wait_min > 20 && (
          <p className="mt-2 text-sm text-muted">You have {fmtDuration(p.wait_min)} free before this stop.</p>
        )}
      </section>

      {isOpen(stop) && (
        <section className="rounded-2xl border border-line bg-white px-4 py-4">
          <h3 className="text-sm font-semibold">Why this risk</h3>
          <ul className="mt-2 flex flex-col gap-1.5 text-sm">
            {[...raises, ...lowers].map((r, i) => (
              <li key={i} className="flex items-start gap-2">
                {r.effect === "raises" ? (
                  <ArrowUp size={16} className="mt-0.5 shrink-0 text-bad" />
                ) : (
                  <ArrowDown size={16} className="mt-0.5 shrink-0 text-ok" />
                )}
                <span>{r.text}</span>
              </li>
            ))}
          </ul>
          <div className="mt-4">
            <RiskCurve stop={stop} />
          </div>
        </section>
      )}

      {isOpen(stop) && (
        <section className="grid grid-cols-3 gap-2">
          <a href={wazeLink(stop)} target="_blank" rel="noreferrer" className="flex flex-col items-center gap-1 rounded-2xl border border-line bg-white py-3 text-sm font-medium">
            <Navigation size={20} /> Waze
          </a>
          <a
            href={googleMapsLink(stop, day.rider.vehicle)}
            target="_blank"
            rel="noreferrer"
            className="flex flex-col items-center gap-1 rounded-2xl border border-line bg-white py-3 text-sm font-medium"
          >
            <Navigation size={20} /> Google Maps
          </a>
          <a href={whatsappLink(day, stop)} target="_blank" rel="noreferrer" className="flex flex-col items-center gap-1 rounded-2xl border border-line bg-white py-3 text-sm font-medium">
            <MessageCircle size={20} /> WhatsApp
          </a>
        </section>
      )}

      {isOpen(stop) && !failing && (
        <section className="grid grid-cols-2 gap-3">
          <button
            disabled={busy}
            onClick={() => onOutcome(stop.id, "delivered")}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-ok py-4 font-semibold text-white disabled:opacity-60"
          >
            <CheckCircle2 size={20} /> Delivered
          </button>
          <button
            disabled={busy}
            onClick={() => setFailing(true)}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-bad py-4 font-semibold text-white disabled:opacity-60"
          >
            <XCircle size={20} /> Failed
          </button>
        </section>
      )}

      {isOpen(stop) && failing && (
        <section className="rounded-2xl border border-line bg-white px-4 py-4">
          <h3 className="font-semibold">What happened?</h3>
          <div className="mt-3 flex flex-col gap-2">
            {FAIL_REASONS.map((r) => (
              <button
                key={r}
                disabled={busy}
                onClick={() => onOutcome(stop.id, "failed", r)}
                className="rounded-xl border border-line px-3 py-2.5 text-left text-sm font-medium hover:bg-canvas disabled:opacity-60"
              >
                {r}
              </button>
            ))}
            <button onClick={() => setFailing(false)} className="mt-1 text-sm text-muted">
              Cancel
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

import { ArrowRightLeft, Clock, Coffee } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Day, type PreviewPlan } from "../api";
import { bandColor, RiskChip } from "../components/RiskChip";
import { StopMap, type MapPoint } from "../components/StopMap";
import { fmtDuration, fmtTime, isOpen, replySummary } from "../lib/format";

export function RouteScreen({ day, onOpenStop }: { day: Day; onOpenStop: (id: string) => void }) {
  const [showNormal, setShowNormal] = useState(false);
  const [normal, setNormal] = useState<PreviewPlan | null>(null);
  const planned = day.stops.filter((s) => s.planned && isOpen(s)).sort((a, b) => a.planned!.start_min - b.planned!.start_min);
  const done = day.stops.filter((s) => s.status === "delivered");

  useEffect(() => {
    if (!showNormal) return;
    api.preview("time_optimal").then(setNormal).catch(() => setNormal(null));
  }, [showNormal, day.plan?.version]);

  if (!day.plan || planned.length === 0) {
    return (
      <div className="rounded-2xl border border-line bg-white p-6 text-center">
        <p className="font-semibold">No route yet</p>
        <p className="mt-1 text-sm text-muted">Go to Today and tap Plan my day.</p>
      </div>
    );
  }

  const byId = new Map(day.stops.map((s) => [s.id, s]));
  const points: MapPoint[] = [
    ...planned.map((s, i) => ({
      id: s.id,
      lat: s.lat,
      lng: s.lng,
      label: String(i + 1),
      color: bandColor[s.risk_band ?? "low"],
      title: `${i + 1}. ${s.customer}, ${fmtTime(s.planned!.start_min)}`,
      ring: s.status === "retry",
    })),
    ...done.map((s) => ({ id: s.id, lat: s.lat, lng: s.lng, label: "✓", color: "#9b9196", title: `${s.customer}, delivered` })),
  ];
  const line: [number, number][] = [[day.position.lat, day.position.lng], ...planned.map((s) => [s.lat, s.lng] as [number, number])];
  const normalLine: [number, number][] | undefined = normal
    ? [[day.position.lat, day.position.lng], ...normal.stops.map((p) => [byId.get(p.stop_id)!.lat, byId.get(p.stop_id)!.lng] as [number, number])]
    : undefined;

  return (
    <div className="flex flex-col gap-4">
      <StopMap points={points} hub={day.hub} line={line} altLine={showNormal ? normalLine : undefined} onSelect={onOpenStop} />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted">
          Plan v{day.plan.version} · {day.plan.total_km.toFixed(1)} km · finish {fmtTime(day.plan.finish_min)}
        </p>
        <button
          onClick={() => setShowNormal((v) => !v)}
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium ${
            showNormal ? "border-ink bg-ink text-white" : "border-line bg-white"
          }`}
        >
          <ArrowRightLeft size={15} /> {showNormal ? "Hide normal app" : "Compare with a normal app"}
        </button>
      </div>

      {showNormal && normal && (
        <div className="rounded-2xl border border-line bg-white px-4 py-3 text-sm">
          <p className="font-semibold">A normal route app (dashed line)</p>
          <p className="text-muted">
            Shortest time, same stops: finishes {fmtTime(normal.finish_min)}, {normal.total_km.toFixed(1)} km, but RouteSense's model
            expects <b className="text-bad">{normal.expected_failures.toFixed(1)}</b> failed attempts against{" "}
            <b className="text-ok">{day.plan.expected_failures.toFixed(1)}</b> on this plan.
          </p>
        </div>
      )}

      <ol className="flex flex-col gap-2">
        {planned.map((s, i) => {
          const p = s.planned!;
          const reply = replySummary(s.reply);
          return (
            <li key={s.id} className="flex flex-col gap-2">
              {p.wait_min > 20 && (
                <div className="flex items-center gap-2 px-2 text-sm text-muted">
                  <Coffee size={15} /> Free time {fmtDuration(p.wait_min)}, until {fmtTime(p.start_min)}
                </div>
              )}
              <button
                onClick={() => onOpenStop(s.id)}
                className="flex gap-3 rounded-2xl border border-line bg-white px-4 py-3 text-left"
              >
                <div
                  className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-bold text-white"
                  style={{ background: bandColor[s.risk_band ?? "low"] }}
                >
                  {i + 1}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-semibold">
                      {fmtTime(p.start_min)} · {s.customer}
                    </p>
                    <RiskChip band={s.risk_band} risk={s.risk} compact />
                  </div>
                  <p className="truncate text-sm text-muted">{s.area}</p>
                  <div className="mt-1 flex flex-wrap gap-1.5 text-xs">
                    {p.good_window && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-canvas px-2 py-0.5 font-medium">
                        <Clock size={12} /> Best {fmtTime(p.good_window[0])} to {fmtTime(p.good_window[1])}
                      </span>
                    )}
                    {p.moved_min !== null && p.moved_min !== undefined && Math.abs(p.moved_min) >= 30 && (
                      <span className="rounded-full bg-warn-soft px-2 py-0.5 font-medium text-warn">
                        Moved {p.moved_min > 0 ? "later" : "earlier"} by {fmtDuration(p.moved_min)}
                      </span>
                    )}
                    {s.status === "retry" && <span className="rounded-full bg-warn-soft px-2 py-0.5 font-medium text-warn">Retry</span>}
                    {reply && <span className="rounded-full bg-brand-soft px-2 py-0.5 font-medium text-brand">{reply}</span>}
                  </div>
                </div>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

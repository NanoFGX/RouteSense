import { Building2, Check, Copy, ExternalLink, Home, MessageCircle, RotateCcw, Sparkles, Store } from "lucide-react";
import { useState } from "react";
import type { Day, Stop } from "../api";
import { RiskChip } from "../components/RiskChip";
import { fmtTime, isOpen, propertyLabel, replyLink, replySummary, whatsappLink } from "../lib/format";

const propIcon = { landed: Home, high_rise: Building2, shop_office: Store };

const statusStyle: Record<Stop["status"], { label: string; cls: string }> = {
  pending: { label: "To deliver", cls: "bg-canvas text-muted" },
  retry: { label: "Retry later", cls: "bg-warn-soft text-warn" },
  delivered: { label: "Delivered", cls: "bg-ok-soft text-ok" },
  carried: { label: "Tomorrow", cls: "bg-bad-soft text-bad" },
  self_collect: { label: "Self-collect", cls: "bg-brand-soft text-brand" },
};

function AskRow({ day, stop }: { day: Day; stop: Stop }) {
  const [copied, setCopied] = useState(false);
  const top = stop.reasons.find((r) => r.effect === "raises");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(replyLink(day, stop));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      window.prompt("Copy this link", replyLink(day, stop));
    }
  };
  return (
    <li className="flex flex-col gap-2 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold">{stop.customer}</p>
          <p className="truncate text-sm text-muted">{top ? top.text : stop.area}</p>
        </div>
        <RiskChip band={stop.risk_band} risk={stop.risk} compact />
      </div>
      <div className="flex flex-wrap gap-2">
        <a
          href={whatsappLink(day, stop)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 rounded-full bg-[#1f8f4e] px-3 py-1.5 text-sm font-semibold text-white"
        >
          <MessageCircle size={16} /> Ask on WhatsApp
        </a>
        <a
          href={replyLink(day, stop)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-sm font-medium"
        >
          <ExternalLink size={15} /> Open customer link
        </a>
        <button
          onClick={copy}
          className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-sm font-medium"
        >
          {copied ? <Check size={15} /> : <Copy size={15} />} {copied ? "Copied" : "Copy link"}
        </button>
      </div>
    </li>
  );
}

export function TodayScreen({
  day,
  busy,
  onPlan,
  onReset,
}: {
  day: Day;
  busy: boolean;
  onPlan: () => void;
  onReset: () => void;
}) {
  const [confirmReset, setConfirmReset] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const open = day.stops.filter(isOpen);
  const flagged = open
    .filter((s) => s.risk_band !== "low" && !s.reply)
    .sort((a, b) => (b.risk ?? 0) - (a.risk ?? 0));
  const expected = open.reduce((sum, s) => sum + (s.risk ?? 0), 0);
  const replied = day.stops.filter((s) => s.reply).length;
  const order = new Map((day.stops.filter((s) => s.planned) || []).map((s, i) => [s.id, i + 1]));

  return (
    <div className="flex flex-col gap-5">
      <section className="grid grid-cols-3 gap-2">
        {[
          { label: "Parcels", value: day.stops.length },
          { label: "May fail (expected)", value: `~${expected.toFixed(1)}` },
          { label: "Replied", value: replied },
        ].map((c) => (
          <div key={c.label} className="rounded-2xl border border-line bg-white px-3 py-3">
            <p className="text-2xl font-bold tabular-nums">{c.value}</p>
            <p className="text-xs text-muted">{c.label}</p>
          </div>
        ))}
      </section>

      <section className="rounded-2xl bg-brand px-4 py-4 text-white">
        {day.plan ? (
          <>
            <p className="text-sm text-white/80">Plan v{day.plan.version}</p>
            <p className="mt-0.5 text-lg font-semibold">
              {open.length} stops left · finish around {fmtTime(day.plan.finish_min)}
            </p>
            <p className="text-sm text-white/80">
              {day.plan.total_km.toFixed(1)} km · about {day.plan.expected_failures.toFixed(1)} failed attempts expected
            </p>
          </>
        ) : (
          <>
            <p className="text-lg font-semibold">Plan the day around who is home</p>
            <p className="mt-1 text-sm text-white/85">
              RouteSense predicts which deliveries may fail and times each stop for when the customer is likely in.
            </p>
          </>
        )}
        <button
          onClick={onPlan}
          disabled={busy || open.length === 0}
          className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-white py-3 text-sm font-semibold text-brand disabled:opacity-60"
        >
          <Sparkles size={18} /> {busy ? "Planning with OR-Tools..." : day.plan ? "Re-plan now" : "Plan my day"}
        </button>
      </section>

      {flagged.length > 0 && (
        <section className="rounded-2xl border border-line bg-white px-4 pt-4">
          <h2 className="font-semibold">Ask before you go</h2>
          <p className="text-sm text-muted">
            Highest risk first. One tap sends the customer a link to pick a time; their answer updates your route.
          </p>
          <ul className="divide-y divide-line">
            {(showAll ? flagged : flagged.slice(0, 5)).map((s) => (
              <AskRow key={s.id} day={day} stop={s} />
            ))}
          </ul>
          {flagged.length > 5 && (
            <button onClick={() => setShowAll((v) => !v)} className="w-full border-t border-line py-3 text-sm font-medium text-brand">
              {showAll ? "Show fewer" : `Show all ${flagged.length}`}
            </button>
          )}
        </section>
      )}

      <section className="rounded-2xl border border-line bg-white">
        <h2 className="px-4 pt-4 font-semibold">All parcels</h2>
        <ul className="divide-y divide-line">
          {day.stops.map((s) => {
            const Icon = propIcon[s.property_type];
            const st = statusStyle[s.status];
            const reply = replySummary(s.reply);
            return (
              <li key={s.id} className="flex gap-3 px-4 py-3">
                <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-canvas text-sm font-semibold text-muted">
                  {order.get(s.id) ?? <Icon size={17} />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-semibold">{s.customer}</p>
                    {isOpen(s) ? (
                      <RiskChip band={s.risk_band} risk={s.risk} compact />
                    ) : (
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${st.cls}`}>{st.label}</span>
                    )}
                  </div>
                  <p className="truncate text-sm text-muted">
                    {s.area} · {propertyLabel[s.property_type]}
                    {s.cod ? ` · COD RM${s.cod_amount.toFixed(0)}` : ""}
                  </p>
                  <div className="mt-1 flex flex-wrap gap-1.5 text-xs">
                    {s.planned && isOpen(s) && (
                      <span className="rounded-full bg-canvas px-2 py-0.5 font-medium">ETA {fmtTime(s.planned.start_min)}</span>
                    )}
                    {s.status === "retry" && <span className="rounded-full bg-warn-soft px-2 py-0.5 font-medium text-warn">Retry</span>}
                    {reply && <span className="rounded-full bg-brand-soft px-2 py-0.5 font-medium text-brand">{reply}</span>}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="rounded-2xl border border-line bg-white px-4 py-4">
        <h2 className="font-semibold">Today so far</h2>
        <ul className="mt-2 flex flex-col gap-2 text-sm">
          {[...day.events].reverse().slice(0, 8).map((e, i) => (
            <li key={i} className="flex gap-3">
              <span className="w-16 shrink-0 tabular-nums text-muted">{fmtTime(e.t)}</span>
              <span>{e.text}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col items-center gap-2 pb-2">
        {confirmReset ? (
          <div className="flex items-center gap-2 text-sm">
            <span>Start the demo day again?</span>
            <button
              onClick={() => {
                setConfirmReset(false);
                onReset();
              }}
              className="rounded-full bg-ink px-3 py-1.5 font-semibold text-white"
            >
              Reset
            </button>
            <button onClick={() => setConfirmReset(false)} className="rounded-full border border-line px-3 py-1.5">
              Cancel
            </button>
          </div>
        ) : (
          <button onClick={() => setConfirmReset(true)} className="inline-flex items-center gap-1.5 text-sm text-muted">
            <RotateCcw size={15} /> Reset demo day
          </button>
        )}
      </section>
    </div>
  );
}

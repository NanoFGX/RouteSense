import { CheckCircle2, Loader2, PackageOpen } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type Reply, type ReplyView } from "../api";
import { fmtTime } from "../lib/format";

type Choice = "confirmed" | "after" | "before" | "tomorrow" | "self_collect";

const TIMES = Array.from({ length: 22 }, (_, i) => 10 * 60 + i * 30); // 10:00 am to 8:30 pm

export function ReplyPage() {
  const { token = "" } = useParams();
  const [view, setView] = useState<ReplyView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [choice, setChoice] = useState<Choice>("confirmed");
  const [after, setAfter] = useState(18 * 60 + 30);
  const [before, setBefore] = useState(13 * 60);
  const [safePlace, setSafePlace] = useState(false);
  const [codReady, setCodReady] = useState(false);
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    api.replyView(token).then(setView).catch((e: Error) => setError(e.message));
  }, [token]);

  const submit = async () => {
    setSending(true);
    setError(null);
    const body: Partial<Reply> & { choice: Reply["choice"] } =
      choice === "after"
        ? { choice: "window", after_min: after, safe_place: safePlace, cod_ready: codReady }
        : choice === "before"
          ? { choice: "window", before_min: before, safe_place: safePlace, cod_ready: codReady }
          : choice === "confirmed"
            ? { choice: "confirmed", safe_place: safePlace, cod_ready: codReady }
            : { choice };
    try {
      const r = await api.reply(token, body);
      setDone(r.message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  };

  const option = (id: Choice, title: string, extra?: React.ReactNode) => (
    <label
      className={`flex cursor-pointer flex-col gap-2 rounded-2xl border px-4 py-3 ${choice === id ? "border-brand bg-brand-soft" : "border-line bg-white"}`}
    >
      <span className="flex items-center gap-3">
        <input type="radio" name="choice" checked={choice === id} onChange={() => setChoice(id)} className="h-4 w-4 accent-[#8a1538]" />
        <span className="font-medium">{title}</span>
      </span>
      {choice === id && extra}
    </label>
  );

  return (
    <div className="mx-auto flex min-h-full max-w-md flex-col gap-5 px-4 pb-10 pt-6">
      <header className="flex items-center gap-2">
        <img src="/icon.svg" alt="" className="h-8 w-8" />
        <span className="text-lg font-bold">RouteSense</span>
      </header>

      {!view && !error && (
        <p className="flex items-center gap-2 text-muted">
          <Loader2 className="animate-spin" size={18} /> Loading your delivery
        </p>
      )}
      {error && !view && <p className="rounded-2xl bg-bad-soft px-4 py-3 text-bad">{error}</p>}

      {view && done && (
        <section className="rise flex flex-col items-center gap-3 rounded-2xl border border-line bg-white px-5 py-8 text-center">
          <CheckCircle2 size={44} className="text-ok" />
          <p className="text-lg font-semibold">{done}</p>
          <p className="text-sm text-muted">You can close this page.</p>
        </section>
      )}

      {view && !done && (
        <>
          <section className="rounded-2xl bg-brand px-5 py-5 text-white">
            <PackageOpen size={28} />
            <h1 className="mt-2 text-xl font-semibold">Hi {view.customer}, your parcel arrives today</h1>
            <p className="mt-1 text-white/85">
              {view.rider} is delivering in {view.area}
              {view.eta ? `, planned around ${view.eta.from} to ${view.eta.to}` : ""}. When should he come?
            </p>
          </section>

          {view.status !== "pending" && view.status !== "retry" ? (
            <p className="rounded-2xl bg-canvas px-4 py-3 text-sm">This parcel is no longer on today's route.</p>
          ) : (
            <form
              className="flex flex-col gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                submit();
              }}
            >
              {option("confirmed", "I'll be home today")}
              {option(
                "after",
                "Come after a time",
                <select
                  id="after-time"
                  value={after}
                  onChange={(e) => setAfter(Number(e.target.value))}
                  className="rounded-xl border border-line bg-white px-3 py-2"
                >
                  {TIMES.map((m) => (
                    <option key={m} value={m}>
                      After {fmtTime(m)}
                    </option>
                  ))}
                </select>,
              )}
              {option(
                "before",
                "Come before a time",
                <select
                  id="before-time"
                  value={before}
                  onChange={(e) => setBefore(Number(e.target.value))}
                  className="rounded-xl border border-line bg-white px-3 py-2"
                >
                  {TIMES.map((m) => (
                    <option key={m} value={m}>
                      Before {fmtTime(m)}
                    </option>
                  ))}
                </select>,
              )}
              {option("tomorrow", "Deliver tomorrow instead")}
              {option("self_collect", "I'll collect it at a self-collect point")}

              {(choice === "confirmed" || choice === "after" || choice === "before") && (
                <div className="flex flex-col gap-2 rounded-2xl border border-line bg-white px-4 py-3">
                  <label className="flex items-center gap-3 text-sm">
                    <input id="safe-place" type="checkbox" checked={safePlace} onChange={(e) => setSafePlace(e.target.checked)} className="h-4 w-4 accent-[#8a1538]" />
                    If I'm out, leave it with {view.guardhouse ? "the guardhouse" : "a neighbour"}
                  </label>
                  {view.cod && (
                    <label className="flex items-center gap-3 text-sm">
                      <input id="cod-ready" type="checkbox" checked={codReady} onChange={(e) => setCodReady(e.target.checked)} className="h-4 w-4 accent-[#8a1538]" />
                      I'll have the cash ready (RM{view.cod_amount.toFixed(0)})
                    </label>
                  )}
                </div>
              )}

              {error && <p className="rounded-xl bg-bad-soft px-3 py-2 text-sm text-bad">{error}</p>}
              <button
                type="submit"
                disabled={sending}
                className="mt-1 rounded-2xl bg-brand py-3.5 font-semibold text-white disabled:opacity-60"
              >
                {sending ? "Sending..." : `Send to ${view.rider}`}
              </button>
            </form>
          )}

          <p className="text-xs text-muted">
            Your answer is used only to plan this delivery. This link stops working at the end of {view.date}.
          </p>
        </>
      )}
    </div>
  );
}

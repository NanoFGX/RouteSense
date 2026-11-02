// Types and calls for the RouteSense API (FastAPI backend, see backend/routesense/api.py).

export type RiskBand = "low" | "medium" | "high";
export type StopStatus = "pending" | "retry" | "delivered" | "carried" | "self_collect";

export interface Reason {
  text: string;
  effect: "raises" | "lowers";
}

export interface PlannedStop {
  stop_id: string;
  arrival_min: number;
  start_min: number;
  leave_min: number;
  wait_min: number;
  travel_min: number;
  km: number;
  risk: number;
  risk_band: RiskBand;
  good_window: [number, number] | null;
  retry: boolean;
  moved_min?: number | null;
}

export interface Reply {
  choice: "confirmed" | "window" | "tomorrow" | "self_collect";
  after_min?: number | null;
  before_min?: number | null;
  safe_place?: boolean;
  cod_ready?: boolean;
  source?: string;
}

export interface Stop {
  id: string;
  customer: string;
  address: string;
  area: string;
  lat: number;
  lng: number;
  property_type: "landed" | "high_rise" | "shop_office";
  guardhouse: boolean;
  cod: boolean;
  cod_amount: number;
  tw_start: number;
  tw_end: number;
  prior_failures: number;
  token: string;
  phone: string | null;
  status: StopStatus;
  attempts: number;
  reply: Reply | null;
  earliest_min: number | null;
  service_min: number;
  risk: number | null;
  risk_band: RiskBand | null;
  risk_at_min: number;
  reasons: Reason[];
  planned: PlannedStop | null;
  failed_attempts_today: number;
  delivered_min?: number;
}

export interface PlanMeta {
  strategy: string;
  version: number;
  start_min: number;
  finish_min: number;
  total_km: number;
  total_travel_min: number;
  expected_failures: number;
  solve_ms: number;
  dropped: string[];
  made_at_min: number;
}

export interface DayEvent {
  t: number;
  text: string;
  stop_id?: string | null;
  kind?: "info" | "good" | "bad" | "warn" | "plan" | "reply";
}

export interface Day {
  id: string;
  date: string;
  rider: { name: string; vehicle: string };
  hub: { label: string; lat: number; lng: number };
  clock_min: number;
  clock_label: string;
  position: { lat: number; lng: number; label: string };
  plan: PlanMeta | null;
  stops: Stop[];
  next_stop_id: string | null;
  counts: Record<StopStatus, number>;
  events: DayEvent[];
  public_base_url: string | null;
  day_start: number;
  day_end: number;
}

export interface PreviewPlan {
  strategy: string;
  label: string;
  stops: PlannedStop[];
  dropped: string[];
  finish_min: number;
  total_km: number;
  expected_failures: number;
}

export interface Metrics {
  delivered: number;
  delivered_first_try: number;
  first_try_rate: number;
  failed_attempts: number;
  carried_over: number;
  unpaid_min: number;
  km: number;
  finish_min: number;
  work_hours: number;
  active_min: number;
  parcels_per_active_hour: number;
  free_min: number;
}

export interface SimEvent {
  t: number;
  stop_id: string;
  customer: string;
  event: "delivered" | "failed";
  reason?: string;
  attempt: number;
  retry?: boolean;
}

export interface CompareResult {
  status: "ready" | "computing";
  reply_rate?: number;
  replays?: number;
  strategies?: Record<string, { label: string; replays: number; mean: Metrics; per_replay_first_try: number[] }>;
}

export interface SimulateResult extends Metrics {
  strategy: string;
  label: string;
  parcels: number;
  replies: number;
  replans: number;
  events: SimEvent[];
  stops: Record<string, { lat: number; lng: number; customer: string; area: string }>;
  hub: { lat: number; lng: number; label: string };
}

export interface ReplyView {
  customer: string;
  rider: string;
  area: string;
  status: StopStatus;
  cod: boolean;
  cod_amount: number;
  property_type: string;
  guardhouse: boolean;
  eta: { from: string; to: string } | null;
  reply: Reply | null;
  date: string;
  window: { from: string; to: string };
}

export interface ModelInfo {
  trained_at: string;
  scenario: string;
  metrics: {
    train_rows: number;
    test_rows: number;
    test_routes: number;
    logistic_regression: Record<string, number>;
    xgboost: Record<string, number>;
  };
  data_checks: Record<string, { passed: boolean } & Record<string, unknown>>;
  logged_outcomes: number;
  retrain_threshold: number;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  return res.json() as Promise<T>;
}

export const api = {
  day: () => call<Day>("/api/day"),
  reset: () => call<Day>("/api/day/reset", { method: "POST" }),
  plan: () => call<Day>("/api/plan", { method: "POST" }),
  preview: (strategy: string) => call<PreviewPlan>(`/api/plan/preview?strategy=${strategy}`),
  outcome: (stop_id: string, status: "delivered" | "failed", reason?: string) =>
    call<{ message: string; day: Day }>("/api/outcome", {
      method: "POST",
      body: JSON.stringify({ stop_id, status, reason }),
    }),
  riskCurve: (stopId: string) =>
    call<{ points: { minute: number; label: string; risk: number }[] }>(`/api/stops/${stopId}/risk`),
  replyView: (token: string) => call<ReplyView>(`/api/reply/${token}`),
  reply: (token: string, body: Partial<Reply> & { choice: Reply["choice"] }) =>
    call<{ ok: boolean; message: string }>(`/api/reply/${token}`, { method: "POST", body: JSON.stringify(body) }),
  compare: (replyRate: number) => call<CompareResult>(`/api/compare?reply_rate=${replyRate}`),
  simulate: (strategy: string, seed: number) =>
    call<SimulateResult>("/api/simulate", { method: "POST", body: JSON.stringify({ strategy, seed }) }),
  model: () => call<ModelInfo>("/api/model"),
};

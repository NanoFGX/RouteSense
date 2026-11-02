import type { Day, Reply, RiskBand, Stop } from "../api";

export function fmtTime(minute: number | null | undefined): string {
  if (minute === null || minute === undefined) return "";
  const m = Math.round(minute);
  const h = Math.floor(m / 60);
  const mm = m % 60;
  const suffix = h < 12 ? "am" : "pm";
  const h12 = h % 12 || 12;
  return `${h12}:${String(mm).padStart(2, "0")} ${suffix}`;
}

export function fmtDuration(minutes: number): string {
  const m = Math.round(Math.abs(minutes));
  const h = Math.floor(m / 60);
  const rest = m % 60;
  if (h === 0) return `${rest} min`;
  return rest ? `${h} h ${rest} min` : `${h} h`;
}

export const bandLabel: Record<RiskBand, string> = { low: "Low risk", medium: "Medium risk", high: "High risk" };

export const propertyLabel: Record<Stop["property_type"], string> = {
  landed: "Landed house",
  high_rise: "High-rise",
  shop_office: "Shop or office",
};

export function replySummary(reply: Reply | null): string | null {
  if (!reply) return null;
  if (reply.choice === "tomorrow") return "Asked for tomorrow";
  if (reply.choice === "self_collect") return "Will self-collect";
  const parts: string[] = [];
  if (reply.choice === "window") {
    if (reply.after_min) parts.push(`after ${fmtTime(reply.after_min)}`);
    if (reply.before_min) parts.push(`before ${fmtTime(reply.before_min)}`);
  } else {
    parts.push("home today");
  }
  if (reply.safe_place) parts.push("leave with guard");
  if (reply.cod_ready) parts.push("cash ready");
  return "Replied: " + parts.join(", ");
}

/** Where the customer link lives. Set ROUTESENSE_PUBLIC_URL on the server to use a LAN or tunnel address. */
export function replyLink(day: Day, stop: Stop): string {
  const base = (day.public_base_url || window.location.origin).replace(/\/$/, "");
  return `${base}/r/${stop.token}`;
}

/** WhatsApp click-to-chat. With no number (the demo data) WhatsApp asks which chat to send it to. */
export function whatsappLink(day: Day, stop: Stop): string {
  const text =
    `Hi ${stop.customer}, saya ${day.rider.name}, rider untuk parcel anda hari ini. ` +
    `Bila masa sesuai untuk saya hantar? / I'm delivering your parcel today. When suits you? ` +
    replyLink(day, stop);
  const phone = stop.phone ? stop.phone.replace(/\D/g, "") : "";
  return `https://wa.me/${phone}?text=${encodeURIComponent(text)}`;
}

export function wazeLink(stop: Stop): string {
  return `https://waze.com/ul?ll=${stop.lat},${stop.lng}&navigate=yes`;
}

export function googleMapsLink(stop: Stop, vehicle: string): string {
  const mode = vehicle === "motorcycle" ? "two-wheeler" : "driving";
  return `https://www.google.com/maps/dir/?api=1&destination=${stop.lat},${stop.lng}&travelmode=${mode}`;
}

export const isOpen = (s: Stop) => s.status === "pending" || s.status === "retry";

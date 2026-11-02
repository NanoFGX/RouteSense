import type { RiskBand } from "../api";
import { bandLabel } from "../lib/format";

const styles: Record<RiskBand, string> = {
  low: "bg-ok-soft text-ok",
  medium: "bg-warn-soft text-warn",
  high: "bg-bad-soft text-bad",
};

export function RiskChip({ band, risk, compact = false }: { band: RiskBand | null; risk: number | null; compact?: boolean }) {
  if (!band || risk === null) return null;
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold ${styles[band]}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {compact ? `${Math.round(risk * 100)}%` : `${bandLabel[band]} · ${Math.round(risk * 100)}%`}
    </span>
  );
}

export const bandColor: Record<RiskBand, string> = { low: "#17804c", medium: "#c98a0b", high: "#c0352b" };

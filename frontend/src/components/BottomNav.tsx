import { BarChart3, ListChecks, Map, Navigation } from "lucide-react";

export type Tab = "today" | "route" | "next" | "compare";

const tabs: { id: Tab; label: string; icon: typeof Map }[] = [
  { id: "today", label: "Today", icon: ListChecks },
  { id: "route", label: "Route", icon: Map },
  { id: "next", label: "Next stop", icon: Navigation },
  { id: "compare", label: "Compare", icon: BarChart3 },
];

export function BottomNav({ tab, onChange }: { tab: Tab; onChange: (t: Tab) => void }) {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-[1000] border-t border-line bg-white/95 backdrop-blur"
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
    >
      <div className="mx-auto grid max-w-md grid-cols-4">
        {tabs.map(({ id, label, icon: Icon }) => {
          const active = tab === id;
          return (
            <button
              key={id}
              onClick={() => onChange(id)}
              className={`flex flex-col items-center gap-0.5 py-2.5 text-[11px] font-medium focus-visible:outline-2 focus-visible:outline-brand ${
                active ? "text-brand" : "text-muted"
              }`}
              aria-current={active ? "page" : undefined}
            >
              <Icon size={20} strokeWidth={active ? 2.4 : 1.8} />
              {label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}

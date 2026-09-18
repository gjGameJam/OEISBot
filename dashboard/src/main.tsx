import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { fmtInt, useApi } from "./lib";
import { AttemptsView, EstimatorView, HistoryView, QueueView, ReviewsView } from "./views";

const TABS = [
  { id: "estimator", label: "Estimator accuracy", view: EstimatorView },
  { id: "queue", label: "Queue", view: QueueView },
  { id: "attempts", label: "Attempts", view: AttemptsView },
  { id: "reviews", label: "Review inbox", view: ReviewsView },
  { id: "history", label: "Run history", view: HistoryView },
] as const;

interface Summary {
  candidates: number; attempts: number; wins: number; open_reviews: number; machine_hours: number;
  oeisdata_commit: string | null; synced_at: string | null;
}

function App() {
  const fromHash = () => TABS.find((t) => `#${t.id}` === window.location.hash)?.id ?? "estimator";
  const [tab, setTab] = useState<string>(fromHash);
  useEffect(() => { if (window.location.hash !== `#${tab}`) window.history.pushState(null, "", `#${tab}`); }, [tab]);
  useEffect(() => {
    const onHash = () => setTab(fromHash());
    window.addEventListener("hashchange", onHash);
    window.addEventListener("popstate", onHash);
    return () => { window.removeEventListener("hashchange", onHash); window.removeEventListener("popstate", onHash); };
  }, []);
  const { data } = useApi<Summary>("/api/summary");
  const View = TABS.find((t) => t.id === tab)!.view;
  return (
    <div className="shell">
      <div className="topbar">
        <h1>OEISBot</h1>
        <span className="meta">
          {data ? `${fmtInt(data.candidates)} candidates · ${fmtInt(data.attempts)} runs · ${fmtInt(data.wins)} wins · ` +
            `${fmtInt(data.open_reviews)} awaiting review · ${data.machine_hours.toFixed(1)} machine hours` : ""}
        </span>
        <span className="spacer" />
        <span className="meta">
          {data?.oeisdata_commit ? `oeisdata ${data.oeisdata_commit.slice(0, 10)}, synced ${new Date(data.synced_at!).toLocaleString()}` : ""}
        </span>
      </div>
      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </nav>
      <View />
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);

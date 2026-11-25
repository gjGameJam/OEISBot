import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { daemonLine, type DaemonReport } from "./daemonline";
import { fmtInt, tabKeys, useApi } from "./lib";
import { PickMapView } from "./pickmap";
import { AttemptsView, EstimatorView, HistoryView, QueueView, ReviewsView } from "./views";

const TABS = [
  { id: "estimator", label: "Estimator accuracy", view: EstimatorView },
  { id: "pickmap", label: "Pick map", view: PickMapView },
  { id: "queue", label: "Queue", view: QueueView },
  { id: "attempts", label: "Attempts", view: AttemptsView },
  { id: "reviews", label: "Review inbox", view: ReviewsView },
  { id: "history", label: "Run history", view: HistoryView },
] as const;

interface Summary {
  candidates: number; attempts: number; wins: number; rejected_wins?: number; open_reviews: number; machine_hours: number;
  oeisdata_commit: string | null; synced_at: string | null;
}

const plural = (n: number, word: string) => `${fmtInt(n)} ${word}${n === 1 ? "" : "s"}`;

/** One line under the header, on every tab: whether `oeisbot daemon` is running and what it is doing
 *  (daemonline.ts decides the words). Polled like everything else. Before the first answer an empty line of
 *  the same height holds its place, so the tabs do not jump when it arrives. */
function DaemonStrip() {
  const { data, error } = useApi<DaemonReport>("/api/daemon");
  // `useApi` keeps the last answer when a request fails. For this line that would be "Daemon running ..."
  // left on screen by a server that has gone away, so a failure is said instead of shown as current.
  if (error) return <div className="daemon idle"><span className="dot" aria-hidden="true" /><span>Daemon status unavailable ({error})</span></div>;
  if (!data) return <div className="daemon idle" aria-hidden="true"><span className="dot" /><span>&nbsp;</span></div>;
  const line = daemonLine(data, Date.now());
  // Not a live region: the text carries a ticking "N min ago", and a screen reader would read the line
  // out again every minute of every pick.
  return (
    <div className={`daemon ${line.tone}`}>
      <span className="dot" aria-hidden="true" />
      <span>{line.text}</span>
      {line.notes.map((n) => <span className="note" key={n}>{n}</span>)}
    </div>
  );
}

function App() {
  const fromHash = () => TABS.find((t) => `#${t.id}` === window.location.hash)?.id ?? "estimator";
  const [tab, setTab] = useState<string>(fromHash);
  // Choosing a tab adds a history entry, so Back returns to the last tab. Arriving with no fragment or an
  // unknown one does not: the address is corrected in place, or Back would land on the same view again.
  const choose = (id: string) => { if (id !== tab) { window.history.pushState(null, "", `#${id}`); setTab(id); } };
  useEffect(() => { if (window.location.hash !== `#${tab}`) window.history.replaceState(null, "", `#${tab}`); }, [tab]);
  useEffect(() => {
    // an address edited to a fragment that names no tab resolves to the first one; the address is put right
    // here, because when that tab is already showing no state changes and the effect above never runs
    const onHash = () => {
      const id = fromHash();
      if (window.location.hash !== `#${id}`) window.history.replaceState(null, "", `#${id}`);
      setTab(id);
    };
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
          {/* "sequences with keyword more" and not "candidates": it is every such entry in the mirror, far more
              than any pool a session draws from (the Queue and the Pick map each say how many those hold) */}
          {data ? `${fmtInt(data.candidates)} sequences with keyword more · ${plural(data.attempts, "run")} · ${plural(data.wins, "win")}` +
            `${data.rejected_wins ? ` (${fmtInt(data.rejected_wins)} more rejected in review)` : ""} · ` +
            `${fmtInt(data.open_reviews)} awaiting review · ${data.machine_hours.toFixed(1)} machine hours` : ""}
        </span>
        <span className="spacer" />
        <span className="meta">
          {data?.oeisdata_commit ? `oeisdata ${data.oeisdata_commit.slice(0, 10)}` +
            (data.synced_at && !isNaN(new Date(data.synced_at).getTime()) ? `, synced ${new Date(data.synced_at).toLocaleString()}` : "") : ""}
        </span>
      </div>
      <DaemonStrip />
      {/* One stop for the Tab key, on the selected tab; Left, Right, Home and End move the focus along the row
          and Enter or Space opens the focused tab (tabs.tabAfter says why moving does not open). */}
      <nav className="tabs" role="tablist" aria-label="Views" onKeyDown={tabKeys(TABS.map((t) => `tab-${t.id}`))}>
        {TABS.map((t) => (
          <button key={t.id} id={`tab-${t.id}`} role="tab" aria-selected={tab === t.id} aria-controls="tab-panel"
                  tabIndex={tab === t.id ? 0 : -1} onClick={() => choose(t.id)}>{t.label}</button>
        ))}
      </nav>
      <div id="tab-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
        <View />
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);

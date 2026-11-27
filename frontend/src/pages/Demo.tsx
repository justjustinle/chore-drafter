// /demo/:scenario: every screen, driven by the mock API instead of the backend.

import { Link, useParams } from "react-router-dom";
import { ApiChoice } from "../api/context";
import { mockApi, type Scenario } from "../mock/mockApi";
import { HouseholdView } from "./HouseholdPage";

const SCENARIOS: { id: Scenario; label: string }[] = [
  { id: "setup", label: "Setup" },
  { id: "estimation", label: "Estimation" },
  { id: "open-week", label: "Open week" },
  { id: "auction", label: "Live auction" },
  { id: "quest-week", label: "Quest week" },
  { id: "history", label: "Chronicle" },
];

const apis = new Map<Scenario, ReturnType<typeof mockApi>>();

export default function Demo() {
  const scenario = (useParams()["*"] || "auction") as Scenario;
  if (!apis.has(scenario)) apis.set(scenario, mockApi(scenario));
  const api = apis.get(scenario)!;

  return (
    <div>
      <div className="window" style={{ padding: "10px 16px", marginBottom: 18 }}>
        <div className="row">
          <strong>Demo mode</strong>
          <span className="subtle">(pretend data, nothing is saved)</span>
          {SCENARIOS.map((s) => (
            <Link key={s.id} to={`/demo/${s.id}`} className={`btn small ${s.id === scenario ? "" : "quiet"}`}>
              {s.label}
            </Link>
          ))}
        </div>
      </div>
      <ApiChoice.Provider value={api}>
        <HouseholdView
          key={scenario}
          id={1}
          apiKey="cd_demo"
          memberId={1}
          tab={scenario === "history" ? "history" : "guild"}
          linkBase="/demo"
        />
      </ApiChoice.Provider>
    </div>
  );
}

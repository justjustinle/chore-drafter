// The Guild Chronicle: every closed week.

import { useGame } from "../api/context";
import { useLive } from "../api/live";
import { Pips, Tokens, Window } from "../components/ui";

export default function History() {
  const { api, key, household } = useGame();
  const history = useLive(() => api.history(key, household.id), 15000, [household.id]);

  return (
    <div>
      <Window title="📚 The Guild Chronicle">
        {!history.data ? (
          <p className="subtle">Dusting off the old tomes…</p>
        ) : history.data.length === 0 ? (
          <p className="subtle">No weeks have closed yet. The first chapter is still being written.</p>
        ) : (
          history.data.map((week) => (
            <div key={week.week_id} style={{ marginBottom: 20 }}>
              <h3>
                Week of {new Date(week.starts_on).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })}
              </h3>
              <ul className="list">
                {week.chores.map((chore, i) => (
                  <li key={i}>
                    <span aria-label={chore.done ? "Done" : "Not done"} title={chore.done ? "Done" : "Not done"}>
                      {chore.done ? "✅" : "⬜"}
                    </span>
                    <div style={{ flex: 1 }}>
                      <strong>{chore.name}</strong> <span className="subtle">by {chore.assigned_to ?? "nobody"}</span>
                      <div className="row" style={{ gap: 6 }}>
                        <Pips value={chore.effort_points} />
                        <span className="subtle num">{chore.effort_points} effort</span>
                      </div>
                    </div>
                    {chore.price_paid != null ? <Tokens value={chore.price_paid} /> : <span className="chip blue">Assigned</span>}
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
      </Window>

      <Window title="🦉 The Commissioner">
        <div className="owl">
          <span style={{ fontSize: "2.4rem" }} aria-hidden="true">
            🦉
          </span>
          <div className="bubble">
            <p style={{ margin: 0 }}>
              Hoo! I'm still studying the old tomes. Once the AI Commissioner arrives (Layer 9), I'll suggest which chores
              to re-weigh, and show you the weeks I read and the model I used.
            </p>
          </div>
        </div>
      </Window>
    </div>
  );
}

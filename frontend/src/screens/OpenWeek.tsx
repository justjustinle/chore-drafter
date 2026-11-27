// Week status OPEN: flag chores for a re-vote, then the owner starts the auction.

import { useGame } from "../api/context";
import { useLive } from "../api/live";
import { friendlyError } from "../components/errors";
import { Pips, Window, flavourFor, useToast } from "../components/ui";

export default function OpenWeek({ weekId }: { weekId: number }) {
  const { api, key, household, isOwner, refreshHousehold } = useGame();
  const toast = useToast();
  const week = useLive(() => api.week(key, weekId), 2000, [weekId]);

  if (!week.data) return <p className="subtle">Unrolling the week's map…</p>;

  const flagged = new Set(week.data.flagged_chore_ids);
  const totalEffort = week.data.chores.reduce((sum, chore) => sum + chore.effort_points, 0);

  async function run(action: () => Promise<unknown>) {
    try {
      await action();
      await Promise.all([week.refresh(), refreshHousehold()]);
    } catch (error) {
      toast(friendlyError(error), "warn");
    }
  }

  return (
    <div>
      <Window
        title={`☀️ Week of ${new Date(week.data.starts_on).toLocaleDateString(undefined, { day: "numeric", month: "long" })}`}
        actions={
          isOwner && (
            <>
              {flagged.size > 0 && (
                <button type="button" className="btn gold" onClick={() => run(() => api.startReEstimation(key, weekId))}>
                  🔁 Re-vote {flagged.size} flagged
                </button>
              )}
              {/* The server decides whether the market can open (e.g. flagged chores
                  must be re-voted first) and says why if not. */}
              <button type="button" className="btn green" onClick={() => run(() => api.startAuction(key, weekId))}>
                🔔 Open the market
              </button>
            </>
          )
        }
      >
        <div className="row" style={{ gap: 18 }}>
          <span className="chip blue num">Total effort: {totalEffort}</span>
          <span className="chip gold num">🪙 100 tokens each, +1 for everyone per nomination</span>
          <span className="chip grey num">{household.members.length} adventurers</span>
        </div>
        <p className="subtle">
          Think a chore's effort is off? Flag it and the party re-votes on it before the market opens.
        </p>
        <div className="cards">
          {week.data.chores.map((chore) => (
            <div className="quest-card" key={chore.id}>
              <div className="name">{chore.name}</div>
              {flagged.has(chore.chore_id) && <span className="chip tangerine">🚩 Flagged</span>}
              <div className="flavour">{flavourFor(chore.chore_id)}</div>
              <div className="num" style={{ fontWeight: 700, marginTop: 6 }}>
                {chore.effort_points} effort
              </div>
              <Pips value={chore.effort_points} />
              <div style={{ marginTop: 10 }}>
                <button
                  type="button"
                  className="btn quiet small"
                  disabled={flagged.has(chore.chore_id)}
                  onClick={() => run(() => api.flag(key, weekId, chore.chore_id))}
                >
                  🚩 Flag for re-vote
                </button>
              </div>
            </div>
          ))}
        </div>
      </Window>
    </div>
  );
}

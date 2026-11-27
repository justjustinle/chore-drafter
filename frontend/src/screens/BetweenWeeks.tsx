// ACTIVE household with no week open: the owner opens the next one.

import { useState } from "react";
import { Link } from "react-router-dom";
import { useGame } from "../api/context";
import { friendlyError } from "../components/errors";
import { Pips, Window, useToast } from "../components/ui";

export default function BetweenWeeks() {
  const { api, key, household, isOwner, refreshHousehold } = useGame();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  async function openWeek() {
    setBusy(true);
    try {
      await api.openWeek(key, household.id);
      await refreshHousehold();
    } catch (error) {
      toast(friendlyError(error), "warn");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Window
      title="🌙 The guild rests"
      actions={
        isOwner ? (
          <button type="button" className="btn green" onClick={openWeek} disabled={busy}>
            ☀️ Open a new week
          </button>
        ) : undefined
      }
    >
      <p>
        {isOwner
          ? "When you're ready, open a new week. Everyone gets 100 tokens and the market opens."
          : "Waiting for the owner to open the next week."}{" "}
        <Link to={`/h/${household.id}/history`}>Read the chronicle</Link> of past weeks.
      </p>
      <div className="cards">
        {household.chores.map((chore) => (
          <div className="quest-card" key={chore.id}>
            <div className="name">{chore.name}</div>
            <div className="num">{chore.effort_points} effort</div>
            {chore.effort_points != null && <Pips value={chore.effort_points} />}
          </div>
        ))}
      </div>
    </Window>
  );
}

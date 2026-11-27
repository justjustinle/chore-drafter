// Blind voting: the first estimation, or a re-estimation at the start of a week.

import { useState } from "react";
import { useGame } from "../api/context";
import { useLive } from "../api/live";
import { friendlyError } from "../components/errors";
import { Avatar, Modal, Window, flavourFor, useToast } from "../components/ui";

export default function Estimation() {
  const { api, key, household, memberId, isOwner, refreshHousehold } = useGame();
  const toast = useToast();
  const status = useLive(() => api.estimation(key, household.id), 2000, [household.id]);

  const [index, setIndex] = useState(0);
  // Your pick is shown only while you are on that card; moving on hides it.
  const [picked, setPicked] = useState<{ choreId: number; points: number } | null>(null);
  const [confirmClose, setConfirmClose] = useState(false);

  if (!status.data) return <p className="subtle">Gathering the voting slips…</p>;

  const round = status.data;
  const chores = round.chore_ids
    .map((id) => household.chores.find((c) => c.id === id))
    .filter((c): c is NonNullable<typeof c> => !!c);
  const me = round.voters.find((v) => v.member_id === memberId);
  const myVotes = new Set(me?.voted_chore_ids ?? []);
  const chore = chores[Math.min(index, chores.length - 1)];

  function goTo(next: number) {
    setPicked(null);
    setIndex((next + chores.length) % chores.length);
  }

  async function vote(points: number) {
    if (!chore) return;
    setPicked({ choreId: chore.id, points });
    try {
      const result = await api.vote(key, household.id, chore.id, points);
      if (result.estimation_closed) {
        await refreshHousehold();
        return;
      }
      await status.refresh();
    } catch (error) {
      toast(friendlyError(error), "warn");
    }
  }

  async function forceClose() {
    try {
      await api.forceClose(key, household.id);
      setConfirmClose(false);
      await refreshHousehold();
    } catch (error) {
      setConfirmClose(false);
      toast(friendlyError(error), "warn");
    }
  }

  const pickedHere = picked && chore && picked.choreId === chore.id ? picked.points : null;

  return (
    <div className="grid-2">
      <Window
        title={round.week_id ? "🔁 Re-weigh the flagged quests" : "⚖️ Weigh the quests"}
        actions={
          isOwner && (
            <button type="button" className="btn quiet small" onClick={() => setConfirmClose(true)}>
              Force close
            </button>
          )
        }
      >
        <p className="subtle" aria-live="polite">
          You've voted on {myVotes.size} of {chores.length} chores. Votes stay secret until everyone is done.
        </p>
        {chore && (
          <div className="quest-card" style={{ padding: 22 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span className="subtle num">
                Card {Math.min(index, chores.length - 1) + 1} of {chores.length}
              </span>
              {myVotes.has(chore.id) ? (
                <span className="chip green">✔ You've voted</span>
              ) : (
                <span className="chip grey">Not voted yet</span>
              )}
            </div>
            <div className="name" style={{ fontSize: "1.5rem", marginTop: 8 }}>
              {chore.name}
            </div>
            <div className="flavour">{flavourFor(chore.id)}</div>
            {chore.description && <p>{chore.description}</p>}
            <p style={{ marginBottom: 6, fontWeight: 600 }}>How much effort is it? (1 = a breeze, 10 = a boss fight)</p>
            <div className="pip-picker" role="group" aria-label={`Effort for ${chore.name}`}>
              {Array.from({ length: 10 }, (_, i) => i + 1).map((points) => (
                <button
                  key={points}
                  type="button"
                  className={`pip-button${pickedHere && points <= pickedHere ? " filled" : ""}${pickedHere === points ? " picked" : ""}`}
                  aria-pressed={pickedHere === points}
                  onClick={() => vote(points)}
                >
                  {points}
                </button>
              ))}
            </div>
            <p className="subtle" style={{ fontSize: "0.85rem" }}>
              Picking again changes your vote.
            </p>
            <div className="row" style={{ justifyContent: "space-between", marginTop: 8 }}>
              <button type="button" className="btn quiet small" onClick={() => goTo(index - 1)} disabled={chores.length < 2}>
                ← Previous
              </button>
              <button type="button" className="btn small" onClick={() => goTo(index + 1)} disabled={chores.length < 2}>
                Next →
              </button>
            </div>
          </div>
        )}
      </Window>

      <Window title="🗳️ The party">
        <ul className="list">
          {round.voters.map((voter) => (
            <li key={voter.member_id}>
              <Avatar memberId={voter.member_id} name={voter.display_name} crown={voter.member_id === household.owner_member_id} />
              <strong style={{ flex: 1 }}>{voter.member_id === memberId ? "You" : voter.display_name}</strong>
              {voter.done ? (
                <span className="chip green">✔ Voted</span>
              ) : (
                <span className="chip grey">💭 Thinking… {voter.voted_chore_ids.length}/{chores.length}</span>
              )}
            </li>
          ))}
        </ul>
      </Window>

      {confirmClose && (
        <Modal title="Close the voting now?" onClose={() => setConfirmClose(false)}>
          <p>
            Any missing votes are ignored, and each chore's effort becomes the average of the votes it has. Chores with no
            votes at all can't be closed yet.
          </p>
          <div className="row">
            <button type="button" className="btn gold" onClick={forceClose}>
              Close the voting
            </button>
            <button type="button" className="btn quiet" onClick={() => setConfirmClose(false)}>
              Keep waiting
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

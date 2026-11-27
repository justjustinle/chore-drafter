// Week status ASSIGNED: who does what, fun titles, and ticking chores off.

import { useState } from "react";
import { useGame } from "../api/context";
import { useLive } from "../api/live";
import type { Assignments, MemberEffort } from "../api/types";
import { friendlyError } from "../components/errors";
import { Avatar, Pips, Tokens, Window, useReducedMotion, useToast } from "../components/ui";

export default function QuestWeek({ weekId }: { weekId: number }) {
  const { api, key, memberId, isOwner, household, refreshHousehold } = useGame();
  const toast = useToast();
  const reducedMotion = useReducedMotion();
  const assignments = useLive(() => api.assignments(key, weekId), 4000, [weekId]);
  const [closing, setClosing] = useState(false);

  if (!assignments.data) return <p className="subtle">Pinning up the quest board…</p>;
  const data = assignments.data;
  const titles = funTitles(data);
  // Chores the guild assigned (rather than won at auction) are dealt in one by one.
  let dealt = 0;

  async function markDone(weekChoreId: number) {
    try {
      await api.markDone(key, weekChoreId);
      await assignments.refresh();
    } catch (error) {
      toast(friendlyError(error), "warn");
    }
  }

  async function closeWeek() {
    setClosing(true);
    try {
      await api.closeWeek(key, weekId);
      await refreshHousehold();
    } catch (error) {
      toast(friendlyError(error), "warn");
    } finally {
      setClosing(false);
    }
  }

  return (
    <div>
      <Window
        title="🗺️ This week's quests"
        actions={
          isOwner && data.status === "ASSIGNED" && (
            <button type="button" className="btn quiet" onClick={closeWeek} disabled={closing}>
              🌙 Close the week
            </button>
          )
        }
      >
        <p className="subtle">Tick off your own quests as you finish them. Everyone else's are read-only.</p>
        <div className="board">
          {data.members.map((member) => {
            const mine = data.chores.filter((chore) => chore.assigned_member_id === member.member_id);
            const you = member.member_id === memberId;
            return (
              <div className="quest-card" key={member.member_id}>
                <div className="row" style={{ marginBottom: 8 }}>
                  <Avatar memberId={member.member_id} name={member.display_name} crown={member.member_id === household.owner_member_id} large />
                  <div style={{ flex: 1 }}>
                    <div className="name">{you ? `${member.display_name} (you)` : member.display_name}</div>
                    <div className="row" style={{ gap: 6 }}>
                      {(titles.get(member.member_id) ?? []).map((title) => (
                        <span key={title} className="chip gold">
                          {title}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="num" style={{ fontWeight: 700 }}>
                      {member.effort} effort
                    </div>
                    <Tokens value={member.tokens_spent} /> <span className="subtle">spent</span>
                  </div>
                </div>
                <ul className="list">
                  {mine.map((chore) => {
                    const delay = chore.assigned_via === "FINISH" && !reducedMotion ? dealt++ * 0.25 : 0;
                    const done = chore.done_at != null;
                    return (
                      <li
                        key={chore.id}
                        className={chore.assigned_via === "FINISH" ? "deal-in" : ""}
                        style={{ animationDelay: `${delay}s` }}
                      >
                        <button
                          type="button"
                          className={`done-check${done ? " done" : ""}`}
                          disabled={!you || done}
                          onClick={() => markDone(chore.id)}
                          aria-label={done ? `${chore.name}: done` : you ? `Mark ${chore.name} done` : `${chore.name}: not done yet`}
                        >
                          {done ? "✓" : ""}
                        </button>
                        <div style={{ flex: 1 }}>
                          <strong style={{ textDecoration: done ? "line-through" : undefined }}>{chore.name}</strong>
                          <div className="row" style={{ gap: 6 }}>
                            <Pips value={chore.effort_points} />
                            <span className="subtle num">{chore.effort_points}</span>
                            {chore.assigned_via === "AUCTION" ? (
                              <span className="chip gold">
                                Won for <Tokens value={chore.price_paid ?? 0} />
                              </span>
                            ) : (
                              <span className="chip blue">🏰 Assigned</span>
                            )}
                          </div>
                        </div>
                      </li>
                    );
                  })}
                  {mine.length === 0 && <li className="subtle">A week off. Lucky!</li>}
                </ul>
              </div>
            );
          })}
        </div>
      </Window>
    </div>
  );
}

/** Light-hearted titles, worked out from the assignments the server returned. */
function funTitles(data: Assignments): Map<number, string[]> {
  const titles = new Map<number, string[]>();
  const give = (member: MemberEffort | undefined, title: string) => {
    if (!member) return;
    titles.set(member.member_id, [...(titles.get(member.member_id) ?? []), title]);
  };
  const unique = (best: MemberEffort[], score: (m: MemberEffort) => number) =>
    best.filter((m) => score(m) === score(best[0])).length === 1 ? best[0] : undefined;

  if (data.members.length < 2) return titles;
  const bySpent = [...data.members].sort((a, b) => a.tokens_spent - b.tokens_spent);
  give(unique(bySpent, (m) => m.tokens_spent), "🐉 The Token Hoarder");

  const byEffort = [...data.members].sort((a, b) => b.effort - a.effort);
  give(unique(byEffort, (m) => m.effort), "🛡️ Guild Tank");

  const buyers = data.members.filter((m) => m.tokens_spent > 0 && m.effort > 0);
  const rate = (m: MemberEffort) => m.tokens_spent / m.effort;
  const byRate = buyers.sort((a, b) => rate(a) - rate(b));
  if (byRate.length) give(unique(byRate, rate), "🛒 Bargain Hunter");

  const assignedCount = (m: MemberEffort) =>
    data.chores.filter((c) => c.assigned_member_id === m.member_id && c.assigned_via === "FINISH").length;
  const byAssigned = [...data.members].sort((a, b) => assignedCount(b) - assignedCount(a));
  if (assignedCount(byAssigned[0]) > 0) give(unique(byAssigned, assignedCount), "🧲 Guild's Pick");

  return titles;
}

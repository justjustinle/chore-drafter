// /h/:id: loads the household and shows the screen for its phase / week status.
// Which screen shows is decided ONLY by what the API returns, never by local flags.

import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { Game, useApi, type GameContext } from "../api/context";
import { useLive } from "../api/live";
import { membershipFor } from "../api/session";
import type { Chore, Household } from "../api/types";
import { friendlyError } from "../components/errors";
import { Window } from "../components/ui";
import Auction from "../screens/Auction";
import BetweenWeeks from "../screens/BetweenWeeks";
import Estimation from "../screens/Estimation";
import History from "../screens/History";
import OpenWeek from "../screens/OpenWeek";
import QuestWeek from "../screens/QuestWeek";
import Reveal from "../screens/Reveal";
import Setup from "../screens/Setup";

export default function HouseholdPage({ tab = "guild" }: { tab?: "guild" | "history" }) {
  const id = Number(useParams().id);
  const membership = membershipFor(id);

  if (!membership) {
    return (
      <Window title="🚪 You're not in this guild on this device">
        <p>Open your invite link, or paste your key on the front page.</p>
        <Link to="/">Back to the front door</Link>
      </Window>
    );
  }
  return <HouseholdView id={id} tab={tab} apiKey={membership.key} memberId={membership.memberId} />;
}

/** The household screens for one membership. Also used by the /demo pages. */
export function HouseholdView({
  id,
  tab,
  apiKey,
  memberId,
  linkBase,
}: {
  id: number;
  tab: "guild" | "history";
  apiKey: string;
  memberId: number;
  /** Set by the demo pages, which have their own navigation. */
  linkBase?: string;
}) {
  const api = useApi();
  const live = useLive(() => api.household(apiKey, id), 2000, [id, apiKey]);
  const household = live.data;
  const reveal = useEstimationReveal(household);

  const game = useMemo<GameContext | null>(() => {
    if (!household) return null;
    const names = new Map(household.members.map((m) => [m.id, m.display_name]));
    return {
      api,
      key: apiKey,
      memberId,
      household,
      isOwner: household.owner_member_id === memberId,
      refreshHousehold: live.refresh,
      nameOf: (member) => (member == null ? "nobody" : member === memberId ? "You" : names.get(member) ?? "someone"),
    };
  }, [api, apiKey, memberId, household, live.refresh]);

  if (!game) {
    if (live.error) {
      const forbidden = live.error instanceof ApiError && [401, 403].includes(live.error.status);
      return (
        <Window title={forbidden ? "🗝️ That key doesn't open this guild" : "🌧️ Can't load the guild"}>
          <p>{friendlyError(live.error)}</p>
          <Link to="/">Back to the front door</Link>
        </Window>
      );
    }
    return <p className="subtle">Opening the guild hall…</p>;
  }

  return (
    <Game.Provider value={game}>
      <div className="topbar" style={{ marginTop: -6 }}>
        <div>
          <h1 style={{ margin: 0 }}>{game.household.name}</h1>
          <span className="subtle">{phaseLabel(game.household)}</span>
        </div>
        {!linkBase && <nav className="tabs" aria-label="Guild sections">
          <Link className={`btn small ${tab === "guild" ? "" : "quiet"}`} to={`/h/${id}`}>
            Guild hall
          </Link>
          <Link className={`btn small ${tab === "history" ? "" : "quiet"}`} to={`/h/${id}/history`}>
            Chronicle
          </Link>
        </nav>}
      </div>
      {tab === "history" ? (
        <History />
      ) : reveal.chores ? (
        <Reveal chores={reveal.chores} onDone={reveal.dismiss} />
      ) : (
        <Screen household={game.household} />
      )}
    </Game.Provider>
  );
}

function Screen({ household }: { household: Household }) {
  if (household.phase === "SETUP") return <Setup />;
  if (household.phase === "ESTIMATION" || household.estimation_open) return <Estimation />;
  const week = household.current_week;
  if (!week) return <BetweenWeeks />;
  if (week.status === "OPEN") return <OpenWeek weekId={week.id} />;
  if (week.status === "AUCTION") return <Auction weekId={week.id} />;
  return <QuestWeek weekId={week.id} />;
}

function phaseLabel(household: Household): string {
  if (household.phase === "SETUP") return "Gathering the party";
  if (household.phase === "ESTIMATION" || household.estimation_open) return "Weighing the quests";
  const status = household.current_week?.status;
  if (status === "OPEN") return "A new week dawns";
  if (status === "AUCTION") return "The market is open!";
  if (status === "ASSIGNED") return "Quest week";
  return "Resting between weeks";
}

/** When a voting round closes, show the flip-reveal of the new effort points once. */
function useEstimationReveal(household: Household | undefined) {
  const wasVoting = useRef<boolean | null>(null);
  const [chores, setChores] = useState<Chore[] | null>(null);
  useEffect(() => {
    if (!household) return;
    const voting = household.phase === "ESTIMATION" || household.estimation_open;
    if (wasVoting.current === true && !voting) setChores(household.chores);
    wasVoting.current = voting;
    // If the game moves on (the market opens) while the reveal is still up,
    // step aside so nobody misses their turn.
    if (household.current_week?.status === "AUCTION") setChores(null);
  }, [household]);
  return { chores, dismiss: () => setChores(null) };
}

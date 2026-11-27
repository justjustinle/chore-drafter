// Week status AUCTION: the live market. Polls GET /weeks/{id}/auction every second.

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { useGame } from "../api/context";
import { useLive } from "../api/live";
import type { AuctionState, MemberTokens, WeekChore } from "../api/types";
import { errorTone, fieldErrors, friendlyError } from "../components/errors";
import { Avatar, Modal, Pips, TipButton, Tokens, Window, flavourFor, useReducedMotion, useToast } from "../components/ui";
import { diffAuction, type CrierEvent } from "./auctionEvents";

const BID_STEPS = [
  { label: "+1", add: 1, key: "1" },
  { label: "+5", add: 5, key: "2" },
  { label: "+10", add: 10, key: "3" },
];

export default function Auction({ weekId }: { weekId: number }) {
  const game = useGame();
  const { api, key, memberId, isOwner, nameOf, refreshHousehold } = game;
  const toast = useToast();
  const reducedMotion = useReducedMotion();

  const live = useLive(() => api.auction(key, weekId), 1000, [weekId]);
  const state = live.data;

  // ---------- Effects derived from comparing polls ----------
  const previous = useRef<AuctionState>();
  const [events, setEvents] = useState<CrierEvent[]>([]);
  const [popups, setPopups] = useState<{ id: number; text: string }[]>([]);
  const [stamp, setStamp] = useState<string | null>(null);
  const clockOffset = useRef(0); // server time minus local time, in ms

  useEffect(() => {
    if (!state) return;
    clockOffset.current = new Date(state.server_time).getTime() - Date.now();
    const before = previous.current;
    const fresh = diffAuction(before, state, nameOf);
    if (fresh.length) setEvents((current) => [...fresh.reverse(), ...current].slice(0, 12));

    if (before?.lot && state.lot && before.lot.lot_id === state.lot.lot_id && state.lot.high_bid > before.lot.high_bid && !reducedMotion) {
      const id = Date.now();
      const rise = state.lot.high_bid - before.lot.high_bid;
      setPopups((p) => [...p, { id, text: `+${rise}!` }, { id: id + 1, text: `${state.lot!.high_bid} Tokens!` }]);
      window.setTimeout(() => setPopups((p) => p.filter((x) => x.id !== id && x.id !== id + 1)), 1300);
    }
    if (before && state.sold_chores.length > before.sold_chores.length) {
      setStamp("CLAIMED!");
      window.setTimeout(() => setStamp(null), 1600);
    }
    previous.current = state;
    // When the auction ends, the household's week status changes: refresh it
    // so the page moves on to the quest week.
    if (state.status !== "AUCTION") refreshHousehold();
  }, [state, nameOf, reducedMotion, refreshHousehold]);

  // ---------- Actions ----------
  const [busy, setBusy] = useState(false);
  const act = useCallback(
    async (action: () => Promise<unknown>) => {
      if (busy) return;
      setBusy(true);
      try {
        await action();
      } catch (error) {
        if (error instanceof ApiError && error.status === 422) {
          toast(Object.values(fieldErrors(error))[0] ?? error.detail, "warn");
        } else {
          toast(friendlyError(error), errorTone(error));
        }
      } finally {
        setBusy(false);
        await live.refresh(); // after success or a 409, show the latest state
      }
    },
    [busy, toast, live],
  );

  const me = state?.members.find((m) => m.member_id === memberId);
  const lot = state?.lot;
  const myBidTurn = !!lot && lot.turn_member_id === memberId;
  const myNominationTurn = !!state?.nomination && state.nomination.member_id === memberId && !lot;

  const bid = useCallback(
    (amount: number) => lot && act(() => api.bid(key, weekId, amount, lot.turn_number)),
    [act, api, key, weekId, lot],
  );
  const pass = useCallback(() => lot && act(() => api.pass(key, weekId, lot.turn_number)), [act, api, key, weekId, lot]);

  // ---------- Keyboard: Space / 1 = +1, 2 = +5, 3 = +10, A = all-in, P = pass ----------
  useEffect(() => {
    if (!myBidTurn || !lot || !me) return;
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (["INPUT", "TEXTAREA"].includes(target.tagName) || event.repeat) return;
      const affordable = (amount: number) => amount <= me.tokens_left;
      let amount: number | null = null;
      if (event.key === " " || event.key === "1") amount = lot.high_bid + 1;
      else if (event.key === "2") amount = lot.high_bid + 5;
      else if (event.key === "3") amount = lot.high_bid + 10;
      else if (event.key.toLowerCase() === "a") amount = me.tokens_left;
      else if (event.key.toLowerCase() === "p") {
        event.preventDefault();
        pass();
        return;
      }
      if (amount !== null) {
        event.preventDefault();
        if (amount > lot.high_bid && affordable(amount)) bid(amount);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [myBidTurn, lot, me, bid, pass]);

  // ---------- Owner fallback ----------
  const [confirmFinish, setConfirmFinish] = useState(false);
  const [guide, setGuide] = useState(false);
  const [openFrame, setOpenFrame] = useState<MemberTokens | null>(null);

  if (!state) return <p className="subtle">Opening the market stalls…</p>;

  const totalChores = state.sold_chores.length + state.unsold_chores.length;
  const totalEffort = [...state.sold_chores, ...state.unsold_chores].reduce((sum, c) => sum + c.effort_points, 0);

  return (
    <div>
      <div className="banner">
        <h1>
          🏪 The Sunday Market · <span className="num">Lot {state.sold_chores.length + (lot ? 1 : 0)}</span>
          <span className="subtle num" style={{ fontSize: "1rem" }}>
            {" "}
            · {state.unsold_chores.length} of {totalChores} chores left
          </span>
        </h1>
        <div className="row">
          <button type="button" className="btn quiet small" onClick={() => setGuide(true)}>
            📖 Guidebook
          </button>
          {isOwner && (
            <button type="button" className="btn gold small" onClick={() => setConfirmFinish(true)}>
              🏰 The Guild Assigns
            </button>
          )}
        </div>
      </div>

      <div className="ticker" aria-label="Town crier">
        {events.length === 0 ? (
          <span style={{ paddingLeft: 16 }}>📣 Hear ye! The market is open.</span>
        ) : (
          // Newest first: each new event slides in at the front of the ribbon.
          <div className="ticker-track" aria-live="polite">
            {events.map((event, i) => (
              <span key={event.id} className={i === 0 ? "ticker-new" : "subtle"}>
                {event.kind === "sold" ? "🏆" : event.kind === "pass" ? "🙅" : event.kind === "finish" ? "🏰" : "📣"} {event.text}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="auction-layout">
        <div>
          <Window className="pedestal">
            {stamp && !reducedMotion && <Confetti />}
            {stamp && (
              <div className="stamp" role="status">
                <span>{stamp}</span>
              </div>
            )}
            {popups.map((popup, i) => (
              <span key={popup.id} className="popup" style={{ marginLeft: i % 2 ? 130 : -120 }} aria-hidden="true">
                {popup.text}
              </span>
            ))}

            {lot ? (
              <>
                <div className="scroll-card">
                  <div className="name">{lot.chore_name}</div>
                  <div className="flavour subtle">{flavourFor(lot.chore_id)}</div>
                  {lot.chore_description && <p style={{ margin: "6px 0" }}>{lot.chore_description}</p>}
                  <div className="row" style={{ justifyContent: "center" }}>
                    <strong className="num">{lot.effort_points} effort</strong>
                    <Pips value={lot.effort_points} />
                  </div>
                </div>
                <div className="subtle">High bid</div>
                <div className="high-bid" aria-live="polite">
                  {lot.high_bid}
                </div>
                <div className="row" style={{ justifyContent: "center", marginTop: 6 }}>
                  <Avatar memberId={lot.high_bidder_id} name={displayName(state, lot.high_bidder_id)} crown />
                  <strong>{nameOf(lot.high_bidder_id)}</strong> leads
                </div>

                <TurnTimer deadline={lot.turn_deadline} offset={clockOffset.current} />

                {myBidTurn && me ? (
                  <div className="controls" role="group" aria-label="Your bid">
                    {BID_STEPS.map((step) => {
                      const amount = lot.high_bid + step.add;
                      const tooMuch = amount > me.tokens_left;
                      return (
                        <TipButton
                          key={step.label}
                          className="btn gold"
                          disabled={tooMuch || busy}
                          tip={tooMuch ? `You only have ${me.tokens_left} tokens` : undefined}
                          onClick={() => bid(amount)}
                          aria-keyshortcuts={step.key}
                        >
                          {step.label} <span className="num">({amount})</span> <span className="kbd">{step.key}</span>
                        </TipButton>
                      );
                    })}
                    <TipButton
                      className="btn gold"
                      disabled={me.tokens_left <= lot.high_bid || busy}
                      tip={me.tokens_left <= lot.high_bid ? "All your tokens wouldn't beat the high bid" : undefined}
                      onClick={() => bid(me.tokens_left)}
                      aria-keyshortcuts="A"
                    >
                      All-In <span className="num">({me.tokens_left})</span> <span className="kbd">A</span>
                    </TipButton>
                    <button type="button" className="btn quiet" disabled={busy} onClick={pass} aria-keyshortcuts="P">
                      Pass <span className="kbd">P</span>
                    </button>
                  </div>
                ) : (
                  <div className="speech">
                    {lot.passed_member_ids.includes(memberId)
                      ? "You passed on this one. "
                      : lot.high_bidder_id === memberId
                        ? "You're in the lead! "
                        : ""}
                    Waiting for {nameOf(lot.turn_member_id)}…
                  </div>
                )}
              </>
            ) : state.nomination ? (
              myNominationTurn ? (
                <Nominate
                  chores={state.unsold_chores}
                  tokensLeft={me?.tokens_left ?? 0}
                  busy={busy}
                  deadline={state.nomination.deadline}
                  offset={clockOffset.current}
                  onNominate={(choreId, openingBid) =>
                    act(() => api.nominate(key, weekId, choreId, openingBid, state.nomination!.turn_number))
                  }
                />
              ) : (
                <>
                  <h2>📜 {nameOf(state.nomination.member_id)} is choosing a quest to put up…</h2>
                  <TurnTimer deadline={state.nomination.deadline} offset={clockOffset.current} />
                </>
              )
            ) : (
              <h2>🎉 Every quest has a hero!</h2>
            )}
          </Window>

          <Window title="🗂️ Quest queue">
            {state.unsold_chores.length === 0 ? (
              <p className="subtle">Nothing left to auction.</p>
            ) : (
              <div className="cards">
                {state.unsold_chores
                  .filter((chore) => chore.chore_id !== lot?.chore_id)
                  .map((chore) => (
                    <div className="quest-card" key={chore.id}>
                      <div className="name">{chore.name}</div>
                      <div className="row">
                        <span className="num">{chore.effort_points}</span>
                        <Pips value={chore.effort_points} />
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </Window>
        </div>

        <Window title="⚔️ Party">
          <div className="party">
            {state.members.map((member) => (
              <PartyFrame
                key={member.member_id}
                member={member}
                state={state}
                you={member.member_id === memberId}
                totalEffort={totalEffort}
                onOpen={() => setOpenFrame(member)}
              />
            ))}
          </div>
        </Window>
      </div>

      {openFrame && (
        <QuestLog member={openFrame} chores={state.sold_chores} you={openFrame.member_id === memberId} onClose={() => setOpenFrame(null)} />
      )}

      {guide && (
        <Modal title="📖 The Market Guidebook" onClose={() => setGuide(false)}>
          <ul>
            <li>Everyone starts the week with 100 tokens. Unspent tokens vanish when the week ends.</li>
            <li>On your nomination turn, pick a chore and make an opening bid of at least 1. You must nominate.</li>
            <li>Every time a chore is nominated, everyone gets 1 extra token, so you can always open.</li>
            <li>Bidding goes round the table. Bid higher than the current high bid, or pass. Once you pass, you're out for that chore.</li>
            <li>If you can't afford to beat the high bid, you pass automatically.</li>
            <li>The chore is sold when everyone else has passed. The winner pays their bid.</li>
            <li>Each turn has 30 seconds. Running out of time counts as a pass.</li>
            <li>If the market can't finish, the guild owner can assign what's left so everyone's effort evens out.</li>
          </ul>
          <p className="subtle">
            Keyboard on your turn: <span className="kbd">Space</span> or <span className="kbd">1</span> +1,{" "}
            <span className="kbd">2</span> +5, <span className="kbd">3</span> +10, <span className="kbd">A</span> All-In,{" "}
            <span className="kbd">P</span> Pass.
          </p>
        </Modal>
      )}

      {confirmFinish && (
        <Modal title="🏰 Let the guild assign the rest?" onClose={() => setConfirmFinish(false)}>
          <p>
            Use this if the market can't finish. Any chore being bid on now goes to its current high bidder, and every
            remaining chore is shared out by the guild so effort evens out.
          </p>
          <div className="row">
            <button
              type="button"
              className="btn gold"
              disabled={busy}
              onClick={async () => {
                await act(() => api.finish(key, weekId));
                setConfirmFinish(false);
                await refreshHousehold();
              }}
            >
              {busy ? "Assigning…" : "Assign the rest"}
            </button>
            <button type="button" className="btn quiet" onClick={() => setConfirmFinish(false)}>
              Keep bidding
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ---------- Turn timer: drains towards the SERVER's deadline ----------

function TurnTimer({ deadline, offset }: { deadline: string; offset: number }) {
  const [now, setNow] = useState(() => Date.now() + offset);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now() + offset), 200);
    return () => window.clearInterval(timer);
  }, [offset]);

  const end = new Date(deadline).getTime();
  const left = Math.max(0, end - now);
  const seconds = Math.ceil(left / 1000);
  // The bar's full width is the turn length, worked out from the deadline the
  // server sent when the turn started (never a local 30-second countdown).
  const total = useRef<{ deadline: string; length: number }>();
  if (!total.current || total.current.deadline !== deadline) {
    total.current = { deadline, length: Math.max(left, 1000) };
  }
  const fraction = Math.min(1, left / total.current.length);
  const urgent = seconds <= 10;

  return (
    <div>
      <div
        className={`timer${urgent ? " urgent" : ""}`}
        role="timer"
        aria-label={left > 0 ? `${seconds} seconds left` : "Time's up, waiting for the server"}
      >
        <div className="timer-fill" style={{ width: `${fraction * 100}%` }} />
      </div>
      <div className="timer-label" style={{ color: urgent ? "#c2410c" : undefined }}>
        {left > 0 ? `⏳ ${seconds}s${urgent ? " · hurry!" : ""}` : "⌛ Waiting…"}
      </div>
    </div>
  );
}

// ---------- Nomination turn ----------

function Nominate({
  chores,
  tokensLeft,
  busy,
  deadline,
  offset,
  onNominate,
}: {
  chores: WeekChore[];
  tokensLeft: number;
  busy: boolean;
  deadline: string;
  offset: number;
  onNominate: (choreId: number, openingBid: number) => void;
}) {
  const [choreId, setChoreId] = useState<number | null>(null);
  const [opening, setOpening] = useState("1");
  const [error, setError] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const amount = Number(opening);
    if (!Number.isInteger(amount) || amount < 1) {
      setError("Open with at least 1 token");
      return;
    }
    if (choreId == null) return;
    setError("");
    onNominate(choreId, amount);
  }

  return (
    <div>
      <h2>📜 Choose a quest to put up!</h2>
      <TurnTimer deadline={deadline} offset={offset} />
      <div className="cards" style={{ margin: "12px 0", textAlign: "left" }}>
        {chores.map((chore) => (
          <button
            type="button"
            key={chore.id}
            className={`quest-card clickable${choreId === chore.chore_id ? " selected" : ""}`}
            aria-pressed={choreId === chore.chore_id}
            onClick={() => setChoreId(chore.chore_id)}
            style={{ font: "inherit", color: "inherit", textAlign: "left" }}
          >
            <div className="name">{chore.name}</div>
            <div className="row">
              <span className="num">{chore.effort_points}</span>
              <Pips value={chore.effort_points} />
            </div>
          </button>
        ))}
      </div>
      {choreId != null && (
        <form onSubmit={submit} className="row" style={{ justifyContent: "center" }}>
          <label htmlFor="opening-bid" style={{ margin: 0 }}>
            Opening bid
          </label>
          <input
            id="opening-bid"
            type="number"
            min={1}
            value={opening}
            onChange={(e) => setOpening(e.target.value)}
            style={{ width: 110 }}
            aria-describedby="opening-hint"
          />
          <button className="btn green" type="submit" disabled={busy}>
            Nominate
          </button>
          <div id="opening-hint" className="subtle" style={{ width: "100%" }}>
            You have <Tokens value={tokensLeft} />, plus the 1 everyone gets when you nominate.
          </div>
          {error && <div className="field-error">{error}</div>}
        </form>
      )}
    </div>
  );
}

// ---------- Party frames ----------

function PartyFrame({
  member,
  state,
  you,
  totalEffort,
  onOpen,
}: {
  member: MemberTokens;
  state: AuctionState;
  you: boolean;
  totalEffort: number;
  onOpen: () => void;
}) {
  const lot = state.lot;
  const nominating = !lot && state.nomination?.member_id === member.member_id;
  const bidding = lot?.turn_member_id === member.member_id;
  const passed = lot?.passed_member_ids.includes(member.member_id);
  const leading = lot?.high_bidder_id === member.member_id;
  const active = nominating || bidding;

  let chip = <span className="chip grey">Waiting</span>;
  if (active && you) chip = <span className="chip blue">⭐ Your turn</span>;
  else if (nominating) chip = <span className="chip blue">📜 Nominating</span>;
  else if (bidding) chip = <span className="chip blue">💬 Bidding</span>;
  else if (leading) chip = <span className="chip gold">👑 High bidder</span>;
  else if (passed) chip = <span className="chip grey">🙅 Passed</span>;
  else if (member.tokens_left === 0) chip = <span className="chip tangerine">🪙 Out of tokens</span>;

  const share = totalEffort ? Math.round((member.effort_won / totalEffort) * 100) : 0;

  return (
    <button type="button" className={`frame${active ? " active" : ""}`} onClick={onOpen} aria-label={`${member.display_name}: open quest log`}>
      <Avatar memberId={member.member_id} name={member.display_name} crown={leading} />
      <div className="who">
        <strong>{you ? `${member.display_name} (you)` : member.display_name}</strong>
        {chip}
      </div>
      <div className="stats">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <Tokens value={member.tokens_left} />
          <span className="subtle num" style={{ fontSize: "0.85rem" }}>
            {member.effort_won} effort won
          </span>
        </div>
        <div className="workload" role="img" aria-label={`${member.effort_won} of ${totalEffort} effort this week`}>
          <div className="workload-fill" style={{ width: `${share}%` }} />
        </div>
      </div>
    </button>
  );
}

function QuestLog({
  member,
  chores,
  you,
  onClose,
}: {
  member: MemberTokens;
  chores: WeekChore[];
  you: boolean;
  onClose: () => void;
}) {
  const won = chores.filter((chore) => chore.assigned_member_id === member.member_id);
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="window drawer" role="dialog" aria-label={`${member.display_name}'s quest log`} onClick={(e) => e.stopPropagation()}>
        <div className="window-title">
          <h2>📒 {you ? "Your" : `${member.display_name}'s`} quest log</h2>
          <button type="button" className="btn quiet small" onClick={onClose}>
            Close
          </button>
        </div>
        {won.length === 0 ? (
          <p className="subtle">No quests claimed yet.</p>
        ) : (
          <ul className="list">
            {won.map((chore) => (
              <li key={chore.id}>
                <div style={{ flex: 1 }}>
                  <strong>{chore.name}</strong>
                  <div className="subtle num">{chore.effort_points} effort</div>
                </div>
                {chore.price_paid != null ? <Tokens value={chore.price_paid} /> : <span className="chip grey">Assigned</span>}
              </li>
            ))}
          </ul>
        )}
      </aside>
    </div>
  );
}

function Confetti() {
  const colours = ["#facc15", "#4ade80", "#38bdf8", "#fb923c", "#c4b5fd"];
  return (
    <>
      {Array.from({ length: 24 }, (_, i) => (
        <span
          key={i}
          className="confetti"
          aria-hidden="true"
          style={{
            left: `${(i * 37) % 100}%`,
            background: colours[i % colours.length],
            animationDelay: `${(i % 6) * 0.06}s`,
          }}
        />
      ))}
    </>
  );
}

/** The member's real name (for avatars), where nameOf() says "You" for yourself. */
function displayName(state: AuctionState, memberId: number): string {
  return state.members.find((m) => m.member_id === memberId)?.display_name ?? "?";
}

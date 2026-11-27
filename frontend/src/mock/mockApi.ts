// A pretend backend for the /demo pages. It returns JSON shaped exactly like
// the real API (see src/api/types.ts), so every screen can be designed and
// checked without running FastAPI. The auction scenario ticks along on its
// own so the timer, popups, ticker and stamps can be seen in motion.

import type { Api } from "../api/client";
import type {
  Assignments,
  AuctionState,
  Chore,
  EstimationStatus,
  HistoryWeek,
  Household,
  Member,
  WeekChore,
} from "../api/types";

export type Scenario = "setup" | "estimation" | "open-week" | "auction" | "quest-week" | "history";

const now = () => new Date().toISOString();
const YOU = 1;

const MEMBERS: Member[] = [
  { id: 1, display_name: "Justin", email: "justin@example.com", turn_order: 1, joined_at: now() },
  { id: 2, display_name: "Sam", email: "sam@example.com", turn_order: 2, joined_at: now() },
  { id: 3, display_name: "Jordan", email: "jordan@example.com", turn_order: 3, joined_at: now() },
  { id: 4, display_name: "Alex", email: "alex@example.com", turn_order: 4, joined_at: now() },
];

const CHORE_LIST: [string, string | null, number][] = [
  ["Bins", "Tuesday night, both bins", 2],
  ["Bathroom", "Toilet, sink, shower and mirror", 8],
  ["Hoovering", "Every room downstairs", 5],
  ["Mopping", "Kitchen and hall", 4],
  ["Dishes", "Clear the rack every evening", 6],
  ["Laundry", null, 3],
];

function chores(estimated: boolean): Chore[] {
  return CHORE_LIST.map(([name, description, effort], i) => ({
    id: i + 1,
    household_id: 1,
    name,
    description,
    effort_points: estimated ? effort : null,
    created_by: 1,
  }));
}

function weekChores(): WeekChore[] {
  return chores(true).map((c) => ({
    id: c.id,
    chore_id: c.id,
    name: c.name,
    description: c.description,
    effort_points: c.effort_points!,
    assigned_member_id: null,
    assigned_via: null,
    price_paid: null,
    done_at: null,
  }));
}

function household(scenario: Scenario): Household {
  const phase = scenario === "setup" ? "SETUP" : scenario === "estimation" ? "ESTIMATION" : "ACTIVE";
  const status =
    scenario === "open-week" ? "OPEN" : scenario === "auction" ? "AUCTION" : scenario === "quest-week" ? "ASSIGNED" : null;
  return {
    id: 1,
    name: "Maple Cottage",
    phase,
    owner_member_id: YOU,
    created_at: now(),
    members: scenario === "setup" ? MEMBERS.slice(0, 3) : MEMBERS,
    chores: chores(phase === "ACTIVE"),
    current_week: status ? { id: 1, starts_on: "2026-11-29", status } : null,
    estimation_open: phase === "ESTIMATION",
  };
}

// ---------- The auction, simulated from the clock ----------

const START = Date.now();
const TURN = 8000; // demo turns are 8 seconds so things move

function auctionAt(ms: number): AuctionState {
  const all = weekChores();
  const turnIndex = Math.floor(ms / TURN);
  const lotLength = 6; // each demo lot: nomination turn, 4 bids/passes, sale
  const lotIndex = Math.min(Math.floor(turnIndex / lotLength), all.length);
  const step = turnIndex % lotLength;
  const order = MEMBERS.map((m) => m.id);

  const sold = all.slice(0, lotIndex).map((c, i) => ({
    ...c,
    assigned_member_id: order[(i + 1) % order.length],
    assigned_via: "AUCTION" as const,
    price_paid: 4 + i * 3,
  }));
  const spent = (id: number) => sold.filter((c) => c.assigned_member_id === id).reduce((s, c) => s + (c.price_paid ?? 0), 0);
  const effort = (id: number) => sold.filter((c) => c.assigned_member_id === id).reduce((s, c) => s + c.effort_points, 0);
  const nominated = lotIndex + (step > 0 ? 1 : 0);
  const members = MEMBERS.map((m) => ({
    member_id: m.id,
    display_name: m.display_name,
    tokens_left: 100 + nominated - spent(m.id),
    effort_won: effort(m.id),
  }));
  const deadline = new Date(START + (turnIndex + 1) * TURN).toISOString();

  if (lotIndex >= all.length) {
    return { week_id: 1, status: "ASSIGNED", nomination: null, lot: null, members, unsold_chores: [], sold_chores: sold, server_time: now() };
  }
  const unsold = all.slice(lotIndex);
  const nominator = order[lotIndex % order.length];
  if (step === 0) {
    return {
      week_id: 1,
      status: "AUCTION",
      nomination: { member_id: nominator, turn_number: lotIndex + 1, deadline },
      lot: null,
      members,
      unsold_chores: unsold,
      sold_chores: sold,
      server_time: now(),
    };
  }
  const chore = unsold[0];
  const bidder = (k: number) => order[(order.indexOf(nominator) + k) % order.length];
  const high = 3 + (step - 1) * 2;
  return {
    week_id: 1,
    status: "AUCTION",
    nomination: null,
    lot: {
      lot_id: lotIndex + 1,
      chore_id: chore.chore_id,
      chore_name: chore.name,
      chore_description: chore.description,
      effort_points: chore.effort_points,
      nominated_by: nominator,
      high_bid: high,
      high_bidder_id: bidder(step - 1),
      turn_member_id: bidder(step),
      turn_number: step,
      turn_deadline: deadline,
      passed_member_ids: step >= 4 ? [bidder(1)] : [],
    },
    members,
    unsold_chores: unsold,
    sold_chores: sold,
    server_time: now(),
  };
}

function assignments(): Assignments {
  const owners = [2, 1, 3, 4, 1, 3];
  const chores = weekChores().map((c, i) => ({
    ...c,
    assigned_member_id: owners[i],
    assigned_via: (i % 3 === 2 ? "FINISH" : "AUCTION") as "FINISH" | "AUCTION",
    price_paid: i % 3 === 2 ? null : 3 + i * 4,
    done_at: i === 1 ? now() : null,
  }));
  return {
    week_id: 1,
    status: "ASSIGNED",
    chores,
    members: MEMBERS.map((m) => {
      const mine = chores.filter((c) => c.assigned_member_id === m.id);
      return {
        member_id: m.id,
        display_name: m.display_name,
        effort: mine.reduce((s, c) => s + c.effort_points, 0),
        tokens_spent: mine.reduce((s, c) => s + (c.price_paid ?? 0), 0),
      };
    }),
  };
}

const HISTORY: HistoryWeek[] = [
  {
    week_id: 1,
    starts_on: "2026-11-22",
    chores: [
      { name: "Bathroom", effort_points: 8, assigned_to: "Sam", assigned_via: "AUCTION", price_paid: 12, done: true },
      { name: "Bins", effort_points: 2, assigned_to: "Justin", assigned_via: "AUCTION", price_paid: 3, done: true },
      { name: "Dishes", effort_points: 6, assigned_to: "Jordan", assigned_via: "FINISH", price_paid: null, done: false },
    ],
  },
];

export function mockApi(scenario: Scenario): Api {
  const votes = new Set<number>([1, 2]);
  const ok = <T>(value: T) => new Promise<T>((resolve) => window.setTimeout(() => resolve(value), 120));
  const estimation = (): EstimationStatus => ({
    round_id: 1,
    week_id: null,
    opened_at: now(),
    chore_ids: chores(false).map((c) => c.id),
    voters: MEMBERS.map((m) => ({
      member_id: m.id,
      display_name: m.display_name,
      voted_chore_ids: m.id === YOU ? [...votes] : m.id === 2 ? [1, 2, 3, 4, 5, 6] : [1],
      done: m.id === 2,
    })),
  });

  return {
    me: () => ok({ member_id: YOU, household_id: 1, household_name: "Maple Cottage", display_name: "Justin", is_owner: true }),
    createHousehold: () => ok({ ...household("setup"), api_key: "cd_demo" }),
    acceptInvite: () => ok({ ...MEMBERS[1], api_key: "cd_demo" }),
    household: () => ok(household(scenario)),
    invite: (_k, _h, email) =>
      ok({ id: 1, household_id: 1, email, expires_at: now(), link: "http://localhost:8000/invites/demo-token-abc123/accept" }),
    addChore: () => ok({}),
    startEstimation: () => ok(estimation()),
    estimation: () => ok(estimation()),
    vote: (_k, _h, choreId, points) => {
      votes.add(choreId);
      return ok({ chore_id: choreId, points, estimation_closed: false });
    },
    forceClose: () => ok({}),
    openWeek: () => ok({ id: 1, household_id: 1, starts_on: "2026-11-29", status: "OPEN", chores: weekChores(), flagged_chore_ids: [] }),
    week: () => ok({ id: 1, household_id: 1, starts_on: "2026-11-29", status: "OPEN", chores: weekChores(), flagged_chore_ids: [2] }),
    flag: () => ok({}),
    startReEstimation: () => ok(estimation()),
    startAuction: () => ok(auctionAt(Date.now() - START)),
    auction: () => ok(auctionAt(Date.now() - START)),
    nominate: () => ok(auctionAt(Date.now() - START)),
    bid: () => ok(auctionAt(Date.now() - START)),
    pass: () => ok(auctionAt(Date.now() - START)),
    finish: () => ok(assignments()),
    assignments: () => ok(assignments()),
    markDone: () => ok(weekChores()[0]),
    closeWeek: () => ok({ id: 1, household_id: 1, starts_on: "2026-11-29", status: "CLOSED", chores: weekChores(), flagged_chore_ids: [] }),
    history: () => ok(HISTORY),
  };
}

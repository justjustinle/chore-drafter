// The Town Crier. There is no events endpoint, so events are worked out by
// comparing each poll of the auction state with the one before it.
// This only DESCRIBES what changed; it never decides anything.

import type { AuctionState } from "../api/types";

export interface CrierEvent {
  id: string;
  text: string;
  kind: "open" | "bid" | "pass" | "sold" | "finish" | "turn";
}

export function diffAuction(
  before: AuctionState | undefined,
  after: AuctionState,
  nameOf: (memberId: number | null | undefined) => string,
): CrierEvent[] {
  if (!before) return [];
  const events: CrierEvent[] = [];
  const at = after.server_time;

  // A chore finished selling (or was assigned by the owner's finish).
  const soldBefore = new Set(before.sold_chores.map((c) => c.id));
  for (const chore of after.sold_chores) {
    if (soldBefore.has(chore.id)) continue;
    if (chore.assigned_via === "FINISH") {
      events.push({ id: `finish-${chore.id}`, kind: "finish", text: `The guild assigns ${chore.name} to ${nameOf(chore.assigned_member_id)}` });
    } else {
      events.push({
        id: `sold-${chore.id}`,
        kind: "sold",
        text: `${chore.name} sold to ${nameOf(chore.assigned_member_id)} for ${chore.price_paid}!`,
      });
    }
  }

  const lot = after.lot;
  const sameLot = lot && before.lot && before.lot.lot_id === lot.lot_id;

  // A new chore went up.
  if (lot && !sameLot) {
    events.push({
      id: `open-${lot.lot_id}`,
      kind: "open",
      text: `${nameOf(lot.nominated_by)} opened ${lot.chore_name} at ${lot.high_bid}!`,
    });
  }

  if (lot && sameLot && before.lot) {
    if (lot.high_bid > before.lot.high_bid) {
      events.push({ id: `bid-${lot.lot_id}-${lot.high_bid}`, kind: "bid", text: `${nameOf(lot.high_bidder_id)} bid ${lot.high_bid}` });
    }
    const passedBefore = new Set(before.lot.passed_member_ids);
    for (const member of lot.passed_member_ids) {
      if (!passedBefore.has(member)) events.push({ id: `pass-${lot.lot_id}-${member}`, kind: "pass", text: `${nameOf(member)} passed` });
    }
  }

  // A nomination turn was skipped because time ran out.
  if (
    !lot &&
    before.nomination &&
    after.nomination &&
    after.nomination.turn_number > before.nomination.turn_number &&
    before.sold_chores.length === after.sold_chores.length
  ) {
    events.push({ id: `skip-${after.nomination.turn_number}-${at}`, kind: "turn", text: `${nameOf(before.nomination.member_id)} ran out of time` });
  }

  return events;
}

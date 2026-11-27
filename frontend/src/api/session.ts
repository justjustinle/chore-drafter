// The API keys this browser holds: one per household membership.
//
// Keys live in localStorage so you stay "logged in" after a refresh. Every
// read and write is wrapped in try/catch because storage can be blocked
// (private windows, strict privacy settings); the app still works, you just
// have to paste your key again next time.

export interface Membership {
  householdId: number;
  householdName: string;
  memberId: number;
  displayName: string;
  key: string;
}

const STORAGE_KEY = "chore-draft.memberships";

export function loadMemberships(): Membership[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Membership[]) : [];
  } catch {
    return [];
  }
}

export function saveMembership(membership: Membership): void {
  const others = loadMemberships().filter((m) => m.householdId !== membership.householdId);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...others, membership]));
  } catch {
    // storage unavailable: the membership lasts until the tab closes
  }
}

export function forgetMembership(householdId: number): void {
  const rest = loadMemberships().filter((m) => m.householdId !== householdId);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(rest));
  } catch {
    // nothing to do
  }
}

export function membershipFor(householdId: number): Membership | undefined {
  return loadMemberships().find((m) => m.householdId === householdId);
}

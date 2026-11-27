// The shapes the FastAPI backend returns. They mirror app/schemas.py.
// If the backend changes a response, this is the file to update.

export type Phase = "SETUP" | "ESTIMATION" | "ACTIVE";
export type WeekStatus = "OPEN" | "AUCTION" | "ASSIGNED" | "CLOSED";
export type AssignedVia = "AUCTION" | "FINISH";

export interface Member {
  id: number;
  display_name: string;
  email: string;
  turn_order: number;
  joined_at: string;
}

export interface Chore {
  id: number;
  household_id: number;
  name: string;
  description: string | null;
  effort_points: number | null;
  created_by: number;
}

export interface WeekSummary {
  id: number;
  starts_on: string;
  status: WeekStatus;
}

export interface Household {
  id: number;
  name: string;
  phase: Phase;
  owner_member_id: number;
  created_at: string;
  members: Member[];
  chores: Chore[];
  current_week: WeekSummary | null;
  estimation_open: boolean;
}

export interface HouseholdCreated extends Household {
  api_key: string;
}

export interface MemberCreated extends Member {
  api_key: string;
}

export interface Me {
  member_id: number;
  household_id: number;
  household_name: string;
  display_name: string;
  is_owner: boolean;
}

export interface Invite {
  id: number;
  household_id: number;
  email: string;
  expires_at: string;
  link: string;
}

export interface VoterStatus {
  member_id: number;
  display_name: string;
  voted_chore_ids: number[];
  done: boolean;
}

export interface EstimationStatus {
  round_id: number;
  week_id: number | null;
  opened_at: string;
  chore_ids: number[];
  voters: VoterStatus[];
}

export interface VoteResult {
  chore_id: number;
  points: number;
  estimation_closed: boolean;
}

export interface WeekChore {
  id: number;
  chore_id: number;
  name: string;
  description: string | null;
  effort_points: number;
  assigned_member_id: number | null;
  assigned_via: AssignedVia | null;
  price_paid: number | null;
  done_at: string | null;
}

export interface Week {
  id: number;
  household_id: number;
  starts_on: string;
  status: WeekStatus;
  chores: WeekChore[];
  flagged_chore_ids: number[];
}

export interface NominationState {
  member_id: number;
  turn_number: number;
  deadline: string;
}

export interface LotState {
  lot_id: number;
  chore_id: number;
  chore_name: string;
  chore_description: string | null;
  effort_points: number;
  nominated_by: number;
  high_bid: number;
  high_bidder_id: number;
  turn_member_id: number;
  turn_number: number;
  turn_deadline: string;
  passed_member_ids: number[];
}

export interface MemberTokens {
  member_id: number;
  display_name: string;
  tokens_left: number;
  effort_won: number;
}

export interface AuctionState {
  week_id: number;
  status: WeekStatus;
  nomination: NominationState | null;
  lot: LotState | null;
  members: MemberTokens[];
  unsold_chores: WeekChore[];
  sold_chores: WeekChore[];
  server_time: string;
}

export interface MemberEffort {
  member_id: number;
  display_name: string;
  effort: number;
  tokens_spent: number;
}

export interface Assignments {
  week_id: number;
  status: WeekStatus;
  chores: WeekChore[];
  members: MemberEffort[];
}

export interface HistoryChore {
  name: string;
  effort_points: number;
  assigned_to: string | null;
  assigned_via: AssignedVia | null;
  price_paid: number | null;
  done: boolean;
}

export interface HistoryWeek {
  week_id: number;
  starts_on: string;
  chores: HistoryChore[];
}

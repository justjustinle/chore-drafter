// The one module that talks to the backend.
//
// Screens never call fetch() themselves: they call these functions. The
// `Api` interface is implemented twice: by `httpApi` (the real FastAPI
// backend) and by `mockApi` in src/mock/ (fixed JSON, for the /demo pages).

import type {
  Assignments,
  AuctionState,
  EstimationStatus,
  HistoryWeek,
  Household,
  HouseholdCreated,
  Invite,
  Me,
  MemberCreated,
  VoteResult,
  Week,
  WeekChore,
} from "./types";

// Where the API lives. On Vercel the API is served by the same project at
// /api, so a production build defaults to that. In development, the API runs
// separately on port 8000. VITE_API_URL overrides both.
export const API_URL: string =
  import.meta.env.VITE_API_URL ?? (import.meta.env.PROD ? "/api" : "http://localhost:8000");

/** An error response from the API, with its status code and message. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public fields: Record<string, string> = {},
  ) {
    super(detail);
  }
}

export interface Api {
  me(key: string): Promise<Me>;
  createHousehold(name: string, email: string, displayName: string): Promise<HouseholdCreated>;
  acceptInvite(token: string, displayName: string): Promise<MemberCreated>;
  household(key: string, id: number): Promise<Household>;
  invite(key: string, householdId: number, email: string): Promise<Invite>;
  addChore(key: string, householdId: number, name: string, description: string | null): Promise<unknown>;
  startEstimation(key: string, householdId: number): Promise<EstimationStatus>;
  estimation(key: string, householdId: number): Promise<EstimationStatus>;
  vote(key: string, householdId: number, choreId: number, points: number): Promise<VoteResult>;
  forceClose(key: string, householdId: number): Promise<unknown>;
  openWeek(key: string, householdId: number): Promise<Week>;
  week(key: string, weekId: number): Promise<Week>;
  flag(key: string, weekId: number, choreId: number): Promise<unknown>;
  startReEstimation(key: string, weekId: number): Promise<EstimationStatus>;
  startAuction(key: string, weekId: number): Promise<AuctionState>;
  auction(key: string, weekId: number): Promise<AuctionState>;
  nominate(key: string, weekId: number, choreId: number, openingBid: number, turn: number): Promise<AuctionState>;
  bid(key: string, weekId: number, amount: number, turn: number): Promise<AuctionState>;
  pass(key: string, weekId: number, turn: number): Promise<AuctionState>;
  finish(key: string, weekId: number): Promise<Assignments>;
  assignments(key: string, weekId: number): Promise<Assignments>;
  markDone(key: string, weekChoreId: number): Promise<WeekChore>;
  closeWeek(key: string, weekId: number): Promise<Week>;
  history(key: string, householdId: number): Promise<HistoryWeek[]>;
}

interface RequestOptions {
  method?: string;
  key?: string;
  body?: unknown;
  headers?: Record<string, string>;
  /** Set for auction actions: sent as Idempotency-Key, and reused if we retry. */
  idempotent?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { ...options.headers };
  if (options.key) headers["X-API-Key"] = options.key;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  // One key per user action. A retry of the same action must reuse it, so
  // the server can recognise the repeat and replay its first answer.
  if (options.idempotent) headers["Idempotency-Key"] = crypto.randomUUID();

  const send = () =>
    fetch(API_URL + path, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });

  let response: Response;
  try {
    response = await send();
  } catch (networkError) {
    // The request may or may not have reached the server. Only actions with
    // an idempotency key are safe to send again, and only with the SAME key.
    if (!options.idempotent) throw networkError;
    response = await send();
  }

  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}

async function toApiError(response: Response): Promise<ApiError> {
  let detail = response.statusText;
  const fields: Record<string, string> = {};
  try {
    const body = await response.json();
    if (typeof body.detail === "string") {
      detail = body.detail;
    } else if (Array.isArray(body.detail)) {
      // FastAPI 422: a list of {loc: ["body", "field"], msg: "..."}
      detail = "Please check the highlighted fields";
      for (const problem of body.detail) {
        const field = String(problem.loc?.[problem.loc.length - 1] ?? "form");
        fields[field] = String(problem.msg);
      }
    }
  } catch {
    // not JSON: keep the status text
  }
  return new ApiError(response.status, detail, fields);
}

const post = <T>(path: string, key?: string, body?: unknown, idempotent = false) =>
  request<T>(path, { method: "POST", key, body, idempotent });

export const httpApi: Api = {
  me: (key) => request("/me", { key }),
  createHousehold: (name, email, displayName) =>
    request("/households", {
      method: "POST",
      body: { name },
      headers: { "X-User-Email": email, "X-User-Name": displayName },
    }),
  acceptInvite: (token, displayName) =>
    request(`/invites/${encodeURIComponent(token)}/accept`, {
      method: "POST",
      headers: { "X-User-Name": displayName },
    }),
  household: (key, id) => request(`/households/${id}`, { key }),
  invite: (key, householdId, email) => post(`/households/${householdId}/invites`, key, { email }),
  addChore: (key, householdId, name, description) =>
    post(`/households/${householdId}/chores`, key, { name, description }),
  startEstimation: (key, householdId) => post(`/households/${householdId}/estimation/start`, key),
  estimation: (key, householdId) => request(`/households/${householdId}/estimation`, { key }),
  vote: (key, householdId, choreId, points) =>
    request(`/households/${householdId}/estimation/votes/${choreId}`, { method: "PUT", key, body: { points } }),
  forceClose: (key, householdId) => post(`/households/${householdId}/estimation/close`, key),
  openWeek: (key, householdId) => post(`/households/${householdId}/weeks`, key, {}),
  week: (key, weekId) => request(`/weeks/${weekId}`, { key }),
  flag: (key, weekId, choreId) => post(`/weeks/${weekId}/flags`, key, { chore_id: choreId }),
  startReEstimation: (key, weekId) => post(`/weeks/${weekId}/estimation/start`, key),
  startAuction: (key, weekId) => post(`/weeks/${weekId}/auction/start`, key),
  auction: (key, weekId) => request(`/weeks/${weekId}/auction`, { key }),
  nominate: (key, weekId, choreId, openingBid, turn) =>
    post(`/weeks/${weekId}/auction/nominate`, key, { chore_id: choreId, opening_bid: openingBid, turn_number: turn }, true),
  bid: (key, weekId, amount, turn) =>
    post(`/weeks/${weekId}/auction/bid`, key, { amount, turn_number: turn }, true),
  pass: (key, weekId, turn) => post(`/weeks/${weekId}/auction/pass`, key, { turn_number: turn }, true),
  finish: (key, weekId) => post(`/weeks/${weekId}/finish`, key),
  assignments: (key, weekId) => request(`/weeks/${weekId}/assignments`, { key }),
  markDone: (key, weekChoreId) => post(`/week-chores/${weekChoreId}/done`, key),
  closeWeek: (key, weekId) => post(`/weeks/${weekId}/close`, key),
  history: (key, householdId) => request(`/households/${householdId}/history`, { key }),
};

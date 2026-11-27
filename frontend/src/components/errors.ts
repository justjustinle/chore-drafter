import { ApiError } from "../api/client";

/** A friendly sentence for any error an action can throw. */
export function friendlyError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409 && /moved on|already been taken/i.test(error.detail)) {
      return "Too slow, the turn moved on!";
    }
    if (error.status === 401) return "The guild doesn't recognise your key. Try pasting it again.";
    return error.detail;
  }
  if (error instanceof TypeError) return "Can't reach the guild hall. Is the server running?";
  return "Something went wrong.";
}

/** Tone for a toast: stale turns and refusals are warnings. */
export function errorTone(error: unknown): "warn" | "info" {
  return error instanceof ApiError && (error.status === 409 || error.status === 403) ? "warn" : "info";
}

/** Field messages from a 422, e.g. { name: "String should have at least 1 character" }. */
export function fieldErrors(error: unknown): Record<string, string> {
  return error instanceof ApiError && error.status === 422 ? error.fields : {};
}

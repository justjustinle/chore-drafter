// Which API to use (real or mock), and which membership is acting.
// Screens read both with useGame() instead of importing them directly.

import { createContext, useContext } from "react";
import type { Api } from "./client";
import type { Household } from "./types";

export interface GameContext {
  api: Api;
  key: string;
  memberId: number;
  household: Household;
  isOwner: boolean;
  /** Re-fetch the household (phase, members, current week). */
  refreshHousehold: () => Promise<void>;
  /** Display name for a member id. */
  nameOf: (memberId: number | null | undefined) => string;
}

export const Game = createContext<GameContext | null>(null);

export function useGame(): GameContext {
  const game = useContext(Game);
  if (!game) throw new Error("useGame() must be used inside a household page");
  return game;
}

export const ApiChoice = createContext<Api | null>(null);

export function useApi(): Api {
  const api = useContext(ApiChoice);
  if (!api) throw new Error("No API provided");
  return api;
}

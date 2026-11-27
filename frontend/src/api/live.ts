// Live data. The ONLY place that decides how screens stay up to date.
//
// Today it polls: it calls `load` every `intervalMs` milliseconds. In Layer 12
// this can switch to WebSockets without any screen changing, because screens
// only ever call useLive() and read { data, error, refresh }.

import { useCallback, useEffect, useRef, useState } from "react";

export interface Live<T> {
  data: T | undefined;
  error: unknown;
  /** Fetch again right now (after an action, or after a 409). */
  refresh: () => Promise<void>;
}

export function useLive<T>(load: () => Promise<T>, intervalMs: number, deps: unknown[] = []): Live<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<unknown>();
  const loadRef = useRef(load);
  loadRef.current = load;

  const refresh = useCallback(async () => {
    try {
      setData(await loadRef.current());
      setError(undefined);
    } catch (problem) {
      setError(problem);
    }
  }, []);

  useEffect(() => {
    let stopped = false;
    let timer: number | undefined;
    const tick = async () => {
      await refresh();
      // Wait for one poll to finish before scheduling the next, so a slow
      // server never has several requests from us piling up.
      if (!stopped) timer = window.setTimeout(tick, intervalMs);
    };
    tick();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh, intervalMs, ...deps]);

  return { data, error, refresh };
}

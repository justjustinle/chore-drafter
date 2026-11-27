// Shown once when voting closes: each chore's final effort flips into view.

import { useEffect, useState } from "react";
import type { Chore } from "../api/types";
import { Pips, Window } from "../components/ui";

export default function Reveal({ chores, onDone }: { chores: Chore[]; onDone: () => void }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (shown >= chores.length) return;
    const timer = window.setTimeout(() => setShown((n) => n + 1), 350);
    return () => window.clearTimeout(timer);
  }, [shown, chores.length]);

  return (
    <Window title="✨ The votes are in!" actions={<button type="button" className="btn green" onClick={onDone}>Onwards</button>}>
      <div className="cards">
        {chores.map((chore, i) => (
          <div key={chore.id} className={`flip${i < shown ? " revealed" : ""}`}>
            <div className="flip-inner">
              <div className="quest-card flip-face" aria-hidden={i < shown}>
                <span className="name">{chore.name}</span>
                <span className="subtle">?</span>
              </div>
              <div className="quest-card flip-face flip-back" aria-hidden={i >= shown}>
                <div>
                  <div className="name">{chore.name}</div>
                  <div style={{ fontFamily: "var(--title)", fontSize: "1.6rem", fontWeight: 700 }} className="num">
                    {chore.effort_points ?? "–"} effort
                  </div>
                  {chore.effort_points != null && <Pips value={chore.effort_points} />}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Window>
  );
}

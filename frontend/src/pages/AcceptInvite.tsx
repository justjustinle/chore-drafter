// /invites/:token: join a household from an invite link.

import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { useApi } from "../api/context";
import { saveMembership } from "../api/session";
import { friendlyError } from "../components/errors";
import { Window } from "../components/ui";

type Outcome =
  | { kind: "form" }
  | { kind: "joined"; householdId: number; name: string; key: string }
  | { kind: "missing" }
  | { kind: "gone" }
  | { kind: "error"; message: string };

export default function AcceptInvite() {
  const { token = "" } = useParams();
  const api = useApi();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<Outcome>({ kind: "form" });

  async function accept(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const member = await api.acceptInvite(token, name);
      const me = await api.me(member.api_key);
      saveMembership({
        householdId: me.household_id,
        householdName: me.household_name,
        memberId: member.id,
        displayName: member.display_name,
        key: member.api_key,
      });
      setOutcome({ kind: "joined", householdId: me.household_id, name: me.household_name, key: member.api_key });
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) setOutcome({ kind: "missing" });
      else if (error instanceof ApiError && error.status === 410) setOutcome({ kind: "gone" });
      else setOutcome({ kind: "error", message: friendlyError(error) });
    } finally {
      setBusy(false);
    }
  }

  if (outcome.kind === "joined") {
    return (
      <Window title="🎉 Welcome to the guild!" className="modal" >
        <p>
          You've joined <strong>{outcome.name}</strong>.
        </p>
        <p className="subtle">
          Your secret key is saved in this browser. Copy it somewhere safe if you want to play from another device:
        </p>
        <div className="slip num">{outcome.key}</div>
        <p>
          <Link className="btn green" to={`/h/${outcome.householdId}`}>
            Enter the guild hall
          </Link>
        </p>
      </Window>
    );
  }

  if (outcome.kind === "missing") {
    return (
      <Window title="🔍 This invite doesn't exist">
        <p>Check the link with whoever sent it. It may have been copied incompletely.</p>
        <Link to="/">Back to the front door</Link>
      </Window>
    );
  }

  if (outcome.kind === "gone") {
    return (
      <Window title="⌛ This invite has expired or been used">
        <p>Invites last 7 days and work once. Ask the guild owner for a fresh one.</p>
        <Link to="/">Back to the front door</Link>
      </Window>
    );
  }

  return (
    <Window title="📜 You've been invited to a guild">
      <form onSubmit={accept}>
        <div className="field">
          <label htmlFor="join-name">What should your housemates call you?</label>
          <input id="join-name" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        {outcome.kind === "error" && <div className="field-error">{outcome.message}</div>}
        <button className="btn green" type="submit" disabled={busy}>
          {busy ? "Joining…" : "Join the guild"}
        </button>
      </form>
    </Window>
  );
}

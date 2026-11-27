// The front door: your guilds, found a new one, or bring a key from another device.

import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApi } from "../api/context";
import { forgetMembership, loadMemberships, saveMembership } from "../api/session";
import { fieldErrors, friendlyError } from "../components/errors";
import { Window, useToast } from "../components/ui";

export default function Home() {
  const api = useApi();
  const navigate = useNavigate();
  const toast = useToast();
  const [memberships, setMemberships] = useState(loadMemberships);

  const [householdName, setHouseholdName] = useState("");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createErrors, setCreateErrors] = useState<Record<string, string>>({});

  const [pastedKey, setPastedKey] = useState("");
  const [keyError, setKeyError] = useState("");

  async function create(event: FormEvent) {
    event.preventDefault();
    setCreating(true);
    setCreateErrors({});
    try {
      const household = await api.createHousehold(householdName, email, displayName);
      saveMembership({
        householdId: household.id,
        householdName: household.name,
        memberId: household.owner_member_id,
        displayName,
        key: household.api_key,
      });
      navigate(`/h/${household.id}`);
    } catch (error) {
      const fields = fieldErrors(error);
      if (Object.keys(fields).length) setCreateErrors(fields);
      else toast(friendlyError(error), "warn");
    } finally {
      setCreating(false);
    }
  }

  async function useKey(event: FormEvent) {
    event.preventDefault();
    setKeyError("");
    try {
      const me = await api.me(pastedKey.trim());
      saveMembership({
        householdId: me.household_id,
        householdName: me.household_name,
        memberId: me.member_id,
        displayName: me.display_name,
        key: pastedKey.trim(),
      });
      navigate(`/h/${me.household_id}`);
    } catch (error) {
      setKeyError(friendlyError(error));
    }
  }

  return (
    <div className="grid-2">
      <Window title="🏰 Your guilds">
        {memberships.length === 0 ? (
          <p className="subtle">No guilds yet. Found one, or accept an invite link from a housemate.</p>
        ) : (
          <ul className="list">
            {memberships.map((m) => (
              <li key={m.householdId}>
                <div style={{ flex: 1 }}>
                  <Link to={`/h/${m.householdId}`} style={{ fontWeight: 700 }}>
                    {m.householdName}
                  </Link>
                  <div className="subtle">as {m.displayName}</div>
                </div>
                <button
                  type="button"
                  className="btn quiet small"
                  onClick={() => {
                    forgetMembership(m.householdId);
                    setMemberships(loadMemberships());
                  }}
                >
                  Forget
                </button>
              </li>
            ))}
          </ul>
        )}
      </Window>

      <Window title="🪧 Found a new guild">
        <form onSubmit={create}>
          <div className="field">
            <label htmlFor="household-name">Household name</label>
            <input id="household-name" value={householdName} onChange={(e) => setHouseholdName(e.target.value)} required />
            {createErrors.name && <div className="field-error">{createErrors.name}</div>}
          </div>
          <div className="field">
            <label htmlFor="your-name">Your name</label>
            <input id="your-name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
            {createErrors["x-user-name"] && <div className="field-error">{createErrors["x-user-name"]}</div>}
          </div>
          <div className="field">
            <label htmlFor="your-email">Your email</label>
            <input id="your-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            {createErrors["x-user-email"] && <div className="field-error">{createErrors["x-user-email"]}</div>}
          </div>
          <button className="btn green" type="submit" disabled={creating}>
            {creating ? "Founding…" : "Found the guild"}
          </button>
        </form>
      </Window>

      <Window title="🗝️ Use your key on this device">
        <p className="subtle">Each member gets a secret key when they join. Paste yours to play from here.</p>
        <form onSubmit={useKey}>
          <div className="field">
            <label htmlFor="api-key">API key</label>
            <input id="api-key" value={pastedKey} onChange={(e) => setPastedKey(e.target.value)} placeholder="cd_…" required />
            {keyError && <div className="field-error">{keyError}</div>}
          </div>
          <button className="btn" type="submit">
            Enter the guild
          </button>
        </form>
      </Window>
    </div>
  );
}

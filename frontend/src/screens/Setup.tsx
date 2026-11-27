// Phase SETUP: the Guild Hall. Members, chores, invites, and starting estimation.

import { useState, type FormEvent } from "react";
import { useGame } from "../api/context";
import { fieldErrors, friendlyError } from "../components/errors";
import { Avatar, TipButton, Window, flavourFor, useToast } from "../components/ui";

export default function Setup() {
  const { api, key, household, isOwner, refreshHousehold } = useGame();
  const toast = useToast();

  const [choreName, setChoreName] = useState("");
  const [choreDescription, setChoreDescription] = useState("");
  const [choreErrors, setChoreErrors] = useState<Record<string, string>>({});

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState("");
  const [starting, setStarting] = useState(false);

  async function addChore(event: FormEvent) {
    event.preventDefault();
    setChoreErrors({});
    try {
      await api.addChore(key, household.id, choreName, choreDescription.trim() || null);
      setChoreName("");
      setChoreDescription("");
      await refreshHousehold();
    } catch (error) {
      const fields = fieldErrors(error);
      if (Object.keys(fields).length) setChoreErrors(fields);
      else toast(friendlyError(error), "warn");
    }
  }

  async function invite(event: FormEvent) {
    event.preventDefault();
    setInviteError("");
    try {
      const created = await api.invite(key, household.id, inviteEmail);
      // The API's link points at the API. Housemates should land on this
      // front end instead, so rebuild the link with the same token.
      const token = created.link.split("/invites/")[1]?.split("/")[0] ?? "";
      setInviteLink(`${window.location.origin}/invites/${token}`);
      setInviteEmail("");
    } catch (error) {
      setInviteError(fieldErrors(error).email ?? friendlyError(error));
    }
  }

  async function beginEstimation() {
    setStarting(true);
    try {
      await api.startEstimation(key, household.id);
      await refreshHousehold();
    } catch (error) {
      toast(friendlyError(error), "warn");
    } finally {
      setStarting(false);
    }
  }

  const enoughMembers = household.members.length >= 2;
  const enoughChores = household.chores.length >= 1;
  const whyNot = !enoughMembers
    ? "Invite at least one more member first"
    : !enoughChores
      ? "Add at least one chore first"
      : undefined;

  return (
    <div className="grid-2">
      <Window
        title="🏰 Guild Hall"
        actions={
          isOwner && (
            <TipButton className="btn green" disabled={!!whyNot || starting} tip={whyNot} onClick={beginEstimation}>
              ⚖️ Begin the Estimation
            </TipButton>
          )
        }
      >
        <h3>Party ({household.members.length})</h3>
        <ul className="list">
          {household.members.map((member) => (
            <li key={member.id}>
              <Avatar memberId={member.id} name={member.display_name} crown={member.id === household.owner_member_id} />
              <div>
                <strong>{member.display_name}</strong>
                {member.id === household.owner_member_id && <span className="chip gold" style={{ marginLeft: 8 }}>👑 Owner</span>}
                <div className="subtle">{member.email}</div>
              </div>
            </li>
          ))}
        </ul>

        <h3 style={{ marginTop: 18 }}>Quest board ({household.chores.length})</h3>
        {household.chores.length === 0 ? (
          <p className="subtle">No quests posted yet.</p>
        ) : (
          <div className="cards">
            {household.chores.map((chore) => (
              <div className="quest-card" key={chore.id}>
                <div className="name">{chore.name}</div>
                <div className="flavour">{flavourFor(chore.id)}</div>
                {chore.description && <p style={{ margin: "6px 0 0" }}>{chore.description}</p>}
              </div>
            ))}
          </div>
        )}
      </Window>

      <div>
        <Window title="📌 Post a chore">
          <form onSubmit={addChore}>
            <div className="field">
              <label htmlFor="chore-name">Chore name</label>
              <input id="chore-name" value={choreName} onChange={(e) => setChoreName(e.target.value)} placeholder="Take out the bins" />
              {choreErrors.name && <div className="field-error">{choreErrors.name}</div>}
            </div>
            <div className="field">
              <label htmlFor="chore-description">Description (optional)</label>
              <textarea id="chore-description" rows={2} value={choreDescription} onChange={(e) => setChoreDescription(e.target.value)} />
              {choreErrors.description && <div className="field-error">{choreErrors.description}</div>}
            </div>
            <button className="btn" type="submit">
              Post chore
            </button>
          </form>
        </Window>

        {isOwner && (
          <Window title="✉️ Invite a housemate">
            <form onSubmit={invite}>
              <div className="field">
                <label htmlFor="invite-email">Their email</label>
                <input id="invite-email" type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} required />
                {inviteError && <div className="field-error">{inviteError}</div>}
              </div>
              <button className="btn" type="submit">
                Write an invite
              </button>
            </form>
            {inviteLink && (
              <div style={{ marginTop: 14 }}>
                <p className="subtle" style={{ margin: "0 0 6px" }}>
                  Send them this link. Expires in 7 days, works once.
                </p>
                <div className="slip">{inviteLink}</div>
                <button
                  type="button"
                  className="btn quiet small"
                  style={{ marginTop: 8 }}
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(inviteLink);
                      toast("Invite link copied!", "ok");
                    } catch {
                      toast("Couldn't copy. Select the link and copy it by hand.", "warn");
                    }
                  }}
                >
                  📋 Copy link
                </button>
              </div>
            )}
          </Window>
        )}
      </div>
    </div>
  );
}

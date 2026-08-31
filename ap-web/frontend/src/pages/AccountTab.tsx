import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  getMyAccount,
  scheduleMyAccountDeletion,
  type AccountSummary,
} from "../api";
import { useAuth } from "../context/AuthContext";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function AccountTab() {
  const { logout } = useAuth();
  const [searchParams] = useSearchParams();
  const [summary, setSummary] = useState<AccountSummary | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const reauthReady = searchParams.get("delete") === "ready";
  const previousAccountDeleted = searchParams.get("deletion") === "completed";
  const recovered = searchParams.get("recovered") === "1";

  useEffect(() => {
    getMyAccount()
      .then(setSummary)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load account"))
      .finally(() => setLoading(false));
  }, []);

  const scheduleDeletion = async () => {
    setSubmitting(true);
    setError("");
    try {
      const result = await scheduleMyAccountDeletion(confirmation);
      window.location.href = `/account-recovery?scheduled=${encodeURIComponent(result.deletion_due_at)}`;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to schedule deletion");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <p className="loading">Loading account...</p>;
  if (!summary) return <p className="error">{error || "Account could not be loaded."}</p>;

  const { account, counts } = summary;
  return (
    <div className="account-tab">
      {previousAccountDeleted && (
        <p className="notice notice-warning" role="status">
          The previous account passed its recovery deadline and was permanently
          deleted. You are now signed in with a new, empty account.
        </p>
      )}
      {recovered && (
        <p className="notice notice-success" role="status">
          Account restored. The deletion request has been cancelled.
        </p>
      )}
      {error && <p className="notice notice-danger" role="alert">{error}</p>}

      <section className="settings-section">
        <h3>Identity</h3>
        <dl className="account-facts">
          <div><dt>Discord name</dt><dd>{account.discord_username}</dd></div>
          <div><dt>Joined</dt><dd>{formatDate(account.created_at)}</dd></div>
          <div>
            <dt>Room access</dt>
            <dd>{account.room_creation_blocked ? "Blocked" : "Available"}</dd>
          </div>
        </dl>
        <p className="settings-hint">
          Your name is refreshed from Discord when you sign in. Existing room and
          YAML names are not rewritten.
        </p>
        <a className="btn btn-sm" href="/api/auth/login?next=/my/account">
          Refresh from Discord
        </a>
      </section>

      <section className="settings-section account-section">
        <h3>Your data</h3>
        <div className="account-count-grid">
          <Link to="/rooms"><strong>{counts.rooms}</strong><span>Hosted rooms</span></Link>
          <Link to="/my/yamls"><strong>{counts.saved_yamls}</strong><span>Saved YAMLs</span></Link>
          <Link to="/my/yamls"><strong>{counts.submissions}</strong><span>Submissions</span></Link>
          <Link to="/my/presets"><strong>{counts.presets}</strong><span>Presets</span></Link>
          <Link to="/my/templates"><strong>{counts.room_templates}</strong><span>Room templates</span></Link>
        </div>
        <div className="account-actions">
          <a className="btn btn-sm" href="/api/my/account/export" download>
            Download my data
          </a>
          <a className="btn btn-sm" href="/privacy">Privacy</a>
        </div>
      </section>

      <section className="settings-section account-section">
        <h3>Session</h3>
        <button type="button" className="btn btn-sm" onClick={() => void logout()}>
          Sign out
        </button>
      </section>

      <section className="settings-section account-section account-danger-zone">
        <h3>Delete account</h3>
        <p>
          Deletion starts with a <strong>{summary.deletion_grace_days}-day recovery period</strong>.
          Your account is locked immediately, but no data is removed until the displayed
          deadline. Existing public room links remain available during that period. Sign in
          with the same Discord account before then to restore access.
        </p>
        <p className="settings-hint">
          Permanent deletion removes {counts.rooms} hosted room{counts.rooms === 1 ? "" : "s"},
          including {counts.hosted_submissions} submission{counts.hosted_submissions === 1 ? "" : "s"}
          inside them, plus your {counts.submissions} submission{counts.submissions === 1 ? "" : "s"}
          in other rooms, {counts.saved_yamls} saved YAML{counts.saved_yamls === 1 ? "" : "s"},
          {` ${counts.presets}`} preset{counts.presets === 1 ? "" : "s"}, and
          {` ${counts.room_templates}`} room template{counts.room_templates === 1 ? "" : "s"}.
        </p>
        <p className="settings-hint">
          Scheduling deletion also signs this browser out of sibling AP-Pie services
          that use the shared sign-in cookie.
        </p>

        {summary.is_owner ? (
          <p className="notice notice-warning">
            The owner account uses a manual verified deletion process so the only
            operating identity cannot be removed accidentally.
          </p>
        ) : reauthReady ? (
          <div className="account-delete-confirm">
            <p className="notice notice-warning">
              Discord reauthentication succeeded. This authorization expires shortly
              and can be used once.
            </p>
            <label htmlFor="account-delete-confirmation">Type DELETE to continue</label>
            <input
              id="account-delete-confirmation"
              type="text"
              autoComplete="off"
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
            />
            <button
              type="button"
              className="btn btn-danger"
              disabled={confirmation !== "DELETE" || submitting}
              onClick={() => void scheduleDeletion()}
            >
              {submitting ? "Scheduling..." : "Schedule account deletion"}
            </button>
          </div>
        ) : (
          <a className="btn btn-danger" href="/api/auth/account-delete-reauth">
            Reauthenticate with Discord
          </a>
        )}
      </section>
    </div>
  );
}

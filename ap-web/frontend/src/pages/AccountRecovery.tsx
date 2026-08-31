import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  getAccountRecoveryStatus,
  recoverMyAccount,
  type AccountRecoveryStatus,
} from "../api";
import { usePageTitle } from "../lib/usePageTitle";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "full",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function AccountRecovery() {
  usePageTitle("Account recovery");
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<AccountRecoveryStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [recovering, setRecovering] = useState(false);
  const [error, setError] = useState("");
  const scheduledAt = searchParams.get("scheduled");

  useEffect(() => {
    getAccountRecoveryStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, []);

  const recover = async () => {
    setRecovering(true);
    setError("");
    try {
      await recoverMyAccount();
      window.location.href = "/my/account?recovered=1";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recovery failed");
      setRecovering(false);
    }
  };

  return (
    <div className="account-recovery">
      <h1>Account recovery</h1>
      {scheduledAt && (
        <p className="notice notice-warning">
          Account deletion is scheduled for {formatDate(scheduledAt)}. No account
          data has been removed yet.
        </p>
      )}
      {error && <p className="notice notice-danger" role="alert">{error}</p>}
      {loading ? (
        <p className="loading">Checking recovery status...</p>
      ) : status ? (
        <section className="settings-section">
          <h3>Restore {status.discord_username}</h3>
          <p>
            Permanent deletion is scheduled for <strong>{formatDate(status.deletion_due_at)}</strong>.
            Restoring now cancels it and leaves your rooms, YAMLs, presets and templates unchanged.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            disabled={recovering}
            onClick={() => void recover()}
          >
            {recovering ? "Restoring..." : "Restore my account"}
          </button>
        </section>
      ) : (
        <section className="settings-section">
          <h3>Verify with Discord</h3>
          <p>
            Sign in with the same Discord account that scheduled deletion. This is
            the only identity that can cancel the request during the recovery period.
          </p>
          <a className="btn btn-primary" href="/api/auth/login?next=/account-recovery">
            Sign in with Discord to recover
          </a>
        </section>
      )}
      <p className="account-recovery-home"><Link to="/">Back to Archipelago Pie</Link></p>
    </div>
  );
}

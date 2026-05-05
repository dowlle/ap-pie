import { useEffect, useState } from "react";
import {
  adminListApworldRequests,
  adminUpdateApworldRequest,
  type ApworldIndexRequest,
  type ApworldGateVerdict,
  type ApworldFuzzerVerdict,
} from "../api";

/**
 * Admin queue for FEAT-30 Phase 0a. Appie triages incoming APWorld index
 * requests here. The page is intentionally task-shaped: each row carries
 * the two gates (Eijebong fuzzer + Claude/FEAT-19 audit) as separate
 * editable fields plus terminal buttons for Approve / Reject / Mark
 * merged. Phase 1 will fold the audit + PR-open steps into off-server
 * worker automation, but the data model stays the same so this UI keeps
 * working as a fallback / observer.
 *
 * Phase 0a is workflow-only: the admin runs the fuzzer + audit by hand
 * (`audit.py file <url>` for the Claude audit, the apworld's CI workflow
 * for Eijebong's fuzzer) and pastes the verdict here. PR open + merge
 * happen on github.com directly.
 */
export default function AdminApworldRequests() {
  const [requests, setRequests] = useState<ApworldIndexRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<string>("");

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await adminListApworldRequests(filter || undefined);
      setRequests(rows);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load requests";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, [filter]);

  return (
    <>
      <h1>APWorld index requests</h1>
      <p className="muted" style={{ maxWidth: "60rem" }}>
        Hosts and maintainers propose new APWorld versions for{" "}
        <code>dowlle/Archipelago-index</code> here. Two gates must pass before merge:
        the Eijebong runtime fuzzer (~100% generation success) and the FEAT-19 Claude
        security audit. Run both off-server, paste verdicts below, then approve and open the PR.
      </p>

      <div className="filter-bar" style={{ marginTop: "1rem" }}>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="audited">Audited</option>
          <option value="approved">Approved</option>
          <option value="pr_opened">PR opened</option>
          <option value="merged">Merged</option>
          <option value="rejected">Rejected</option>
          <option value="failed">Failed</option>
        </select>
        <button className="btn btn-sm" onClick={refresh} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {error && <p style={{ color: "var(--accent-warn)" }}>{error}</p>}

      {!loading && requests.length === 0 && (
        <p className="muted">No requests match this filter.</p>
      )}

      <div className="apworld-request-list">
        {requests.map((r) => (
          <RequestCard key={r.id} request={r} onMutated={refresh} />
        ))}
      </div>
    </>
  );
}

function RequestCard({
  request: req,
  onMutated,
}: {
  request: ApworldIndexRequest;
  onMutated: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const patch = async (body: Parameters<typeof adminUpdateApworldRequest>[1]) => {
    setBusy(true);
    setErr("");
    try {
      await adminUpdateApworldRequest(req.id, body);
      onMutated();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Update failed");
    } finally {
      setBusy(false);
    }
  };

  const onAudit = async (verdict: ApworldGateVerdict) => {
    const url = prompt("Audit report URL (paste a link or path, leave blank to skip):", req.audit_url ?? "") ?? req.audit_url ?? "";
    await patch({
      audit_status: verdict,
      audit_url: url || null,
      status: "audited",
    });
  };

  const onFuzz = async (verdict: ApworldFuzzerVerdict) => {
    const url = prompt("Fuzzer run URL (CI run, local report, etc., leave blank to skip):", req.fuzzer_url ?? "") ?? req.fuzzer_url ?? "";
    await patch({ fuzzer_status: verdict, fuzzer_url: url || null });
  };

  const onApprove = async () => {
    if (!req.fuzzer_status || req.fuzzer_status === "fail") {
      if (!confirm("Fuzzer hasn't passed. Approve anyway?")) return;
    }
    if (!req.audit_status || req.audit_status === "fail") {
      if (!confirm("Audit hasn't passed. Approve anyway?")) return;
    }
    await patch({ status: "approved" });
  };

  const onPrOpened = async () => {
    const url = prompt("PR URL on dowlle/Archipelago-index:", req.pr_url ?? "") ?? "";
    if (!url) return;
    await patch({ status: "pr_opened", pr_url: url });
  };

  const onMerged = async () => {
    if (!confirm("Mark merged? This is the terminal success state.")) return;
    await patch({ status: "merged" });
  };

  const onReject = async () => {
    const reason = prompt("Reason for rejection:", req.reject_reason ?? "");
    if (reason === null) return;
    await patch({ status: "rejected", reject_reason: reason });
  };

  const terminal = req.status === "merged" || req.status === "rejected" || req.status === "failed";

  return (
    <div className="apworld-request-card">
      <div className="apworld-request-head">
        <div>
          <h3 style={{ margin: 0 }}>
            {req.display_name} <span className="muted" style={{ fontSize: "0.85rem" }}>v{req.requested_version}</span>
          </h3>
          <p className="muted" style={{ margin: "0.2rem 0", fontSize: "0.8rem" }}>
            <code>{req.apworld_name}</code>
            {" · "}requested by <strong>{req.requester_username ?? `user ${req.requester_user_id}`}</strong>
            {" "}({req.requester_role.replace("_", " ")})
            {req.source_room_id && <> · room <code>{req.source_room_id}</code></>}
            {" · "}{new Date(req.created_at).toLocaleString()}
          </p>
        </div>
        <span className={`badge badge-${badgeForStatus(req.status)}`}>{req.status}</span>
      </div>

      <div className="apworld-request-body">
        <p style={{ margin: "0.2rem 0" }}>
          <strong>Source URL:</strong>{" "}
          <a href={req.source_url} target="_blank" rel="noopener noreferrer">{req.source_url}</a>
        </p>
        {req.notes && (
          <p className="muted" style={{ margin: "0.2rem 0", whiteSpace: "pre-wrap" }}>
            <strong>Notes:</strong> {req.notes}
          </p>
        )}

        <div className="apworld-request-gates">
          <div>
            <strong>Fuzzer (Eijebong):</strong>{" "}
            <span className={`gate-badge gate-${req.fuzzer_status ?? "none"}`}>
              {req.fuzzer_status ?? "not run"}
            </span>
            {req.fuzzer_url && (
              <> · <a href={req.fuzzer_url} target="_blank" rel="noopener noreferrer">report</a></>
            )}
            {!terminal && (
              <span className="apworld-request-actions">
                <button className="btn btn-sm" disabled={busy} onClick={() => onFuzz("pass")}>pass</button>
                <button className="btn btn-sm" disabled={busy} onClick={() => onFuzz("fail")}>fail</button>
              </span>
            )}
          </div>
          <div>
            <strong>Audit (Claude / FEAT-19):</strong>{" "}
            <span className={`gate-badge gate-${req.audit_status ?? "none"}`}>
              {req.audit_status ?? "not run"}
            </span>
            {req.audit_url && (
              <> · <a href={req.audit_url} target="_blank" rel="noopener noreferrer">report</a></>
            )}
            {!terminal && (
              <span className="apworld-request-actions">
                <button className="btn btn-sm" disabled={busy} onClick={() => onAudit("pass")}>pass</button>
                <button className="btn btn-sm" disabled={busy} onClick={() => onAudit("needs_review")}>needs review</button>
                <button className="btn btn-sm" disabled={busy} onClick={() => onAudit("fail")}>fail</button>
              </span>
            )}
          </div>
        </div>

        {req.pr_url && (
          <p style={{ margin: "0.2rem 0" }}>
            <strong>PR:</strong>{" "}
            <a href={req.pr_url} target="_blank" rel="noopener noreferrer">{req.pr_url}</a>
          </p>
        )}
        {req.reject_reason && (
          <p className="muted" style={{ margin: "0.2rem 0" }}>
            <strong>Reject reason:</strong> {req.reject_reason}
          </p>
        )}

        {!terminal && (
          <div className="apworld-request-footer">
            {req.status !== "approved" && req.status !== "pr_opened" && (
              <button className="btn btn-sm btn-primary" disabled={busy} onClick={onApprove}>Approve</button>
            )}
            {(req.status === "approved" || req.status === "audited") && (
              <button className="btn btn-sm" disabled={busy} onClick={onPrOpened}>Mark PR opened</button>
            )}
            {req.status === "pr_opened" && (
              <button className="btn btn-sm btn-primary" disabled={busy} onClick={onMerged}>Mark merged</button>
            )}
            <button className="btn btn-sm btn-danger" disabled={busy} onClick={onReject}>Reject</button>
          </div>
        )}

        {err && <p style={{ color: "var(--accent-warn)", fontSize: "0.85rem" }}>{err}</p>}
      </div>
    </div>
  );
}

function badgeForStatus(s: ApworldIndexRequest["status"]): string {
  switch (s) {
    case "pending":   return "pending";
    case "audited":   return "save";
    case "approved":  return "save";
    case "pr_opened": return "save";
    case "merged":    return "done";
    case "rejected":  return "error";
    case "failed":    return "error";
  }
}

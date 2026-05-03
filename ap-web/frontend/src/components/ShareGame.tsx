import { useEffect, useRef, useState } from "react";
import { getConnectInfo, type ConnectInfo } from "../api";
import { copyText } from "../lib/copy";

/**
 * Reusable "Share this game" affordance for hosts. Renders a button that
 * opens a native <dialog> with the public /play/:seed URL, a templated chat
 * message listing slots + connection info, and per-field copy buttons.
 *
 * The component fetches /api/connect/:seed itself so it always shows the
 * current server status rather than whatever stale state the parent page
 * happened to have loaded.
 */

function useCopy() {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = async (value: string, key: string) => {
    const ok = await copyText(value);
    if (ok) {
      setCopied(key);
      setTimeout(() => setCopied((k) => (k === key ? null : k)), 1500);
    }
  };
  return { copied, copy };
}

function buildShareMessage(info: ConnectInfo, playUrl: string): string {
  const lines: string[] = [];
  lines.push("Join our Archipelago multiworld!");
  lines.push("");
  lines.push(`Player guide: ${playUrl}`);
  if (info.server.status === "running" && info.server.connection_url) {
    lines.push(`Server:       ${info.server.connection_url}`);
  } else {
    lines.push("Server:       (host will start it before play - check the guide link)");
  }
  lines.push(`Archipelago:  ${info.ap_version}`);
  lines.push("");
  lines.push(`Slots (${info.player_count}):`);
  for (const p of info.players) {
    lines.push(`  ${p.slot}. ${p.name} - ${p.game}`);
  }
  lines.push("");
  lines.push("Open the guide link for step-by-step join instructions.");
  return lines.join("\n");
}

interface ShareGameProps {
  seed: string;
  buttonLabel?: string;
  buttonClassName?: string;
}

function ShareGame({ seed, buttonLabel = "Share", buttonClassName = "btn" }: ShareGameProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const [info, setInfo] = useState<ConnectInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { copied, copy } = useCopy();

  const playUrl = `${window.location.origin}/play/${encodeURIComponent(seed)}`;

  const openDialog = async () => {
    setOpen(true);
    setLoading(true);
    setError(null);
    try {
      const data = await getConnectInfo(seed);
      setInfo(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load game info");
    } finally {
      setLoading(false);
    }
  };

  const closeDialog = () => {
    setOpen(false);
    setInfo(null);
  };

  useEffect(() => {
    const d = dialogRef.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  const message = info ? buildShareMessage(info, playUrl) : "";

  return (
    <>
      <button type="button" className={buttonClassName} onClick={openDialog}>
        {buttonLabel}
      </button>

      <dialog
        ref={dialogRef}
        className="share-dialog"
        onClose={closeDialog}
        onClick={(e) => {
          // Click on the backdrop (the <dialog> itself, not its content) closes it
          if (e.target === dialogRef.current) closeDialog();
        }}
      >
        <div className="share-dialog-body">
          <header className="share-dialog-header">
            <h2 style={{ margin: 0 }}>Share this game</h2>
            <button type="button" className="btn btn-sm" onClick={closeDialog}>Close</button>
          </header>

          {loading && <p className="loading">Loading…</p>}
          {error && <p className="error">{error}</p>}

          {info && (
            <>
              <section style={{ marginTop: "1rem" }}>
                <label className="share-label">Player link</label>
                <div className="share-row">
                  <code className="share-value">{playUrl}</code>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => copy(playUrl, "url")}
                  >
                    {copied === "url" ? "Copied!" : "Copy URL"}
                  </button>
                </div>
                <p className="play-hint" style={{ marginTop: "0.25rem" }}>
                  This page works without an Archipelago Pie account. Send it to anyone you want in the game.
                </p>
              </section>

              {info.server.status === "running" && info.server.connection_url && (
                <section style={{ marginTop: "1rem" }}>
                  <label className="share-label">Server address</label>
                  <div className="share-row">
                    <code className="share-value">{info.server.connection_url}</code>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => copy(info.server.connection_url!, "server")}
                    >
                      {copied === "server" ? "Copied!" : "Copy"}
                    </button>
                  </div>
                </section>
              )}

              <section style={{ marginTop: "1rem" }}>
                <label className="share-label">Discord / chat message</label>
                <textarea
                  className="share-message"
                  value={message}
                  readOnly
                  rows={Math.min(14, message.split("\n").length + 1)}
                />
                <div className="share-row" style={{ marginTop: "0.4rem" }}>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() => copy(message, "message")}
                  >
                    {copied === "message" ? "Copied!" : "Copy message"}
                  </button>
                </div>
              </section>
            </>
          )}
        </div>
      </dialog>
    </>
  );
}

export default ShareGame;

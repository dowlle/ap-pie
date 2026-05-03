import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  connectDownloadUrl,
  connectPatchDownloadUrl,
  getConnectInfo,
  type ConnectInfo,
} from "../api";
import { usePageTitle } from "../lib/usePageTitle";
import CopyButton from "../components/CopyButton";
import ConnectionHero, { type ConnectionStatus } from "../components/ConnectionHero";

/**
 * Public player-connect page. No auth required. The seed in the URL is the
 * capability - seeds are 20-digit random numbers so unguessable in practice.
 * The page is the front door for anyone an Archipelago Pie host invites to a game: it
 * shows connection info, per-slot assignments, download links, and a step-by-
 * step "how to join" guide for players unfamiliar with Archipelago.
 */

function statusToHero(s: ConnectInfo["server"]["status"]): { status: ConnectionStatus; meta: string } {
  switch (s) {
    case "external":
      return { status: "external", meta: "Hosted by the room's host on their own machine. Reach out to them if it's offline." };
    case "running":
      return { status: "live", meta: "Server is live - connect now." };
    case "starting":
      return { status: "pending", meta: "Server is starting. Hang tight, this usually takes a few seconds." };
    case "crashed":
      return { status: "error", meta: "Server crashed. Ask your host to check the logs and relaunch." };
    case "stopped":
      return { status: "warn", meta: "Server is stopped. Ask your host to start it so players can connect." };
    case "never_started":
    default:
      return { status: "pending", meta: "The multiworld is ready - the host just needs to launch it." };
  }
}

function PlayersTable({ info }: { info: ConnectInfo }) {
  return (
    <section className="play-card public-section">
      <h2>Slots ({info.player_count})</h2>
      <p className="play-hint" style={{ marginTop: "0.25rem" }}>
        Find your name below and note the game you're playing. You'll need the exact slot name when you connect.
      </p>
      <div className="table-wrapper" style={{ marginTop: "0.75rem" }}>
        <table className="game-table">
          <thead>
            <tr>
              <th style={{ width: "60px" }}>Slot</th>
              <th>Player name</th>
              <th>Game</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {info.players.map((p) => (
              <tr key={p.slot}>
                <td>{p.slot}</td>
                <td><strong>{p.name}</strong></td>
                <td>{p.game}</td>
                <td><CopyButton value={p.name} label="Copy name" copiedLabel="Copied" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PatchesCard({ info }: { info: ConnectInfo }) {
  if (info.patch_files.length === 0 && !info.has_zip) return null;
  const zipUrl = info.has_zip ? connectDownloadUrl(info.seed) : null;
  return (
    <section className="play-card public-section">
      <h2>Patch files</h2>
      <p className="play-hint">
        Some games need a patched ROM or data file generated per slot. Download the one
        with your slot number in the filename.
      </p>
      {info.patch_files.length > 0 ? (
        <ul className="play-patch-list">
          {info.patch_files.map((f) => (
            <li key={f}>
              <a href={connectPatchDownloadUrl(info.seed, f)} download>
                {f}
              </a>
            </li>
          ))}
        </ul>
      ) : (
        <p className="play-hint" style={{ marginTop: "0.5rem" }}>
          No per-slot patch files in this multiworld.
        </p>
      )}
      {zipUrl && (
        <p style={{ marginTop: "0.9rem" }}>
          <a href={zipUrl} className="btn" download>
            Or download the full multiworld zip
          </a>
        </p>
      )}
    </section>
  );
}

function HowToConnect({ info }: { info: ConnectInfo }) {
  const server = info.server.connection_url ?? "(waiting for host to start the server)";
  return (
    <section className="play-card public-section">
      <h2>How to connect</h2>
      <ol style={{ lineHeight: 1.7, paddingLeft: "1.25rem" }}>
        <li>
          <strong>Install the Archipelago launcher</strong> if you don't have it.{" "}
          <a href="https://github.com/ArchipelagoMW/Archipelago/releases/latest" target="_blank" rel="noreferrer">
            Download the latest release
          </a>{" "}
          for your platform.
        </li>
        <li>
          <strong>Open the zip</strong> (button above) and run the patch file matching your slot.
          It launches the correct client for your game automatically. For games that don't
          need patching, just start the AP client that matches your game.
        </li>
        <li>
          <strong>In the client's Connect dialog</strong>, enter:
          <ul>
            <li>Server: <code>{server}</code></li>
            <li>Slot name: your exact name from the table above</li>
            <li>Password: ask the host if one is set (often blank)</li>
          </ul>
        </li>
        <li>
          <strong>Start playing.</strong> Checks you find send items to other players; they send things back.
        </li>
      </ol>
      <p className="play-hint" style={{ marginTop: "1rem" }}>
        First time using Archipelago?{" "}
        <a href="https://archipelago.gg/tutorial" target="_blank" rel="noreferrer">
          Read the tutorial
        </a>{" "}
        - it covers installing game-specific clients and patching ROMs.
      </p>
    </section>
  );
}

function Play() {
  const { seed = "" } = useParams<{ seed: string }>();
  const [info, setInfo] = useState<ConnectInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  usePageTitle(info ? `Seed ${info.seed}` : null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await getConnectInfo(seed);
        if (!cancelled) {
          setInfo(data);
          setError(null);
        }
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load game info");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [seed]);

  if (loading && !info) {
    return <p className="loading">Loading game info…</p>;
  }
  if (error || !info) {
    return (
      <div>
        <h1>Game not found</h1>
        <p className="play-hint">
          The game <code>{seed}</code> doesn't exist on this server. Double-check the
          link your host shared with you.
        </p>
      </div>
    );
  }

  const hero = statusToHero(info.server.status);
  const url = info.server.connection_url;

  return (
    <div>
      <header style={{ marginBottom: "1.5rem" }}>
        <p className="play-hint" style={{ margin: 0, marginBottom: "0.35rem" }}>
          Seed <code>{info.seed}</code> · Archipelago {info.ap_version} ·{" "}
          {info.player_count} {info.player_count === 1 ? "player" : "players"}
        </p>
        <h1 style={{ marginBottom: 0 }}>Join this Archipelago game</h1>
      </header>

      {url ? (
        <ConnectionHero url={url} status={hero.status} meta={hero.meta} />
      ) : (
        <div className="play-banner play-banner-info">
          <strong>Server not yet started.</strong> {hero.meta}
        </div>
      )}

      <PlayersTable info={info} />
      <PatchesCard info={info} />
      <HowToConnect info={info} />
    </div>
  );
}

export default Play;

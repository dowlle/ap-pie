import { discordInvite } from "../../site-links.json";

export default function DiscordFeedback() {
  return (
    <p>
      Report issues in <strong>#ap-pie-feedback</strong> on{" "}
      <a href={discordInvite} rel="noreferrer">Appie's Games Discord</a>.
    </p>
  );
}

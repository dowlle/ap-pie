import assert from "node:assert/strict";
import { test } from "node:test";
import { isDiscordInvite } from "../../public/discord-analytics.js";

test("both Discord invite URL formats count as the same kind of link", () => {
  assert.equal(isDiscordInvite(new URL("https://discord.gg/example")), true);
  assert.equal(isDiscordInvite(new URL("https://discord.com/invite/example?source=profile")), true);
});

test("Discord channel URLs, missing invites and lookalike hosts do not count", () => {
  for (const url of [
    "https://discord.com/channels/123/456",
    "https://discord.com/invite/",
    "https://discord.gg/",
    "https://discord.gg.example.com/example",
    "https://example.com/invite/example",
  ]) {
    assert.equal(isDiscordInvite(new URL(url)), false, url);
  }
});

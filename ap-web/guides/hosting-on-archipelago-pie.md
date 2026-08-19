## What this room is for

An Archipelago Pie room is a **collection room**. It gives your group one public page for rules, deadlines, YAML submissions, APWorld versions, and early checks before you generate the multiworld.

It is not the Archipelago server used during play. After collection closes, you download the submitted worlds, generate locally, upload the successful seed to archipelago.gg, and share the resulting connection details.

![The common hosting workflow moves from an announcement to a YAML collector, custom APWorld handoff, local generation, upload to archipelago.gg, and finally connecting to play.](/img/guides/announcement-to-play.svg)

## Before you create the room

Prepare the information players need before making their YAMLs:

- whether the game is synchronized or asynchronous;
- the submission deadline and any APWorld freeze date;
- the Archipelago version you will generate with;
- allowed, discouraged, or banned games;
- the maximum number of worlds per player;
- expected game length and testing requirements;
- how players should send custom APWorlds that are missing from the index;
- where players can find the maintained setup guide for each game;
- the start procedure, tracker policy, and activity rules.

Putting these rules in the room description keeps the collector link useful even when the Discord announcement scrolls away.

## Step 1: get host access

Sign in to Archipelago Pie with Discord. Room creation is currently in closed beta, so new hosts need approval. After signing in, contact Appie on Discord to request host access.

Players do not need host access to open a shared room, build a YAML, or submit to a room that accepts them.

## Step 2: create the collection room

Open **Rooms**, select **Create Room**, and complete the form.

### Room basics

Give the room a recognizable event name. Put the full player-facing rules and links in the description. Markdown is supported, so headings and lists remain readable.

### Discord login

Require Discord login when you need a stable identity beside each submission or want to enforce a per-user submission cap. Anonymous submission can be useful for a low-friction private group, but the room cannot reliably count anonymous uploads per person.

### Normal submission or claim mode

Leave claim mode off for the common workflow where every player creates and submits their own YAML.

Enable claim mode only when you will upload a pool of prepared YAMLs first and want logged-in players to claim those existing slots. Turn it on before bulk uploading because it does not retroactively remove ownership from earlier submissions.

### Submission cap and deadline

Set the maximum number of YAMLs each logged-in player may submit. Use `0` for unlimited submissions.

Set an auto-close deadline when submissions should stop at a known time. Players see the deadline and countdown on the public room page. You can still close the room manually or change the deadline later.

### APWorld version policy

The default policy pins specific versions and shows players which version to install. Keep this for scheduled games where local generation needs a reproducible set of APWorlds.

Flexible or latest-version policies are available for groups that deliberately accept version drift. State that choice in the rules so players do not assume that every version is interchangeable.

Select **Create** when the room is ready. If you host similar events repeatedly, save the settings as a reusable room template.

## Step 3: share the public room

Copy the room's public link into the Discord announcement. Ask each player to:

1. read the room rules;
2. use the listed Archipelago and APWorld versions;
3. create one YAML for each world they are bringing;
4. submit before the deadline;
5. send you any custom APWorld release that the collector does not know.

![An anonymized YAML collection room highlighting the deadline and rules, version policy, submitted worlds, and the checklist for custom APWorlds.](/img/guides/collector-checklist.svg)

*A player should be able to find the deadline, version policy, event rules, and custom-world instructions without returning to Discord.*

## Step 4: review submissions and APWorlds

The host room shows every submitted slot. Check player names, games, validation status, warnings, and duplicate or unexpected submissions while players can still correct them.

Archipelago Pie checks known file structure and option values, but those checks are advisory. A green submission is not proof that the complete multiworld will generate. Custom forks, weighted options, triggers, meta settings, and interactions between worlds may only fail during generation.

Open **Room settings → APWorlds** to review or pin versions. **Auto-pin from index** can fill missing pins for indexed games without replacing versions you already pinned manually. If a required custom APWorld is absent from the index, obtain the exact release from the player before your freeze date.

## Step 5: close and download

When the deadline arrives, select **Close Room**. Closing prevents new normal submissions while you prepare generation. You can reopen the room if a correction is required.

Use **Download all YAMLs** to receive the collected world configurations as one zip. **Download all APWorlds** bundles pinned custom integrations that are available through the index; it skips built-in worlds and games the index does not contain. Add separately supplied custom APWorlds yourself.

Keep the collection room unchanged while generating. It remains your record of submitted slot names, versions, and player ownership.

## Step 6: generate locally

Install the Archipelago version named in your room rules. Install every required custom APWorld at the pinned or frozen version, extract the downloaded YAMLs into the `Players` folder, and run **Generate** from the Archipelago Launcher.

If generation fails, use the error to identify the affected world. Ask that player for a corrected YAML rather than silently changing their options. Reopen the collection room when they should replace the stored submission, then close and download again before the next attempt.

The output zip is the generated multiworld. Do not share connection details until generation has succeeded.

## Step 7: upload and publish the start

Upload the successful output zip through the official [Host Game page](https://archipelago.gg/uploads). Archipelago creates the playable server room and provides its address and port.

Share the server address, exact slot names, optional password, and any tracker links with the group. You can also add the external host and port in the Archipelago Pie room settings so the collection page points players toward the live server.

Before announcing that the game is ready, check that:

- generation succeeded with the frozen Archipelago and APWorld versions;
- every player received the maintained setup guide for their game;
- any generated player-specific patches or mods were delivered;
- the server address, exact slot names, and optional password were shared;
- players know where to get help and whether they may connect before a synchronized start;
- each player has completed the connection test appropriate for their game.

Archipelago Pie organizes the pre-generation collection. It does not install or configure every participant's game client. Send new players to [Setting up an Archipelago game client](/guides/setting-up-a-game-client), then to the maintained instructions for their exact game and version.

For a synchronized event, state whether players may connect before the countdown and warn them when connecting itself sends a location. For an asynchronous event, publish the activity, hint, tracker, and slot-release rules with the room link.

## Ionium Lobby is another collector

[Ionium Lobby](https://ap-lobby.ionium.us/) is an independent community YAML collector with room rules, YAML creation and editing, APWorld listings, and custom-world workflows. Some Archipelago communities already organize their games there.

Choose the collector that fits your group and keep one collector as the source of truth for an event. Do not split normal submissions across Archipelago Pie and Ionium unless you have a deliberate reconciliation plan before generation.

Ionium Lobby is open source at [ionium-ap/Archipelago-lobby](https://github.com/ionium-ap/Archipelago-lobby). It is not operated by Archipelago Pie.

## Continue the hosting workflow

- [Getting started with Archipelago](/guides/getting-started) explains the player journey and terminology.
- [Setting up your YAML](/guides/setting-up-your-yaml) covers player configuration in more detail.
- [Setting up an Archipelago game client](/guides/setting-up-a-game-client) covers the player handoff, connection patterns, and pre-play testing.
- [Hosting a multiworld](/guides/hosting-a-multiworld) continues with generation, server hosting, and host commands.
- The [official setup guide](https://archipelago.gg/tutorial/Archipelago/setup_en) is the canonical reference for local generation and server connection.

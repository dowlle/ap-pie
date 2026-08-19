## What is Archipelago?

Archipelago connects randomized games. A location in one world can contain an item for another world, even when the two worlds use different games. Each player continues playing their own game while Archipelago sends items between everyone who is connected.

You can also use Archipelago alone. A solo seed has one world, with its items rearranged inside that game.

Official game support and documentation live on [archipelago.gg](https://archipelago.gg/). Community APWorlds add more game integrations outside the official release.

## Start with three ideas

**A randomizer changes where progression is found.** An ability, key, or other important item may appear at a different location each time a seed is generated.

**A multiworld connects generated worlds.** A location in your world may award an item to another slot. Items for your slot may be found by other worlds.

**A multi-game uses different games in the same multiworld.** One person might play a platformer while another plays a role-playing game. Archipelago handles the item exchange between their clients.

![The common community workflow moves from a Discord announcement to a YAML collector, custom APWorld handoff, local generation, upload to archipelago.gg, and finally connecting to play.](/img/guides/announcement-to-play.svg)

*Players prepare and submit their worlds. The host handles generation, upload, and the final start instructions.*

## Choose what you want to do

You do not need to understand every Archipelago tool before starting. Pick the path that matches what you have now.

### Join a multiworld

Choose this path when a host announces a multiworld, often through Discord. It may be a synchronized game that everyone starts together or a long-running asynchronous game that people play on their own schedule. The announcement should tell you the format, submission deadline, Archipelago version, and rules for choosing and playing your games.

Read the complete announcement before making your YAML. Limits on game count, expected game length, banned games, hint settings, trackers, and activity requirements are event rules chosen by the host, not universal Archipelago rules.

![An anonymized YAML collection room highlighting the deadline and rules, version policy, submitted worlds, and the checklist for custom APWorlds.](/img/guides/collector-checklist.svg)

*Collectors look different, but these are the details to find before submitting your world.*

#### Submit your world

1. Open the YAML collector shared by the host. Archipelago Pie and Ionium Lobby are examples of collectors.
2. Check the room rules, deadline, Archipelago version, available APWorld versions, and any APWorld freeze date before choosing your game.
3. Create one YAML for your world. It contains your exact slot name and the options for your randomized game.
4. Submit the YAML through the collector before the deadline.
5. Install and test the client or mod required by your game. A host may require you to prove that the same YAML generates and completes as a solo seed before accepting it.

If your custom APWorld or exact version is not available through the collector or its APWorld index, follow the host's custom-world submission process before the deadline or freeze date. Send the release or source link they request and do not assume that the host already has it. If your submission was wrong or the APWorld changes before versions are frozen, tell the host. The host needs the version your configuration was made for when generating the game.

You do not need the generator or server tools as a player. After submissions close, the host downloads the YAMLs, installs the required custom APWorlds, and generates the multiworld on their computer.

#### Connect and follow the start rules

After local generation succeeds, the host uploads the generated seed to archipelago.gg and shares the server address, your exact slot name, and a password if the room uses one.

For a synchronized game, follow the host's start instructions. You may be allowed to connect before the countdown, but do not begin playing or send locations until the host says the game has started. Some clients send a location as soon as they connect, so wait to connect when the host or game-specific guide warns about that.

For an asynchronous game, the host normally announces when generation and upload are complete, then shares the room and tracker links. Claim your slot if the chosen tracker requires it and follow the event's activity, update, hint, and release rules. There is usually no shared countdown after the room opens, but the host's announcement is authoritative.

Trackers such as Cheese Tracker or sphere trackers are optional community tools. They can show progress, hints, BK status, and activity, but they do not replace the Archipelago server address used by your game client.

![A comparison of synchronized and asynchronous multiworlds. Synchronized games wait for a countdown, while asynchronous games use ongoing tracker and activity rules.](/img/guides/sync-vs-async.svg)

*Both formats use the same generated room. The event rules determine when and how people play.*

Sometimes a host gives you an existing slot in a multiworld that has already been generated. In that less common case, you can skip YAML creation and use the game files and connection details supplied by the host.

### Create a solo seed

Choose this path when you want to try Archipelago with one world.

1. Pick a game from the [official supported games list](https://archipelago.gg/games).
2. Open its setup and options pages and configure one world.
3. Generate the seed on archipelago.gg when the game supports web generation, or use the local Archipelago software.
4. Create a server room from the generated seed and connect your client.

### Organize a multiworld

Choose this path when several worlds should be generated together.

1. Announce whether the game is synchronized or asynchronous, plus the submission deadline, APWorld freeze, Archipelago version, game rules, tracker policy, activity expectations, and start procedure.
2. Create a collection room and gather one configuration for each world. Most players bring one world, so this usually means one YAML per player.
3. Collect any custom APWorld releases that are not available through the collector and install the exact versions required by the submitted YAMLs.
4. Close submissions, download the YAMLs, and generate all worlds together on the host computer.
5. Upload the successful generation to archipelago.gg, create the server room, and share its connection details.
6. For a synchronized game, run the countdown and tell players when they may begin sending locations. For an asynchronous game, publish the room and tracker links with the ongoing activity and hint rules.

Archipelago Pie helps with step 2. A host can create a collection room, pin APWorld versions, and collect configurations through the browser before generation.

## Words you will see

**Location or check:** A place or action that can award an item. Players often call completed locations "checks."

**World:** One generated copy of a game, with its own options and item placements.

**Slot:** The world's identity in a room. Its slot name must match exactly when the client connects.

**YAML or player-options file:** A text file that describes a world and its settings. A normal setup uses one YAML per generated world.

**Seed:** The generated item placement and output files created from one or more world configurations.

**Room:** An Archipelago server instance created from a seed. It provides the address that clients connect to.

**Client:** Software that connects a game to the room, reports completed locations, and receives items.

**APWorld:** The integration that teaches Archipelago how a game works. A `.apworld` file is an installable package for a custom APWorld.

## Configure a world

Every world needs a game, an exact slot name, and a set of options. Many APWorld releases include a template, Archipelago can generate templates for installed worlds, and supported games provide options pages on archipelago.gg.

Start with the maintainer's documented defaults, then read the game-specific setup guide and option descriptions. Custom APWorld versions can differ, so use the version chosen by the host.

Archipelago Pie can build configurations for indexed APWorld versions. Its checks catch known structural and option problems early, but they are advisory. Final compatibility is decided when the host generates with the intended Archipelago and APWorld versions.

## From configuration to play

The complete handoff is:

1. World configurations are collected.
2. The generator creates a seed and player output files.
3. The seed is uploaded to archipelago.gg or hosted with the local server.
4. A server room is started.
5. Players connect their clients with the address and exact slot names.
6. For a synchronized game, players wait for the host's start signal before sending locations.

An Archipelago Pie collection room covers the first step. It is separate from the Archipelago server room used during play.

## Continue with the official documentation

You should now know which path applies to you and which information you need. Use these official pages when you need the full reference or a game-specific setup guide:

- The [Archipelago FAQ](https://archipelago.gg/faq/en/) explains randomizers, multiworlds, and solo play.
- The [Archipelago glossary](https://archipelago.gg/glossary/en/) defines the terms used by clients and servers.
- The [official setup guide](https://archipelago.gg/tutorial/Archipelago/setup_en) covers installation, generation, hosting, and connection.
- The [supported games list](https://archipelago.gg/games) links each bundled game's setup and options pages.
- The [community APWorld index](/apworlds) lists additional integrations and their available setup, audit, and generation-test information.

For Crash Team Racing, [our complete setup guide](/guides/ctr) covers the native client from download to connection. If you get stuck, ask in the [Archipelago Discord](https://discord.gg/8Z65BR2) or the support space named by your game's maintainer.

## What is Archipelago?

Archipelago connects randomized games. A location in one world can contain an item for another world, even when the two worlds use different games. Each player continues playing their own game while Archipelago sends items between everyone who is connected.

You can also use Archipelago alone. A solo seed has one world, with its items rearranged inside that game.

The games included with Archipelago are listed on [archipelago.gg](https://archipelago.gg/games). People in the community make APWorlds for many more games.

> **Want to see what you can play?**
>
> Find games, setup guides, downloads, and YAML builders. [Browse the APWorld index →](/apworlds)

## Start with three ideas

**A randomizer changes where important items are found.** An ability, key, or other useful item may appear somewhere different each time you generate a game.

**A multiworld connects several randomized games.** Something you complete may give an item to another player. They may find items that belong to you.

**A multi-game lets those players use different games.** One person might play a platformer while another plays a role-playing game. Archipelago sends the right items to each game.

## From options to playing

Every Archipelago game follows the same broad path:

1. Configure each world with a YAML or options page.
2. Generate those world configurations together to create a seed.
3. Host the generated seed in an Archipelago server room.
4. Set up each game's client, mod, or connector.
5. Connect with the server address and exact slot name, then play.

A client or connector links your game to the Archipelago server. It reports completed locations and receives your items. Depending on the game, it may be a separate program, part of a mod, or an entry added to Archipelago Launcher. [Setting up an Archipelago game client](/guides/setting-up-a-game-client) explains the common patterns.

Archipelago Pie helps before generation by collecting YAMLs and keeping APWorld versions together. Its collection room is not the server room used during play.

![The common community workflow moves from a Discord announcement to a YAML collector, custom APWorld handoff, local generation, upload to archipelago.gg, and finally connecting to play.](/img/guides/announcement-to-play.svg)

## Choose what you want to do

You do not need to understand every Archipelago tool before starting. Pick the path that matches what you have now.

### Join a multiworld

Choose this path when a host announces a multiworld, often through Discord. It may be a sync that everyone starts together or an async that people play in their own time. The announcement should tell you which kind it is, when YAML submissions close, which Archipelago version to use, and any rules for choosing your game.

Read the whole announcement before making your YAML. The host may limit how many games you can bring, ask for a certain game length, ban a few games, or set rules for hints and activity. Those are rules for that multiworld, not rules built into Archipelago.

#### Submit your world

1. Open the YAML collector shared by the host. Archipelago Pie and Ionium Lobby are examples of collectors.
2. Check the rules, deadline, Archipelago version, and available APWorld versions before choosing your game. Some hosts also set a freeze date after which APWorld versions may no longer change.
3. Create one YAML for your world. It contains your exact slot name and the options for your randomized game.
4. Submit the YAML through the collector before the deadline.
5. Follow the maintained setup guide for your game, then install and test its client, mod, or connector. [The game-client guide](/guides/setting-up-a-game-client) explains what to expect. Some hosts ask you to finish a solo seed with the same YAML before joining.

> **Need to make your YAML?**
>
> Find the game, choose the version requested by the host, and select **Create YAML**. You can download it or send it straight to one of your Archipelago Pie rooms. [Open the YAML Builder →](/yaml-builder)

![An anonymized YAML collection room highlighting the deadline and rules, version policy, submitted worlds, and the checklist for custom APWorlds.](/img/guides/collector-checklist.svg)

*Collectors look different, but these are the details to find before submitting your world.*

If the collector does not list your custom APWorld or version, ask the host how to send it before the deadline. Send the release or source link they request, even if you have played that APWorld with them before. Tell the host if you sent the wrong version or it changes before the freeze. They need the version your YAML was made for.

You do not need the generator or server tools as a player. After submissions close, the host downloads the YAMLs, installs the required custom APWorlds, and generates the multiworld on their computer.

#### Connect and follow the start rules

After local generation succeeds, the host uploads the generated seed to archipelago.gg and shares the server address, your exact slot name, a password if the room uses one, and any player file or setup instructions your game needs.

For a sync, follow the host's start instructions. You may be allowed to connect before the countdown, but do not play or send locations until the host starts the game. Some clients send a location as soon as they connect. If yours does, wait until the countdown before connecting.

For an async, the host normally posts when the room is ready and shares the room and tracker links. Claim your slot if the tracker asks you to. Check the host's rules for activity, hints, updates, and what happens to slots that stop playing. There is usually no shared countdown. When in doubt, follow the latest message from the host.

Trackers such as Cheese Tracker or sphere trackers are optional community tools. They can show progress, hints, activity, and whether somebody is blocked. Your game still connects with the Archipelago server address, not the tracker link.

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

Choose this path when you are the person bringing everyone's YAMLs together and generating the game.

1. Announce whether it is a sync or async, when submissions close, which Archipelago version to use, and the rules players need before making a YAML.
2. Create a collection room and gather one YAML for each world. Most players bring one world, so this usually means one YAML per player.
3. Collect any custom APWorlds that the collector does not have.
4. Close submissions, download the YAMLs, and generate the game on your computer.
5. Upload the result to archipelago.gg and share the connection details.
6. For a sync, run the countdown. For an async, post the room, tracker, activity, and hint information.

> **Ready to organize a game?**
>
> Set the rules, collect YAMLs, keep APWorld versions together, and download everything for generation. [Host a room on Archipelago Pie →](/guides/hosting-on-archipelago-pie)

## Words you will see

**Location or check:** A place or action that can award an item. Players often call completed locations "checks."

**Logic:** The rules used during generation and play to decide which locations your current items and chosen settings make reachable. A location is "in logic" when the randomizer expects you can reach it with what your slot currently has.

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

Archipelago Pie can build YAMLs for games and versions listed in the index. It can catch many mistakes in the file and its options, but it cannot promise that the full multiworld will generate. The host finds that out when they generate with the chosen Archipelago and APWorld versions.

## What happens after the YAMLs are ready

The rest of the journey is:

1. World configurations are collected.
2. The generator creates a seed and player output files.
3. The seed is uploaded to archipelago.gg or hosted with the local server.
4. A server room is started.
5. Players connect their clients with the address and exact slot names.
6. For a synchronized game, players wait for the host's start signal before sending locations.

An Archipelago Pie collection room covers the first step. It is separate from the Archipelago server room used during play.

## Continue with the official documentation

Use these official pages when you need a game-specific guide or more detail:

- The [Archipelago FAQ](https://archipelago.gg/faq/en/) explains randomizers, multiworlds, and solo play.
- The [Archipelago glossary](https://archipelago.gg/glossary/en/) defines the terms used by clients and servers.
- The [official setup guide](https://archipelago.gg/tutorial/Archipelago/setup_en) covers installation, generation, hosting, and connection.
- The [supported games list](https://archipelago.gg/games) links each bundled game's setup and options pages.
- The [community APWorld index](/apworlds) lists more games, setup links, downloads, and the checks AP-Pie has run for each version.

For Crash Team Racing, [our complete setup guide](/guides/ctr) covers the native client from download to connection. If you get stuck, ask in the [Archipelago Discord](https://discord.gg/8Z65BR2) or the support space named by your game's maintainer.

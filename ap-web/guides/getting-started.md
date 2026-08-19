## What is Archipelago?

Archipelago connects randomized games. A location in one world can contain an item for another world, even when the two worlds use different games. Each player continues playing their own game while Archipelago sends items between everyone who is connected.

You can also use Archipelago alone. A solo seed has one world, with its items rearranged inside that game.

Official game support and documentation live on [archipelago.gg](https://archipelago.gg/). Community APWorlds add more game integrations outside the official release.

## Start with three ideas

**A randomizer changes where progression is found.** An ability, key, or other important item may appear at a different location each time a seed is generated.

**A multiworld connects generated worlds.** A location in your world may award an item to another slot. Items for your slot may be found by other worlds.

**A multi-game uses different games in the same multiworld.** One person might play a platformer while another plays a role-playing game. Archipelago handles the item exchange between their clients.

## Choose what you want to do

You do not need to understand every Archipelago tool before starting. Pick the path that matches what you have now.

### Join an existing room

Choose this path when somebody has already generated the multiworld and given you connection details.

1. Follow the setup guide for your game and install the client or mod it requires.
2. Obtain the server address, your exact slot name, and the password if the room uses one.
3. Start the game and its client, then connect with those details.

You normally do not need to create a YAML or install every host tool just to join. Follow the game-specific guide because connection steps differ between games.

### Create a solo seed

Choose this path when you want to try Archipelago with one world.

1. Pick a game from the [official supported games list](https://archipelago.gg/games).
2. Open its setup and options pages and configure one world.
3. Generate the seed on archipelago.gg when the game supports web generation, or use the local Archipelago software.
4. Create a server room from the generated seed and connect your client.

### Organize a multiworld

Choose this path when several worlds should be generated together.

1. Decide which games and APWorld versions the group will use.
2. Gather one configuration for each world. Most players bring one world, so this usually means one YAML per player.
3. Generate all world configurations together to create one seed.
4. Create or host an Archipelago room from that seed and share its address.
5. Each player connects using the exact slot name assigned to their world.

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

An Archipelago Pie collection room covers the first step. It is separate from the Archipelago server room used during play.

## Continue with the official documentation

You should now know which path applies to you and which information you need. Use these official pages when you need the full reference or a game-specific setup guide:

- The [Archipelago FAQ](https://archipelago.gg/faq/en/) explains randomizers, multiworlds, and solo play.
- The [Archipelago glossary](https://archipelago.gg/glossary/en/) defines the terms used by clients and servers.
- The [official setup guide](https://archipelago.gg/tutorial/Archipelago/setup_en) covers installation, generation, hosting, and connection.
- The [supported games list](https://archipelago.gg/games) links each bundled game's setup and options pages.
- The [community APWorld index](/apworlds) lists additional integrations and their available setup, audit, and generation-test information.

For Crash Team Racing, [our complete setup guide](/guides/ctr) covers the native client from download to connection. If you get stuck, ask in the [Archipelago Discord](https://discord.gg/8Z65BR2) or the support space named by your game's maintainer.

## What the client does

An Archipelago client or connector links your game to the server room. It reports the locations you complete, receives items for your slot, and passes those items into the game.

The shape differs by game. You may see a separate Archipelago client window, a connection screen inside a mod, a launcher entry installed by an APWorld, or another connector documented by the maintainer. That variation is normal. This guide explains the shared pieces; the maintained guide for your exact game and version supplies the installation steps.

## What you need from the host

Do not start from an old room or a file from another seed. Ask the host for:

- the exact game and APWorld version;
- the maintained game-specific setup guide;
- the current server address and port;
- your exact slot name;
- the room password, if it uses one;
- any patch, mod, or other player-specific file generated for your slot;
- the start rule, especially whether connecting may send a location before a synchronized countdown.

Your slot name is the identity generated from your YAML. Spelling and capitalization must match the room exactly.

The **room page link** is a web page you can open in a browser. It shows connection information and, when a game produces them, player-specific data files. The **server address** is the host and port the client connects to, often written like `archipelago.gg:38281`. Do not paste the room page URL into a client unless the game-specific guide explicitly asks for it.

## Know which file you have

Several files can appear in the same Archipelago workflow:

- An **`.apworld`** installs a community game integration into Archipelago. Hosts need the required integrations for generation, and some players also install one to gain a launcher client or template support.
- A **YAML** describes one world and its options before generation. It is not a client or a game patch.
- A **generated player file** belongs to one slot in one seed. Depending on the game, it may patch legally obtained game data, install a seed-specific mod, or contain another form of player output.
- A **client or connector** is the software path that exchanges checks and items with the server while you play.

Use files from the current seed and the exact versions chosen by the host. Similar filenames from an earlier game are not interchangeable.

## Start with the game-specific guide

For a game included with Archipelago, open the [official supported games list](https://archipelago.gg/games), select the game, and use its setup guide. Official pages describe required game data, patches, emulators, clients, and connection steps for that integration.

For a community APWorld, use the maintainer's setup guide for the exact release. The [APWorld catalog](/apworlds) links a guide where one is recorded. A repository link is not automatically a setup guide, and some catalog entries do not yet have maintained instructions recorded. Ask the host or maintainer rather than guessing from another game.

Installing a community `.apworld` is often straightforward: open it through Archipelago Launcher or place it where that maintainer directs, then restart the launcher. But installing the integration does not necessarily install the base game, mod loader, generated player file, or every client component. Follow the release's own instructions.

> **Treat custom APWorlds as software, not passive data.**
>
> An installed `.apworld` can run code on your computer when Archipelago opens. Download only the exact release requested by the host from a source you trust. AP-Pie's audit information can help you review a release, but it is not a guarantee that the code is safe.

## Common setup patterns

These patterns help you recognize what a guide is asking for. A game may combine them or change its setup between versions.

### Generated patch and external client

Some integrations generate a patch for a legally obtained base game or ROM. Opening the player file may ask for the original game data, create a patched copy, and start or pair with a client. Use the game guide's required region, revision, emulator, and connector instructions.

### Separate game-specific client

Some games use a client supplied with Archipelago or by the integration maintainer. Start it, then enter the room details or use the connection command documented by that game.

### Mod with an integrated connector

Some modern games connect through an installed mod. The address and slot may be entered in an in-game menu, chat command, developer console, or mod configuration. There may be no separate client window.

### Launcher component installed by an APWorld

A community `.apworld` can add a game-specific client to Archipelago Launcher. Restart the launcher after installation and use the new entry only as its setup guide directs.

### Manual client or tracker-assisted play

Some integrations require the player to mark checks manually or use a dedicated manual client. A tracker can help show progress, but it does not replace the game client unless that integration's guide says it does.

### Browser or network-native integration

A smaller group of games or clients runs in a browser or connects through its own network interface. Use the URL and identity flow documented by that integration rather than assuming the normal launcher steps apply.

## Connect and test before play

Run the test the game-specific guide recommends before the event begins:

1. Confirm that the game, client, Archipelago, and APWorld versions match the host's versions.
2. Start every required mod, emulator bridge, connector, or client.
3. Open the current room page, download your player-specific file when one is provided, and copy the current server address and port.
4. Enter the server address, exact slot name, and password when required.
5. Confirm that the client reports a successful connection to the intended slot.
6. Confirm that the running game and connector can communicate.
7. Stop before completing or sending a location if the host has not started a synchronized game.

A successful server connection proves that the client reached the room. It does not always prove that the connector can read and update the game, so complete the game-specific communication test too.

## Troubleshooting the right layer

**You cannot find the client.** Check the maintained setup guide and release assets. For a community APWorld, confirm that it installed successfully and that Archipelago Launcher was restarted.

**The server refuses the connection.** Make sure you entered the server's `host:port`, not the browser URL for the room page. Recopy the current address and port from the room page, then check the password and exact slot name. A hosted room may have resumed with updated connection details after sleeping.

**The client connects but the game does not react.** The server side is working; inspect the game-side connector, mod loader, emulator script, permissions, or integration logs described by the setup guide.

**The slot is missing or belongs to another game.** Confirm that you are using the generated room and slot from the current seed, not the pre-generation collection room or an older server.

**Items arrive in the client but not in the game.** Keep the client connected, check the integration's delivery rules, and take its logs to the maintainer or support channel. Some games apply received items only at specific safe moments.

## Continue with your game

This guide stops where game-specific installation begins. Use the maintained guide for your exact game and release, and ask the host when a required guide or player file was not included in the handoff.

- [Getting started with Archipelago](/guides/getting-started) explains worlds, YAMLs, seeds, rooms, and the Join/Solo/Organize paths.
- [Setting up your YAML](/guides/setting-up-your-yaml) covers configuration before generation.
- [Browse the APWorld catalog](/apworlds) to find community integrations, versions, downloads, builders, and recorded setup links.

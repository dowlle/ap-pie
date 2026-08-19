## What a host actually does

Every multiworld has one person wearing the host hat. The host collects one configuration for each world, generates the game from that stack, puts the server online, and gives every player what they need to connect. Most players bring one world, so this often looks like one YAML per player.

Before you start, install Archipelago itself from the [official releases page](https://github.com/ArchipelagoMW/Archipelago/releases). The installer bundles the launcher, the generator, and the server in one package.

## Step 1: collect the YAMLs

Each player normally submits one YAML for each world they bring, and [Setting up your YAML](/guides/setting-up-your-yaml) explains that side. You can collect the files however you like, but chasing attachments through chat gets old fast. [How to host a room on Archipelago Pie](/guides/hosting-on-archipelago-pie) covers creating a collection room, sharing one link, checking submissions, closing at the deadline, and downloading the complete stack.

## Step 2: generate the game

Put all the YAML files in the `Players` folder inside your Archipelago install, then open the Archipelago Launcher and click **Generate**. The generator reads every YAML, weaves the worlds together, and writes a zip into the `output` folder. That zip is your whole multiworld in one file.

If generation fails, the error usually names the YAML that caused it. You can also check any single file beforehand at [archipelago.gg/check](https://archipelago.gg/check).

## Step 3: put the server online

The easy route is letting archipelago.gg host for you. Go to the [Host Game page](https://archipelago.gg/uploads), upload the zip from your `output` folder, and the site creates a room page. That web page shows the server address and port and, when available, lets each player download the data file generated for their slot. Hosted rooms may sleep after inactivity and resume when somebody opens the room page, so players should use the current connection details shown there.

You can also host on your own machine. Extract the `.archipelago` file from the output zip and double-click it, which starts the bundled Archipelago server on port 38281. Players outside your network can only reach it if you forward that port, so for most groups the archipelago.gg route is less hassle.

## Step 4: share and play

Give every player a complete handoff:

- the exact game, Archipelago, and APWorld version;
- the maintained game-specific setup guide;
- any generated player-specific patch, mod, or other output;
- the room page link, so players can see current connection information and retrieve available data files;
- the server address and port from the current room page;
- the exact slot name from the generated seed;
- the room password, if it uses one;
- the support channel and any synchronized-start rules.

From there each game's client, mod, or connector takes over. [Setting up an Archipelago game client](/guides/setting-up-a-game-client) explains the common patterns and a pre-play test. Exact installation steps belong in the game-specific guide.

While the game runs, the server console (or the room page on archipelago.gg) accepts commands. Players can ask for hints with their earned hint points, and as host you can release a leaver's remaining items or collect what belongs to a finished player. Type `/help` in the console to see what is available.

## Where to go next

If your players are new to all of this, hand them [Getting started with Archipelago](/guides/getting-started) and the per-game guides on [the guides page](/guides). For keeping an eye on everyone's progress, the room page here shows a live tracker, and [PopTracker](/guides/setting-up-poptracker) covers personal tracking.

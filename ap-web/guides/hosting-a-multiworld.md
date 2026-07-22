## What a host actually does

Every multiworld has one person wearing the host hat. The host collects a YAML from each player, generates the game from that stack, puts the server online, and shares the address so everyone can connect. None of those steps is hard, and this page walks through all four.

Before you start, install Archipelago itself from the [official releases page](https://github.com/ArchipelagoMW/Archipelago/releases). The installer bundles the launcher, the generator, and the server in one package.

## Step 1: collect the YAMLs

Each player owes you one YAML per game they play, and [Setting up your YAML](/guides/setting-up-your-yaml) explains that side. You can collect the files however you like, but chasing attachments through chat gets old fast, which is what this site exists for. [Create a room](/), share one link, and players submit their YAML in the browser while a validator checks every upload against the real generator rules. When the deadline passes, you download the whole stack as one zip.

## Step 2: generate the game

Put all the YAML files in the `Players` folder inside your Archipelago install, then open the Archipelago Launcher and click **Generate**. The generator reads every YAML, weaves the worlds together, and writes a zip into the `output` folder. That zip is your whole multiworld in one file.

If generation fails, the error usually names the YAML that caused it. You can also check any single file beforehand at [archipelago.gg/check](https://archipelago.gg/check).

## Step 3: put the server online

The easy route is letting archipelago.gg host for you. Go to the [Host Game page](https://archipelago.gg/uploads), upload the zip from your `output` folder, and the site creates a room page with the server address and port on it. The room stays available for days, so an async game where players connect whenever they have time works fine.

You can also host on your own machine. Extract the `.archipelago` file from the output zip and double-click it, which starts the bundled Archipelago server on port 38281. Players outside your network can only reach it if you forward that port, so for most groups the archipelago.gg route is less hassle.

## Step 4: share and play

Give every player the server address and their slot name, which must match the name in their YAML exactly. From there their own game clients take over.

While the game runs, the server console (or the room page on archipelago.gg) accepts commands. Players can ask for hints with their earned hint points, and as host you can release a leaver's remaining items or collect what belongs to a finished player. Type `/help` in the console to see what is available.

## Where to go next

If your players are new to all of this, hand them [Getting started with Archipelago](/guides/getting-started) and the per-game guides on [the guides page](/guides). For keeping an eye on everyone's progress, the room page here shows a live tracker, and [PopTracker](/guides/setting-up-poptracker) covers personal tracking.

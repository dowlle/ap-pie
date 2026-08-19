## What PopTracker is

PopTracker is an open source progress tracker for randomizers. You load a pack for your game and it shows your items, your map, and which checks are currently in logic, and with auto-tracking connected it updates itself while you play. It is the tool most Archipelago players reach for when the in-game tracking is not enough.

PopTracker helps you track checks and progression. It does not replace your game's Archipelago client unless that game's maintained setup guide explicitly describes that workflow. Set up the game side first with its own guide or [the game-client overview](/guides/setting-up-a-game-client).

## Installing PopTracker

Download it from the [PopTracker releases page](https://github.com/black-sliver/PopTracker/releases). Builds exist for Windows, macOS, and Linux, and on Windows you just unzip and run it. The app itself is game-agnostic, so this is a one-time install.

## Finding a pack for your game

This is the step that trips most people up, because packs are community-made and there is no single official store. Each game's pack lives wherever its community put it, which is usually a GitHub repository, and the reliable ways to find one are the game's own community channels and the [PopTracker Discord](https://discord.com/invite/gwThqMCPgK), which exists partly to point people at pack repositories. Games on this site have their packs linked from their guides where one exists, and Crash Team Racing has a community pack in active development at [CTRTrackerAP](https://github.com/therawkhawk64/CTRTrackerAP).

When you find a pack, download its release zip. You do not need to extract it.

## Loading the pack

The quick way is dragging the downloaded zip onto the PopTracker window and then picking it from the **Load** button in the top left corner. If you prefer keeping things organized on disk, PopTracker also reads packs from a few folders, and on Windows the simplest one is a `packs` folder next to the executable, with `Documents/PopTracker/packs` as a good alternative that survives updates.

## Connecting it to your game

Packs that support Archipelago auto-tracking show a grey **AP** symbol at the top of the window. Click it and enter the same details your game client uses, meaning the server address, your slot name, and the room password if there is one. The symbol turns colored once the connection is live, and from then on the tracker marks your checks and items as they happen in game.

If a pack tracks manually only, it still works, and you click things off yourself as you go.

## Where to go next

If you have not set up the game side yet, the per-game guides on [the guides page](/guides) cover that, and [Getting started with Archipelago](/guides/getting-started) explains the multiworld basics the tracker is showing you.

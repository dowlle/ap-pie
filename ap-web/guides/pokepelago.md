## What Poképelago is

Poképelago turns recalling Pokémon names into an Archipelago world. You catch a Pokémon by typing its name in the browser client. Each successful guess can send an item to any world in the multiworld, while items from other players unlock more of your dex.

There is no ROM, emulator, or separate game installation. The playable client runs at [pokepelago.ap-pie.com](https://pokepelago.ap-pie.com/). The custom `pokepelago.apworld` is only needed by the person generating the seed.

![The Poképelago browser client showing caught Pokémon and hidden silhouettes across three regions.](/img/guides/pokepelago-gameplay.png)

This guide reflects the current published release, Poképelago APWorld **0.6.4**. That APWorld requires **Archipelago 0.6.7 or newer**. In an organized multiworld, always use the exact APWorld version chosen by the host.

New to rooms, slots, YAMLs, and checks? Read [Getting started with Archipelago](/guides/getting-started) first.

## Try it without Archipelago

You can play Poképelago as a standalone guessing game before making a seed.

1. Open [Poképelago](https://pokepelago.ap-pie.com/).
2. Choose a sprite source. The quickest option on the opening screen configures PokeAPI sprites for your browser. You can also import a local sprite folder from Settings.
3. Select **Play Standalone**.
4. Choose your guessing language and type Pokémon names into the bar at the top.

Standalone progress stays in that browser. It is separate from every Archipelago slot you connect later.

## What you need for an Archipelago seed

If you are only joining a room that somebody else generated, you need the browser client and the connection details from your host. You do not need to install Archipelago or the APWorld yourself.

If you are creating or generating the seed, you need:

- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases/latest), version 0.6.7 or newer;
- [`pokepelago.apworld` for version 0.6.4](https://github.com/dowlle/PokepelagoClient/releases/download/v0.6.4/pokepelago.apworld);
- [`Pokepelago.yaml` from the same release](https://github.com/dowlle/PokepelagoClient/releases/download/v0.6.4/Pokepelago.yaml), or a YAML created for that same APWorld version;
- one YAML for every world included in the generation.

Custom APWorlds can run code on the generator's computer. Download Poképelago from its maintained release page and do not accept an unexplained replacement file from a third party.

## Install the APWorld

1. Open the Archipelago Launcher.
2. Select **Install APWorld** and choose `pokepelago.apworld`. On Windows, dragging the file onto the launcher or double-clicking it also works.
3. Keep only the version your seed will use. The generator and every Poképelago YAML in the multiworld should agree on that version.

Once installed, Poképelago behaves like the worlds included with Archipelago for local template creation and generation. Players using the browser client do not launch a Poképelago component from the Archipelago Launcher.

## Set up your YAML

Start from the `Pokepelago.yaml` shipped beside the APWorld. Change `name` to the exact slot name you want to use, then review the options under `Pokepelago`.

Poképelago 0.6.4 is available in the [APWorld catalog](/apworlds) and its [YAML Builder](/yaml-builder/pokepelago). [Setting up your YAML](/guides/setting-up-your-yaml) explains names, option weights, validation, and handoff in more detail.

### Pick regions deliberately

`regions` is the manual list of regions in your dex. `random_region_count` is disabled by default, so the manual list is honored unless you turn random selection on.

- For a small first seed, start with Kanto or two familiar regions.
- A nonzero `random_region_count` overrides the manual `regions` list.
- With `group_hisui_galar` enabled, random Gen 8 selection includes Galar and Hisui together.
- Version 0.6.4 will not randomly select Hisui as the only region. Hisui has only seven Pokémon, which is too small for some heavy lock combinations.

You can still request manual Hisui-only play with a light lock setup. Version 0.6.4 rejects a manual solo-Hisui configuration when two or more lock systems are enabled, before generation reaches a cryptic `FillError`. Pair Hisui with Galar or another region, or disable some locks.

### Choose how much gating you want

Type, region, route, evolution-line, badge, legendary, trade, baby, fossil, Ultra Beast, Paradox, and stone locks can all control which Pokémon are currently catchable.

For a first game, keep the template defaults and add one unfamiliar lock system at a time. Two details are easy to miss:

- The YAML key is `route_locks_enabled`. A key named `route_locks` is ignored by Archipelago.
- Route Locks and Line Locks automatically enable Dexsanity because their progression items need the per-Pokémon locations.

Line Locks add one progression item per active evolution family. Combining them with five or more regions and most other locks can make generation substantially slower. That is not a browser-client problem. Reduce the region or lock count if you want a faster first seed.

The default `local_filler_percent: auto` keeps much of Poképelago's large filler pool inside its own world while leaving progression and useful gate items available to the multiworld. It is a good default for group and asynchronous games.

## Generate and host the seed

1. Put every player's YAML in the Archipelago `Players` folder. Do not compress the individual YAML files.
2. Open the Archipelago Launcher and select **Generate**.
3. Find the generated `AP_*.zip` in the `output` folder.
4. Upload that archive through the [Archipelago host page](https://archipelago.gg/uploads), or start it with a local Archipelago server.
5. Share the server host, port, each player's exact slot name, and the password if the room uses one.

Uploading a generated seed to archipelago.gg is the easiest route for the browser client because the hosted room supports the secure WebSocket connection required by an HTTPS page.

## Connect the browser client

1. Open [pokepelago.ap-pie.com](https://pokepelago.ap-pie.com/).
2. Configure a sprite source on the opening screen. Poképelago does not host ripped sprite assets itself.
3. Choose **Connect to Archipelago**, then open **Manage Games** and select **Add Game**.
4. Give the saved connection any display name you recognize.
5. Enter the server hostname and port from the room page in their separate fields.
6. Enter your slot name exactly, including capitalization and spaces.
7. Add the room password only when the host supplied one, save, and select **Connect**.

The public client is served over HTTPS, so a remote server must support `wss://`. Standard archipelago.gg rooms do. Plain `ws://` connections are available only for localhost from the public client.

Saved games and progress live in your browser. A room password is stored in browser local storage when you save it, so avoid saving sensitive passwords on a shared computer.

## Start guessing

Choose the language you want to guess in and start typing Pokémon names. A recognized full name submits automatically.

The grid reflects the seed's active regions and the items your slot has received. A dark or locked entry is not necessarily a missing sprite. Select a Pokémon to see which gate is still closed. Starting items and Oak's Lab checks synchronize when you connect, and newly received keys update the available guesses.

You can request Archipelago hints from a Pokémon's detail view. The goal and caught count shown by the client come from the generated seed.

## Troubleshooting

### The APWorld will not install or load

Confirm that Archipelago is 0.6.7 or newer and that the file is named `pokepelago.apworld`. Re-download it from the maintained release page if its origin is uncertain.

### My manual regions were ignored

Set `random_region_count` to `0` or `disabled`. Any other value tells the generator to replace the manual `regions` list with a random selection.

### Route Locks do nothing

Use `route_locks_enabled` in the YAML. Archipelago ignores unknown option keys, including the tempting but incorrect `route_locks` spelling.

### Generation fails with Hisui

Version 0.6.4 does not randomly choose Hisui as the only region. If you manually select only Hisui and enable two or more lock systems, generation stops with an option error explaining the constraint. Add Galar or another region, or disable some locks.

### The client shows no Pokémon images

Return to Settings and configure a GitHub sprite repository URL, use the PokeAPI shortcut on the opening screen, or import a local sprite folder. The application intentionally does not ship the sprite artwork.

### The client cannot connect

Check the hostname, port, exact slot name, and password against the room page. From the public HTTPS site, remote servers must offer secure WebSockets. Use an archipelago.gg-hosted room when you do not control TLS and WebSocket proxying yourself.

### A Pokémon will not submit

Confirm the selected guessing language, then open the Pokémon's detail view. The seed may require a Type Key, Region Pass, Route Key, Line Unlock, badge, or another gate item before the guess is legal.

## Where to get help

Use the [Poképelago 0.6.4 release page](https://github.com/dowlle/PokepelagoClient/releases/tag/v0.6.4) for the maintained APWorld, template, and release notes. Report reproducible client or APWorld problems in the [Poképelago issue tracker](https://github.com/dowlle/PokepelagoClient/issues). For general multiworld questions, join the [Archipelago Discord](https://discord.gg/8Z65BR2).

## Crash Team Racing, the Archipelago way

CTR Archipelago turns the 1999 PlayStation classic into a native PC randomizer that connects to Archipelago multiworlds on its own. No emulator, no ROM patching, no extra client. Warp pads ask for new requirements every seed, and trophies, keys, gems, and relics become items that can come from any world in your multiworld.

New to Archipelago itself? Read [Getting started with Archipelago](/guides/getting-started) first. It explains rooms, YAML files, and slots. This page gets the game itself running.

<!-- video embed slot: setup walkthrough, when published -->

## What you need

1. **The game client.** Free, from the [releases page](https://github.com/dowlle/ctr-native-ap/releases). Download the latest release and unzip it into a folder of its own.
2. **A disc image of your own North American (NTSC-U) Crash Team Racing disc.** Usually a `.bin` file. The European and Japanese releases are detected and refused, so it really has to be the North American disc.

No Python, no installer, nothing to extract.

## Step 1: first launch

Run `ctr_native_ap.exe` once. On a fresh start it creates an `assets` folder next to the executable and tells you what it is waiting for. <!-- VERIFY: confirm on-screen wording on the shipped build -->

## Step 2: drop in your disc image

Copy your disc image into that `assets` folder. The filename does not matter: the game scans the folder and recognizes a valid North American disc automatically. <!-- VERIFY: confirm shipped discovery behavior --> Launch again and the game boots to the main menu.

If your image is a `.chd`, or something goes wrong here, the [full setup guide](https://github.com/dowlle/ctr-native-ap/blob/main/SETUP.md) covers every variant.

## Step 3: connect to your room

In the game, go to **Options** and then **Connection**. Fill in three fields:

- **Server**: your room address, for example `archipelago.gg:38281`. You can paste it straight from your room page. <!-- VERIFY: confirm paste ships in the current release -->
- **Slot**: your player name, spelled exactly as it appears in the room.
- **Password**: only if your room has one.

Hit **Connect** and watch the status line on the same screen. Once it says connected, you are done: settings are saved and the game reconnects by itself on later launches.

## Playing on Steam Deck

The Deck build works without a keyboard. Add the game to Steam, launch it from Gaming Mode, and focusing any connection field brings up the on-screen keyboard. The setup guide on GitHub has the details.

## Your YAML

The release bundle includes a template YAML with every option documented. Set your name, pick your goal, and submit it to your host. <!-- video embed slot: YAML explainer, when published -->

## When something goes wrong

The game tells you what is missing and why, and the [setup guide's troubleshooting section](https://github.com/dowlle/ctr-native-ap/blob/main/SETUP.md) covers the common cases. For crashes or a seed that looks impossible, run `support-bundle.bat` next to the executable and bring the archive it makes to the Discord or a GitHub issue. It contains your logs with the password stripped out, and no game data.

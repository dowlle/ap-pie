## Crash Team Racing, the Archipelago way

[CTR Archipelago](/ctr) turns the 1999 PlayStation classic into a native PC randomizer that connects to Archipelago multiworlds on its own, so you do not need an emulator, ROM patching, or a separate client. Warp pads ask for new requirements every seed, and trophies, keys, gems, and relics become items that can come from any world in your multiworld.

New to Archipelago itself? Read [Getting started with Archipelago](/guides/getting-started) first. It explains rooms, YAML files, and slots. This page gets the game itself running. And if you only want plain Crash Team Racing on PC without the randomizer, see [Play Crash Team Racing on PC](/guides/crash-team-racing-pc) instead.

## What you need

**The game client**, from the [download page](/ctr/download). Download the latest stable release and unzip it into a folder of its own. There is nothing else to install, and you do not need Python.

> **Bring your own disc.** No game data is included. You need a disc image of your own North American (NTSC-U) Crash Team Racing disc, usually a `.bin` file. A `.cue` plus `.bin`, a single `.bin`, or a `.chd` all work. The European and Japanese releases are detected and refused, so it really has to be the North American disc.
>
> If you only have the physical disc, dump it with any standard PlayStation disc-dumping tool first. The game wants a raw image (MODE2/2352, which is what most dumping tools produce by default), not a renamed `.iso`.

## Step 1: first launch

Run `ctr_native_ap.exe` (Windows) or `ctr_native_ap` (Linux) once. On a fresh start it creates an `assets` folder next to the executable and tells you what it is waiting for. <!-- VERIFY: confirm on-screen wording on the shipped build -->

## Step 2: drop in your disc image

Copy your disc image into that `assets` folder. The filename does not matter: the game scans the folder and recognizes a valid North American disc automatically. <!-- VERIFY: confirm shipped discovery behavior --> Launch again and the game boots to the main menu.

If your image is a `.chd`, or something goes wrong here, the [full setup guide](https://github.com/dowlle/ctr-native-ap/blob/main/SETUP.md) covers every variant.

## Step 3: connect to your room

In the game, go to **Options** and then **Connection**. Fill in three fields:

- **Server**: your room address, for example `archipelago.gg:38281`. You can paste it straight from your room page. <!-- VERIFY: confirm paste ships in the current release -->
- **Slot**: your player name, spelled exactly as it appears in the room.
- **Password**: only if your room has one.

Hit **Connect** and watch the status line on the same screen. Once it says connected, you are done: settings are saved and the game reconnects by itself on later launches.

## Playing on Linux and Steam Deck

The Linux build ships as a `.tar.gz` with a `ctr_native_ap` executable inside; extract it and run it the same way as the Windows build. On Steam Deck it works without a keyboard: add the game to Steam, launch it from Gaming Mode, and focusing any connection field brings up the on-screen keyboard. The [setup guide on GitHub](https://github.com/dowlle/ctr-native-ap/blob/main/SETUP.md) has the details.

## Your YAML

If somebody already generated the multiworld for your group, you can skip this section: joining needs nothing but the client and your room details. A YAML is how you pick your own settings while the host is still collecting players for a new game.

The release bundle includes a template YAML with every option documented, and you can also build one in the browser from [the APWorld index](/apworlds) with the Create YAML button on the CTR entry. Set your name, pick your goal, and submit it to your host. The [setup guide on GitHub](https://github.com/dowlle/ctr-native-ap/blob/main/SETUP.md) covers the details, and [Setting up your YAML](/guides/setting-up-your-yaml) explains the format in depth if it is new to you.

## When something goes wrong

The game tells you what is missing and why, and the [setup guide's troubleshooting section](https://github.com/dowlle/ctr-native-ap/blob/main/SETUP.md) covers the common cases. For crashes or a seed that looks impossible, run `support-bundle.bat` (Windows) or `support-bundle.sh` (Linux) next to the executable and bring the archive it makes to Discord or a [GitHub issue](https://github.com/dowlle/ctr-native-ap/issues). It contains your logs with the password stripped out, and no game data.

## Come say hi

For questions, feedback, or showing off a seed, join the [Archipelago Discord](https://discord.gg/8Z65BR2) and find the [Crash Team Racing channel](https://discord.com/channels/731205301247803413/1222304293751750777).

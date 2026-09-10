## Crash Team Racing, the Archipelago way

[CTR Archipelago](/ctr) turns the 1999 PlayStation classic into a native PC randomizer that connects to Archipelago multiworlds on its own, so you do not need an emulator, ROM patching, or a separate client. Warp pads ask for new requirements every seed, and trophies, keys, gems, and relics become items that can come from any world in your multiworld.

New to Archipelago itself? Read [Getting started with Archipelago](/guides/getting-started) first. It explains rooms, YAML files, and slots. This page gets the game itself running. And if you only want plain Crash Team Racing on PC without the randomizer, see [Play Crash Team Racing on PC](/guides/crash-team-racing-pc) instead.

## What you need

**0.2.0 is the current stable release.** Read the [full release notes](/ctr/reference/0-2-0-release-notes) for the new settings, experimental features and remaining testing coverage. Use a matching 0.2.0 client and APWorld when generating a new game, with fresh seeds.

Prefer video? [Watch Appie's CTR setup walkthrough](https://youtu.be/9x63P6JP93E). It predates 0.2.0, so use the current downloads and written instructions alongside it. If you are organizing the multiworld, the [hosting video](https://youtu.be/CpRbyRodayM) and [written hosting guide](/guides/hosting-a-multiworld) cover generation and running the server.

**The game client**, from the [download page](/ctr/download). Download the latest stable release and unzip it into a folder of its own. The raw `.bin` setup needs no Python; `.chd` extraction uses the tools described below.

> **Bring your own disc.** No game data is included. You need a disc image of your own North American (NTSC-U) Crash Team Racing disc, usually a `.bin` file. A `.cue` plus `.bin`, a single `.bin`, or a `.chd` all work. The European and Japanese releases are detected and refused, so it really has to be the North American disc.
>
> If you only have the physical disc, dump it with any standard PlayStation disc-dumping tool first. The game wants a raw image (MODE2/2352, which is what most dumping tools produce by default), not a renamed `.iso`.

## Step 1: first launch

Run `ctr_native_ap.exe` (Windows) or `ctr_native_ap` (Linux) once. On a fresh start it creates an `assets` folder next to the executable and tells you what it is waiting for. <!-- VERIFY: confirm on-screen wording on the shipped build -->

## Step 2: drop in your disc image

Copy your raw `.bin` disc image into that `assets` folder. The filename does not matter: the game scans the `.bin` files and recognizes a valid North American disc automatically. Launch again and the game boots to the main menu.

For a `.chd`, use the bundled `extract_assets.py` with Python and `chdman`, following the [extraction instructions](https://github.com/dowlle/ctr-native-ap/blob/v0.2.0/SETUP.md#appendix-extracting-the-assets-most-people-should-skip-this). The automatic drop-in path above is for raw `.bin` images.

## Step 3: connect to your room

In the game, go to **Options** and then **Connection**. Fill in three fields:

- **Server**: your room address, for example `archipelago.gg:38281`. You can paste it straight from your room page.
- **Slot**: your player name, spelled exactly as it appears in the room.
- **Password**: only if your room has one.

Hit **Connect** and watch the status line on the same screen. Once it says connected, you are done: settings are saved and the game reconnects by itself on later launches.

## Playing on Linux and Steam Deck

The Linux build ships as a `.tar.gz` with a `ctr_native_ap` executable inside; extract it and run it the same way as the Windows build. On Steam Deck it works without a keyboard: add the game to Steam, launch it from Gaming Mode, and focusing any connection field brings up the on-screen keyboard. The [setup guide on GitHub](https://github.com/dowlle/ctr-native-ap/blob/main/SETUP.md) has the details.

## Your YAML

If somebody already generated the multiworld for your group, you can skip this section: joining needs nothing but the client and your room details. A YAML is how you pick your own settings while the host is still collecting players for a new game.

The easiest way is the browser builder: **[open the CTR YAML Builder](/yaml-builder/ctr)** and it starts right away, no searching needed. Set your name, pick your goal, and the rest of the options come filled in with sensible defaults you can adjust as you like. Review the result, download it, and hand it to your host.

You can also start from the [template YAML published as a separate release asset](/ctr/download/template) and edit it by hand if you would rather; [Setting up your YAML](/guides/setting-up-your-yaml) explains the format in depth. Use the template that matches the CTR APWorld version your host is generating with. The [setup guide on GitHub](https://github.com/dowlle/ctr-native-ap/blob/main/SETUP.md) has the full details.

A dedicated CTR 0.2.0 YAML explanation video is coming soon. Until then, the [0.2.0 Builder](/yaml-builder/ctr?version=0.2.0), its option help and the [CTR reference](/ctr/reference) cover the available settings.

## When something goes wrong

The game tells you what is missing and why, and the [setup guide's troubleshooting section](https://github.com/dowlle/ctr-native-ap/blob/main/SETUP.md) covers the common cases. For crashes or a seed that looks impossible, run `support-bundle.bat` (Windows) or `support-bundle.sh` (Linux) next to the executable and attach the archive it makes to a [GitHub issue](https://github.com/dowlle/ctr-native-ap/issues/new/choose), or bring it to the [Crash Team Racing channel](https://discord.com/channels/731205301247803413/1222304293751750777) on the Archipelago Discord. It contains your logs with the password stripped out, and no game data.

## Come say hi

For questions, feedback, or showing off a seed, join the [Archipelago Discord](https://discord.gg/8Z65BR2) and find the [Crash Team Racing channel](https://discord.com/channels/731205301247803413/1222304293751750777).

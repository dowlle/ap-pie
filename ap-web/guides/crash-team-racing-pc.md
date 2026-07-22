## Crash Team Racing, running natively on your PC

Crash Team Racing, the 1999 PlayStation kart racer, can be played on a modern PC today, and it does not go through an emulator. The game runs as a native Windows or Linux program with the original handling intact, which is possible thanks to a community decompilation effort. This page walks you through setting it up.

## How is this possible?

Over several years, the [CTR-ModSDK](https://github.com/CTR-tools/CTR-ModSDK) project decompiled Crash Team Racing: the community reconstructed the game's original code from the PlayStation release. On top of that work, [ctr-native](https://github.com/CTR-tools/ctr-native) rebuilds the game as a real PC program. Both projects are open source, and neither is affiliated with the game's publisher.

A decompilation does more than enable a PC port. Because the game's code is readable again, modding becomes practical in a way it never was on the original disc. The randomizer covered [elsewhere on this site](/guides/ctr) exists because of exactly that.

## What you need

**The ctr-native release**, from the [ctr-native releases page](https://github.com/CTR-tools/ctr-native/releases). Download the latest Windows zip (or the Linux build) and unzip it into a folder of its own.

> **Bring your own disc.** No game data is included, and none of these projects distribute any. You need a disc image of your own North American (NTSC-U) Crash Team Racing disc, in the common raw PSX BIN layout (MODE2/2352 sectors). A cooked 2048-byte ISO will not work, and other regions are not supported.

## Setup

1. Unzip the release. You get `ctr_native.exe` (or `ctr_native` on Linux).
2. Create an `assets` folder next to the executable, copy your disc image into it, and rename the copy to `ctr-u.bin`:

        CTR-Native/
          ctr_native.exe
          assets/
            ctr-u.bin

3. Launch the executable. The game boots to the main menu and plays like you remember, at your monitor's resolution.

Keep in mind that the port is in active development and its releases are marked as beta. Most things work well, but if you hit a rough edge, the [ctr-native issue tracker](https://github.com/CTR-tools/ctr-native/issues) is the right place to report it.

## Want more than vanilla?

The same decompilation powers a growing mod scene, and the biggest thing built on it so far is **CTR Archipelago**: a randomizer that shuffles the adventure mode's progression and can connect your race to a multiworld with your friends' games. It ships as its own standalone build of the port, so it is one download with the same setup as above. Start with [our CTR Archipelago guide](/guides/ctr), and if multiworlds are new to you, [Getting started with Archipelago](/guides/getting-started) explains the concept first.

![Racing on Cortex Vortex in CTR Archipelago 0.2.1](/img/ctr/cortex-vortex-hero.jpg)

**CTR Archipelago 0.2.1 adds Hit Character checks, races on Slide Coliseum and Turbo Track, Cortex Vortex, an in-game Adventure tracker and room links on Windows, plus a batch of logic fixes.**

**[Download 0.2.1](/ctr/download)** · **[Setup guide](/ctr/setup)** · **[Build a 0.2.1 YAML](/yaml-builder/ctr?version=0.2.1)**

## At a glance

- Add Trophy Races and CTR Challenges to Slide Coliseum and Turbo Track, or turn on Hit Character checks for every racer you hit.
- Race Oxide's Final Challenge on [Lockheart's Cortex Vortex](https://www.youtube.com/watch?v=pV2NdYr8W0Y), and optionally put the track on a warp pad and in Gem Cups too.
- Open the Adventure tracker from the hub pause menu to see checks per destination, racer locks and what you've received.
- Click your slot's link on an Archipelago room page and the game opens and connects (Windows).
- [AP boxes](/ctr/reference/ap-boxes) get a new crate look and can show the colour of the item inside.
- Boost requirements, shuffled pads, racer locks and two hard-to-reach AP boxes are fixed.

## Where should I start?

- **Joining a room?** Get the client from the [download page](/ctr/download) and follow the [CTR setup guide](/ctr/setup). You need your own NTSC-U disc image. On Windows you can open your slot's link on the room page and the client connects for you; if the room has a password, you still type it on the Connection page.
- **Preparing a YAML?** Use the [0.2.1 YAML Builder](/yaml-builder/ctr?version=0.2.1) and send the YAML to your host. The [YAML guide](/guides/setting-up-your-yaml) explains the file.
- **Hosting?** Install the matching `ctr.apworld` and follow the [hosting guide](/guides/hosting-a-multiworld). Archipelago 0.6.7 or newer is needed. `Crash.Team.Racing.yaml` on the GitHub release is the template for this version.

## Compatibility and upgrading

- **New games:** use the matching 0.2.1 client, APWorld and YAML with a fresh seed.
- **Ongoing rooms:** ask the host before changing versions, and keep the APWorld that generated the room for its server and Universal Tracker.
- **Replacing the client:** back up your client folder first, including settings and saves. Each platform archive has the client and the matching `ctr.apworld`.
- **Your disc:** you need your own North American (NTSC-U) disc; no game data is included. The client now finds your disc from a path given at startup, a remembered path or the existing assets folder, and shows a file picker on first start if it finds none. Existing setups keep working. The first-start picker wasn't part of the test pass.
- **Linux and Steam Deck:** use the Linux tarball; it needs glibc 2.36 or newer. The Linux build passed its automated checks, and I gave the release candidate a quick check on the Steam Deck.

## Known issues and testing

I played through the Windows test list in Steam on the release candidate: the new box look and colours, the tracker, room links (including a room hosted on archipelago.gg), racer locks, the Options pages, podium skipping and Hit Character checks. Automated tests, both platform builds and the full generation fuzz matrix passed; a local fuzz run on the exact `ctr.apworld` did 19,500 generations with no failures or timeouts. I also gave the release candidate a quick check on the Steam Deck.

- **Reconnecting:** a large backlog of received items can stall the game for a while. If it happens, include the support bundle in your report. See [#147](https://github.com/dowlle/ctr-native-ap/issues/147).
- **Steam Deck:** turning on Fullscreen can cause heavy lag. Leave it off. See [#260](https://github.com/dowlle/ctr-native-ap/issues/260).
- **Podiums:** some characters can appear invisible on the post-race podium. It's cosmetic. See [#282](https://github.com/dowlle/ctr-native-ap/issues/282).
- **Universal Tracker:** if a YAML in the room fills in `custom_tracks`, Universal Tracker may show a datapackage checksum warning. That's expected, and tracking still works normally.
- **Cortex Vortex relic times:** the targets are placeholders using Oxide Station's times until the track author sends real ones. Relic Race checks on Cortex Vortex weren't confirmed in game.

## New checks and options

- **Slide Coliseum and Turbo Track:** `slide_coliseum_races` and `turbo_track_races` (both off by default) add a Trophy Race, or a Trophy Race and CTR Challenge, to these tracks, with letters and podium checks like the other tracks. Their pads show the item for those checks.
- **Cortex Vortex:** Lockheart's track is included and is now the default venue for Oxide's Final Challenge (`oxide_final_track`; pick `oxide_station` for the original). The new `cortex_vortex_track` option (off by default) also puts it on a warp pad and in Gem Cups, with Trophy, Time Trial, CTR Token, letter, podium and Wumpa checks. Because it has no pad of its own, one other destination loses its pad and its checks each seed. If that's a boss track, its 10 Wumpa check stays and you get it in the boss race.
- **Oxide 1:** when your goal is Oxide 2, `oxide_1_optional` makes Oxide's first challenge `mandatory` (default), `optional` or `filler`.
- **Hit Character:** `hit_character` (off by default) adds sixteen checks, one for the first time you hit each racer in an Adventure race. Unlocked guest racers join your races, up to three per race, racers you haven't hit yet first. A boss joins after you beat them, Fake Crash, Penta Penguin and N. Tropy after a win on one of their two tracks, and Nitros Oxide after an Oxide win. If a guest's unlock race isn't in the seed, they join once you hold a set number of Keys: Fake Crash 1, Penta Penguin 2, N. Tropy 3, Nitros Oxide 4. Hits count in Trophy Races, CTR Challenges and other Adventure races, but not in Relic Races, crystal challenges or boss races. With Itemsanity you need a Bomb or Missile before these checks are in logic. Checked in Steam on Windows.
- **Item Box Colours:** `color_boxes_by_item` (on by default) colours AP boxes by the item inside: purple progression, blue useful, cyan filler, salmon trap. Boxes stay pink until the game has looked up what's inside. You can switch colours off for yourself under Options > Archipelago > Item Box Colours; if the seed turned them off, that row reads OFF (SEED). Checked in Steam on Windows.
- **New AP box look:** boxes use a wood frame and crate face read from your own disc, with JurnthReinal's Archipelago face art on top. They're the same size as the retail crates, and no retail graphics are in the download. Checked in Steam on Windows.
- **Room links (Windows):** the Archipelago Launcher now has a Crash Team Racing Client. Clicking your slot's game client link on a room page starts CTR and connects without typing the server or slot. If the game is already open in another room, it asks at the main menu before switching. The client registers itself for these links when it starts, and Options > Archipelago > Room links sets which client opens them. A console window flashes briefly when a link is handled. Checked in Steam on Windows, including a room hosted on archipelago.gg. Room links on Linux and Steam Deck aren't supported yet.

## Logic and generation fixes

- **Boost:** Platinum Time Trials need two Progressive Boosts on Easy and Medium, three on Easy with Blue Fire; Hard keeps its per-track rules. Every boss win needs at least one boost, and Pinstripe on Hot Air Skyway and Oxide on Oxide Station need two at medium shortcut knowledge. Trophy Races on 13 harder tracks need one boost or three weapon types, and every CTR Token Challenge needs one boost when Progressive Boost is on. Under Hard Shortcut Knowledge, Oxide Station's T and R letters and its full CTR Challenge need two boosts.
- **Hard-to-reach checks:** with Itemsanity, Tiger Temple's CTR Token Challenge now needs a shortcut door opener. Mystery Caves Item Box 13 moved one box length earlier so you can reach it off the turtle bounce without boost, and Polar Pass Item Box 4 now sits on the ground. No box was renumbered. Both boxes checked in Steam on Windows.
- **Pads and cups:** a pad's second stage is now always higher than its first when both use the same item type (thanks [venusyprime](https://github.com/venusyprime), [#342](https://github.com/dowlle/ctr-native-ap/issues/342)). Gem Cup finish logic with shuffled pads now looks at the racer locking the cup's actual pad. Racer locks use a different racer each until every racer has been used, and a racer's unlock is never behind a pad that racer locks. Regenerating the same seed number can give different locks.
- **Goals:** a Gems Required goal with Shuffle Gems on and Include Gem Cups off used to stop generation for the whole multiworld. That slot now keeps its Gems on their Gem Cups and the generation log says so. An Oxide Final Challenge relic count above 18 in a single-tier mode now becomes 18 with a warning instead of failing.
- **Settings:** the Upside Down trap is off by default now; give it a weight to bring it back. The `random_without_4_keys` text now says what it does: no pad needs all four Keys, but pads can still need one to three. Option help texts are shorter, with the details on the game page.

## Client and display changes

- **Adventure tracker:** press Square in the hub pause menu, or pick the new TRACKER row, to open a big hub map with the checks at each destination. L1/R1 go through the five hub maps and then two tabs. RACERS shows every racer, whether you have them, the pads they lock (named by where that pad goes in your seed) and their Hit check. ITEMS shows your Keys, Trophies, Relics, CTR Tokens, Gems, boost and stat levels, and the Itemsanity weapon checks. Pad panels show which racer a locked pad needs. Checked in Steam on Windows.
- **Podiums:** an AP Trophy podium shows your received Trophy count and the item at that Trophy check, instead of the retail count-up that jumped back. Checked in Steam on Windows.
- **Skip Podium Ceremonies:** a new option under Options > Gameplay (off by default) skips Trophy, CTR Challenge and Relic Race podiums once the rewards are in. Boss and Gem Cup ceremonies still play. When a Relic Race earns a new relic, the results screen is skipped too and no best time is saved; without a new relic you keep the results and Retry. Checked in Steam on Windows.
- **Options menu:** Options is split into Video, Gameplay, Connection, Archipelago and Authoring pages. Cross now steps through multi-choice rows, and Driver Name can be edited in game. Your saved settings still load. New: VSync (Off, On, Adaptive; off by default) under Video, and Mute When Unfocused under Gameplay for when you alt-tab between games. The window also reopens where you left it, at the same size. Checked in Steam on Windows.
- **AP boxes in locked races:** boss races no longer let you collect a track's AP boxes while that track's pad is still locked. In boss races and Gem Cup legs those boxes now show as see-through and can't be broken until the pad opens.
- **Racer names:** locked pads use the same racer names as the item feed, for example PENTA instead of PENGUIN (thanks [venusyprime](https://github.com/venusyprime), [#362](https://github.com/dowlle/ctr-native-ap/issues/362)).
- **Widescreen:** the gold glow behind a juiced item no longer splits in the middle. Checked at 16:9.
- **Not yet confirmed in game:** Ripper Roo's defeat line now names the item in his check, and whose world it goes to. Wumpa Fruit packages use the real Wumpa Fruit model from your disc, with the AP marker as a fallback. Nitro Drop and Red Potion traps now land in your path at full speed instead of behind you. These are in the release but weren't part of the test pass; please report anything that looks off.
- **Custom tracks:** the Custom Content page now uses Baby T Park 1.0.2, the current version on Project Saphi, when no seed asks for a specific version, so Download Saphi, Copy YAML and Save YAML all use 1.0.2. Seeds made for 1.0.0 still play with your installed 1.0.0 files. The page also shows the full path where it saved the custom-track YAML.
- **Smaller changes:** recorded AI picks the right lap recordings on Cortex Vortex.

## Moved to a later release

The 0.2.0 notes planned these for 0.2.1, and they aren't in it: the optional check for breaking every Relic Race time crate ([#49](https://github.com/dowlle/ctr-native-ap/issues/49)) and harder relic-time tiers ([#120](https://github.com/dowlle/ctr-native-ap/issues/120), [#247](https://github.com/dowlle/ctr-native-ap/issues/247)). A DeathLink mode where a death costs you the race ([#286](https://github.com/dowlle/ctr-native-ap/issues/286)) is in the client already but has no YAML option yet. Generalized custom tracks are planned for 0.3.0. The separate box authoring download isn't part of this release and follows later.

## Credits

[Cortex Vortex](https://www.youtube.com/watch?v=pV2NdYr8W0Y) is by Lockheart. The AP box face art is by JurnthReinal. The Archipelago logo is by Krista Corkos and Christopher Wilson, CC BY-NC 4.0. Thanks to [venusyprime](https://github.com/venusyprime) for the pad and racer name reports, and to everyone who tested the alphas and sent feedback.

## Reporting a problem

[Open a GitHub issue](https://github.com/dowlle/ctr-native-ap/issues/new/choose) with your platform, client version, seed or YAML, what happened and the support bundle. Run `support-bundle.bat` on Windows or `support-bundle.sh` on Linux and look through the bundle before attaching it; it doesn't upload anything by itself.

Questions are welcome in the [Crash Team Racing channel](https://discord.com/channels/731205301247803413/1222304293751750777) on the Archipelago Discord. The [GitHub release](https://github.com/dowlle/ctr-native-ap/releases/tag/v0.2.1) has the downloads, checksums and debug files.

**CTR Archipelago 0.2.0 is the current stable release, published September 10, 2026.** It adds more things to find, more ways to build your kart and more choices for your Adventure Mode goal. Most new systems are optional settings chosen before the game is generated.

**[Download 0.2.0](/ctr/download)** · **[Setup guide](/guides/ctr)** · **[Build a 0.2.0 YAML](/yaml-builder/ctr?version=0.2.0)**

## At a glance

- **Find more rewards:** hunt for AP boxes, collect individual CTR letters and unlock weapon-use or Wumpa checks.
- **Unlock racers and improve your kart:** receive characters, boost abilities and stat upgrades from anywhere in the multiworld.
- **Choose your adventure:** shuffle Gem Cup tracks, add racer requirements to warp pads and combine Oxide, Boss and Gem goals.
- **Add surprises:** choose from twenty trap effects, plus useful items such as a Turbo that waits until your weapon slot is free.
- **Read the game more easily:** clearer pad requirements and item messages, widescreen choices, render scaling and improved recovery after disconnects.

In Archipelago, a **check** is an action that awards something, such as winning a race or breaking an AP box. Its **item** may go to you or another player. Your **YAML** is the settings file you give the host before generation. The **APWorld** is the package that adds CTR to the Archipelago generator; it is separate from the game client you drive in.

## Where should I start?

- **Joining a room that is already generated?** Follow the [CTR setup guide](/guides/ctr): download the client, add your disc image and connect with the server address and slot name your host provides. You do not need to install the APWorld just to play.
- **Preparing settings for a new room?** Open the [0.2.0 YAML Builder](/yaml-builder/ctr?version=0.2.0), set your player name and options, download the YAML and send it to your host. The [YAML guide](/guides/setting-up-your-yaml) explains the file.
- **Generating or hosting the multiworld?** Install the matching [0.2.0 APWorld](/ctr/download/apworld), collect everyone's YAMLs and follow the [hosting guide](/guides/hosting-a-multiworld). AP-Pie helps prepare and collect settings; generation and the game server run through Archipelago.

Prefer video? Watch Appie's [CTR setup walkthrough](https://youtu.be/9x63P6JP93E) or [hosting walkthrough](https://youtu.be/CpRbyRodayM). The setup video predates 0.2.0, so use the current downloads and written instructions alongside it. A dedicated CTR 0.2.0 YAML explanation video is coming soon.

## Compatibility and upgrading

- **New games:** use the matching 0.2.0 client and APWorld, a 0.2.0 YAML and a fresh seed. A seed is the generated game shared by the room.
- **An ongoing room:** ask the host before changing versions. Do not assume an Alpha seed can be mixed with the final 0.2.0 pair. A 0.1.5 client cannot play a 0.2.0 seed correctly.
- **Before replacing a client:** back up the existing folder, including settings and saves. Get the full archive for your platform from the [download page](/ctr/download).
- **Your disc:** you need your own North American (NTSC-U) CTR disc image. No game data is included. A raw `.bin` works directly; `.chd` extraction needs Python and `chdman`, as explained in [setup](/guides/ctr).

## Practical limitations and testing

Automated checks passed for the final release, but some gameplay and connection scenarios still need community playtesting. Recorded-AI playback and custom content are experimental and off by default. Report problems with the client version, platform, seed or YAML and support bundle so they can be reproduced and fixed in a matching 0.2.x release.

- **Steam Deck:** if enabling Fullscreen causes heavy lag, leave it off and use the default windowed setting. See [#260](https://github.com/dowlle/ctr-native-ap/issues/260).
- **Reconnecting:** a large backlog of received items can still cause a long pause. If this happens, include the support bundle in your report.
- **Podiums:** some characters can appear invisible. Nitros Oxide has no retail win-dance model; other reported cases remain under investigation. See [#282](https://github.com/dowlle/ctr-native-ap/issues/282).
- **Recorded AI:** opponents currently share a few recorded driving lines, and contributor names can repeat. Finish-line movement and ordinary-crate interactions still need improvement. Turn playback off and start a new race to return to normal AI lines.
- **Custom tracks:** 0.2.0 includes only the narrow Baby T Park preview described below. Generalized custom-track support is planned for 0.3.0.
- **Later additions:** optional checks for breaking every Relic Race time crate, recorded-AI corrections, and Nitro Drop/Red Potion balance improvements are planned for 0.2.1.

## New checks and item families

### AP boxes

`box_locations` adds up to 241 authored AP crates across the 18 race tracks. These are extra places to search, with numbered names for boxes on the same track. `shortcut_knowledge` controls whether easy, medium or hard routes may be required.

Only the local player can break an AP crate. Once checked, it stays gone for that seed. The pad shows how many remain, and kart and direct-projectile contact is more forgiving in the final release. Complete PopTracker mapping and per-track box maps are still being developed.

### Itemsanity

With `itemsanity` enabled, CTR's 11 Adventure weapons become unlocks you receive from the multiworld. Using each weapon sends a check, with another for using it while holding ten Wumpa. The weapon unlocks and all 22 firing checks are enabled together. Weapon rolls respect the weapons you own, including in arenas.

### Lettersanity

The C, T and R letters on the 16 CTR Token Challenge tracks can stay vanilla, become individual checks, require received letter items, or use both settings together. The full form adds up to 48 checks and 48 items. A letter you have not received appears translucent and cannot be collected.

### Wumpa progression

Starting-Wumpa upgrades and Wumpa bundle items can join the pool. `wumpa_check` can be off, one check for reaching ten Wumpa anywhere, or one for each eligible track. The track's race, a Gem Cup leg or a boss race on that track can provide another route to the same check.

Routes remain replayable while their eligible Wumpa checks are unfinished. Starting Wumpa is restored after a pause-menu restart. Slide Coliseum and Turbo Track do not receive an unreachable check while they remain relic-only; this release does not add standalone Trophy or CTR Challenge events to those tracks.

### Turbo Grant and Tizi Helper

`Turbo Grant` adds received `Turbo` filler items. A Turbo waits until you are in a race with a free weapon slot instead of being lost.

The optional `Tizi Helper` makes the first four boxes after the Papu's Pyramid start give Masks for the Tiziano shortcut. With Itemsanity enabled, you also need to own the Mask weapon. The generator does not assume you will use this helper to reach required checks.

## Characters and kart progression

### Character unlocks and racer-locked pads

`character_unlocks` puts the other racers in the item pool. Use **Select Character** in the Adventure pause menu to choose a racer you have received.

`racer_locked_pads` sets the maximum number of pads that may require a particular racer. Zero turns it off; higher values require Character Unlocks. A pad shows **REQUIRES &lt;CHARACTER&gt;** until you receive that racer. Entering uses the required racer for that race and restores your previous selection on returning to the hub.

The starting racer and driving class can be chosen in the YAML. Optional manual stat editing is in the pause-menu character screen, not the Garage. Progressive Stats takes priority when enabled.

### Progressive Boost

Boost can be an upgrade ladder shared across the roster or received separately for each racer:

1. Before the first item, ordinary turbo pads work, but powerslides and hang time do not create boost.
2. The first item enables ordinary self-earned boost.
3. The second enables Ultimate Sacred Fire speeds on routes that support them.
4. An optional third enables Blue Fire, with blue exhaust and stronger reserves that can survive U-turns.

Turn the option off to keep ordinary boost behavior. Disable the Blue Fire tier to end the ladder at Ultimate Sacred Fire.

### Progressive Stats

Top Speed, Acceleration and Turning each rise from Very Low through Very High as you receive upgrades. The pause-menu character screen shows the effective ranks. Upgrades can be shared across the roster or belong to individual racers; a Crash upgrade then does not improve Coco.

## Routes, logic, and goals

### Randomized Gem Cups

Gem Cup legs can be drawn independently from the 16 Trophy Race tracks, including repeats. A track's ordinary pad remains a separate route. For AP boxes in a Cup leg, the generator still checks whether you can access that track through its own pad; a Cup entrance alone does not make those boxes available in logic.

### Choose what counts as finishing

Combine beating Oxide, winning a chosen number of the four boss races, and holding a chosen number of the five Gems. Every enabled condition must be met. You can choose Oxide's first Challenge or Final Challenge as the ending, and configure the relic requirement for the Final Challenge.

`oxide_goal: none` keeps both Oxide races as optional checks. `oxide_goal: disabled` closes his garage and removes both races, so you must enable a Boss or Gem goal instead. With optional Oxide, your Boss and Gem goal conditions do not block his optional races.

### Requirements follow your settings

The generator considers character unlocks, racer locks, boost and stat upgrades, weapon and letter ownership, and the shortcut difficulty you selected. It avoids assuming that a racer has upgrades you have only received for somebody else.

Received Sapphire, Gold and Platinum **relic items** count separately: a Platinum item does not count as Gold. Race-result **checks** work differently: beating a Platinum target time can also send that track's Gold and Sapphire checks.

## Traps and comfort items

Twenty effects are included: Icy Road, Low Gravity, Forced USF, Forced Boost, First Person, Wumpa Wipeout, Flatten, Item Reroll, Forced Use, Empty Crates, Weakened Kart, Boost Blocker, Wireframe, Nitro Drop, Reverse Steering, Red Potion, Upside Down, Mirror Mode, Warpball Ambush and Demo Camera.

Use `trap_weights` to make individual effects more common, less common or absent. The client also offers short, normal and long duration presets. Traps wait for an appropriate gameplay moment when needed, and their timers pause with the game.

Optional comfort items let you ignore natural Grass, Dirt/mud, Snow, Water or Ice penalties. They do not cancel the Icy Road trap or affect AI racers.

## Displays, graphics, and presentation

The item feed appears globally and moves to the bottom-left during races. Colors distinguish item types. Pads show clearer requirements, remaining AP boxes and demanded racers; AP crates carry an Archipelago face and classification colors.

Choose 4:3, 16:9, 16:10 or 21:9, plus Original, 2X, 3X, 4X or Native render scale. Smooth Scaling, Texture Filtering and dithering are available. Text still uses the original UI resolution and may look softer than the game at high render scales. Fullscreen persists and can be toggled with F11 or Alt+Enter; Deck users should follow the workaround above if it causes lag.

## Experimental features

### Recorded AI laps

Record your driving lines for opponents to use later. **Save AI Lap Recordings** and **Use Recorded AI Laps** are separate settings under **Options → Authoring**. You can record without changing how opponents drive.

To save, complete a multi-lap race and continue to the results. Up to three eligible clean laps are stored locally in `ap-navpaths` beside the active `config.ini`; the standing-start lap is excluded. Nothing is uploaded. Add compatible `.navlap` files while the game is closed, then enable playback and race on the matching track.

Playback selects up to three usable recordings from a limited newest-first search and shares them across opponents. It does not assign a unique random recording to every racer or guarantee the recorded lap time. AI racers cannot collect AP check boxes. See the [recording instructions](https://github.com/dowlle/ctr-native-ap/blob/main/SETUP.md#experimental-recorded-ai-laps) for filenames, contributor names and troubleshooting.

### Baby T Park preview

A seed can replace the Purple Gem Cup destination with one recognized Baby T Park package. No custom-track files are included. **Options → Custom Content** checks the files you obtain from their creator and reports whether they are compatible. **Ready** does not make the seed use the track; its YAML must select the package before generation.

This preview does not provide arbitrary track libraries, custom Cups, Arcade or Time Trial support. Broader custom-track work remains separate for 0.3.0.

## Fixes and technical history

The following detail is useful if you followed the Alpha releases or are investigating a problem:

- **Final 0.2.0:** more forgiving AP-box contact, remote letter notifications, visual-trap pause handling, racer-lock wording, and reconciled goal/relic-invitation behavior. Secure connections verify both certificate trust and server name; datapackage-cache paths reject unsafe components.
- **Alpha7:** corrected per-track Wumpa eligibility, standalone/Cup replay routes, and handling of the experimental custom track.
- **Alpha5:** fixed shuffled-pad access in seeds that do not require all four Keys and Blue Fire U-turn input. Added render-scale controls and corrected premature Oxide presentation; the final release further updates the goal choices.
- **Alpha4:** fixed the Ripper Roo zero-Key return freeze and incorporated native-engine rendering and retail-behavior corrections.
- **Other reliability work:** checks earned offline are retained for reconnecting to the same seed/slot; settled checks are suppressed. Object storage, race transitions, character state and crate fallbacks received repairs. Large reconnect backlogs remain a reported area to watch.
- **Trap naming:** No Brakes became Forced USF, Wumpa Reset became Wumpa Wipeout, Auto-Use became Forced Use, No Boost became Boost Blocker, Reverse Controls became Reverse Steering, and Nitro became Nitro Drop. The Trap suffix was removed; existing item IDs stayed fixed.

The final merged pair passed native regression tests, APWorld regression tests, all eleven generation fuzz checks, and targeted connection/cache and packaging checks. Windows and Linux builds passed with and without AP integration. All eleven public release assets were downloaded and checked for matching versions, checksums and exact debug symbols. Earlier Alpha gameplay results are not a complete gameplay pass on the final binaries.

## About this release

With much of my attention on my partner's recovery, I've relied more than usual on AI assistance for this release. Astra coordinated implementation, reviews and release preparation around plans and priorities we had already agreed on.

## Reporting a problem

[Open a GitHub issue](https://github.com/dowlle/ctr-native-ap/issues/new/choose) with your platform, client version, seed or YAML, what happened and the support bundle. Run `support-bundle.bat` on Windows or `support-bundle.sh` on Linux; inspect the bundle before attaching it. It does not upload automatically.

Questions are welcome in the [Crash Team Racing channel](https://discord.com/channels/731205301247803413/1222304293751750777) on the Archipelago Discord. The [GitHub release](https://github.com/dowlle/ctr-native-ap/releases/tag/v0.2.0) contains the downloads, checksums and debug symbols.

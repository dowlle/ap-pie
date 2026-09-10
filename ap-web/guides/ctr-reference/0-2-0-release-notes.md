CTR Archipelago 0.2.0 adds many new ways to build a seed. Item boxes and CTR letters can become checks, racers and weapons can enter the item pool, and received items can unlock your kart's boost and stats. Gem Cup tracks can also be randomized, and several victory conditions can be combined. Every major addition is optional and configured per YAML.

> **0.2.0 is the current stable release, published September 10, 2026.** It brings the Alpha work together as a community-tested baseline. Automated checks pass, while remaining gameplay and client-verifier coverage will continue through community reports and versioned fixes. Always use the client and APWorld from the same release.

**[Download 0.2.0](/ctr/download)** · **[Build a 0.2.0 YAML](/yaml-builder/ctr?version=0.2.0)** · **[Setup guide](/guides/ctr)** · **[Release assets and checksums](https://github.com/dowlle/ctr-native-ap/releases/tag/v0.2.0)**

## Setup, hosting and YAML videos

- [CTR setup walkthrough on YouTube](https://youtu.be/9x63P6JP93E): install the client and join a multiworld. The video predates 0.2.0; follow the current downloads and [written setup guide](/guides/ctr) alongside it.
- [Hosting an Archipelago multiworld on YouTube](https://youtu.be/CpRbyRodayM): collect YAMLs, generate the game and host the server. There is also a [written hosting guide](/guides/hosting-a-multiworld).
- A dedicated CTR 0.2.0 YAML explanation video is coming soon. For now, use the [0.2.0 YAML Builder](/yaml-builder/ctr?version=0.2.0), its option help and the [written YAML guide](/guides/setting-up-your-yaml).

## Final 0.2.0 corrections

The final release adds more forgiving AP-box contact for karts and direct projectiles, remote Lettersanity notifications, visual-trap pause corrections and clearer racer-lock wording. Oxide can now be left as optional content or disabled entirely, separately from the Boss and Gem goal conditions. Goal and relic-invitation handling have also been reconciled between the client and generator.

Secure AP connections now verify the certificate's server name as well as its trust chain. Datapackage-cache paths reject unsafe components. These targeted corrections do not mean every trust boundary or gameplay path has been tested.

Recorded-AI playback remains experimental and off by default. Its current shared-line behavior and the planned 0.2.1 corrections are explained below. Generalized custom-track work stays separate for 0.3.0.

With much of my attention on my partner's recovery, I've relied more than usual on AI assistance for this release. Astra coordinated implementation, reviews and release preparation around plans and priorities we had already agreed on. Automated checks cover part of that work; community testing will help us find what they miss.

## Alpha 7 corrections

Alpha 7 tightens the new per-track Reach 10 Wumpa checks introduced during the Alpha 6 preview:

- A Wumpa check is created only when that track has a playable Trophy or arcade-style race in the seed. Slide Coliseum and Turbo Track therefore do not create unreachable Wumpa checks while they remain relic-only.
- The same track-owned check can be collected through its standalone race or through any Gem Cup leg that runs the track. Repeated Cup appearances remain alternative routes to one check.
- An unchecked Wumpa location keeps the appropriate standalone route replayable: the plain Trophy Race route during pad phase 1 and the CTR Challenge side during phase 2.
- A completed Gem Cup remains Raceable while a distinct track in its resolved legs still has an unchecked Wumpa location.
- The experimental custom track participates only when its recognized descriptor is active and its measured capabilities say ten Wumpa can be collected.

These corrections do not add standalone Trophy Race or CTR Challenge events to Slide Coliseum or Turbo Track. Those additional events are not part of this release.

## At a glance

0.2.0 adds new checks, items and ways to progress through Adventure Mode:

- **More places to check:** up to 241 authored AP boxes, Itemsanity weapon checks, CTR Letter locations and Wumpa progression.
- **More things to receive:** racers, weapons, Progressive Boost, Progressive Stats, traps and comfort items.
- **More ways through Adventure Mode:** randomized Gem Cup legs, racer-locked pads, capability-aware logic and goals that can be combined.
- **A clearer client:** a race-friendly item feed, richer warp-pad displays, widescreen and fullscreen controls, render scaling up to 4X or Native, improved recovery and optional AI lap recording.

Most systems are optional. You choose them in your YAML, and the option help in the YAML Builder explains the available values.

## New checks and item families

### Item Box Locations

The `box_locations` option adds authored AP crates across the 18 race tracks. Numbered names distinguish boxes on the same track. There are up to 241 possible positions, with `shortcut_knowledge` controlling whether easy, medium, or hard routes may be required. These are extra scavenger-hunt checks, not retail boxes converted into locations.

Only the local player can break an AP crate. Once checked, it stays gone for that seed. Remaining AP boxes are shown below the warp-pad title. The complete 0.2.0 PopTracker mapping and per-track AP-box maps are still in development, so not every numbered box has a published visual reference yet.

### Itemsanity

The `itemsanity` option can move CTR's 11 Adventure weapons into the multiworld item pool, add checks for using them, or enable both. Each weapon has a normal use check and a juiced check that requires at least ten Wumpa Fruit when fired, for up to 22 use checks.

Roulette results respect the weapons you own. An unavailable weapon is not silently replaced using the retail race-position table, and arena weapons are gated by ownership too.

### Lettersanity

The C, T, and R letters on the 16 CTR Token Challenge tracks can remain vanilla, become locations, become received items that gate collection, or use both halves together. The full form adds up to 48 letter locations and 48 letter items. A letter you have not received is shown translucently and cannot be collected.

### Wumpa progression

0.2.0 adds a configurable Wumpa family: starting-Wumpa progression, bundle filler items, and `Reach 10 Wumpa` checks. The check can be off, global for the whole seed, or separate for each eligible track. Starting Wumpa is restored after a pause-menu restart and the world protects required Wumpa items when fitting a large item pool. The Alpha 7 route and eligibility corrections are retained, and boss races are also modeled as routes to their track's per-track Wumpa check.

### Turbo Grant and Tizi Helper

The `Turbo Grant` option adds received `Turbo` filler items. A Turbo is delivered when it can be used safely; if the player is outside a race or the weapon slot is occupied, the grant waits instead of being discarded.

The optional `Tizi Helper` makes the first four boxes after the Papu's Pyramid starting line give Masks for the Tiziano shortcut. With Itemsanity enabled, it also requires ownership of the Mask weapon. The helper is intentionally excluded from logic.

### Experimental custom content

Alpha 6 added the first deliberately narrow custom-track preview. A seed may replace the Purple Gem Cup destination with one recognized Baby T Park package. The client verifies the package identity, file hashes and measured capabilities before enabling it, and the Custom Content menu reports whether the local installation is Ready. No custom-track files are included in CTR Archipelago.

This is not yet a general custom-track library. Arcade, Time Trial, multiplayer, arbitrary package pools, custom Cups and broader destination randomization remain future work. Custom content stays off unless the generated seed explicitly selects it.

## Characters and kart progression

### Unlock every CTR racer

With `character_unlocks`, all other CTR racers can enter the item pool. A `SELECT CHARACTER` row in the Adventure pause menu opens the character screen. You may only drive a racer you have received. Older seeds without the character phase can still use the screen in browse mode.

The selected racer is stored for the current Archipelago server slot. `racer_locked_pads` can require a particular racer at selected warp pads. The pad shows the requested portrait, refuses entry until that racer has been received and loads the race with the correct racer once unlocked.

`starting_character` chooses the opening racer. `starting_stat_class` chooses the starting driving class, `editable_stats` enables manual stat editing through the pause-menu character interface, and `penta_stats` controls Penta Penguin's stat profile. Stat editing is not a Garage feature.

### Progressive Boost

Progressive Boost controls the boost your kart can create for itself:

- With no copies, powerslide, hang-time and similar self-earned boosts are locked. Ordinary retail turbo pads still work.
- The first copy enables ordinary self-earned boost.
- The second copy enables Ultimate Sacred Fire speeds where the route supports them.
- An optional third copy enables Blue Fire, with blue exhaust and stronger reserve behavior. U-turning retains those reserves.

The option can be off, shared by the full roster or received separately for each character. The Blue Fire tier can be disabled, in which case the chain ends at Ultimate Sacred Fire.

### Progressive Stats

Progressive Top Speed, Acceleration, and Turning raise each stat from Very Low through Very High. The pause-menu character interface shows the effective ranks. The ladders can be disabled, shared by the full roster or received separately for each character. When Progressive Stats is active, its values take priority over manual stat editing.

## Routes, logic, and goals

### Randomized Gem Cups

Each Gem Cup leg can be drawn independently from the 16 Trophy Race tracks, including repeated tracks. The ordinary warp pad for a drawn track remains a separate route, so a cup cannot lock away that track's checks. The client loads the randomized legs and reports the cup summary.

AP boxes inside a randomized Gem Cup leg follow the physical warp-pad access of the track assigned to that leg. They do not inherit an unrelated cup entrance's requirements.

### Composable goals

The old single goal choice is replaced by three conditions that can be combined:

- beat Oxide at his Challenge or Final Challenge;
- win a chosen number of the four boss races;
- hold a chosen number of the five Gems.

Every enabled condition must be met. The final Oxide unlock can separately require configured relic types and counts, and the Final Challenge location now follows the selected unlock mode.

`oxide_goal: none` keeps both Oxide races as optional checks. `oxide_goal: disabled` closes the garage and removes both races entirely, so at least one Boss or Gem condition is required. With an Oxide goal, the configured Boss and Gem conditions participate in the finale flow; with optional Oxide, they do not gate those optional races.

### Capability-aware logic

Logic now accounts for selected racers, racer locks, Progressive Boost, per-character stats and boost ownership, Lettersanity, Itemsanity, custom boxes, Shortcut Knowledge, and the difficulty of additional Trophy Races. Gold and Platinum Time Trials are boost-gated, with stricter requirements on Hot Air Skyway, N. Gin Labs, and Oxide Station where the confirmed route demands them.

The two-stage fill probe now mirrors the real multiworld and companion pre-fill behavior more closely. Large optional pools shed ordinary filler before comfort or progression items and fail clearly when a configuration cannot fit.

### Relic behavior

Relic items and race-result checks are different. Received Sapphire, Gold and Platinum relic items are counted independently for item requirements: a Platinum item does not count as a Gold item. Beating a Platinum target time can still send that track's Gold and Sapphire result checks as well.

Removed Time Trial relics are granted locally, relic races use the AP box gate, and the award ceremony can cycle through multiple distinct award lines. Relic-tier logic and the client verifier use the same boost rules.

## Traps and comfort items

The release includes twenty trap effects: Icy Road, Low Gravity, Forced USF, Forced Boost, First Person, Wumpa Wipeout, Flatten, Item Reroll, Forced Use, Empty Crates, Weakened Kart, Boost Blocker, Wireframe, Nitro Drop, Reverse Steering, Red Potion, Upside Down, Mirror Mode, Warpball Ambush and Demo Camera. `trap_weights` can make individual traps more common, less common, or absent. The client also offers short, normal and long trap-duration presets. The complete combination of effects and race contexts still needs community gameplay coverage.

The trap names were cleaned up for 0.2.0. Existing item ids did not move:

- No Brakes Trap is now Forced USF;
- Wumpa Reset Trap is now Wumpa Wipeout;
- Auto-Use Trap is now Forced Use;
- No Boost Trap is now Boost Blocker;
- Reverse Controls Trap is now Reverse Steering;
- Nitro is now Nitro Drop;
- the `Trap` suffix was removed from the whole family.

These effects are implemented in the matching 0.2.0 pair. Nitro Drop and Red Potion balance improvements remain planned for 0.2.1.

The working effects were rebuilt around a scheduler with corrected activation, pause, reconnect, ownership, and race-transition behavior. Received traps can arm during a race and wait for a safe moment when necessary. Timers suspend while paused, and trap state resets on a new connection so stale effects do not leak between sessions.

Natural-surface comfort items can let the player ignore Grass, Dirt and mud, Snow, Water, or natural Ice. Forced ice, the Icy Road Trap, and AI racers remain unaffected.

## Displays, graphics, and presentation

The item feed now appears globally and moves to the bottom-left during races. Lines are colored by Archipelago classification. Podium checks and incoming race rewards use clearer labels and cues, while connect-time diagnostics are deduplicated.

Warp pads can split waiting items by reward type, show remaining AP boxes, display the demanded racer on racer-locked routes, and tint AP markers by item classification. Progression rewards use a harvested retail crystal presentation, and AP crates use a compiled-in Archipelago face texture with classification colors.

The client now offers 4:3, 16:9, 16:10, and 21:9 aspect ratios with matching field-of-view and HUD scaling. Fullscreen persists and can be toggled with F11 or Alt+Enter. A dithering option is included. The race feed, picker HUD, portraits, credits, lighting, menus, vehicle behavior, and renderer received additional alignment and cleanup.

Alpha 5 adds player-facing Render Scale choices for Original, 2X, 3X, 4X, and Native, plus Smooth Scaling and Texture Filtering options. Text remains at the original UI resolution and can look soft beside the sharper game rendering at 4X or Native. Higher-resolution text is future work.

## Reliability and recovery

Checks earned while disconnected are retained and sent after reconnecting to the same seed and slot. Already-settled checks are suppressed instead of being resent. Connect-time scouting now requests only locations the server declared for the current slot, preventing an old reconnect loop and keeping peer-bound box items visible in the feed.

Alpha 4 fixes the Ripper Roo zero-Key return freeze. Returning after the first boss no longer waits forever for a Key when that seed does not award one there.

Alpha 5 repairs shuffled warp-pad access for seeds whose configuration does not require all four Keys. It also fixes Blue Fire U-turns so the forced-cross input works while reserves are active.

The client also includes safer object-pool rollback, spawn-pointer invalidation, per-player scratch storage, crate-model fallbacks, trap and box reset corrections, racer-lock cleanup on title transitions, and protection against character state leaking between slots.

## Optional AI lap recording

AI lap recording captures your driving lines for computer-controlled racers to use later. Recording and playback are separate options under **Options → Authoring**, both off by default.

Enable **Save AI Lap Recordings**, complete a multi-lap race and continue to the results. Up to three eligible clean laps are saved in `ap-navpaths` beside the active `config.ini`; the standing-start lap is excluded. Nothing is uploaded. Add compatible `.navlap` files while the game is closed, then enable **Use Recorded AI Laps** and start a race on that track. The [versioned recording instructions](https://github.com/dowlle/ctr-native-ap/blob/v0.2.0/SETUP.md#experimental-recorded-ai-laps) explain filenames, driver names and troubleshooting.

Playback currently chooses up to three usable recordings from a bounded newest-first search and shares those lines across opponents. Contributor names can repeat. It does not yet give each opponent a distinct randomly selected recording, and recorded lines do not guarantee the original lap time. Per-racer assignment, broader contributor-pool selection, finish-line smoothing and ordinary-crate interactions are planned corrections for 0.2.1. AI racers cannot collect AP check boxes. Turn playback off and start a new race to use the track's normal AI lines again.

## Native engine update

Alpha 4 incorporates the current upstream ctr-native rendering and retail-parity work. This includes a GPU-backed rendering path, persistent OpenGL state, asynchronous GPU timing, improved VRAM synchronization and feedback, and a broad set of corrections that restore retail menu, HUD, vehicle, navigation, visibility, audio, pause, and Adventure behavior.

That work is retained in 0.2.0 and the final Windows/Linux AP and vanilla configurations all compile. Runtime reports remain useful for rendering, input and game transitions.

## Compatibility and upgrading

A 0.2.0 client can open 0.1.5 seeds using compatibility fallbacks. A 0.1.5 client cannot understand a 0.2.0 seed and may make it impossible to finish.

For new games, use the matching 0.2.0 client and APWorld pair, the 0.2.0 YAML template or Builder, and fresh seeds. Back up an existing folder before replacing it. For an ongoing room, coordinate with the host before changing versions; do not assume every Alpha seed is interchangeable with the final schema-9 pair.

The client still requires a disc image made from your own North American Crash Team Racing disc. No game data is included.

## Testing status

The final merged pair passed the native regression suite, targeted TLS/cache and packaging checks, APWorld regression tests and all eleven generation fuzz checks. All four Windows/Linux AP and vanilla builds passed. The complete eleven-asset release was assembled on GitHub, then downloaded and verified again after publication, including matched versions, checksums and exact debug symbols.

Earlier Alpha gameplay tests supply useful evidence, including Wumpa replay routes and several trap effects, but they are not a full gameplay pass on the final release binaries. The full final gameplay matrix and client-verifier sweep remain community testing work. Untested scenarios have not been relabeled as passes.

0.2.0 is published as stable with these limits documented. Reports will feed into reproduced, verified fixes in matching 0.2.x client/APWorld releases.

## Known issues

- Recorded-AI playback is experimental and off by default, with the limitations above.
- Large reconnect backlogs still need gameplay coverage. Per-item console logging is reduced, but network parsing remains on the game thread. Include the support bundle if reconnecting causes a long freeze.
- Optional checks for breaking every time crate in a Relic Race are deferred to 0.2.1. Generalized custom-track support is planned for 0.3.0.

- A racer can be invisible on the post-race podium. Nitros Oxide in first place is confirmed: the retail game has no win-dance model for him, so nothing is drawn. Reports of Papu Papu after a Gem Cup and Komodo Joe after a relic race are separate and not yet reproduced. Tracked as [#282](https://github.com/dowlle/ctr-native-ap/issues/282).
- On Steam Deck, enabling Fullscreen in the graphics options can cause heavy lag. Leave the default windowed mode on the Deck. Tracked as [#260](https://github.com/dowlle/ctr-native-ap/issues/260).

Download the [stable 0.2.0 release](https://github.com/dowlle/ctr-native-ap/releases/tag/v0.2.0). If a problem appears, [open an issue on GitHub](https://github.com/dowlle/ctr-native-ap/issues/new/choose) and include the platform, seed or YAML, exact build version, what happened, and the generated support bundle. Questions go to the [Crash Team Racing channel](https://discord.com/channels/731205301247803413/1222304293751750777) on the Archipelago Discord.

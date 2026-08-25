CTR Archipelago 0.2.0 is the largest update so far. This page covers the player-facing changes since the current stable release, 0.1.5, through the 0.2.0 Alpha 4 test build.

> **0.2.0 is still a preview.** Alpha 4 is published for testing, not as the new stable release. The final 0.2.0 may contain further corrections. Always use the client and APWorld from the same release.

## At a glance

0.2.0 greatly expands what a seed can randomize. Tracks can contain authored AP item boxes, weapons and CTR letters can become checks and items, racers can join the item pool, kart abilities can be progressive, Gem Cup legs can change, and several goal conditions can be combined. The client also gains a new item feed, richer warp-pad displays, graphics controls, expanded traps, offline check recovery, optional AI lap recording, and many fixes.

Most new systems are optional. A host can keep a seed close to the 0.1.5 rules or turn on a much denser game.

## New checks and item families

### Item Box Locations

The `box_locations` option adds authored AP crates across the 18 race tracks. There are up to 241 possible positions, with `shortcut_knowledge` controlling whether easy, medium, or hard routes may be required. These are extra scavenger-hunt checks, not retail boxes converted into locations.

Only the local player can break an AP crate. Once checked, it stays gone for that seed. Remaining AP boxes are shown below the warp-pad title. A tracker or reference map is strongly recommended when this mode is enabled.

### Itemsanity

The `itemsanity` option moves 11 Adventure weapons into the multiworld item pool and adds use-time checks for firing them. Each weapon has a normal check and a juiced check that requires at least ten Wumpa Fruit when fired, for up to 22 checks.

Roulette results respect the weapons you own. An unavailable weapon is not silently replaced using the retail race-position table, and arena weapons are gated by ownership too.

### Lettersanity

The C, T, and R letters on the 16 CTR Token Challenge tracks can become locations, items, or both. This can add up to 48 letter locations and 48 letter items. A letter you have not received is shown translucently and cannot be collected.

### Wumpa progression

0.2.0 adds a configurable Wumpa family: starting-Wumpa progression, bundle filler items, and a `Reach 10 Wumpa` check. Starting Wumpa is restored after a pause-menu restart and the world protects required Wumpa items when fitting a large item pool.

### Turbo Grant and Tizi Helper

`Turbo Grant` is a received weapon item that gives the player a Turbo when it can be delivered safely. If the player is outside a race or the weapon slot is occupied, the grant waits instead of being discarded.

The optional `Tizi Helper` makes the first four boxes after the Papu's Pyramid starting line give Masks for the Tiziano shortcut. With Itemsanity enabled, it also requires ownership of the Mask weapon. The helper is intentionally excluded from logic.

## Characters and kart progression

### Character unlocks and the hub picker

With `character_unlocks`, the other 15 racers enter the item pool. A `SELECT CHARACTER` row in the Adventure pause menu opens the hub character picker. Older seeds without the character phase can still use the picker in browse mode.

The selected racer is stored per server slot. Racer-locked pads can require a particular racer and now load the race as that racer. Locked pads show the demanded character portrait and refuse entry without silently seating an unowned racer.

The character phase also adds `starting_character`, `starting_stat_class`, `editable_stats`, and `penta_stats`. Editable stats use the Garage interface and persist with the AP slot.

### Progressive Boost

Progressive Boost can gate self-earned boost behind an item chain. The first copy enables ordinary powerslide and hang-time boosts. The second unlocks Ultimate Sacred Fire speeds. An optional third tier unlocks Blue Fire, with the appropriate exhaust and reserve behavior. Retail turbo pads continue to work before the first copy.

### Progressive Stats

Progressive Top Speed, Acceleration, and Turning raise each stat from Very Low through Very High. The Garage and hub picker show the effective ranks. The ladders can be shared by the whole roster or owned separately by each character. When Progressive Stats is active, its values take priority over manual stat editing.

## Routes, logic, and goals

### Randomized Gem Cups

Each Gem Cup leg can be drawn independently from the 16 Trophy Race tracks, including repeated tracks. The ordinary warp pad for a drawn track remains a separate route, so a cup cannot lock away that track's checks. The client loads the randomized legs and reports the cup summary.

### Composable goals

The old single goal choice is replaced by three conditions that can be combined:

- beat Oxide at his Challenge or Final Challenge;
- win a chosen number of the four boss races;
- hold a chosen number of the five Gems.

Every enabled condition must be met. The final Oxide unlock can separately require configured relic types and counts, and the Final Challenge location now follows the selected unlock mode.

### Capability-aware logic

Logic now accounts for selected racers, racer locks, Progressive Boost, per-character stats and boost ownership, Lettersanity, Itemsanity, custom boxes, Shortcut Knowledge, and the difficulty of additional Trophy Races. Gold and Platinum Time Trials are boost-gated, with stricter requirements on Hot Air Skyway, N. Gin Labs, and Oxide Station where the confirmed route demands them.

The two-stage fill probe now mirrors the real multiworld and companion pre-fill behavior more closely. Large optional pools shed ordinary filler before comfort or progression items and fail clearly when a configuration cannot fit.

### Relic behavior

Relic requirements no longer depend on an exact count that can become impossible after receiving a higher tier. Removed Time Trial relics are granted locally, relic races use the AP box gate, and the award ceremony can cycle through multiple distinct award lines. Relic-tier logic and the client verifier use the same boost rules.

## Traps and comfort items

The five working traps remain Icy Road, Low Gravity, Forced USF, Forced Boost, and First Person. `trap_weights` can now make each one more common, less common, or absent. Alpha 4 adds a client-side trap-duration setting with short, normal, and long timing presets.

The trap names were cleaned up for 0.2.0. Existing item ids did not move:

- No Brakes Trap is now Forced USF;
- Wumpa Reset Trap is now Wumpa Wipeout;
- Auto-Use Trap is now Forced Use;
- No Boost Trap is now Boost Blocker;
- Reverse Controls Trap is now Reverse Steering;
- the `Trap` suffix was removed from the whole family.

Additional names are reserved in the datapackage for future effects, including Wumpa Wipeout, Flatten, Item Reroll, Forced Use, Empty Crates, Weakened Kart, Boost Blocker, Wireframe, Nitro, Reverse Steering, Red Potion, Upside Down, Mirror Mode, and Warpball Ambush. They are not drawn into Alpha 4 seeds because their effects are not yet part of the complete shipped pair.

The working effects were rebuilt around a scheduler with corrected activation, pause, reconnect, ownership, and race-transition behavior. Received traps can arm during a race and wait for a safe moment when necessary. Timers suspend while paused, and trap state resets on a new connection so stale effects do not leak between sessions.

Natural-surface comfort items can let the player ignore Grass, Dirt and mud, Snow, Water, or natural Ice. Forced ice, the Icy Road Trap, and AI racers remain unaffected.

## Displays, graphics, and presentation

The item feed now appears globally and moves to the bottom-left during races. Lines are colored by Archipelago classification. Podium checks and incoming race rewards use clearer labels and cues, while connect-time diagnostics are deduplicated.

Warp pads can split waiting items by reward type, show remaining AP boxes, display the demanded racer on racer-locked routes, and tint AP markers by item classification. Progression rewards use a harvested retail crystal presentation, and AP crates use a compiled-in Archipelago face texture with classification colors.

The client now offers 4:3, 16:9, 16:10, and 21:9 aspect ratios with matching field-of-view and HUD scaling. Fullscreen persists and can be toggled with F11 or Alt+Enter. A dithering option is included. The race feed, picker HUD, portraits, credits, lighting, menus, vehicle behavior, and renderer received additional alignment and cleanup.

## Reliability and recovery

Checks earned while disconnected are retained and sent after reconnecting to the same seed and slot. Already-settled checks are suppressed instead of being resent. Connect-time scouting now requests only locations the server declared for the current slot, preventing an old reconnect loop and keeping peer-bound box items visible in the feed.

Alpha 4 fixes the Ripper Roo zero-Key return freeze. Returning after the first boss no longer waits forever for a Key when that seed does not award one there.

The client also includes safer object-pool rollback, spawn-pointer invalidation, per-player scratch storage, crate-model fallbacks, trap and box reset corrections, racer-lock cleanup on title transitions, and protection against character state leaking between slots.

## Optional AI lap recording

An experimental lap recorder can collect AI laps into a versioned local container. Separate options select which AI difficulties are recorded, and the pause menu shows a read-only status row. Recording is off by default. Playback against named community laps, matchmaking, and pace control are planned for a later release.

## Native engine update

Alpha 4 incorporates the current upstream ctr-native rendering and retail-parity work. This includes a GPU-backed rendering path, persistent OpenGL state, asynchronous GPU timing, improved VRAM synchronization and feedback, and a broad set of corrections that restore retail menu, HUD, vehicle, navigation, visibility, audio, pause, and Adventure behavior.

This upstream sync is compile-tested in the exact Alpha 4 package. It remains one of the areas where tester runtime reports are especially useful.

## Compatibility and upgrading

A 0.2.0 client can open 0.1.5 seeds using compatibility fallbacks. A 0.1.5 client cannot understand a 0.2.0 seed and may make it impossible to finish.

Hosts and players should agree on the version before generation. Install the client and APWorld from the same release, back up an existing folder before replacing it, and do not mix Alpha 4 with an earlier 0.2.0 preview.

The client still requires a disc image made from your own North American Crash Team Racing disc. No game data is included.

## Alpha 4 testing status

The matched Alpha 4 pair passed fresh 32-bit Archipelago and vanilla Linux builds, a fresh Windows Archipelago build, the full APWorld fuzz workflow, and focused harnesses for trap scheduling, the first-Key freeze, transition diagnostics, podium parsing, and diagnostic deduplication.

This does not make it a stable release. The upstream engine sync still needs broader runtime coverage, the racer-ownership reload repair is not included, and the remaining 0.2.0 acceptance work continues before the stable release.

Download the current test build from the [0.2.0 Alpha 4 GitHub release](https://github.com/dowlle/ctr-archipelago-apworld/releases/tag/v0.2.0-alpha4). If a problem appears, include the platform, seed or YAML, exact build version, what happened, and the generated support bundle.

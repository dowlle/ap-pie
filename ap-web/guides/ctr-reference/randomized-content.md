CTR Archipelago ranges from a light Adventure Mode shuffle to a much broader overhaul. The host chooses the shape in the YAML before generating the world.

> This page describes stable 0.2.0. Most systems are optional; use the matching version in the Builder. The [release notes](/ctr/reference/0-2-0-release-notes) explain experimental features and remaining testing coverage.

## Adventure routes

- **Warp-pad requirements:** pads can ask for randomized counts of progression items instead of following the original Trophy order.
- **Warp-pad destinations:** supported shuffle modes can separate the physical pad from the track or challenge it enters.
- **Gem Cup tracks:** the tracks inside a Gem Cup can be shuffled.
- **Composable goals:** combine beating Oxide in his Challenge or Final Challenge, winning a chosen number of the four boss races, and holding a chosen number of the five Gems. Every enabled condition must be met. Oxide can instead stay as optional checks or be disabled entirely.

## Checks and rewards

- Trophy Races, Relic Races, CTR Token Challenges, Boss Races, Gem Cups, and Crystal Challenges can send checks.
- Optional podium checks can reward holding or finishing in selected race positions.
- **Itemsanity:** Adventure weapon-use checks and weapon unlock items can be enabled separately or together.
- **AP boxes:** authored crates can be added to tracks as Archipelago checks.
- **Lettersanity:** CTR letters can become checks, received unlock items, or both.
- **Wumpa:** reaching ten Wumpa can be one global check or a separate check for each eligible track; starting-Wumpa upgrades and bundle filler are also available.

The item placed at a check can belong to any player in the multiworld. Completing Cortex Castle does not imply that you receive a CTR item from it.

## Kart capabilities

- **Progressive Boost:** ordinary boost, Ultimate Sacred Fire, and optionally Blue Fire form a received ladder.
- **Progressive Stats:** Top Speed, Acceleration, and Turning each have five ranks.
- **Shared or per character:** stat and boost upgrades can apply across the roster or to individual racers.
- **Shortcut Knowledge:** advanced routes can enter the world's logic at the selected difficulty.

## Characters

- The starting racer can be selected or randomized.
- Characters can become received unlock items.
- Pads can require a particular racer when character locks are enabled.
- Character statistics can stay original, become editable, or be controlled by Progressive Stats.

## Traps and useful items

Trap items can temporarily change the way a race plays. 0.2.0 includes twenty effects, from Icy Road and Low Gravity to Nitro Drop, Mirror Mode, Warpball Ambush and Demo Camera. Individual weights control which traps enter the pool. See the [full trap roster](/ctr/reference/0-2-0-release-notes#traps-and-comfort-items) for the shipped set and testing limits.

0.2.0 also adds useful received items such as queued weapon grants and capability upgrades. Items received outside a legal gameplay moment wait until they can be delivered rather than being discarded.

## What does not change

CTR Archipelago does not distribute Crash Team Racing game data. It runs as a native client but still needs a disc image made from your own North American copy.

Ready to choose which of these systems appear in your world? [Configure them in the guided CTR YAML Builder](/yaml-builder/ctr), review the generated file, and download it for your host.

Archipelago randomizes progression and selected gameplay systems. It does not automatically randomize every visual, track layout, opponent, or physics value. The YAML builder shows the options supported by the version your host is using.

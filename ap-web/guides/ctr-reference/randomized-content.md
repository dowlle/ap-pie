CTR Archipelago ranges from a light Adventure Mode shuffle to a much broader overhaul. The host chooses the shape in the YAML before generating the world.

> Items marked 0.2.0 preview are present in the current test lane and may still receive corrections before the stable release.

## Adventure routes

- **Warp-pad requirements:** pads can ask for randomized counts of progression items instead of following the original Trophy order.
- **Warp-pad destinations:** supported shuffle modes can separate the physical pad from the track or challenge it enters.
- **0.2.0 preview:** the tracks inside a Gem Cup can be shuffled.
- **Boss and final goals:** the world can finish at N. Oxide, the final Oxide race, all bosses, or all Gems, depending on the selected goal.

## Checks and rewards

- Trophy Races, Relic Races, CTR Token Challenges, Boss Races, Gem Cups, and Crystal Challenges can send checks.
- Optional podium checks can reward holding or finishing in selected race positions.
- **0.2.0 preview:** Itemsanity turns using Adventure weapons into checks and makes the weapons themselves progression items.
- **0.2.0 preview:** selected item boxes can become authored Archipelago locations.

The item placed at a check can belong to any player in the multiworld. Completing Cortex Castle does not imply that you receive a CTR item from it.

## Kart capabilities

- **0.2.0 preview:** Progressive Boost can make ordinary boost, Sacred Fire, Ultimate Sacred Fire, and optionally Blue Fire into a received ladder.
- **0.2.0 preview:** Progressive Stats can split Top Speed, Acceleration, and Turning into five ranks.
- **0.2.0 preview:** Progressive Stats can be shared across the roster or owned separately by each character.
- **0.2.0 preview:** Shortcut Knowledge can make advanced routes part of the world's logic at the selected difficulty.

## Characters

- **0.2.0 preview:** the starting racer can be selected or randomized.
- **0.2.0 preview:** characters can become received unlock items.
- **0.2.0 preview:** pads can require a particular racer when character locks are enabled.
- **0.2.0 preview:** character statistics can stay original, become editable, or be controlled by Progressive Stats.

## Traps and useful items

Trap items can temporarily change the way a race plays. The stable release includes the original trap set. The 0.2.0 test lane expands the system substantially, so the complete trap catalogue will be published after the final effects and timings settle.

0.2.0 also adds useful received items such as queued weapon grants and capability upgrades. Items received outside a legal gameplay moment wait until they can be delivered rather than being discarded.

## What does not change

CTR Archipelago does not distribute Crash Team Racing game data. It runs as a native client but still needs a disc image made from your own North American copy.

Archipelago randomizes progression and selected gameplay systems. It does not automatically randomize every visual, track layout, opponent, or physics value. The YAML builder shows the options supported by the version your host is using.

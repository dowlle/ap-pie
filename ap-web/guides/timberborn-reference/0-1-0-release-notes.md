**Timberborn Archipelago 0.1.0 is the first test build for Timberborn 1.1. It brings the ten new 1.1 buildings into the pool, new options for traps, deliveries and your first blueprints, survival logic, and a long list of fixes from the pre-alpha playtests.**

**[Download 0.1.0](/timberborn/download)** · **[Setup guide](/timberborn/setup)** · **[Build a YAML](/yaml-builder/timberborn)**

## At a glance

- Works with Timberborn 1.1, on both Folktails and Iron Teeth.
- Ten new 1.1 buildings are in the item pool.
- You start with the Forester, Stairs and a Platform, so wood never waits on another player.
- New options: trap percentage and a weight per trap, resource package size, where received goods are delivered, and three sizes of resource milestones.
- Logic now expects drought and badtide defences before long goals and survival checks.
- Received goods wait for storage instead of being lost, traps from an old colony no longer fire again, and the Hungry and Thirsty Beavers traps work again.
- Locked shop slots say what they need, and locked buildings show the Archipelago logo.

## Where should I start?

- **Joining a room?** Install the mod from the [download page](/timberborn/download) and follow the [setup guide](/timberborn/setup). You need Timberborn 1.1.
- **Preparing a YAML?** Use the [YAML Builder](/yaml-builder/timberborn) and send the YAML to your host. The [Options](/timberborn/reference/options) page explains every option.
- **Hosting?** Install `timberborn.apworld` from this release and generate locally. Archipelago 0.6.7 or newer is needed.

## Compatibility and upgrading

0.1.0 needs Timberborn 1.1 and will not load on 1.0. Existing item and location IDs did not change, but seeds and saves from 0.0.x were not tested with 0.1.0. Generate a new seed with the 0.1.0 APWorld and YAML, and start a new colony on 1.1.

## New for Timberborn 1.1

- The mod runs on Timberborn 1.1. Buildings that 1.1 renamed keep their Archipelago identity.
- Ten new buildings are in the pools: Airlock, Impermeable Power Shaft and Compact Mechanical Pump for both factions; Hall of Abundance, Sauna and Domed Garden for Folktails; Arch of Progress, Massager, Impermeable Tubeway and Dance Pit for Iron Teeth.
- Existing item and location IDs did not change.

## New options

- **Starting Blueprints** (on by default): start with the Forester, Stairs and Platform.
- **Resource Milestone Set:** `classic` (13), `lite` (31) or `full` (61, default) resource milestones, with early steps such as 10 Gears.
- **Resource packages** replace the old fixed filler items: batches of goods for your faction, scaled by **Resource Package Size**.
- **Goods Delivery:** received goods go into the District Center (default) or into storage.
- **Trap Percentage** and a **weight for each trap**. A weight of 0 removes that trap type.
- **Removed:** Logic Difficulty and Drought Difficulty. They had no effect; YAMLs that still set them generate as before.
- Universal Tracker can track a Timberborn slot without the player's YAML.

## Gameplay and logic fixes

- Blueprints only land in shop slots of their own tier, so no more Smelter in the first slots.
- Buildings that use Explosives or Extract need a badwater source in logic. The Folktails Wonder needs Extract and Paper, and the Iron Teeth Dance Pit needs the Metalsmith.
- Long goals and survival milestones need drought and badtide defences in logic, in early, mid and late stages. The Droughts and Badtides goal ranges are smaller, and the Well-being goal now goes up to 50.
- Droughts and badtides count when they end, and only after you connect. The Wonder counts only when completed in this game, and a reached goal is sent again when you reconnect.
- The Water Storage goal can be won again.
- The Sluice can be built again.
- The Hungry Beavers and Thirsty Beavers traps work again.
- Starting a new colony on the same slot no longer fires the old traps again.
- Received goods wait until there is room instead of being lost, and the wait survives a save.
- Resource milestones keep counting after you load a save.
- Blueprints can no longer be cut from the pool as filler.
- Excluding a later shop slot, or giving one priority, no longer makes generation fail.

## Quality of life

- Scouts reveal and hint only the next slot of their path, and hints are not announced again when you reconnect.
- Scouted shop slots show the real item.
- Locked buildings show the Archipelago logo instead of a huge science cost, and locked shop slots say what they need, such as **Needs: previous check, Smelter, 120 science**.
- The AP Log sits behind game menus, is taller, scrolls along, uses Archipelago colours and has an All/Mine switch.
- Typing in the connect fields no longer triggers game hotkeys; Escape and Enter leave the field.
- `localhost` connects at once.

## Known issues

- Traps can still arrive after you have reached your goal, through a release or collect, so a colony can die after goaling.
- Large resource milestones, such as 1000 Logs, can be in logic much earlier than they should be.
- Resource packages count toward resource milestones in game, so a package can complete one early.
- Boosts are not applied to newly born beavers ([#14](https://github.com/dowlle/timberborn-modding/issues/14)).
- The Wonder goal leaves a long wait with nothing to do while it builds ([#7](https://github.com/dowlle/timberborn-modding/issues/7)).
- A websocket compression warning shows on every connect ([#23](https://github.com/dowlle/timberborn-modding/issues/23)).

## What was tested

This is a test build. The APWorld unit tests and the full fuzz suite pass on both factions.

Played in game on Timberborn 1.1 with Folktails: the Bots goal, a drought counting when it ends, connecting with a Wonder goal on a map where the Wonder was already finished (it does not complete at connect), and the shop, goods deliveries and traps. Moving to a new map on the same slot works too. On Iron Teeth a goods delivery worked, but the rest has had less play. Still open:

1. Iron Teeth on 1.1: the renamed buildings and the new Iron Teeth buildings.
2. Logic timing: checks that show up too early or too late. Tell us which check, which faction and what you had built.

## How it's made

Timberborn Archipelago is developed with AI assistance for code; there is no AI-generated art. The [full disclosure](https://github.com/dowlle/timberborn-modding#ai-usage-disclosure) explains how and why.

## Where the changes came from

- Mod: [#29](https://github.com/dowlle/timberborn-modding/pull/29) (Timberborn 1.1 and the client changes), [#30](https://github.com/dowlle/timberborn-modding/pull/30) (connect fields, localhost, logo, scouts), plus fixes for the Sluice, the Water Storage goal and scouted slots.
- APWorld: [#2](https://github.com/dowlle/TimberbornArchipelago/pull/2) (1.1 logic and options), [#3](https://github.com/dowlle/TimberbornArchipelago/pull/3) (Logic Difficulty removed), [#4](https://github.com/dowlle/TimberbornArchipelago/pull/4) (trap weights and percentage), [#8](https://github.com/dowlle/TimberbornArchipelago/pull/8) (excluded and priority shop slots, `start_inventory_from_pool`), plus the Well-being range, blueprint classification and scouted-slot fixes.

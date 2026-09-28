**Timberborn Archipelago 0.1.0 is the first release for Timberborn 1.1. It brings the ten new 1.1 buildings into the pool, new options for traps, deliveries and your first blueprints, survival logic, and a long list of fixes from the pre-alpha playtests.**

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

> **Placeholder for Stef:** the compatibility statement. What to say about seeds and saves from 0.0.5.x, and whether a 0.0.5 room can be played on the 0.1.0 mod. The draft facts so far: 0.1.0 needs Timberborn 1.1, and existing item and location IDs did not change.

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

## Quality of life

- Scouts reveal and hint only the next slot of their path, and hints are not announced again when you reconnect.
- Scouted shop slots show the real item.
- Locked buildings show the Archipelago logo instead of a huge science cost, and locked shop slots say what they need, such as **Needs: previous check, Smelter, 120 science**.
- The AP Log sits behind game menus, is taller, scrolls along, uses Archipelago colours and has an All/Mine switch.
- Typing in the connect fields no longer triggers game hotkeys; Escape and Enter leave the field.
- `localhost` connects at once.

## Known issues

> **Placeholder for Stef:** known issues at release.

## What was tested

> **Placeholder for Stef:** what was played in game for this release, on which faction and game version.

## How it's made

Timberborn Archipelago is developed with AI assistance for code; there is no AI-generated art. The [full disclosure](https://github.com/dowlle/timberborn-modding#ai-usage-disclosure) explains how and why.

## Where the changes came from

- Mod: [#29](https://github.com/dowlle/timberborn-modding/pull/29) (Timberborn 1.1 and the client changes), [#30](https://github.com/dowlle/timberborn-modding/pull/30) (connect fields, localhost, logo, scouts), plus fixes for the Sluice, the Water Storage goal and scouted slots.
- APWorld: [#2](https://github.com/dowlle/TimberbornArchipelago/pull/2) (1.1 logic and options), [#3](https://github.com/dowlle/TimberbornArchipelago/pull/3) (Logic Difficulty removed), [#4](https://github.com/dowlle/TimberbornArchipelago/pull/4) (trap weights and percentage), plus the Well-being range, blueprint classification and scouted-slot fixes.

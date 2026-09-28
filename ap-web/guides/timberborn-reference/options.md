Every Timberborn option you can set in your YAML, grouped by topic, with its values, default and effect. The [YAML Builder](/yaml-builder/timberborn) sets them in a form; the release's `Timberborn.yaml` is the same list as a template.

## Faction and goals

- **`faction`**: `folktails` (default) or `iron_teeth`; `random` picks one per seed. Your colony must match it. See [Factions](/timberborn/reference/factions).
- **`goal_selection`**: any combination of `Wonder`, `Population`, `Droughts`, `Badtides`, `Well-being`, `Bots` and `Water Storage`. Default: `Wonder`. An empty selection falls back to Wonder.
- **`goal_requirement`**: `any` (default) needs one selected goal, `all` needs every one.
- **`population_goal`**: 10 to 500, default 100. The target for the Population goal.
- **`population_mode`**: what counts toward the Population goal: `beavers_only` (default), `bots_only` or `beavers_and_bots`.
- **`drought_cycles_goal`**: 5 to 40, default 15. Droughts to survive for the Droughts goal. Older YAMLs with a higher number are lowered to 40.
- **`badtide_cycles_goal`**: 1 to 20, default 5. Badtides to survive for the Badtides goal. Older YAMLs with a higher number are lowered to 20.
- **`wellbeing_goal`**: 5 to 50, default 15. The average well-being for the Well-being goal.
- **`bots_goal`**: 1 to 50, default 10. Bots for the Bots goal.
- **`water_storage_goal`**: 500 to 50000, default 5000. Water in stock for the Water Storage goal.

[Goals and survival](/timberborn/reference/goals) explains how each goal is counted and what logic expects.

## Shop

- **`max_science_cost`**: 1000 to 20000, default 5000. The price of the most expensive shop slot.
- **`science_cost_multiplier`**: 10 to 1000 percent, default 100. Scales every shop price: 50 is half price, 200 double.
- **`skip_count`**: 0 to 10, default 3. Skip items in the pool. While traps are possible, skips take at most half of the slots left after blueprints, boosts and scouts.

See [Checks](/timberborn/reference/checks) for how the shop works.

## Blueprints and early game

- **`randomization_style`**: `shuffle` (default) or `grand_chaos`. The option describes `grand_chaos` as also shuffling buildings that cost no science, such as paths and stockpiles. In this version both values generate the same item pool: the buildings that normally cost science.
- **`progressive_items`**: `on` (default) merges buildings that come in sizes into progressive items, `grouped_random` switches each chain on or off at random, `off` keeps every building separate. The chains are listed on [Items](/timberborn/reference/items).
- **`starting_blueprints`**: on by default. You start with Forester, Stairs and Platform, and their slots get resource packages instead.
- **`force_early_items`**: on by default. Puts Levee and Gear Workshop in your first sphere, and with Starting Blueprints on also the Floodgate (or the first Progressive Flood Control) and the Medium Tank. With Starting Blueprints off it forces Forester and Stairs instead of Floodgate and Medium Tank. Off places them anywhere, which makes the start much harder.
- **`extra_early_survival`**: on by default. With Force Early Items and population milestones on, forces one random early housing, food and well-being building into your first sphere (Iron Teeth: housing and well-being).

## Milestones

- **`include_population_milestones`**: on by default. First beaver born, first grown up, and 15, 25, 50, 100 and 200 beavers.
- **`include_wellbeing_milestones`**: on by default. Average well-being 5, 10, 15 and 20.
- **`include_survival_milestones`**: on by default. Your 1st, 5th and 10th drought and badtide.
- **`include_wonder_milestone`**: on by default. Completing your Wonder. Always included when Wonder is a goal.
- **`include_resource_milestones`**: on by default. Checks for reaching a stock of a good.
- **`resource_milestone_set`**: which resource milestones: `classic` (13), `lite` (31) or `full` (61, default).

## Resource packages

- **`resource_package_size`**: 10 to 1000 percent, default 100. Scales every package; every package still delivers at least 1.
- **`goods_delivery`**: `district_center` (default) delivers into the District Center with the most beavers, `storage` into storage buildings with room. Goods that don't fit wait until there is room.

## Traps

- **`include_traps`**: on by default. The master switch for traps.
- **`trap_percentage`**: 0 to 100, default 15. The share of filler slots that become traps instead of resource packages, rounded half up. A default seed has 69 filler slots, so 15 gives 10 traps.
- **`hazardous_weather_trap_weight`**: 0 to 100, default 50.
- **`hungry_beavers_trap_weight`**: 0 to 100, default 30.
- **`thirsty_beavers_trap_weight`**: 0 to 100, default 20.
- **`trap_mode`**: what a Hazardous Weather trap does while bad weather is already on or another weather trap is waiting: `queue` (default) holds it, `skip` drops it.

Each trap is drawn with a chance of its weight divided by the sum of the three weights. A weight of 0 removes that trap type; with all three at 0 there are no traps. What each trap does is on [Items](/timberborn/reference/items).

## Removed options

`logic_difficulty` and `drought_difficulty` were removed. They are hidden, and a YAML that still sets them generates as before; the values have no effect.

## Options every Archipelago game has

Archipelago's common options, such as `progression_balancing`, `accessibility`, `local_items`, `non_local_items`, `start_inventory` and `start_hints`, work for Timberborn too. The [YAML guide](/guides/setting-up-your-yaml) explains them.

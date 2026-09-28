Everything the multiworld can send you in Timberborn Archipelago: building blueprints first, then boosts, scouts, skips, resource packages and traps.

## What a default seed contains

With the default options, a Folktails seed has 211 checks (132 shop slots and 79 milestones) and puts these items in the pool:

<table>
<thead><tr><th>Items</th><th>How many</th></tr></thead>
<tbody>
<tr><td>Blueprints</td><td>129: all 132 Folktails buildings except the three starting blueprints</td></tr>
<tr><td>Boosts</td><td>6</td></tr>
<tr><td>Scouts</td><td>4</td></tr>
<tr><td>Skips</td><td>3</td></tr>
<tr><td>Traps</td><td>10</td></tr>
<tr><td>Resource packages</td><td>59</td></tr>
</tbody>
</table>

Iron Teeth has one building less, so one blueprint and one shop slot less. Options that add or remove milestones change the number of resource packages, because packages fill whatever slots are left.

## Blueprints

A blueprint unlocks one building. Folktails can receive 132 of them and Iron Teeth 131; the [Factions](/timberborn/reference/factions) page lists what only one faction has. Buildings that cost no science in the normal game, such as paths and the District Center, stay unlocked.

**Starting blueprints.** With Starting Blueprints on (the default), you start with the Forester, Stairs and Platform. They unlock as soon as you connect, so wood and basic building never wait on another player.

**Progressive items.** With Progressive Items on (the default), buildings that come in sizes arrive as one item that you receive several times. Each copy unlocks the next size:

- **Progressive Platforms:** Platform, Double Platform, Triple Platform
- **Progressive Flood Control:** Floodgate, Double Floodgate, Triple Floodgate
- **Progressive Bridges:** Suspension Bridge 1x1 up to 6x1
- **Progressive Overhangs:** Overhang 2x1 up to 6x1
- **Progressive Dynamite:** Dynamite, Double Dynamite, Triple Dynamite
- **Progressive Housing** (Folktails): Mini Lodge, Double Lodge, Triple Lodge
- **Progressive Wind Power** (Folktails): Wind Turbine, Large Wind Turbine

With `grouped_random`, each chain is switched on or off at random per seed; with `off`, every building is its own item.

## Boosts

Six boosts, one of each, make your whole colony better for the rest of the game:

- **Faster Movement Speed:** +25% movement speed
- **Increased Carrying Capacity:** +50% carrying capacity
- **Faster Working Speed:** +25% working speed
- **Faster Beaver Growth:** +50% growth speed for kits
- **Longer Life Expectancy:** +25% life expectancy
- **Better Woodcutting Chance:** +25% woodcutting success chance

A boost applies to your beavers and bots when it arrives, and again every time you load the save. Beavers born after the boost arrived get it the next time you load.

## Scouts and skips

**Scout: Path A** to **Scout: Path D** reveal the next slot of one shop path. **Skip** lets you buy an open shop slot without paying its science; the Skip Count option sets how many are in the pool (3 by default, up to 10). Both are explained on the [Checks](/timberborn/reference/checks) page.

## Resource packages

Resource packages fill the rest of the pool. Each one delivers a batch of one good, such as **Package: Logs** (100 Logs), **Package: Gears** (25 Gears) or **Package: Bread** (60 Bread). Each faction only gets goods it can use: 23 kinds for Folktails and 21 for Iron Teeth, with building materials the most common. The Resource Package Size option scales every amount from 10% to 1000%.

Where the goods go depends on the Goods Delivery option:

- **district_center** (default): into the District Center with the most beavers, the way the game gives you your starting goods. Builders can use them right away, beavers eat and drink from it, and its workers haul the rest to storage. Goods it doesn't take go to storage.
- **storage**: into finished storage buildings that take the good and have room.

Goods that find no room wait, and arrive as soon as there is space. They are kept in your save, so nothing is lost when you quit.

<p><img src="/img/timberborn/ap-log-delivery.jpg" alt="The AP Log listing Received 15 Extract from Dowlle, then Delivered 15 Extract to the District Center, among milestones and received blueprints" width="397" height="1037" loading="lazy" style="max-width:340px;margin:0 auto" /></p>

The AP Log after a package of Extract arrived and went into the District Center.

## Traps

Traps are on by default. The Trap Percentage option (15 by default) sets how many of the filler slots become traps instead of resource packages; with the defaults that is 10 traps. Three trap types exist, and their weights set the mix:

- **Hazardous Weather** (weight 50): cuts the current temperate season short, so the next drought or badtide starts early, with the usual warning. The game picks which of the two it is.
- **Hungry Beavers** (weight 30): every beaver becomes critically hungry. They have about three days to eat before they starve.
- **Thirsty Beavers** (weight 20): the same for thirst.

A weight of 0 removes that trap type. If a Hazardous Weather trap arrives while bad weather is already on, the Trap Mode option decides: `queue` (default) holds it until the weather clears, `skip` drops it.

Hungry and Thirsty Beavers only affect beavers; bots have neither need.

## The AP Log

Everything you send and receive shows up in the AP Log on the right of the screen. **Show: All** lists the whole multiworld; **Show: Mine** keeps only what involves you.

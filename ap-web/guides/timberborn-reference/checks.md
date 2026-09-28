In Timberborn Archipelago you send checks in two ways: by buying slots in the AP Shop with science, and by reaching milestones while your colony grows. Nearly every building is locked until its blueprint arrives from the multiworld, so both kinds of check matter.

## The AP Shop

Open the shop with the Archipelago button in the bottom toolbar. It has four paths, **A**, **B**, **C** and **D**. Each path is a row of slots that you buy in order; you can switch between paths whenever you like.

- **One slot per building.** The shop has as many slots as your faction has blueprints: 132 for Folktails and 131 for Iron Teeth, so each path has 32 or 33 slots.
- **You don't see what you're buying.** A slot shows `???`, its science price and its tier. Buying it sends the check, and whatever the multiworld placed there goes to its owner, which may be you.
- **Prices climb.** With the default options the first slots cost about 30 science. Prices rise steadily across the whole shop up to the Max Science Cost option (5000 by default), and the Science Cost Multiplier option scales every price.
- **Skips.** A Skip item lets you buy an open slot without paying its science. The shop shows how many you have.

<p><img src="/img/timberborn/ap-shop-connect.jpg" alt="The AP Shop with four paths, each showing ???, a price in science and tier T1, with Needs: 30 science under the first path" width="820" height="790" loading="lazy" style="max-width:560px;margin:0 auto" /></p>

A fresh shop: every path waits at its first slot, and each card says what it still needs.

## Why a slot is locked

A slot you can't buy yet says what it needs, for example **Needs: previous check, Smelter, 120 science**. It never tells you what the slot holds. A slot can need:

- **The previous slot** of its path.
- **The Forester**, for every slot after the first of each path. With Starting Blueprints on (the default) you have it from the start.
- **Its tier's blueprints.** Slots belong to tiers 1 to 5, and higher tiers open as key blueprints arrive:

<table>
<thead><tr><th>Tier</th><th>Needs</th></tr></thead>
<tbody>
<tr><td>1</td><td>Nothing</td></tr>
<tr><td>2</td><td>Forester, Gear Workshop</td></tr>
<tr><td>3</td><td>Tier 2, Smelter, and for Folktails the Scavenger Flag</td></tr>
<tr><td>4</td><td>Tier 3, Tapper's Shack, Wood Workshop</td></tr>
<tr><td>5</td><td>Tier 4, Bot Part Factory, Bot Assembler, and for Folktails the Refinery</td></tr>
</tbody>
</table>

- **Badwater for Explosives and Extract.** Some slots also need a badwater source plus the Explosives Factory or the Centrifuge: the slots the shop layout set aside for a building that uses Explosives or Extract. The lock text names what is missing. See [Factions](/timberborn/reference/factions) for the badwater buildings.
- **Science.** Enough science points for the price.

A blueprint is only placed in a slot of its own tier or higher, so you won't find the Smelter in the first slots. The one exception is a blueprint that a tier itself needs, like the Smelter for tier 3, which may sit one tier lower.

## Scouts

Scout items (**Scout: Path A** to **Scout: Path D**) reveal the next slot of that path: its card shows the real item instead of `???`, and a hint is created for it. After you buy that slot, the next one is revealed.

## Milestones

Milestones are checks that fire by themselves as your colony grows. Each group can be switched off in the YAML.

- **Population:** first beaver born, first beaver grown up, and 15, 25, 50, 100 and 200 beavers.
- **Well-being:** average well-being 5, 10, 15 and 20.
- **Survival:** surviving your 1st, 5th and 10th drought and your 1st, 5th and 10th badtide. A hazard counts when it ends, and only hazards after you connected count.
- **Wonder:** completing your faction's Wonder in this game. A Wonder finished earlier on the same map doesn't count.
- **Resources:** reaching a stock of a good, such as 25 Gears or 500 Logs. The Resource Milestone Set option picks 13 (classic), 31 (lite) or 61 (full, the default) of them for your faction.

A resource milestone is in logic only once you can make the good with your own buildings. Goods you receive in packages still count toward the stock in game.

## Locked buildings in the build menu

Buildings whose blueprint you haven't received show the Archipelago logo where the unlock cost would be. They unlock the moment the blueprint arrives.

<p><img src="/img/timberborn/locked-levee-tooltip.jpg" alt="The Levee tooltip in the build menu with Unlock: followed by the Archipelago logo, above a toolbar of buildings with red lock badges" width="1178" height="500" loading="lazy" /></p>

The Levee before its blueprint arrived: the unlock cost shows the Archipelago logo.

The Wonder is the exception. It is not an item; you unlock it with science as in the normal game.

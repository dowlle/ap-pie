Your Timberborn world is done when you reach its goal. Pick one or more goals in your YAML, and whether you need any one of them or all of them.

## The seven goals

<table>
<thead><tr><th>Goal</th><th>What you do</th><th>Target (range, default)</th></tr></thead>
<tbody>
<tr><td>Wonder (default)</td><td>Complete your faction's Wonder: the Earth Recultivator for Folktails, the Earth Repopulator for Iron Teeth</td><td>None</td></tr>
<tr><td>Population</td><td>Reach a population; Population Mode decides whether beavers, bots or both count</td><td>10 to 500, default 100</td></tr>
<tr><td>Droughts</td><td>Survive a number of droughts</td><td>5 to 40, default 15</td></tr>
<tr><td>Badtides</td><td>Survive a number of badtides</td><td>1 to 20, default 5</td></tr>
<tr><td>Well-being</td><td>Reach an average well-being level</td><td>5 to 50, default 15</td></tr>
<tr><td>Bots</td><td>Have a number of bots</td><td>1 to 50, default 10</td></tr>
<tr><td>Water Storage</td><td>Have an amount of water in stock</td><td>500 to 50000, default 5000</td></tr>
</tbody>
</table>

**Goal Requirement** sets whether one of the selected goals is enough (`any`, the default) or all of them are needed (`all`). If you select no goal at all, Wonder is used.

## How goals are counted

- **Wonder:** it has to be completed in this game. A Wonder finished earlier on the same map doesn't count. The Wonder building is not an item: you unlock it with science, as in the normal game. The Folktails Wonder needs 500 Extract and 500 Paper, so logic expects a badwater source for it; the Iron Teeth Wonder needs 500 Treated Planks and 500 Berries.
- **Droughts and Badtides:** a hazard counts when it ends, and only hazards after you connected count. Badtides start after a few cycles and come in roughly 40% of cycles, so a badtide target takes longer than the same number of droughts.
- **Water Storage** counts the water your colony has stored, not the size of your tanks.
- The mod sends your win as soon as the goal is met, and sends it again when you reconnect, so a win is not lost to a dropped connection.

While the Water Storage goal is on, the seed holds back water packages so that received water alone can't finish it.

## Survival in logic

The first badtide comes on a fixed cycle whatever you have received. So with Force Early Items and Starting Blueprints on (both are the default), logic puts the Floodgate (or your first Progressive Flood Control) and the Medium Tank in your first sphere, next to the Levee and the Gear Workshop.

Before logic expects you to live through a hazard, it expects these buildings:

<table>
<thead><tr><th>Stage</th><th>Droughts</th><th>Badtides</th></tr></thead>
<tbody>
<tr><td>Early: droughts 1 to 5, badtides 1 to 3</td><td>Levee, Floodgate, Stairs</td><td>Floodgate, Levee, Medium Tank</td></tr>
<tr><td>Mid: droughts 6 to 15, badtides 4 to 10</td><td>Early, plus Medium Tank, Double Floodgate, Platform</td><td>Early, plus Double Floodgate, Contamination Sensor and a cure: Herbalist and Paper Mill (Folktails) or Decontamination Pod (Iron Teeth)</td></tr>
<tr><td>Late: more than that</td><td>Mid, plus Large Tank or Triple Floodgate, and a Gravity Battery, Geothermal Engine or Wind Turbine (Iron Teeth: Steam Engine)</td><td>Mid, plus Large Tank and a Mechanical Fluid Pump or Compact Mechanical Pump (Iron Teeth: Large Water Wheel and a Deep Mechanical Fluid Pump or Compact Mechanical Pump)</td></tr>
</tbody>
</table>

Where the table is used:

- **Survival milestones:** the 1st drought or badtide uses the early row, the 5th the mid row and the 10th the late row.
- **Droughts and Badtides goals:** the row follows the target, as in the table.
- **Long goals:** Wonder, Population 100 or more, Well-being 20 or more and Water Storage 5000 or more need mid drought and early badtide survival.

On top of survival, bigger targets need more of the tech tree in logic. A population of 200, for example, is only expected once shop tier 4 is open, and the Bots goal always expects tier 5.

## Choosing goals

The default goal, the Wonder, needs shop tier 4, the production chains for its goods and mid drought survival, so it makes a long game. For a shorter game, try Population or Well-being with a lower target, or Droughts at 5 to 10. The [Options](/timberborn/reference/options) page lists every option that shapes a seed.

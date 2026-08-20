CTR Archipelago can turn Adventure Mode rewards and even parts of your kart into items. The exact progression model is chosen when the world is generated.

> This page includes 0.2.0 preview systems. They are available to testers but are not part of the current 0.1.5 stable release.

## Adventure progression

Trophies, Keys, Relics, coloured CTR Tokens, and Gems can enter the Archipelago item pool. The reward for a race or challenge is no longer guaranteed to be the reward the original game placed there.

When you clear a location, its item may belong to you or to somebody playing another game. Your own next Key or Trophy can arrive from anywhere in the multiworld. Warp pads read the received item counts, not the original save-file reward bits.

## Progressive Boost

In 0.2.0, a seed can make boost capability progressive. Your kart starts without the full boost package and received Progressive Boost items move it up the configured ladder.

The first received copy enables ordinary self-earned boost. The second raises the kart to Ultra Sacred Fire speeds. A seed can optionally add Blue Fire as its capstone. Before the first copy, ordinary turbo pads still work but powerslides and hang time do not provide self-earned boost. When Progressive Boost is disabled, CTR keeps its ordinary boost behavior and no Progressive Boost items are added.

## Progressive Stats

Progressive Stats applies separate upgrade chains to Top Speed, Acceleration, and Turning. Each chain has five effective ranks:

1. Very Low
2. Low
3. Medium
4. High
5. Very High

You begin at Very Low and each received copy raises that stat by one rank. Very High sits above the best normal character value for that stat. The Garage bars show the effective Archipelago ranks while this system is active.

## Shared or per character

The generator can use one shared set of stat chains for the whole roster or separate chains for every racer.

In shared mode, receiving Progressive Top Speed improves Top Speed for every character. Character choice becomes cosmetic for Top Speed, Acceleration, and Turning while the mode is active.

In per-character mode, every racer owns separate versions of all three chains. An upgrade for Crash does not improve Coco or Tiny. This creates a much larger item pool and makes the characters develop independently.

When Progressive Stats is off, every character keeps the original game's stat table. If a seed also enables editable stats, progressive ownership takes priority and the Garage editor remains read-only.

## What happens on reconnect

Received progression belongs to the Archipelago slot, not only to the current game process. When you reconnect, the client rebuilds the effective capability state from the items the server says you own.

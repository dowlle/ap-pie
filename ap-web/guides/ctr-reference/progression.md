In CTR Archipelago, your next Key, racer or kart upgrade can arrive from anywhere in the multiworld. You choose which systems to use in your YAML before the world is generated.

> This page describes stable 0.2.0. See the [release notes](/ctr/reference/0-2-0-release-notes) for experimental features and remaining testing coverage.

## Adventure progression

Trophies, Keys, Relics, coloured CTR Tokens, and Gems can enter the Archipelago item pool. The reward for a race or challenge is no longer guaranteed to be the reward the original game placed there.

When you clear a location, its item may belong to you or to somebody playing another game. Your own next Key or Trophy can arrive from anywhere in the multiworld. Warp pads count the items you have received, so winning a race does not necessarily bring you closer to a pad's Trophy requirement.

Keys let you travel between the Adventure hubs. Boss garages use Trophy counts instead: Ripper Roo, Papu Papu, Komodo Joe and Pinstripe open at 4, 8, 12 and 16 Trophies respectively. Those are received Trophies, not a requirement to win that many races yourself.

## Progressive Boost

With Progressive Boost enabled, you find your boost abilities as items. Each copy of Progressive Boost unlocks the next step.

The first received copy enables ordinary self-earned boost. The second raises the kart to Ultimate Sacred Fire speeds. A seed can optionally add Blue Fire as its capstone. Before the first copy, ordinary turbo pads still work but powerslides and hang time do not provide self-earned boost. When Progressive Boost is disabled, CTR keeps its ordinary boost behavior and no Progressive Boost items are added.

## Progressive Stats

Progressive Stats applies separate upgrade chains to Top Speed, Acceleration, and Turning. Each chain has five effective ranks:

1. Very Low
2. Low
3. Medium
4. High
5. Very High

You begin at Very Low and each received copy raises that stat by one rank. That means four upgrades per stat, not five items. Very High sits above the best normal character value for that stat. You can check your current ranks in the pause-menu character screen.

## Shared or per character

Choose whether stat upgrades help the whole roster or only the named racer. Progressive Boost has its own shared or per-character setting, so you can choose a different setup for each.

In shared mode, receiving Progressive Top Speed improves Top Speed for every character. Character choice becomes cosmetic for Top Speed, Acceleration, and Turning while the mode is active.

In per-character mode, every racer owns separate versions of all three chains. An upgrade for Crash does not improve Coco or Tiny. This adds many more items to find: 192 stat upgrades across the 16 racers, compared with 12 in shared mode. You need enough checks enabled to fit them into the world.

When Progressive Stats is off, the seed's character and stat settings apply. Editable stats are accessed through the pause-menu character screen; progressive ownership takes priority when enabled.

## What happens on reconnect

Your upgrades are saved for your Archipelago player slot and restored when you reconnect to it. You do not have to find them again after closing the game. A large backlog of items can still cause a pause while reconnecting; see the [release notes](/ctr/reference/0-2-0-release-notes#practical-limitations-and-testing) for current limitations.

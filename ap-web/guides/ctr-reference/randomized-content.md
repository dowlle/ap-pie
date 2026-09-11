You can keep CTR close to the original Adventure Mode or add new checks, unlockable racers and kart upgrades. Choose your settings in a YAML file before your host generates the multiworld.

A **check** is something you do to send an item, such as winning a race or breaking an AP box. That item might be for you or for someone playing another game. Your next Key could come from their world instead of a boss race in yours.

> This page covers CTR Archipelago 0.2.0. Most features below are optional. The [release notes](/ctr/reference/0-2-0-release-notes) explain experimental features and known limitations.

## Adventure routes

- **Warp-pad requirements:** a pad might ask for Keys, Relics, Tokens or Gems instead of the original Trophy count. The symbol above it tells you what you need.
- **Warp-pad destinations:** shuffle where pads take you. The Crash Cove pad might lead to a different track or challenge. See [warp pads and requirements](/ctr/reference/warp-pads) for how the entrance and destination work together.
- **Gem Cup tracks:** each cup can draw its four races from the 16 Trophy tracks. Tracks can repeat, so a cup can include the same track more than once.
- **Choose your goal:** finish by beating Oxide, winning a chosen number of the four boss races, collecting a chosen number of the five Gems, or combining those goals. You must meet every goal you enable. For Oxide, choose his first Challenge or Final Challenge; you can also leave his races as optional checks or remove them.

## Checks and rewards

- **Race and challenge rewards:** Trophy Races, Relic Races, CTR Token Challenges, Boss Races, Gem Cups and Crystal Challenges can send items to the multiworld.
- **Podium checks:** add rewards for holding a position during a race or finishing in the top three. You can also include a check for finishing in any position.
- **Itemsanity:** unlock weapons by receiving them from the multiworld. Using each of the 11 Adventure weapons sends a check, with another for using it while holding ten Wumpa. Weapon unlocks and all 22 firing checks are enabled together.
- **AP boxes:** add extra AP boxes to the tracks for more places to search. Breaking one sends its item to the player it belongs to.
- **Lettersanity:** collecting individual C, T and R letters can send checks. You can also require letter items from the multiworld before you can collect them, or combine both settings. The Letters Per Track option lets you use fewer letter checks.
- **Wumpa:** add one check for reaching ten Wumpa anywhere, or one for each eligible track. You can also receive upgrades to your starting Wumpa and bundles of fruit.

Winning Cortex Castle might send an item to another player. Your own next upgrade can arrive from a check in their game.

## Kart capabilities

- **Progressive Boost:** start without powerslide or hang-time boost and find upgrades to unlock ordinary boost, then Ultimate Sacred Fire. An optional third upgrade adds Blue Fire. Ordinary turbo pads still work before your first upgrade.
- **Progressive Stats:** start at Very Low Top Speed, Acceleration and Turning. Each stat has four upgrades, taking it through five ranks to Very High.
- **Shared or per character:** choose separately for boost and stats whether upgrades help the whole roster or only the named racer. A Crash-only upgrade will not improve Coco. Per-character settings add many more items to find; the [progression guide](/ctr/reference/progression) explains the difference.

**Shortcut Knowledge** tells the generator how difficult the routes to required checks may be. Higher settings can expect harder shortcuts and jumps. It does not teach your kart a new ability or change the track layout.

## Characters

- Pick your starting racer or let the game choose one at random.
- With Character Unlocks on, the other racers arrive as items from the multiworld.
- Racer-Locked Warp Pads can require you to unlock a particular racer. Entering one puts you in that racer's kart and restores your previous choice when you return to the hub.
- Keep the original character stats, choose a starting stat class, allow manual stat editing, or use Progressive Stats.

## Traps and useful items

Received traps can temporarily change the way a race plays. 0.2.0 includes twenty effects, from Icy Road and Low Gravity to Nitro Drop, Mirror Mode, Warpball Ambush and Demo Camera. Use Trap Fill Percentage to choose how much filler becomes traps, and Trap Weights to make individual effects more common or turn them off. See the [full trap roster](/ctr/reference/0-2-0-release-notes#traps-and-comfort-items).

Some items help during a race. For example, a received Turbo waits until you are racing with a free weapon slot before it is delivered. Comfort items can remove natural terrain penalties, such as slowing down on grass or slipping on ice.

## Other ways to change the run

**One-Lap Cups** shortens cup races to one lap. Single races, boss races, Relic Races and CTR Token Challenges keep their normal lap counts.

**DeathLink** shares mishaps with other participating players. You can send one when the mask carries you back after a fall, or after any hit. Receiving a DeathLink forces a mask reset in your game. It is off by default.

The experimental [Baby T Park preview](/ctr/reference/0-2-0-release-notes#baby-t-park-preview) lets a prepared seed replace the Purple Gem Cup with one supported custom track. Stable 0.2.0 does not support general custom-track libraries or custom multiplayer maps.

## What does not change

These options change progression and selected parts of gameplay. They do not automatically shuffle every visual, track layout, opponent or physics value. The Builder shows the settings supported by the version your host is using.

You still need a disc image made from your own North American copy of CTR. The [setup guide](/guides/ctr) explains how to use it; no game data is included with the client.

Ready to choose your settings? [Open the CTR 0.2.0 YAML Builder](/yaml-builder/ctr?version=0.2.0), review the file, and download it for your host.

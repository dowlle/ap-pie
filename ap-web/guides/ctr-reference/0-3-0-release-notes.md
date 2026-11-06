**[Download 0.3.0 alpha 2](https://github.com/dowlle/ctr-native-ap/releases/tag/v0.3.0-alpha2)** · **[Setup guide](/ctr/setup)**

> **This is alpha 2 of 0.3.0, a test build.** v0.2.4 is still the stable version.
> The alpha doesn't update itself. The in-game updater only offers stable releases, so grab new alphas by hand.
> Use a new folder, and keep your 0.2.4 install as it is.
> This page grows with each alpha and turns into the 0.3.0 release notes. Coming from alpha 1? Start with [New in alpha 2](#new-in-alpha-2).

0.3.0 is the biggest update so far. Every seed now comes from one generator and the YAML is one flat list of options. Custom tracks are part of the game: import them, race them in Arcade, or put up to 132 in a seed. There's also Play Solo, a Wumpa Shop, boss randomization, a bunch of new checks and traps, and an in-game updater for the next release.

## New in alpha 2

Alpha 2 fixes a lot of what you found in alpha 1 and adds a few new things.

- **Use the alpha 2 client and the alpha 2 APWorld together.** Download both from the [alpha 2 release](https://github.com/dowlle/ctr-native-ap/releases/tag/v0.3.0-alpha2). Use a new folder or replace your alpha 1 folder; your 0.2.4 install and rooms stay as they are.
- **An alpha 1 room still connects** to the alpha 2 client, and an alpha 1 YAML still works. There are four new options.

### Fixed since alpha 1

- Opening the tracker while the hub save camera moved could start a race with the save menu still on screen. Pause and the tracker now wait until the camera has stopped.
- Wumpa you get outside a race, bought in the shop or sent by other players, is added right away, single fruit included, instead of waiting for the next race.
- Wumpa Wipeout removes all the fruit of the race, also above 10.
- A seed with Spoiler Items on and coloured boxes off starts again.
- Arcade, Time Trial, Versus and Battle play like the original game again: normal boosts, and no AP items, traps or checks.
- Loading another save profile no longer keeps a racer that's locked in the room.
- AP boxes on custom tracks no longer sink into the ground.
- Cups show the custom track's own name instead of "Roo's Tubes".
- Boss garages show the full rival name and a "<Boss>'s Challenge" heading.
- A boss cup now races the rival its garage names, and its banner reads "<Boss>'s Cup".
- Bosses on custom tracks pick a lane ahead of themselves, so the boss no longer stalls when it runs out of time.
- Shop item names stop before the price.
- Hit Character checks count a boss race as soon as you can enter it.
- Only one Cortex Vortex per seed: a downloaded copy is replaced by the one that comes with the game.
- Custom track downloads retry when Project Saphi rate limits them, and errors show the real reason.
- Play Solo names the track it can't publish and replaces a stale copy, instead of "could not publish the Play Solo descriptor".
- The window title shows the plain version.
- No more looping podium noise in the hub after a Trophy Race win.
- A 0.2.x YAML is refused with one readable message.

### New

- **Custom Tracks screen:** one screen with Library, This Seed and Import tabs. The importer keeps track names, lets you rename them, and can import all valid tracks at once.
- **Custom track music:** custom tracks play their own music, however you installed them. Imported tracks without their own music play the music of the track they replace.
- **Box Author Mode** is in the regular client, under Options, Authoring: place AP boxes on a track and export them yourself.
- **Play Solo options:** every YAML option is on the options screen, in groups. Lists like Crystal Arenas and the boss pools are checklists, and the screen tells you when a value won't generate. There's no password by default; you can set one.
- **Play Solo with big libraries:** track checks run in the background, so a large track library no longer freezes the menu.
- **Leaving a race pays:** Exit to map, Restart and a DeathLink loss bank the fruit you picked up, minus hits. Starting fruit never banks.
- **Wumpa Shop pacing:** expensive shelves come into logic later, by the Keys you've received: 100, 300, 600 and 900 Wumpa at 0 to 3 Keys, more at 4. The new option `wumpa_shop_logic_scale` (25 to 400%) scales those amounts.
- **Wumpa bundles are on by default:** some Wumpa filler becomes Small or Big Wumpa Bundles.
- **Hint filters:** `pad_hints_progression_only` and `shop_hints_progression_only` limit pad and shop hints to progression items, and `pad_hints_wait_for_spoiler` makes pad hints wait for Warp Pad Preview. All three are off by default.
- **Pad colours:** the pad beam, hub map and tracker use the same colours. An open pad has a green beam and a pad whose second stage is open a blue-violet one. A finished pad you can still race again for Wumpa keeps the light blue beam with its X.
- **Custom track boost rules:** Ancient Lake, Drive Thru Danger, Bowser Castle 1 and Neon Paradise no longer need USF to finish, and Lights Out needs the first boost.
- **Clearer YAML descriptions** for almost every option, and three options have new display names: Guaranteed Warp Pads (`required_entries`), Pads With Two Requirements (`two_stage_density`) and Papu's Pyramid Mask Helper (`tizi_helper`).

### Known issues in alpha 2

- The Custom Tracks screen still has rough edges: the Library can show only some of your tracks, the Project Saphi catalogue may not show, This Seed can say no seed is loaded while you're connected, and the Import help text is cut off. Fixes come in alpha 3.
- The race-start banner of a cup can show another cup's name, for example "Red Gem Cup" for the Purple Gem Cup. The standings show the right name.
- Some menus are still hard to read where text runs over the logo.
- A seed can still fail to generate with some unusual YAMLs. Generate again, and send me the YAML.
- Short freezes can happen in some races. If you get one, tell me the track.

## What's new

- One generator for every seed, and one flat YAML with 95 options.
- A YAML that sets nothing gets the original game's shape: 18 tracks, 5 Gem Cups, 4 Crystal Challenges and the five boss races, shuffled.
- Custom tracks: import from a patch, Custom Arcade and Time Trial pages, a Track Library, and up to 132 tracks in a seed.
- Cortex Vortex is a full track, with its own music.
- Play Solo: make and play a seed from the title screen, no server needed.
- New checks: Crystalsanity, the arcade arenas, cup sweeps, lap checks, Relic Race Perfect on custom tracks.
- The Wumpa Shop and a Wumpa goal.
- Random boss tracks, racers and weapons, boss cups, the Purple Gem Cup gauntlet and a chaos Final Challenge.
- New traps and filler, Spoiler Items, and traps you can't dodge anymore.
- A `weapon_hit` DeathLink mode.
- An in-game updater, button remapping and starting pads from the tracker.

## Before you update

- **Finish 0.2.x rooms on v0.2.4.** The 0.3.0 client refuses a room made with 0.2.x and says "This room was made with v0.2.x. Play it on the v0.2.4 client." The host keeps the 0.2.4 APWorld for that room, for the server and for Universal Tracker. v0.2.4 stays on the download page.
- **Update by hand this time.** v0.2.4 has no in-game updater. Download 0.3.0 and the matching `ctr.apworld` from the same release, and follow "Updating from 0.2.x" in SETUP.md. Back up your old folder, settings and saves included, and keep it until the new one connects.
- **Make a new YAML.** Build it in the YAML Builder with 0.3.0 selected. An old YAML still loads: removed option names are skipped, but three old values are refused and a lot of defaults changed.
- **Bigger downloads.** Play Solo brings its own Python and Archipelago, so the Windows ZIP is about 14 MB bigger and the Linux tarball about 22 MB.
- **A few things work differently:**
  - Turbo Grant gives you a Turbo at the start of every race now, not once.
  - Editable stats are picked as rank values (VERY LOW to VERY HIGH), so an old setting can land on a nearby rank.
  - With vanilla requirements, the second race on a track pad asks for that hub's Keys, like the original game, and Turbo Track asks for one Gem of each colour.
  - Arcade, Time Trial, Versus and Battle always use the original kart stats, even while you're connected to a room. Your seed's stats are for Adventure.

## One generator and the new YAML

Every seed now comes from one generator. If your YAML doesn't set any content, you get the original game's shape: the 18 race tracks, 5 Gem Cups, 4 Crystal Challenges and the five boss races, on the original 27 warp pads and five garages, shuffled. The first five cups are the original Gem Cups with their Gems. Cup races are drawn, four different tracks per cup. Slide Coliseum and Turbo Track offer all three races now.

The YAML is one flat list of 95 options in twelve groups: Tracks, Cups and Arenas, Bosses, Goal, Pads and Requirements, Checks, Wumpa Shop, Items and Traps, Characters and Stats, Boost, DeathLink and Display. Each thing is set in one place, and the Builder explains every option. Some highlights:

- `pad_placement`: `vanilla`, `shuffle_within_kind` (tracks on track pads, cups on cup pads, arenas on arena pads) or `shuffle`. Vanilla requirements work with all three.
- `retail_tracks`, `cup_count`, `cup_tracks` and `crystal_challenge_count` decide what's in the seed.
- `track_modes` sets which races each track offers, and `race_mode_order` the order they open in.
- With random requirements, the boss garages draw their own requirement too. `garage_requirement_level` sets how big it gets.
- `requirement_weights` is the one table for what pads ask for, and `two_stage_density` decides how many pads get a second requirement. A pad's later races open only after you've won its first race; the pad text says which race to win first.
- `item_pool` is the one place for item counts, relics included.
- `shuffle_keys: off`, `shuffle_gems: off` and `oxide_1_optional: filler` keep those items on their own checks.
- `plando_items` and `item_links` work as you'd expect.

Generation got sturdier too. The generator plans the whole opening and draws again when a plan doesn't fit, and the default YAML starts with more open checks: about 15 instead of 11 in our tests, and 16 instead of 6 with vanilla requirements.

## Custom tracks

Custom tracks are tracks made by the community, like the ones on Project Saphi. In 0.3.0 they're part of the game, in a seed and outside one.

- **Import from a patch.** Many tracks come as a patch for your own disc. Go to Options > Custom Content and press Select > Import track files, put the patch in `assets/tracks/import/`, or just drop the `.xdelta` or `.vcdiff` file on the game window. The game builds the track from your own NTSC-U disc. Race tracks only for now.
- **Current Seed.** Options > Custom Content opens on a Current Seed tab that lists every track your room needs, Ready or Missing. "Install missing content" gets them in one go. It can download any track that's registered and on Project Saphi. The game reads the track registry online, so new tracks don't need a new client, and it keeps a copy for when you're offline. The game only installs files that match what the room expects.
- **Custom Arcade and Time Trial.** In Arcade and Time Trial, Left and Right flip through pages of your custom tracks after the original ones. R2 searches, L2 rescans. It works without a room.
- **Track Library.** A new page in Options shows the tracks you have installed.
- **One track store.** Every track you install shows up in Play Solo, whether it came from the Track Manager's Project Saphi downloads, Current Seed, the patch importer or a package you put in by hand. Tracks that only work in Time Trial are listed, but can't go on Adventure pads. A seed uses one revision of a track.
- **Up to 132 tracks in a seed.** `custom_tracks` is a list of track packages. They go into the same pool as the original tracks: on pads, as cup legs (`cup_custom_legs` sets how many per cup) and as boss tracks. `required_entries` makes sure a track gets its own pad.
- **Everything works on them:** Trophy Race, CTR Challenge with letters, Relic Race with the track's own times, Relic Race Perfect, podium checks, item boxes (one for each weapon crate the track's package states, up to 15), Reach 10 Wumpa, Hit Character, and lap checks. Tracks with measured Wumpa count toward the Wumpa Shop and goal.
- **Proper names.** A registered track's checks use its name, like `Baby T Park: Trophy Race`. Two tracks with the same name get `(Custom)` or the author added.
- **Cortex Vortex** is a full track now. `cortex_vortex_track` is `off`, `in_pool` (it may get a pad or a cup leg) or `own_pad` (it always gets one). It plays its own music by Lockheart instead of Oxide Station's.
- **For track makers:** the Custom Content page writes the complete 0.3.0 descriptor, with checkpoints and AI paths (a track needs both to host a boss race), weapon crates, super turbo pads, and Relic Race times you can set on the page. A track only claims Arcade with 8 spawn points.
- In two-player Adventure, a custom track race runs as one player for player 1.

## Play Solo

Pick PLAY SOLO on the title screen to make and play a one-player seed without setting up a server.

- Start from a preset (**Quick**, **Standard** or **Full Adventure**), import a YAML, or import a one-player room. You can also drop a YAML into the `solo/inbox` folder. The YAML Builder has the same three presets.
- A preset opens a short options screen. If you have custom tracks installed, a Custom Tracks page lets you set each one to not used, in the pool, or its own pad. Imported tracks show up there straight away; a track without a lap count gets a laps picker.
- The game runs a private Archipelago server on your own computer. Nothing goes over the internet, and it works offline.
- To do that, the game starts its own copy of Python in the background (it's in the `solo-runtime` folder, so you don't need Python installed). The server only listens on your own PC (127.0.0.1). If your antivirus asks about it, that's what it is.
- Your seeds are saved in the `solo` folder next to the game, with their progress. Back it up with your memory cards.
- DeathLink is off in solo, imported YAMLs and rooms too.
- You can't paste a YAML from the clipboard, or change an imported YAML's options in game, yet.

## New checks and options

All of these are off by default unless it says otherwise.

- **Crystalsanity** (`crystalsanity`): every crystal in a Crystal Challenge is a check.
- **Arcade arenas:** Parking Lot, The North Bowl and Lab Basement can be Crystal Challenges. List them in `crystal_arenas`. Their timers are 1:05, 1:30 and 0:50.
- **No arenas:** `crystal_challenge_count: 0` takes the arenas out completely, pads and checks. Purple CTR Tokens stay in the item pool.
- **Cup sweeps** (`cup_sweep_checks`): a check for winning all four races of one cup run.
- **Lap checks** (`lap_completion_checks`): a check for finishing the first lap on each track you race, boss races included.
- **Relic Race Perfect** works on Cortex Vortex and custom tracks too.
- **Podium checks from cups:** podium checks now also count in Gem Cup legs on a track. `cup_only_podium_rungs` gives podium checks to tracks you only race in cups.
- **Reach 10 Wumpa** (`per_track`) can be earned in cup legs and boss races, and tracks raced only in cups or boss races get one too.
- **Wumpa Shop** (`wumpa_shop_slots`, on by default with 10 slots per hub): open WUMPA SHOP in a hub's save menu and spend the fruit you've collected on checks. `wumpa_shop_prices` scales the prices, `wumpa_shop_progression: excluded` keeps progression out of the shop, and `wumpa_shop_hints` (on) hints a page's items when you open it. WUMPA SHOP is the first row of the save menu, and the hub and shop show your total as COLLECTED. A slot's price doesn't tell you whether it holds progression.
- **Wumpa goal** (`goal_wumpa`): collect this much fruit as part of your goal.
- **Bosses:**
  - `boss_track_shuffle`: each garage races its boss on a drawn track, custom tracks and Cortex Vortex included. `boss_track_pool` limits the tracks.
  - `boss_opponent_shuffle`: each garage gets a drawn boss racer. `boss_character_pool` limits who; list N. Oxide to let him be a garage boss.
  - `boss_kit_shuffle`: drawn weapon sets for the bosses, with `boss_attack_assignment`, `boss_attack_intensity`, `boss_loss_easing` and `boss_weapon_pool`. `oxide_attack_profile` and `oxide_weapon_pool` do the same for N. Oxide.
  - `boss_cups`: up to four garages hold a four-race boss cup instead of one race.
  - `purple_cup_boss_gauntlet`: the Purple Gem Cup races the four garage bosses' weapons in order. Needs `boss_kit_shuffle`.
  - The garage panel and the tracker show the track, the rival and the kit.
- **Guest racers:** with random bosses, the drawn racer and the garage's original boss swap places in the race field until you beat the garage.
- **Chaos final:** `oxide_final_track: vanilla_chaos` or `vortex_chaos` races the Final Challenge on Oxide Station or Cortex Vortex against five armed rivals.
- **CTR-first adventure** (`adventure_structure: ctr_first`): the CTR Challenge replaces the Trophy Race. First place pays the Trophy Race check; first place with all the letters also pays the CTR Token.
- **Race type menu:** a track pad lets you pick which race to run. `race_type_selector` sets when the menu opens (`always` or `productive`), and the Race Type Menu row in Options can override it.
- **Your own pad rules** (`warp_pad_rules`): set the first requirement of any pad yourself, for example a free Crash Cove. The pad shows the rule and how many you have.
- **Spoiler Items** (`spoiler_items`): pad previews and box colours stay hidden until you receive Warp Pad Preview and AP Box Colours.
- **Pad Approach Hints** (`pad_approach_hints`, off by default): driving up to an open pad hints its unchecked checks that are in logic, each location once. Hints cannot be undone and the whole room sees them.
- **Item and location groups** for hint commands: per-character stats (like `Crash Bandicoot Stats`), every registered track and arena, race modes, relic tiers (like `Relic Race Sapphire`), podium checks, bosses, item boxes and Hit Characters.

## Items and traps

- **Clocked Out** (new trap): the clock power-up hits you for about 8 seconds.
- **Reverse Camera** (new trap): you see the rear view, steering stays normal.
- **Reserve Top-Up** (new filler, on by default): tops up about 25% of your boost reserve during a race.
- **Traps you can't dodge:** Nitro Drop and Red Potion hit your kart directly instead of spawning ahead of you. Item Reroll and Forced Use go through even if you fire during the warning, and if your slot is empty they wait for your next item.
- **Turbo Grant** gives you a Turbo at the start of every race once you have it, and a restart gives you a new one. With Itemsanity on it still waits for the Turbo item.
- **`start_inventory_from_pool`** works for CTR now.

## DeathLink

- New mode **`weapon_hit`**: a death you receive spins you out like a weapon hit. A shield, mask or invincibility still blocks it, and you still get the popup.
- **`any_hit` is gone.** A YAML with it is refused; use `weapon_hit` or `mask_reset`.
- When a newer death replaces one that was waiting, the old one shows a DEATHLINK IGNORED popup instead of vanishing.
- A big pile of deaths at once shows one summary popup.
- Relic Races have stakes while a relic check is open and in logic.
- DeathLink is always off in Play Solo.

## Quality of life

- **In-game updater.** From 0.3.0 on, the game checks for new stable releases (alphas aren't offered) and offers them on the main menu. It checks the signature before it changes anything, keeps your settings, saves, tracks and solo seeds, and keeps the old files until the new version starts. You can turn it off in Options > Archipelago. It won't update from an exFAT SD card on the Steam Deck; update by hand there.
- **Controls page.** Options > Controls lets you pick a device per player, remap every button and stick, set the stick deadzone, and remap the AP shortcut keys. Ported from CTR Native Expanded.
- **Start pads from the tracker.** Pick a pad or garage in the in-game tracker and start it from there (`tracker_pad_launch`, on by default).
- **The tracker names what a locked race needs,** like `2 RED GEMS`.
- **Rank selector.** With Progressive Boost or Progressive Stats, press SQUARE in the hub character picker to drive a lower rank than you've unlocked. It's saved per seed.
- **Item box numbers.** Each AP item box shows its number above it, so you know which one is Item Box 12. Turn it off with the Item Box Numbers row in Options.
- **Finished pads** can be raced again.

## Fixes

- **SlotLock:** generation no longer fails when SlotLock or a similar world wraps a CTR rule. That slot's race-loss DeathLink just sends on every loss. Reported on Discord.
- **Vanilla requirements and Keys:** the second race on a track pad now asks for the hub's Keys. Thanks BEXUS99 for the report (#499).
- **Stat bar:** the character picker shows all five Progressive ranks, so 3 and 4 don't both look full. Thanks DragRedSim for the report (#466).
- **Boss map star:** with a Bosses goal, a boss someone else collected keeps its star on the hub map until you beat it yourself.
- **Busy races:** effects, crates and explosions have four times more room, and if they still run out, the game skips the effect instead of crashing.
- **Warp Orb in Mirror Mode:** it keeps its model now, not just the lightning.
- **Hit Character:** backing out of the Hit chooser no longer warps you again.
- **Universal Tracker:** it no longer drops items found on custom track checks.
- **Item boxes:** every custom track whose package states weapon crates gets AP item boxes now, one per crate, at most 15. Before, only registered tracks got them. If a track's boxes don't match between the seed and the client, that track's boxes switch off instead of sending the wrong checks.
- **Wumpa Shop prices:** a slot's price no longer depends on what's in it, so the cheap slots don't give away progression.
- **Wumpa fruit:** Adventure races count all your fruit past 10 and bank it when you finish. Exit to map, Restart and a DeathLink loss bank the fruit you picked up, minus hits. A first pad race you've won stays open for farming Wumpa while the later races are still locked.
- **Failed seeds:** most of the seeds that used to fail to generate now generate.

## Known issues

- **Rooms from 0.2.x** don't load on 0.3.0. Play them on v0.2.4.
- **Rare failed seed:** with some unusual YAMLs (lots of cups and arenas, Itemsanity, many traps) a seed can still fail to generate. Generating again fixes it. If it happens, send me the YAML.
- **Old YAMLs:** Archipelago prints one warning line per removed option name. The seed still generates.
- **Menus:** some menus are hard to read, especially Options and Custom Tracks, where text runs over the logo.
- **Custom Tracks screen:** the Library can show only some of your tracks, the Project Saphi catalogue may not show, This Seed can say no seed is loaded while you're connected, and the Import help text is cut off.
- **Cup banner:** the race-start banner of a cup can show another cup's name. The standings show the right name.
- **Short freezes** can happen in some races. If you get one, tell me the track.
- **Wumpa Shop prices** are a first guess and will get tuned once there's more play data.
- **Random bosses:** the boss's voice lines may be silent when a different racer takes the garage, and the scene after the race shows the garage's original boss. The echo in a boss race follows the boss, not the drawn track.
- **Custom tracks:** the importer takes race tracks only, no arenas and no LZMA patches. In two-player Adventure a custom track race runs as one player.
- **Play Solo:** no clipboard paste, and an imported YAML's options can't be changed in game.
- **Updater:** fails safe on an exFAT SD card on the Steam Deck, so update by hand there.
- **Room links** from the room page still work on Windows only.
- **Reconnecting:** a big pile of received items can stall the game for a while (#147).
- **Podium:** some characters can be invisible on the podium after a race. It's only cosmetic (#282).

## Verifying your download

`manifest.json` lists the SHA-256 of both client archives, and `manifest.json.minisig` is its signature with the release key (key ID 46F129D8BEF2D633, public key `ctr-release-minisign.pub` in the repository).

To check it with minisign, put `manifest.json` and `manifest.json.minisig` in the same folder and run:

`minisign -Vm manifest.json -P RWQz1vK+2CnxRlzUFiAM8FlyI706TxjELuc+8d4N9uh06nS1zAKGuD6x`

It should say the signature is verified. Then compare the SHA-256 of your client archive with its line in `manifest.json`. With Python 3 and minisign you can also download every asset into one folder and run `python3 tools/verify-release.py <folder> --version v0.3.0` from the source at the v0.3.0 tag. The in-game updater does the same check by itself from now on.

## Thanks

Thanks to MarioSpore for the box number, pad rules, item and location groups, `weapon_hit`, trap and Turbo Grant ideas, venusyprime for the arena and Spoiler Items ideas, BEXUS99 for the filler and Clocked Out ideas and the vanilla Keys report, and DragRedSim for the stat bar report. Thanks to thecodingbob for the Controls page from CTR Native Expanded, Lockheart for Cortex Vortex and its music, LRG2Pancho and every track maker on Project Saphi, and everyone on Discord who tested, reported the SlotLock crash and sent ideas.

## Found a problem?

Open a GitHub issue with your platform, client version, seed or YAML, what happened, and the support bundle. Run `support-bundle.bat` on Windows or `support-bundle.sh` on Linux, and look through the bundle before you attach it. It doesn't upload anything by itself.

Questions are welcome in the Crash Team Racing channel on the Archipelago Discord. The GitHub release has the downloads, checksums, the signed manifest and debug files.

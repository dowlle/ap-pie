**CTR Archipelago 0.2.2 adds three YAML options, Skip Cutscenes and Discord Status, and fixes the mid-race freezes, the Steam Deck fullscreen lag and a few cutscenes and traps that fired too often.**

**[Download 0.2.2](/ctr/download)** · **[Setup guide](/ctr/setup)** · **[Build a 0.2.2 YAML](/yaml-builder/ctr?version=0.2.2)**

## At a glance

- New YAML options: Remove Playable Oxide, Relic Race Perfect Checks, and a DeathLink mode where a death costs you the race.
- Held 1st now needs your first boost (or a useful weapon with Itemsanity) in logic, and easy and medium need a boost for Trophy Races with Itemsanity off.
- New local options: Skip Cutscenes, and Discord Status to show your race in Discord.
- The one-second freezes while racing are fixed, and so is the Fullscreen lag on Steam Deck.
- The boss door scene and the Oxide Final Challenge scene play once instead of after every podium.
- Traps, Wumpa and Turbo Grants from an old room no longer carry over to a fresh room of the same seed.
- Downloads now come with a signed manifest you can check.

## Where should I start?

- **Joining a room?** Get the client from the [download page](/ctr/download) and follow the [CTR setup guide](/ctr/setup). You need your own NTSC-U disc image.
- **Preparing a YAML?** Use the [0.2.2 YAML Builder](/yaml-builder/ctr?version=0.2.2) and send the YAML to your host. The [YAML guide](/guides/setting-up-your-yaml) explains the file.
- **Hosting?** Install the matching `ctr.apworld` and follow the [hosting guide](/guides/hosting-a-multiworld). Archipelago 0.6.7 or newer is needed. `Crash.Team.Racing.yaml` on the GitHub release is the template for this version.

## Compatibility and upgrading

- **New games:** use the 0.2.2 client with the 0.2.2 APWorld and YAML.
- **Ongoing 0.2.1 rooms:** you can keep playing a 0.2.1 room on the 0.2.2 client. The host keeps the 0.2.1 APWorld for that room's server and Universal Tracker. I played a 0.2.1 room on 0.2.2 through Steam on Windows and nothing from before replayed.
- **Replacing the client:** back up your client folder first, including settings and saves. Each platform archive has the client and the matching `ctr.apworld`.
- **Linux and Steam Deck:** use the Linux tarball; it needs glibc 2.36 or newer.

## Known issues and testing

I tested on Windows through Steam. On an early 0.2.2 build I raced for about twelve minutes to check the freeze fix: no freezes while racing, but the short pauses on screen changes are still there. On the first release candidate I played a room from 0.2.1 (no old traps replayed), checked Discord Status, played a Remove Playable Oxide room (Oxide still races and hitting him still sends his check), and won a Trophy race in a hub whose Key I already had, which correctly skipped the boss door. The case where the boss door scene plays once wasn't checked in game. On the release build I checked the title screen and raced once. Automated tests and both platform builds passed, and a full fuzz run on the exact `ctr.apworld` passed all ten checks with no failures or timeouts. Earlier 0.2.2 test builds ran on the Steam Deck, where I checked the Fullscreen fix and Flatten in the hub; the final Linux build passed its automated checks, but I didn't run it on the Deck.

- **Pauses on screen changes:** loading into the hub, the main menu or a restart can still pause the game for up to about a second. Low frame rate in Gem Stone Valley and the Cortex Castle area is still open too. See [#376](https://github.com/dowlle/ctr-native-ap/issues/376).
- **Reconnecting:** a large backlog of received items can stall the game for a while. If it happens, include the support bundle in your report. See [#147](https://github.com/dowlle/ctr-native-ap/issues/147).
- **Podiums:** some characters can appear invisible on the post-race podium. It's cosmetic. See [#282](https://github.com/dowlle/ctr-native-ap/issues/282).
- **Universal Tracker:** if a YAML in the room fills in `custom_tracks`, Universal Tracker may show a datapackage checksum warning. That's expected, and tracking still works normally.
- **Cortex Vortex relic times:** the targets are still placeholders using Oxide Station's times until the track author sends real ones.

## New options

- **Remove Playable Oxide:** `remove_playable_oxide` (Characters group, off by default, needs Character Unlocks) takes Nitros Oxide out of the racers you can unlock. His unlock item isn't created, so the pool gets one more filler or trap. Starting Character `random_any` never picks him and no warp pad is locked to him. He still races against you as the boss, and his Hit Character check stays. It can't be combined with Starting Character set to Nitros Oxide. With per-character Progressive Boost or Stats, Oxide's own upgrade items are still in the pool and do nothing. Thanks [Bethany81707](https://github.com/Bethany81707) for the idea ([#426](https://github.com/dowlle/ctr-native-ap/issues/426)). Oxide as an opponent was checked in Steam on Windows; the racer lock and start rules were checked on 200 generated seeds.
- **Relic Race Perfect Checks:** `relic_perfect_checks` (off by default) adds a check to each Relic Race for breaking every time crate. You get it whatever time you finish with and whether you already own the relic. A race lost to DeathLink doesn't send it. It's in logic with the Relic Race itself; N. Gin Labs also needs Ultimate Sacred Fire. Cortex Vortex has no Perfect check. Thanks [Argentum722](https://github.com/Argentum722) for the idea ([#49](https://github.com/dowlle/ctr-native-ap/issues/49)). A perfect run sent the check in a Steam Deck test session.
- **DeathLink race loss:** the new DeathLink value `race_loss` sends like `mask_reset`, when you fall off the track or get eaten. A death you receive ends your current race on the spot as a last-place loss, and nothing that race would have paid out is awarded. In a Gem Cup the cup carries on, and if that was the last race and you still win on points, the cup reward still pays. A death that arrives outside a race waits for your next one. Thanks [JustinMarshall98](https://github.com/JustinMarshall98) for the idea ([#286](https://github.com/dowlle/ctr-native-ap/issues/286)). Not tested in game yet; it needs a second DeathLink player.
- **Skip Cutscenes:** a new local option under Options > Gameplay (off by default). It skips the boss intro and outro scenes and the Oxide Final Challenge scene. Title intros, endings and credits play as before. Not confirmed in game yet.
- **Discord Status:** a new local option under Options > Archipelago (off by default). With Discord running on the same computer, your status shows the track and mode (like "Crash Cove, Trophy Race" or "Exploring N. Sanity Beach"), your check count while connected, and a race clock. It sends no room, slot or seed details. With the option off, nothing is started. Thanks [venusyprime](https://github.com/venusyprime) for the idea ([#366](https://github.com/dowlle/ctr-native-ap/issues/366)). Checked in Steam on Windows.

## Logic changes

- **Held 1st:** with Progressive Boost on, every Held 1st check now needs your first Progressive Boost, or one useful weapon (Mask, Missile, Bomb, Warpball or N. Tropy Clock) when Itemsanity is on. That's on every difficulty and every track. Held 1st on Cortex Castle and Hot Air Skyway also needs Ultimate Sacred Fire now, and Oxide Station keeps needing it unless Shortcut Knowledge is hard. This came from a player report: Held 1st on a bare kart took a lot of retries.
- **Easy and medium with Itemsanity off:** these used to add no boost requirement. Now winning a Trophy Race on the difficulty-gated tracks needs your first Progressive Boost, and on easy so do Finish on Podium and Held 1st. With Itemsanity on nothing changes. Thanks [MarioSpore](https://github.com/MarioSpore) ([#329](https://github.com/dowlle/ctr-native-ap/issues/329)).
- **Slide Coliseum and Turbo Track:** their Trophy Races were in logic with nothing at every difficulty. They now follow the same rule as the other Trophy Races.
- **Custom-track letters:** C, T and R letters on a custom track were in logic with no requirement. They now need the same as that track's CTR Token Challenge, like retail letters.
- **Option texts:** Logic Difficulty now says what "boost" means, names the useful weapons and lists every track that needs Ultimate Sacred Fire.
- **Generation log:** hosts get a shorter log. The two-stage fill check runs once per room, CTR warnings print once per slot, and options that change nothing are summed up on one line per player.

## Fixes and client changes

- **Freezes:** some players on 0.2.1 had the whole game freeze for about a second, mostly mid-race. The client now writes its state file and its log on a background thread, and writes a line to `ctr-ap.log` for any frame that takes too long. On my Windows PC I had no more freezes while racing. See the known issues for the pauses that remain.
- **Steam Deck Fullscreen:** turning on Fullscreen in Game Mode dropped the game to about 9 fps. The client now asks for fullscreen once instead of every frame. Checked on the Steam Deck with a 0.2.2 test build ([#260](https://github.com/dowlle/ctr-native-ap/issues/260)).
- **Boss door scene:** with enough Trophies received, the boss intro played after every Trophy win in a hub until you had that hub's Key. It now plays at most once per hub, and only while that boss garage is open and the boss race isn't won yet. Skip Cutscenes skips it too. Thanks [SoraKH13](https://github.com/SoraKH13) for the report ([#377](https://github.com/dowlle/ctr-native-ap/issues/377)). The hub whose Key I already held was checked in Steam on Windows; the scene playing once wasn't.
- **Oxide Final Challenge scene:** it played after every Relic Race podium once the relic gate was open. It now plays once per seed, and the item feed says "Oxide Final Challenge is open" once when you can take it on. Thanks [Bethany81707](https://github.com/Bethany81707) for narrowing it down to Relic Race podiums ([#377](https://github.com/dowlle/ctr-native-ap/issues/377)). Not confirmed in game yet.
- **Fresh rooms:** the client remembers which traps, Wumpa and Turbo Grants it already applied, because the server resends every item when you connect. That memory used to be a local file, so a fresh room of a seed you'd played before could skip them. It's now stored in the room, so a new room starts clean and a reconnect picks up where you were. The first time you connect a 0.2.1 room with 0.2.2, the old local record moves into the room once. Checked in Steam on Windows with a 0.2.1 room.
- **Traps:** a Mask (the weapon, or the rescue after falling off the track) used to drop a running trap, so queued Flattens could stop until the next track and one could get lost. Traps now wait out the Mask. Flatten also no longer fires in the hub; it waits for your next race. Thanks [BEXUS99](https://github.com/BEXUS99) ([#416](https://github.com/dowlle/ctr-native-ap/issues/416)). Flatten in the hub was checked on the Steam Deck; the Mask case wasn't checked in game.
- **Boost reserves bar:** with a lot of reserves stacked up, the bar turned red and drew past its edge. It now stays full, and turns purple while reserves are past that point, where they stop draining. Reserves themselves work as before. Thanks [MarioSpore](https://github.com/MarioSpore) ([#387](https://github.com/dowlle/ctr-native-ap/issues/387)). Not confirmed in game yet.
- **Title screen:** the ring behind Crash has the six Archipelago colours now, and ARCHIPELAGO shows under the CRASH TEAM RACING banner. Checked in Steam on Windows.
- **Seed check:** the `[AP VERIFY]` seed check in `ctr-ap.log` now covers Hit Character, Relic Race Perfect and the Slide Coliseum and Turbo Track checks. On 0.2.1 it said INDETERMINATE on every seed with Hit Character or trial races.

## Verifying your download

This is the first release with a signed manifest. `manifest.json` lists the SHA-256 of both client archives, and `manifest.json.minisig` is its signature, made with the release key (key ID `46F129D8BEF2D633`, public key `ctr-release-minisign.pub` in the repository).

To check it with [minisign](https://jedisct1.github.io/minisign/), download `manifest.json` and `manifest.json.minisig` next to each other and run:

    minisign -Vm manifest.json -P RWQz1vK+2CnxRlzUFiAM8FlyI706TxjELuc+8d4N9uh06nS1zAKGuD6x

It should say the signature is verified. Then compare the SHA-256 of your client archive with its line in `manifest.json`.

If you have Python 3 and minisign, you can also download every asset of the release into one folder and run `python3 tools/verify-release.py <folder> --version v0.2.2` from the source at the `v0.2.2` tag. It prints `verified signed release v0.2.2` when everything matches.

## Credits

Discord Status shows the Archipelago logo, which is by Krista Corkos and Christopher Wilson, CC BY-NC 4.0. Thanks to [SoraKH13](https://github.com/SoraKH13), [Bethany81707](https://github.com/Bethany81707), [MarioSpore](https://github.com/MarioSpore), [BEXUS99](https://github.com/BEXUS99), [Argentum722](https://github.com/Argentum722), [JustinMarshall98](https://github.com/JustinMarshall98) and [venusyprime](https://github.com/venusyprime) for the reports and ideas in this release, and to everyone who sent feedback on 0.2.1.

## Reporting a problem

[Open a GitHub issue](https://github.com/dowlle/ctr-native-ap/issues/new/choose) with your platform, client version, seed or YAML, what happened and the support bundle. Run `support-bundle.bat` on Windows or `support-bundle.sh` on Linux and look through the bundle before attaching it; it doesn't upload anything by itself.

Questions are welcome in the [Crash Team Racing channel](https://discord.com/channels/731205301247803413/1222304293751750777) on the Archipelago Discord. The [GitHub release](https://github.com/dowlle/ctr-native-ap/releases/tag/v0.2.2) has the downloads, checksums, the signed manifest and debug files.

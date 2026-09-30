**CTR Archipelago 0.2.3 reworks DeathLink, fixes the crash when a DeathLink arrived with the `race_loss` setting, and adds a DeathLink Send option so you choose what sends a death. It also fixes the Relic Race closing before its Perfect check, the low frame rate in the hubs, and makes warp pads show every open location.**

**[Download 0.2.3](/ctr/download)** · **[Setup guide](/ctr/setup)** · **[Build a 0.2.3 YAML](/yaml-builder/ctr?version=0.2.3)**

## At a glance

- DeathLink is reworked. A death you receive applies only during a live race and is never saved for later. Every received death shows a popup with who died and the cause.
- Fixed a crash when a DeathLink arrived with `death_link: race_loss`.
- New YAML option `death_link_send` chooses what makes you send a death: falling off or getting eaten, getting hit by a weapon, or losing a race. Your old YAML keeps working.
- `race_loss` now goes both ways: losing a race sends a death, and a death you receive costs you the race.
- There is no send-only DeathLink. Anything that sends also receives.
- Three new rows on Options > Archipelago set the send conditions in game.
- Fixed the Relic Race closing before you could take its Perfect check, and the warp pad now shows the item at the Perfect.
- Much lower cost of the warp pads in the hubs, which was the cause of the low frame rate in Gem Stone Valley.
- Warp pads now show the item of every open location behind them: item boxes, CTR letters and Wumpa too.
- Relic Race Perfect checks need Ultimate Sacred Fire on every track, Held 1st has no boost floor on hard, and Slide Coliseum and Turbo Track relics are gated like the other tracks.

## Where should I start?

- **Joining a room?** Get the client from the [download page](/ctr/download) and follow the [CTR setup guide](/ctr/setup). You need your own NTSC-U disc image.
- **Preparing a YAML?** Use the [0.2.3 YAML Builder](/yaml-builder/ctr?version=0.2.3) and send the YAML to your host. The [YAML guide](/guides/setting-up-your-yaml) explains the file.
- **Hosting?** Install the matching `ctr.apworld` and follow the [hosting guide](/guides/hosting-a-multiworld). Archipelago 0.6.7 or newer is needed. `Crash.Team.Racing.yaml` on the GitHub release is the template for this version.

## Compatibility and upgrading

- **New games:** use the 0.2.3 client with the 0.2.3 APWorld and YAML.
- **Ongoing 0.2.2 rooms:** you can keep playing a 0.2.2 room on the 0.2.3 client. A room without the new `death_link_send` setting sends what it did before (see below). The host keeps the 0.2.2 APWorld for that room's server and Universal Tracker.
- **Replacing the client:** back up your client folder first, including settings and saves. Each platform archive has the client and the matching `ctr.apworld`.
- **Linux and Steam Deck:** use the Linux tarball; it needs glibc 2.36 or newer.

## Known issues and testing

I tested on Windows through Steam. On the 0.2.3 test build I checked check sending, item receiving and reconnecting, DeathLink receive (a death in the middle of a race with the popup, a death in the hub being dropped, a death during a pause landing when the race runs again), DeathLink send (one death on a lost race, on restart and on exit to the map, none on a fall when only `race_loss` sends, and no echo of a received death), the Relic Race retry after a DeathLink, the Relic Race Perfect pad fix, the warp pad glow with boxes, letters and Wumpa, the frame rate in Gem Stone Valley and the Cortex Castle area, and the short letter names. Automated tests and both platform builds passed, and a full fuzz run on the exact `ctr.apworld` passed all ten checks with no failures or timeouts. I did not test with a second real DeathLink player (a scripted sender stood in), the tracker's boss garage colours, Oxide and Cortex Vortex races or custom tracks, and I did not run this version on the Steam Deck.

- **Pauses on screen changes:** loading into the hub, the main menu or a restart can still pause the game for up to about a second.
- **Reconnecting:** a large backlog of received items can stall the game for a while. If it happens, include the support bundle in your report. See [#147](https://github.com/dowlle/ctr-native-ap/issues/147).
- **Podiums:** some characters can appear invisible on the post-race podium. It's cosmetic. See [#282](https://github.com/dowlle/ctr-native-ap/issues/282).
- **Universal Tracker:** if a YAML in the room fills in `custom_tracks`, Universal Tracker may show a datapackage checksum warning. That's expected, and tracking still works normally.
- **Cortex Vortex relic times:** the targets are still placeholders using Oxide Station's times until the track author sends real ones.
- **Custom-track letters:** in the item feed they keep their full item name, because the seed has no display title for a custom slot.
- **Long pad cycles:** a cup pad with many open locations cycles through its items one after another, which can take about a minute for one pass.

## DeathLink rework

DeathLink in 0.2.3 follows four rules.

- **Never queued.** A death you receive applies only while you are in a live race: on a track, after the lights go out, not paused, not in a menu, cutscene or loading screen, not at the end of the race. Anywhere else it is dropped. In 0.2.2 a death that arrived outside a race waited for your next race; that is gone. It applies to every DeathLink mode.
- **Pausing does not dodge it.** A death that arrives while the race is paused applies when the race runs again. If you restart, exit to the map or quit from the pause menu first, it is dropped. A death that cannot land at that moment (for example right after a mask reset) is tried again for a few frames and then dropped.
- **Every death shows a popup.** It names who died and the cause, and it shows on the results screen and the cup standings too, so you see it after a `race_loss` ends your race at once. A dropped death shows `DEATHLINK IGNORED` and `<name>: NOT IN A RACE`.
- **Receiving and sending are set apart.** `death_link` sets what a received death does to you. The new `death_link_send` sets what makes you send one.

### What a received death does (`death_link`)

- `off`: DeathLink is disabled, nothing is sent or received.
- `mask_reset`: a received death forces the full mask reset on you.
- `race_loss`: a received death ends your current race on the spot as a last-place loss, and nothing that race would have paid out is awarded. In a Gem Cup the cup carries on, and if that was the last race and you still win on points, the cup reward still pays. In a Crystal Challenge it ends as TRY AGAIN and no token check is sent. In a Relic Race the run fails (no relic, no Perfect check, no high score, no ghost) and you get the normal RETRY or EXIT TO MAP menu; Retry starts a fresh run.
- `any_hit`: an old value, kept so older YAML files still load. It receives like `mask_reset`.

### What makes you send a death (`death_link_send`)

- `mask_grab`: falling off the track or being eaten.
- `weapon_hit`: getting hit by a weapon.
- `race_loss`: losing a race, losing the whole Gem Cup (never a single lost leg of a cup), or choosing RESTART or EXIT TO MAP from the pause menu during a race. Losing means a Trophy Race, boss race or CTR Challenge finished outside 1st, or a Crystal Challenge with crystals missing. A Relic Race has no fail state in the normal game, so its end does not send.

A loss that was forced on you by a received death never sends one back: not its results screen, not the retry, not a restart or exit right after it, and not any fall or hit it causes.

If you leave `death_link_send` out of your YAML, nothing changes from before. `mask_reset` sends on mask grabs, `any_hit` on mask grabs and weapon hits, and `race_loss` on mask grabs and race losses. Once you write the option, your list replaces that, so list every trigger you want.

### No send-only DeathLink

A slot that sends deaths also receives them. If you list a trigger in `death_link_send` while `death_link` is `off`, DeathLink is switched on as `mask_reset` (the mildest receive effect) and generation prints a notice. Receive-only is allowed: use an empty list.

### YAML examples

Keep it as it was before (mask grabs send, a received death resets your mask):

```yaml
Crash Team Racing:
  death_link: mask_reset
```

Send only when you lose a race, and a received death costs you the race:

```yaml
Crash Team Racing:
  death_link: race_loss
  death_link_send:
    - race_loss
```

Send on every kind of death, receive as a mask reset:

```yaml
Crash Team Racing:
  death_link: mask_reset
  death_link_send:
    - mask_grab
    - weapon_hit
    - race_loss
```

Receive only, never send:

```yaml
Crash Team Racing:
  death_link: mask_reset
  death_link_send: []
```

Send-only is not possible. This turns DeathLink on as `mask_reset`:

```yaml
Crash Team Racing:
  death_link: off
  death_link_send:
    - race_loss
```

### In game

Options > Archipelago has the DeathLink row and three new rows, `DL SEND FALL`, `DL SEND HIT` and `DL SEND LOSS`. Each of the three is SEED, OFF or ON: SEED follows your YAML, and OFF or ON overrides that trigger. They change live, like the DeathLink row. The DeathLink row now also has the RACE LOSS value, so every tier can be picked in game. Set to OFF it is fully off, with no DeathLink tag and no sends. Forcing the DeathLink row to a value brings the send defaults that value always had.

## Logic changes

These only matter with Progressive Boost on.

- **Relic Race Perfect:** every Relic Race Perfect check now needs Ultimate Sacred Fire (two Progressive Boosts) on every logic difficulty. In 0.2.2 only N. Gin Labs did. A player on hard logic had Blizzard Bluff's Perfect in logic with no boost, but one time crate in the lake shortcut needs a boost.
- **Held 1st on hard:** at hard logic difficulty Held 1st has no boost floor any more. On hard the Trophy Race win has no boost requirement, so a seed could have the win in logic but not Held 1st, although winning means you held 1st. Easy and medium keep the floor. The track rules for Hot Air Skyway, Cortex Castle and Oxide Station are unchanged.
- **Slide Coliseum and Turbo Track relics:** if one of these has no Trophy Race in your seed, its Gold and Platinum relics now need the same boost as on other tracks (Sapphire stays free). Before, they needed nothing.
- Nothing about location names, IDs or what a slot sends changed for these.

## Fixes and client changes

- **DeathLink crash:** a DeathLink arriving with `death_link: race_loss` could crash the game in Trophy and boss races when the results screen appeared. A forced loss now ends the race the way a normal last-place finish does. It was reported on Discord.
- **Relic Race closing early:** with Relic Race Perfect checks on, the warp pad closed once you had won the Platinum without a Perfect, which locked the Perfect check away. The pad now keeps offering the Relic Race while the Perfect is open, and shows the item placed at the Perfect. Thanks [BEXUS99](https://github.com/BEXUS99) for the report ([#439](https://github.com/dowlle/ctr-native-ap/issues/439)). Checked in Steam on Windows.
- **Hub frame rate:** the hub warp pads asked the Archipelago layer about every box, letter and relic location every frame, and each question copied the whole list of checked and missing locations. The bigger the seed, the slower it got, and Gem Stone Valley has the most pads. The client now keeps one copy and only refreshes it when something changes. On a Linux test client the pad cost in Gem Stone Valley went from about 3.9 ms to 0.11 ms a frame for a seed with 147 locations, and from 13.8 ms to 0.13 ms for 480. The frame rate in Gem Stone Valley and the Cortex Castle area was checked in Steam on Windows. See [#376](https://github.com/dowlle/ctr-native-ap/issues/376) for what remains. 
- **Warp pad glow:** a pad now shows the item of every open location behind it. Item boxes, CTR letters and per-track Wumpa were counted for the pad state but left out of the glow before. With `one_pile` everything shares the three slots and cycles three at a time. With `by_reward_type` Wumpa and item boxes go in the race slot and CTR letters in the token slot. The pad state itself (open, closed, done) is unchanged. Checked in Steam on Windows.
- **Item feed names:** letters for Slide Coliseum, Turbo Track and Cortex Vortex now use the short name, like `C: SLIDE COLISEUM`, `T: TURBO TRACK` and `R: CORTEX VORTEX`, the same as retail track letters. Custom-track letters keep their full name.
- **Tracker boss garages:** in the in-game tracker's hub map every boss garage node was green whether or not it was open. A node is now gold when its boss check is done, green when the garage is open, and red when it is locked.

## Verifying your download

`manifest.json` lists the SHA-256 of both client archives, and `manifest.json.minisig` is its signature, made with the release key (key ID `46F129D8BEF2D633`, public key `ctr-release-minisign.pub` in the repository).

To check it with [minisign](https://jedisct1.github.io/minisign/), download `manifest.json` and `manifest.json.minisig` next to each other and run:

```
minisign -Vm manifest.json -P RWQz1vK+2CnxRlzUFiAM8FlyI706TxjELuc+8d4N9uh06nS1zAKGuD6x
```

It should say the signature is verified. Then compare the SHA-256 of your client archive with its line in `manifest.json`.

If you have Python 3 and minisign, you can also download every asset of the release into one folder and run `python3 tools/verify-release.py <folder> --version v0.2.3` from the source at the `v0.2.3` tag. It prints `verified signed release v0.2.3` when everything matches.

## Credits

Thanks to [venusyprime](https://github.com/venusyprime) for the more accurate Tizi Helper description, [BEXUS99](https://github.com/BEXUS99) for the Relic Race report, and to everyone who sent feedback on 0.2.2, including the DeathLink crash report on Discord.

## Reporting a problem

[Open a GitHub issue](https://github.com/dowlle/ctr-native-ap/issues/new/choose) with your platform, client version, seed or YAML, what happened and the support bundle. Run `support-bundle.bat` on Windows or `support-bundle.sh` on Linux and look through the bundle before attaching it; it doesn't upload anything by itself.

Questions are welcome in the [Crash Team Racing channel](https://discord.com/channels/731205301247803413/1222304293751750777) on the Archipelago Discord. The [GitHub release](https://github.com/dowlle/ctr-native-ap/releases/tag/v0.2.3) has the downloads, checksums, the signed manifest and debug files.

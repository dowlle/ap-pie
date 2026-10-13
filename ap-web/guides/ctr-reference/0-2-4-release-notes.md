**0.2.4 makes big rooms generate a lot faster and refuses far fewer YAMLs. Race-loss DeathLink now checks whether the race still matters to you. The Slide Coliseum and Turbo Track pads also won't trap you after a Collect, plus a few more fixes.**

**[Download 0.2.4](/ctr/download)** · **[Setup guide](/ctr/setup)** · **[Build a 0.2.4 YAML](/yaml-builder/ctr?version=0.2.4)**

## What's new

- Big rooms generate much faster.
- Far fewer YAMLs get refused. In our tests, every YAML that worked on 0.2.3 still works.
- Race-loss DeathLink only sends when the race still mattered for you.
- The Slide Coliseum and Turbo Track pads no longer trap you after a Collect.
- Bosses only count when you beat them yourself.
- Itemsanity can't get stuck on a weapon you have no race left for.
- If a seed has fewer than 10 Sapphire Relics, the Slide Coliseum pad opens at the number it has.
- No more BIN prompt on every launch when you use extracted assets.
- L2 no longer breaks the Demo Camera trap.

## Getting started

- **Playing:** grab the client from the [download page](/ctr/download) and follow the [setup guide](/ctr/setup). You need your own NTSC-U disc image.
- **Making a YAML:** use the [0.2.4 YAML Builder](/yaml-builder/ctr?version=0.2.4). There are no new options, so your 0.2.3 YAML works as is.
- **Hosting:** install the matching `ctr.apworld` and follow the [hosting guide](/guides/hosting-a-multiworld). You need Archipelago 0.6.7 or newer, and 0.6.8 works too. `Crash.Team.Racing.yaml` on the GitHub release is the template for this version.

## Upgrading

- For new games, use the 0.2.4 client and the 0.2.4 APWorld together.
- You can keep playing a 0.2.3 room on the 0.2.4 client. DeathLink works the old way there, and bosses you already beat stay beaten. The host keeps the 0.2.3 APWorld for that room.
- Back up your client folder before replacing it, settings and saves included.
- On Linux and Steam Deck, use the Linux tarball. It needs glibc 2.36 or newer.

## Generation

We fixed two things that slowed down big rooms. Placement didn't change: the same seed gives the same result.

- The APWorld used to fill the whole room once as a practice run before placing items. That doubled the work and never changed anything, so it's gone. A 100-player test room went from about 7 minutes to under 4.
- Checking whether a racer was locked behind itself got slower as rooms grew. It now runs once per room. On a 1,000-player test room that went from about an hour to under 3 seconds.
- The check now covers racer unlocks shared through item links, so a racer can't be locked behind itself.

Fewer YAMLs get refused. In our random tests about 4 in 10 got refused, down from almost 8 in 10 on 0.2.3. What changed:

- **Not enough locations:** a seed is refused only when it doesn't have enough locations for its required items. The error shows how many it needs and has. No options get turned on automatically.
- **Final Challenge:** if `oxide_final_challenge_relic_count` asks for more relics than the seed has, it's lowered with a notice instead of refusing the seed.
- **Slide Coliseum:** with vanilla warp pads and fewer than 10 Sapphire Relics, the pad opens at the Sapphires that exist. The pad shows that number, and Aku Aku only mentions 10 relics when it's really 10.
- **Narrow starts:** a slot with fewer than 2 starting checks is refused with a message that explains why. We don't hand out items to fix it.
- **Early items:** no early Keys with vanilla warp pads, and Itemsanity asks for one early weapon instead of up to two, so early items can't use up every starting check.

## Race-loss DeathLink

In 0.2.3, `race_loss` sent a death whenever you lost a race or Gem Cup, or used RESTART or EXIT TO MAP. Now it only sends one if you haven't collected that race's win and the race is in logic for you. Losing a race you already won sends nothing. Neither does losing a race you aren't expected to win yet.

- **A race's win** means its main check: the Trophy Race, the CTR Token Challenge, the boss race, the Gem Cup gem, or the Crystal Challenge token. For a Relic Race, any open relic counts; Perfect doesn't.
- A check also counts as **collected** if someone marked it for you with `!collect`, `!release` or co-op.
- **In logic** means the same as in Universal Tracker. Bosses only count when you beat them yourself.
- **It's decided when the race starts.** An item you get mid-race won't change the DeathLink check until your next attempt. For a Gem Cup, it's decided at the first race.
- **Still the same:** a received death won't send one back. Losing one Gem Cup race won't send one either. Falls and weapon hits still send as before.
- **Old seeds:** a room made before 0.2.4 keeps the old rule on the new client, and an older client keeps the old rule in a 0.2.4 room. There's no option to get the old rule in a new seed.

## Fixes

- **Trial pads stuck after a Collect:** a Collect could check the Slide Coliseum or Turbo Track CTR Challenge while you still needed letters, and then the pad spun you in the warp forever. Now it keeps offering the CTR Challenge as long as the challenge or a letter is open, like every other track. If a pad ever has nothing left to offer, it lets you go instead of holding you. Reported on Discord.
- **More pad fixes:** a trial track behind a shuffled pad now respects that pad's second requirement, and custom track pads stay open for their CTR Challenge and letters. If the trial letters can't be loaded from your disc, the item feed tells you once.
- **Bosses:** a boss now only counts when you won its race yourself. Before, a Collect or `!release` could finish a Bosses goal or open the Oxide garage without a single boss raced. It also fixes an any_percent softlock: someone else's Collect could make the garage offer the Final Challenge, but that challenge doesn't finish any_percent. Wins you got while disconnected are kept and sent when you reconnect. Thanks [Bethany81707](https://github.com/Bethany81707) for the idea ([#458](https://github.com/dowlle/ctr-native-ap/issues/458)).
- **Itemsanity:** a weapon you got after finishing every open pad had nowhere to be fired, so its check could stall the seed. Finished pads now stay open as a normal race while you have a weapon with an open check. Thanks [BEXUS99](https://github.com/BEXUS99) for the report ([#452](https://github.com/dowlle/ctr-native-ap/issues/452)).
- **BIN prompt:** if you extracted your assets with `extract_assets.py` (from a CHD, for example) and had no `.bin`, the game asked for one on every launch. Now it doesn't. A `.bin` in the folder is still used first. Thanks [venusyprime](https://github.com/venusyprime) for the report ([#444](https://github.com/dowlle/ctr-native-ap/issues/444)).
- **Demo Camera trap:** pressing L2 during the trap switched back to the normal camera. L2 now does nothing while the trap is on and works normally after. Thanks [BEXUS99](https://github.com/BEXUS99) for the report ([#454](https://github.com/dowlle/ctr-native-ap/issues/454)).

## What I tested

I tried the trial pad fix on Windows. After a Collect, both pads offer the CTR Challenge again, the letters send, finishing the challenge doesn't send anything twice, and the pads go gray when everything's done. The automated tests, both builds and a full fuzz run passed, and the client connects fine to an Archipelago 0.6.8 server. I haven't played the new DeathLink rule, the boss changes, the itemsanity pads, the Slide Coliseum gate, the BIN prompt fix or the Demo Camera fix myself yet. If something's off, please let me know.

## Known issues

- **Mixed accessibility:** a CTR slot with full accessibility next to a slot with `accessibility: minimal` can fail to generate on some seeds. Generating again fixes it.
- **Short pauses:** loading into the hub, the main menu or a restart can still freeze the game for up to a second.
- **Reconnecting:** a big pile of received items can stall the game for a while. If that happens, please include the support bundle in your report ([#147](https://github.com/dowlle/ctr-native-ap/issues/147)).
- **Podium:** some characters can be invisible on the podium after a race. It's only cosmetic ([#282](https://github.com/dowlle/ctr-native-ap/issues/282)).
- **Universal Tracker:** if a YAML in the room uses `custom_tracks`, Universal Tracker may warn about a datapackage checksum. You can ignore it; tracking still works.
- **Cortex Vortex:** the relic times are placeholders copied from Oxide Station until the track author sends real ones.
- **Custom-track letters:** they show their full item name in the item feed.
- **Long pad cycles:** a pad with lots of open locations shows its items one at a time, so one round can take about a minute.

## Verifying your download

`manifest.json` lists the SHA-256 of both client archives, and `manifest.json.minisig` is its signature with the release key (key ID `46F129D8BEF2D633`, public key `ctr-release-minisign.pub` in the repository).

To check it with [minisign](https://jedisct1.github.io/minisign/), put `manifest.json` and `manifest.json.minisig` in the same folder and run:

```
minisign -Vm manifest.json -P RWQz1vK+2CnxRlzUFiAM8FlyI706TxjELuc+8d4N9uh06nS1zAKGuD6x
```

It should say the signature is verified. Then compare the SHA-256 of your client archive with its line in `manifest.json`.

With Python 3 and minisign you can also download every asset of the release into one folder and run `python3 tools/verify-release.py <folder> --version v0.2.4` from the source at the `v0.2.4` tag. It prints `verified signed release v0.2.4` when everything matches.

## Thanks

Thanks to [venusyprime](https://github.com/venusyprime) for the BIN prompt report, [BEXUS99](https://github.com/BEXUS99) for the itemsanity and Demo Camera reports, [Bethany81707](https://github.com/Bethany81707) for the boss goal idea, and everyone on Discord who sent DeathLink feedback and the trial pad report.

## Found a problem?

[Open a GitHub issue](https://github.com/dowlle/ctr-native-ap/issues/new/choose) with your platform, client version, seed or YAML, what happened, and the support bundle. Run `support-bundle.bat` on Windows or `support-bundle.sh` on Linux, and look through the bundle before you attach it. It doesn't upload anything by itself.

Questions are welcome in the [Crash Team Racing channel](https://discord.com/channels/731205301247803413/1222304293751750777) on the Archipelago Discord. The [GitHub release](https://github.com/dowlle/ctr-native-ap/releases/tag/v0.2.4) has the downloads, checksums, the signed manifest and debug files.

The generation badge on an APWorld card describes the displayed release's recorded tests. Hover over it or focus it with the keyboard for an explanation. Click or tap it for details; press Escape to dismiss a tooltip.

The fuzzer repeatedly tries to generate an Archipelago world with randomized settings and seeds. This helps find combinations that a normal test with one player's YAML might miss. Additional checks look for specific problems in the generation code.

## What do the catalog badges mean?

- **Tests pending.** No generation result is recorded for this release yet. This does not mean it passed or that a test is currently running.
- **Generation passed.** The recorded randomized checks have a clean verdict and zero reported failures in both the generation rate and highest check rate. This is a result from a test sample, not a guarantee that every configuration works.
- **Generation warnings.** The recorded verdict is flaky or broken, or at least one displayed failure rate is above zero. Inspect the badge for the warning and open the details before planning your session.

The warning explanation appears in the tooltip rather than as an extra sentence on the card. Cards with recorded results also show the test date.

The separate **Review pending** badge means no release-specific security review is published in the catalog yet. It is not a security clearance. Existing YAML Builder availability is separate from these badges.

## What do clean, flaky and broken mean in the details?

- **Green: clean.** Low failure rates in the recorded checks. This can include some failures. Test your actual settings before your session.
- **Amber: flaky.** The checks found reliability problems. Check known issues and allow time to investigate generation failures.
- **Red: broken.** The checks found substantial generation problems. Review the result and version carefully before planning a session around it.

These raw verdicts belong to a particular APWorld version. A result for an older release does not describe every newer release. The overview shows Tests pending when a result is missing; compact version dots elsewhere may be absent instead. Neither is a pass.

The overview's Generation warnings badge can therefore include a raw clean verdict with nonzero failures. Raw broken results remain warnings on the overview: randomized failures alone do not establish that standard settings cannot generate.

## What does the fuzzer try?

The standard randomized run varies game options and seeds, then attempts generation. In the test results this run is named `default`. That name describes the standard fuzz check: it does **not** mean that every attempt uses the game's default option values.

Other checks target particular behaviours, such as item and location counts, placement references, accessibility, and whether repeating generation produces consistent output. A separate run relaxes restrictive starting settings. Each check answers a different question, so a failure in one check should be read in its own context.

The pipeline also has a separate generation check using canonical default settings for the exact APWorld archive. That distinction matters: even if all attempts in a randomized run fail, it does not prove that the APWorld can never generate. A raw **broken** result can coexist with successful default-settings generation. The current catalog badges do not publish that separate canonical result, so Generation passed does not establish successful standard generation.

## How to read the numbers

The modal shows the randomized generation failure rate, the highest recorded check failure rate and its check name, the recorded seed count, and the test date.

Use **Open GitHub report** to inspect the published report when an exact-result link is available. **View recorded result on GitHub** opens the index record at the revision AP-Pie is serving. Some historical records do not retain the original report URL; the details say so rather than linking to an unrelated run.

For example, a 2% failure rate means two out of every hundred counted attempts failed in that particular sample. It does not mean your YAML has a 2% chance of failing. Your settings, APWorld version, Archipelago version and the other worlds in your group can differ from the test environment.

The highest check rate may come from a targeted check rather than ordinary generation. Read its name alongside the percentage. The displayed seed count is recorded metadata; it should not be assumed to be the number of attempts completed by every check.

## Does a green badge mean the APWorld is safe?

Fuzz testing measures generation behaviour. Security review is a separate process that looks for malicious or unsafe code. Neither a green badge nor successful generation certifies that an APWorld is safe.

Generation tests also do not play the game from start to finish. They cannot guarantee that the client connects correctly, every location works in game, or every combination of players' worlds is compatible. A working YAML Builder is another separate check: being able to export settings does not prove that those settings will generate or play correctly.

## Before your group starts

1. Check the exact APWorld version your host plans to use and read its setup guide.
2. Look at the badge's recorded rates, check name and test date.
3. Have the host test the group's actual YAMLs together in their generation environment before the session.
4. If generation fails, keep the error log and check the APWorld's known issues. Include the version and relevant settings when reporting a reproducible problem, removing private information before sharing logs or YAMLs.

AP-Pie displays the result so you can make an informed choice. The badge itself does not block you from choosing that version.

Browse the [APWorld catalog](/apworlds), or read about [hosting an Archipelago multiworld](/guides/hosting-a-multiworld).

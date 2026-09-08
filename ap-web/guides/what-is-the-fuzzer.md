The coloured dot beside an APWorld version tells you how that version performed in automated generation tests. Click it to see the recorded result and what it means.

The fuzzer repeatedly tries to generate an Archipelago world with randomized settings and seeds. This helps find combinations that a normal test with one player's YAML might miss. Additional checks look for specific problems in the generation code.

## What do clean, flaky and broken mean?

- **Green: clean.** Low failure rates in the recorded checks. This can include some failures. Test your actual settings before your session.
- **Amber: flaky.** The checks found reliability problems. Check known issues and allow time to investigate generation failures.
- **Red: broken.** The checks found substantial generation problems. Review the result and version carefully before planning a session around it.

These labels belong to a particular APWorld version. A result for an older release does not describe every newer release. If a version has no badge, AP-Pie has no recorded fuzz result to display for it. Absence is not a pass.

The green result is called **clean** in the catalog. It is not a guarantee that every test passed or that every possible configuration works.

## What does the fuzzer try?

The standard randomized run varies game options and seeds, then attempts generation. In the test results this run is named `default`. That name describes the standard fuzz check: it does **not** mean that every attempt uses the game's default option values.

Other checks target particular behaviours, such as item and location counts, placement references, accessibility, and whether repeating generation produces consistent output. A separate run relaxes restrictive starting settings. Each check answers a different question, so a failure in one check should be read in its own context.

The pipeline also has a separate generation check using canonical default settings for the exact APWorld archive. That distinction matters: even if all attempts in a randomized run fail, it does not prove that the APWorld can never generate. A **broken** badge can coexist with a successful default-settings generation.

## How to read the numbers

The modal shows the randomized generation failure rate, the highest recorded check failure rate and its check name, the recorded seed count, and the test date.

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

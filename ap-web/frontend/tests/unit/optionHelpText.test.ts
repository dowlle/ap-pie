// Unit tests for the YAML Builder option help normalisation.
// Run with `npm run test:unit` (Node's built-in test runner, no browser).
import { test } from "node:test";
import assert from "node:assert/strict";
import { normalizeOptionHelp } from "../../src/lib/optionHelpText.ts";

const doc = (lines: string[]) => lines.join("\n");

test("leaves an already single-line description unchanged", () => {
  const text = "Enable DeathLink: when you die, everyone dies.";
  assert.equal(normalizeOptionHelp(text), text);
});

test("returns an empty string for missing help", () => {
  assert.equal(normalizeOptionHelp(undefined), "");
  assert.equal(normalizeOptionHelp(null), "");
  assert.equal(normalizeOptionHelp(""), "");
});

test("joins hard-wrapped paragraphs and keeps blank-line paragraph breaks (CTR Custom Tracks)", () => {
  const text = doc([
    "Play a community custom track in place of a Gem Cup.",
    "",
    "Fill it in and the Gem Cup you name stops running its four retail tracks.",
    "Its warp pad still asks for the same four CTR Tokens and it still awards",
    "the same Gem, but behind the pad is a single race on the custom track, and",
    "winning that race is what awards the Gem.",
    "",
    "This option is a mapping, so the Archipelago website's options pages",
    "cannot show it and a YAML exported from there will not contain it.",
  ]);
  assert.equal(
    normalizeOptionHelp(text),
    doc([
      "Play a community custom track in place of a Gem Cup.",
      "",
      "Fill it in and the Gem Cup you name stops running its four retail tracks. Its warp pad still asks for the same four CTR Tokens and it still awards the same Gem, but behind the pad is a single race on the custom track, and winning that race is what awards the Gem.",
      "",
      "This option is a mapping, so the Archipelago website's options pages cannot show it and a YAML exported from there will not contain it.",
    ]),
  );
});

test("keeps list items and joins their wrapped continuation lines (CTR Logic Difficulty)", () => {
  const text = doc([
    "How much the logic expects you to be able to do.",
    "",
    "It only applies while both Progressive Boost and Itemsanity are",
    "randomizing your capabilities.",
    "",
    "- **easy**: winning a race, finishing on the podium and holding first",
    "  all wait until you have boost or a couple of decent weapons.",
    "- **medium** (default): only winning the race waits. Placement checks",
    "  stay available.",
    "- **hard**: no extra requirement; you are expected to manage.",
    "",
    "Tracks whose geometry genuinely demands speed ignore this setting.",
    "Cortex Castle and Hot Air Skyway always need USF, and so does Oxide",
    "Station unless Shortcut Knowledge is set to hard.",
  ]);
  assert.equal(
    normalizeOptionHelp(text),
    doc([
      "How much the logic expects you to be able to do.",
      "",
      "It only applies while both Progressive Boost and Itemsanity are randomizing your capabilities.",
      "",
      "- **easy**: winning a race, finishing on the podium and holding first all wait until you have boost or a couple of decent weapons.",
      "- **medium** (default): only winning the race waits. Placement checks stay available.",
      "- **hard**: no extra requirement; you are expected to manage.",
      "",
      "Tracks whose geometry genuinely demands speed ignore this setting. Cortex Castle and Hot Air Skyway always need USF, and so does Oxide Station unless Shortcut Knowledge is set to hard.",
    ]),
  );
});

test("keeps numbered list items on their own lines", () => {
  const text = doc([
    "Pick the order the bosses appear in:",
    "1. vanilla keeps the retail order of the four bosses in the adventure",
    "   hub, the way the original game plays it.",
    "2) shuffled randomizes the order.",
  ]);
  assert.equal(
    normalizeOptionHelp(text),
    doc([
      "Pick the order the bosses appear in:",
      "1. vanilla keeps the retail order of the four bosses in the adventure hub, the way the original game plays it.",
      "2) shuffled randomizes the order.",
    ]),
  );
});

test("turns a reST :: example into a fenced code block (CTR Trap Weights)", () => {
  const text = doc([
    "Example - never pick first person, pick icy road twice as often as usual,",
    "everything else default::",
    "",
    "    trap_fill_percentage: 10",
    "    trap_weights:",
    "      first_person: 0",
    "      icy_road: 10",
    "",
    "Setting every trap to 0 while `Trap Fill Percentage` is above 0",
    "is an error.",
  ]);
  assert.equal(
    normalizeOptionHelp(text),
    doc([
      "Example - never pick first person, pick icy road twice as often as usual, everything else default:",
      "",
      "```",
      "trap_fill_percentage: 10",
      "trap_weights:",
      "  first_person: 0",
      "  icy_road: 10",
      "```",
      "",
      "Setting every trap to 0 while `Trap Fill Percentage` is above 0 is an error.",
    ]),
  );
});

test("drops a lone :: marker and keeps blank lines inside the example", () => {
  const text = doc([
    "Examples",
    "::",
    "",
    "    # Enable all",
    "    allowed_chapters: [\"All\"]",
    "",
    "    # Enable only vehicle levels",
    "    allowed_chapters:",
    "      - 1-4",
  ]);
  assert.equal(
    normalizeOptionHelp(text),
    doc([
      "Examples",
      "",
      "```",
      "# Enable all",
      "allowed_chapters: [\"All\"]",
      "",
      "# Enable only vehicle levels",
      "allowed_chapters:",
      "  - 1-4",
      "```",
    ]),
  );
});

test("fences an indented block after an Example: line (CTR Requirement Weights, Pokepelago Regions)", () => {
  assert.equal(
    normalizeOptionHelp(doc([
      "Example:",
      "",
      "    requirement_variety: custom",
      "    requirement_weights:",
      "      Trophy: 30",
    ])),
    doc(["Example:", "", "```", "requirement_variety: custom", "requirement_weights:", "  Trophy: 30", "```"]),
  );
  assert.equal(
    normalizeOptionHelp(doc([
      "Provide a YAML list of region names, for example:",
      "    regions:",
      "      - Kanto",
      "(Inline form also works: regions: [Kanto, Johto, Hoenn].)",
    ])),
    doc([
      "Provide a YAML list of region names, for example:",
      "",
      "```",
      "regions:",
      "  - Kanto",
      "```",
      "",
      "(Inline form also works: regions: [Kanto, Johto, Hoenn].)",
    ]),
  );
});

test("uses a longer fence when the example itself contains backticks", () => {
  const out = normalizeOptionHelp(doc(["Example::", "", "    ```", "    nested", "    ```"]));
  assert.equal(out, doc(["Example:", "", "````", "```", "nested", "```", "````"]));
});

test("keeps Label: value lines apart and joins their wrapped continuations", () => {
  const text = doc([
    "Determines which Relics of Chaos are added to the item pool, but are not guaranteed",
    "None: No Relics of Chaos will be included in the item pool at all, whatever",
    "the other settings say.",
    "Some: At least 5 Relics of Chaos will be included in the item pool",
    "**All:** Every Relic of Chaos will be included in the item pool.",
    "open: lowercase single-word values are labels too.",
    "MUST_WIN - You must purchase the arcade machine AND get the high score.",
  ]);
  assert.equal(
    normalizeOptionHelp(text),
    doc([
      "Determines which Relics of Chaos are added to the item pool, but are not guaranteed",
      "None: No Relics of Chaos will be included in the item pool at all, whatever the other settings say.",
      "Some: At least 5 Relics of Chaos will be included in the item pool",
      "**All:** Every Relic of Chaos will be included in the item pool.",
      "open: lowercase single-word values are labels too.",
      "MUST_WIN - You must purchase the arcade machine AND get the high score.",
    ]),
  );
});

test("joins a wrapped lowercase phrase that happens to contain a colon", () => {
  const text = doc([
    "Five traps change the camera or the screen itself and may be visually",
    "intense or uncomfortable: First Person, Wireframe, Upside Down, Mirror",
    "Mode, and Demo Camera.",
  ]);
  assert.equal(
    normalizeOptionHelp(text),
    "Five traps change the camera or the screen itself and may be visually intense or uncomfortable: First Person, Wireframe, Upside Down, Mirror Mode, and Demo Camera.",
  );
});

test("keeps short markerless list lines and the line after a colon", () => {
  const text = doc([
    "Percentage of filler items replaced with the following traps:",
    "Bee Trap",
    "Random Debuff Trap",
    "Meteor Shower Trap",
  ]);
  assert.equal(normalizeOptionHelp(text), text);
});

test("keeps indented lines that are not list continuations and does not make them code", () => {
  const text = doc([
    "Inverted: The Light World and Dark World have been flipped.",
    "    - Link spawns at the Bomb Shop and Dark Sanctuary",
    "    - All Dark World portals now take you to the Light World",
    "progressive: All Cracks except the Hyrule Castle Crack are closed.",
    "  Instead, there are two Progressive Merge items.",
  ]);
  const out = normalizeOptionHelp(text);
  assert.equal(out, text);
  assert.ok(!out.includes("```"));
});

test("does not start an indented code block after a blank line", () => {
  assert.equal(
    normalizeOptionHelp(doc(["Randomize the abilities.", "", "        (Double Jump, Wall Jump, Dash)"])),
    doc(["Randomize the abilities.", "", "(Double Jump, Wall Jump, Dash)"]),
  );
});

test("keeps a banner line on its own line", () => {
  const text = doc([
    "-- GENERATION PERFORMANCE --------------------------------------------",
    "Line Locks is the single biggest cost on generation time, because it adds",
    "one progression item per evolution family.",
  ]);
  assert.equal(
    normalizeOptionHelp(text),
    doc([
      "-- GENERATION PERFORMANCE --------------------------------------------",
      "Line Locks is the single biggest cost on generation time, because it adds one progression item per evolution family.",
    ]),
  );
});

test("joins a wrapped line that starts with + instead of making it a list", () => {
  const text = doc([
    "Most Type Keys must go in non-type-gated locations (starting slots + milestones",
    "+ dexsanity locations). Disabling Dexsanity removes those locations.",
  ]);
  assert.equal(
    normalizeOptionHelp(text),
    "Most Type Keys must go in non-type-gated locations (starting slots + milestones + dexsanity locations). Disabling Dexsanity removes those locations.",
  );
});

test("passes author-written Markdown fences through untouched", () => {
  const text = doc(["Set it like this:", "```yaml", "goal:", "  bosses: 3", "```", "Done."]);
  assert.equal(normalizeOptionHelp(text), doc(["Set it like this:", "", "```yaml", "goal:", "  bosses: 3", "```", "Done."]));
});

test("normalises Windows line endings and tabs", () => {
  assert.equal(
    normalizeOptionHelp("First part of a sentence that wraps\r\nonto a second line."),
    "First part of a sentence that wraps onto a second line.",
  );
});

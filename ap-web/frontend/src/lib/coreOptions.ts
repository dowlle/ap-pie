import type { TemplateOption } from "../api";

/**
 * Archipelago's own per-slot options, offered on every builder form.
 *
 * The builder derives its form from what an apworld declares, so options
 * Archipelago provides centrally were previously unreachable: a world's
 * schema contains them only if the world happens to redeclare them. These
 * two apply to every game (`CommonOptions` in Archipelago 0.6.7
 * `Options.py:1387`), need no data we do not already have, and are the ones
 * a normal player is most likely to want.
 *
 * Deliberately NOT here:
 *  - `death_link` is a per-world mixin (`DeathLinkMixin`, Options.py:1727).
 *    A game that supports it declares it, so it already appears in the
 *    world's own options. Adding it centrally would offer it for games
 *    that do not implement it.
 *  - the item/location-name family (`start_inventory`, `exclude_locations`
 *    and friends) needs name lists we cannot derive without executing the
 *    world. The review step's YAML editor covers them instead.
 *  - `item_links`, the plando family, triggers and weighted values are all
 *    marked by Archipelago itself as not-simple-UI (`Visibility` flags,
 *    Options.py:70-76). Same answer: the editor.
 *
 * Values are only written into the YAML when the user actually picks one.
 * Leaving a control on "game default" omits the key entirely, which matters
 * because a world using `ItemsAccessibility` defaults to `items` rather
 * than `full` - writing our own default would silently change its game.
 */
export const CORE_CATEGORY = "Archipelago options";

export const CORE_OPTIONS: TemplateOption[] = [
  {
    name: "progression_balancing",
    display_name: "Progression Balancing",
    type: "range",
    category: CORE_CATEGORY,
    min: 0,
    max: 99,
    default: 50,
    named_values: { disabled: 0, normal: 50, extreme: 99 },
    description:
      "How hard Archipelago works to move your progression items earlier, so " +
      "you spend less of the game stuck with nothing to do.\n\n" +
      "- **normal** (50) is the default and is right for most players.\n" +
      "- **disabled** (0) leaves the item placement alone.\n" +
      "- **extreme** (99) front-loads progression as much as it can.",
  },
  {
    name: "accessibility",
    display_name: "Accessibility",
    type: "choice",
    category: CORE_CATEGORY,
    choices: ["full", "minimal", "items"],
    default: "full",
    description:
      "What the generator guarantees you can reach.\n\n" +
      "- **full**: everything in your world can be reached and collected.\n" +
      "- **minimal**: only what is needed to finish your goal is guaranteed. " +
      "Locations may end up unreachable.\n" +
      "- **items**: every logically relevant item can be obtained, though some " +
      "locations may not be reachable. Only some games treat this as distinct " +
      "from full.",
  },
];

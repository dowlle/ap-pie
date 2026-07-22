## Your YAML is just your settings

Every player brings one YAML file per game they play. It tells the generator which game you are on, what your player name is, and how you want your game randomized. You do not write it from scratch, because every game ships a template with every option already filled in with sensible defaults and explained in comments. Setting up a YAML mostly means changing the handful of options you care about, and this guide walks through everything you will meet along the way, from the basic option shapes to the settings that every Archipelago game shares.

## Getting a template

There are two easy ways to get one. On the website, open the [supported games list](https://archipelago.gg/games), pick your game, click its **Options Page**, set everything with normal form controls, and click **Export Options** to download a ready YAML. If you would rather work locally, open the Archipelago Launcher and click **Generate Template Options**, which writes a template for every installed game into your `Players/Templates` folder.

For games that live outside the official list, the template comes with the apworld. Community games like the ones in [this site's APWorld index](/apworlds) usually ship it in their release download, and their setup guides say where to look.

## Reading the options

Open the file in any text editor and you will see the same few shapes repeated. A toggle takes `true` or `false`. A choice option lists its allowed values in the comment above it, and you pick one of them. A range takes a number between the bounds the comment gives you. The comments are the real documentation, and they sit right next to the thing they explain.

Two fields deserve extra care before anything else. Your `name` is your slot name, and it has to match exactly what you type when your game client connects. And if your host pinned specific apworld versions for the room, generate your template from that same version so the options line up.

## How weights actually work

This is the part of the format that confuses the most people, so it deserves a proper explanation. In a template, most options do not look like `mode: standard`. They look like this instead:

    mode:
      standard: 50
      inverted: 0

Those numbers are weights, and the best way to think about them is raffle tickets. Every value with a number above zero has that many tickets in a draw, and when your seed generates, the generator draws one ticket and that value wins. In the example above, `standard` holds all fifty tickets and `inverted` holds none, so `standard` wins every time, and the file behaves exactly as if you had written `mode: standard`.

The interesting part starts when you spread the tickets. Give `standard` a weight of 3 and `inverted` a weight of 1, and three out of four seeds will roll standard while the fourth surprises you. The absolute numbers do not matter, only the proportions, so 3 and 1 behaves the same as 75 and 25. This is how players who have done a hundred seeds keep things fresh, because the file itself rolls the dice for them.

If you find weights confusing in practice, you can ignore them entirely. Put any number on the one value you want, leave everything else at zero, and every option becomes a fixed choice. That is how the templates ship, and it is a perfectly good way to play.

## Letting the generator pick numbers

Range options accept a few special values besides plain numbers. Writing `random` picks any allowed value, `random-low` leans toward small numbers, `random-high` leans toward large ones, and `random-middle` clusters around the center. You can also bound the roll with `random-range-40-60`, which picks something between 40 and 60. These combine with weights like any other value, so a range option can hold tickets for a fixed number and a random roll at the same time.

## The options every game has

A few settings appear in every Archipelago template regardless of the game, and they shape the multiworld experience more than most game-specific options do.

**Progression balancing** exists because of a failure mode every multiworld player learns to dread, which the community calls BK mode, after sitting stuck with nothing to do. Your next useful item is in someone else's world, they have not found it yet, and you are done exploring everything you can reach. Progression balancing fights that by quietly moving items that unblock players into earlier parts of the multiworld, so everyone keeps moving. It is a number from 0 to 99, and the default of 50 means the generator tries to keep you at no less than half the progress of the furthest player. Higher values smooth the experience further at the cost of more predictable item placement, 0 turns the system off entirely, and unless you know you want something else, the default is a good place to stay.

**Accessibility** decides how much of your world the generator must keep reachable. The default of `full` guarantees every location in your world can be reached, `items` only guarantees you can obtain every logically relevant item, and `minimal` promises nothing beyond the seed being beatable, which can leave whole areas of your game permanently locked. Minimal makes for faster and more chaotic seeds, and it is a deliberate choice rather than a beginner's one.

## Shaping where the items go

The template ends with a block of item and location options that are empty by default, and they are worth knowing even if you never touch them. `start_inventory` hands you chosen items at the start of the game, which is how people play with a weapon from minute one. `local_items` forces chosen items to stay in your own world, and `non_local_items` pushes them into other worlds. `start_hints` gives you free server hints for chosen items from the start, and `start_location_hints` does the same for locations. `exclude_locations` marks locations that must not hold anything important, which is the polite way to opt out of a check you hate, and `priority_locations` does the opposite by forcing something important onto a location. `item_links` lets several players pool a chosen item so that when one of them finds it, everyone in the link receives it.

There is also a `triggers` block for conditional logic, where one option can change other options when it rolls a certain way. It is genuinely advanced, and the [official advanced guide](https://archipelago.gg/tutorial/Archipelago/advanced_settings/en) covers it when you get there.

## One file, several games

The `game` field at the top accepts weights just like any other option, so a single file can hold tickets for several games, with an options block for each. Every seed then rolls which game you are playing that time. It is a favorite of players who genuinely cannot decide, and it works in any room that allows those games.

## Checking your work

The site validates YAMLs at [archipelago.gg/check](https://archipelago.gg/check), which catches most mistakes before they cost your host a failed generation. Rooms on this site run the same class of checks automatically when you submit, so a bad file is caught at upload rather than on generation night.

## Handing it in

Send the file to whoever hosts your game. If they use this site, they will give you a room link where you drop the file in the browser, and [Hosting a multiworld](/guides/hosting-a-multiworld) shows what happens on their side of the fence.

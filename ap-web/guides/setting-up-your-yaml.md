## Your YAML is just your settings

Every player brings one YAML file per game they play. It tells the generator which game you are on, what your player name is, and how you want your game randomized. You do not write it from scratch, because every game ships a template with every option already filled in with sensible defaults and explained in comments. Setting up a YAML mostly means changing the handful of options you care about.

## Getting a template

There are two easy ways to get one. On the website, open the [supported games list](https://archipelago.gg/games), pick your game, click its **Options Page**, set everything with normal form controls, and click **Export Options** to download a ready YAML. If you would rather work locally, open the Archipelago Launcher and click **Generate Template Options**, which writes a template for every installed game into your `Players/Templates` folder.

For games that live outside the official list, the template comes with the apworld. Community games like the ones in [this site's APWorld index](/apworlds) usually ship it in their release download, and their setup guides say where to look.

## Reading the options

Open the file in any text editor and you will see the same few shapes repeated. A toggle takes `true` or `false`. A choice option lists its allowed values in the comment above it, and you type one of them. A range takes a number between the bounds the comment gives you. The comments are the real documentation, and they sit right next to the thing they explain.

You may notice that options can also take several values with numbers behind them. Those numbers are weights, and the generator rolls between the values you weight above zero. Weighting `standard: 1` and `chaos: 1` means a coin flip every seed. If you just want one fixed behavior, give that value any weight and leave the others at zero, which is what the templates do by default.

Two fields deserve extra care. Your `name` is your slot name, and it has to match exactly what you type when your game client connects. And if your host pinned specific apworld versions for the room, generate your template from that same version so the options line up.

## Checking your work

The site validates YAMLs at [archipelago.gg/check](https://archipelago.gg/check), which catches most mistakes before they cost your host a failed generation. Rooms on this site run the same class of checks automatically when you submit, so a bad file is caught at upload rather than on generation night.

## Handing it in

Send the file to whoever hosts your game. If they use this site, they will give you a room link where you drop the file in the browser, and [Hosting a multiworld](/guides/hosting-a-multiworld) shows what happens on their side of the fence.

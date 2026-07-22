## What is Archipelago?

Archipelago is a multiworld randomizer. It takes a group of games, shuffles their unlocks and items into one shared pool, and spreads that pool across every player's world. When you find an item in your game, it might be yours, or it might belong to a friend playing a completely different game. Your own progression is out there too, waiting in someone else's world.

You can also play solo. One game, one world, everything shuffled within it. That is a classic randomizer, and it works exactly the same way.

Archipelago supports hundreds of games, from Zelda and Metroid classics to modern indies. The officially supported list lives at [archipelago.gg/games](https://archipelago.gg/games), and that is only part of the picture: the community maintains many more integrations, browsable in [our APWorld index](/apworlds), including this site's own games like Crash Team Racing. Each supported game has its own "apworld": a small add-on that teaches Archipelago how that game works.

## Start here: your first game in five steps

1. **Pick a game you own** from the [official games list](https://archipelago.gg/games) or [the community APWorld index](/apworlds). Good first picks are games you know well; the randomizer is more fun when the base game is familiar.
2. **Install Archipelago.** Download the latest installer from the [official releases page](https://github.com/ArchipelagoMW/Archipelago/releases). It bundles the generator, the server, and the clients most games need.
3. **Follow your game's setup guide.** Every game on [archipelago.gg/games](https://archipelago.gg/games) links its own guide, and the general tutorials live at [archipelago.gg/tutorial](https://archipelago.gg/tutorial). Playing Crash Team Racing? Use [our CTR guide](/guides/ctr) instead, it covers everything in one place.
4. **Make your YAML** (your settings file, explained below) and generate a game, or hand the YAML to whoever is hosting.
5. **Connect and play.** Your game's client connects to the room address, and from there items flow automatically.

Stuck at any step? The [Archipelago Discord](https://discord.gg/8Z65BR2) is active and friendly, and most games have their own channel there.

## YAMLs, rooms, and clients

**A YAML file.** Your settings file. It says which game you are playing, what your player name (slot name) is, and how you want your game randomized. Every player brings one YAML per game they play.

**A room.** The shared session. Someone collects everyone's YAML files, generates a seed from them, and hosts a server. The room has an address (something like `archipelago.gg:38281`) that every player connects to.

**A client.** The program that connects your game to the room. Some games have a built-in client, others use a separate program. The game's setup guide tells you which.

## How a multiworld gets started

1. One person volunteers as host and collects YAML files from all players. This site exists to make that step painless: a host creates a room here and players submit their YAML through their browser.
2. The host generates the game. This produces one seed containing every player's world.
3. The host starts the server, usually on [archipelago.gg](https://archipelago.gg) itself, and shares the address.
4. Each player starts their own game with its client and connects with the address and their slot name.
5. Play. Items you find are sent automatically, and items sent to you show up in your game.

You do not have to bring your own group either, because open multiworlds are announced all the time. Hosts post them in the [official Archipelago Discord](https://discord.gg/8Z65BR2), and several streamer communities run big regular ones, with [360Chrism](https://www.twitch.tv/360chrism)'s community among the largest, hosting events that have crossed seven hundred players in one multiworld.

## Setting up your first YAML

Every apworld ships a template YAML with all its options explained in comments. Open it in any text editor, set your name, adjust the options you care about, and leave the rest alone. Defaults are sensible everywhere. You can also generate a template for many games on [archipelago.gg/games](https://archipelago.gg/games) under the game's options page, and fine-tune it from there.

Two rules save the most headaches. Your slot name must match exactly between the YAML and what you type in your client when connecting. And when your host pins specific apworld versions for a room, use the same version they pinned. When you are ready to go deeper, [Setting up your YAML](/guides/setting-up-your-yaml) is the complete guide, covering weights, progression balancing, and every option all games share.

## Where this site fits

Archipelago Pie is a YAML collector and lobby manager. Hosts create a room, set a deadline, and pin apworld versions, and players submit their YAML in the browser instead of passing files around in chat. The room page also shows a live tracker once the game is running.

## Ready for a specific game?

- **Crash Team Racing:** [our full setup guide](/guides/ctr) takes you from zero to racing in about five minutes.
- **Any other game:** find it on [archipelago.gg/games](https://archipelago.gg/games) or in [the community APWorld index](/apworlds) and follow its linked setup guide; the general tutorials are at [archipelago.gg/tutorial](https://archipelago.gg/tutorial).
- **Questions along the way:** the [Archipelago Discord](https://discord.gg/8Z65BR2) is the fastest place to get help.

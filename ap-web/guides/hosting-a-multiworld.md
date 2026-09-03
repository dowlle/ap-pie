## What a host actually does

Every multiworld has one person wearing the host hat. The host collects one configuration for each world, generates the game from that stack, puts the server online, and gives every player what they need to connect. Most players bring one world, so this often looks like one YAML per player.

Playing alone does not skip any of this. A seed with one world still has to be generated and then hosted, and the host in that case is you, on your own machine.

Before you start, install Archipelago itself from the [official releases page](https://github.com/ArchipelagoMW/Archipelago/releases). The installer bundles the launcher, the generator, and the server in one package.

## Step 1: collect the YAMLs

Each player normally submits one YAML for each slot they bring, and [Setting up your YAML](/guides/setting-up-your-yaml) explains that side. Players who do not want to edit the file by hand can use the [guided YAML Builder](/yaml-builder). You can collect the files however you like, but chasing attachments through chat gets old fast. [How to host a room on Archipelago Pie](/guides/hosting-on-archipelago-pie) covers creating a collection room, sharing one link, checking submissions, closing at the deadline, and downloading the complete stack.

![The Players folder in Windows Explorer, holding one YAML file for each slot in the multiworld.](/img/guides/hosting-players-folder.png)

*However you collect them, you end up with one YAML per slot. This stack is two slots from two players.*

## Step 2: generate the game

Put all the YAML files in the `Players` folder inside your Archipelago install. On Windows the install sits at `C:\ProgramData\Archipelago`, so the folder you want is `C:\ProgramData\Archipelago\Players`. If you cannot find it, the launcher's **Browse Files** entry opens the install folder for you.

The same install folder holds `custom_worlds`. That is where APWorlds live for games Archipelago does not ship with, and the launcher's **Install APWorld** entry puts them there. A host generating [Crash Team Racing](/guides/ctr) or [Poképelago](/guides/pokepelago) needs that game's APWorld installed before generation will work.

![The Archipelago install folder in Windows Explorer, with the Players folder selected among the other install folders.](/img/guides/hosting-archipelago-folder.png)

*The `Players` folder sits in the Archipelago install folder, next to `output` and `custom_worlds`.*

Then open the Archipelago Launcher and click **Generate**. The generator reads every YAML, weaves the worlds together, and writes a zip into `C:\ProgramData\Archipelago\output`. The file is named `AP_` followed by a long number, so `AP_99118272869059136761.zip` and similar. That single zip is your whole multiworld.

![The Archipelago Launcher window listing Host, Generate, Options Creator and the other tools.](/img/guides/hosting-launcher-generate.png)

*Generate and Host are both in the Archipelago Launcher, alongside the clients and the other tools.*

![The output folder in Windows Explorer, holding one generated multiworld zip named with an AP number.](/img/guides/hosting-generate-output.png)

*A successful run leaves exactly one new zip in the `output` folder. That is the file you upload or host.*

If generation fails, the error usually names the YAML that caused it. You can also check any single file beforehand at [archipelago.gg/check](https://archipelago.gg/check).

## Step 3: put the server online

The easy route is letting archipelago.gg host for you. It takes three steps.

First, open the [Host Game page](https://archipelago.gg/uploads) and select **Upload File**. Pick the `AP_...zip` from your `output` folder.

![The Host Game page on archipelago.gg, with the Upload File button that takes the generated zip.](/img/guides/hosting-upload-form.png)

*The Host Game page takes the zip straight from your `output` folder. Upload File is the only control you need.*

Second, the upload gives you a seed page rather than a running server. It lists the seed, how many players are in it, and a spoiler download. Select **Create New Room** to start the server.

![The Seed Info page on archipelago.gg, listing the seed, the player count, the spoiler download and the Create New Room link.](/img/guides/hosting-seed-info.png)

*Uploading creates a seed. Create New Room turns that seed into a server your players can join.*

Third, you land on the room page. It carries the address and port to connect to, one row per slot with any data file that slot needs to download, a tracker link per slot, and a console for host commands. Hosted rooms may sleep after inactivity and resume when somebody opens the room page, so players should use the current connection details shown there.

You can also host on your own machine. Click **Host** in the Archipelago Launcher. A **Select multiworld data** dialog opens in your `output` folder, and you pick the `AP_...zip` directly, with no need to extract anything first. A console window titled **Running Archipelago** then opens and the server is up.

![The bundled Archipelago server console running locally, reporting the address and port it is hosting on.](/img/guides/hosting-local-console.png)

*A self-hosted server runs in a console window and prints the address and port it listens on.*

Warnings at the top of that console are normal. Lines about custom worlds with a missing manifest, or worlds that were not loaded because the game is already loaded, do not stop the server. The line that matters is `Hosting game at <address>:38281`, and that address and port are what your players connect to.

Players outside your network can only reach a self-hosted server if you forward port 38281, so for most groups the archipelago.gg route is less hassle. If you would rather not use the launcher, extracting the `.archipelago` file from the zip and double-clicking it starts the same server.

## Step 4: share and play

Give every player a complete handoff:

- the exact game, Archipelago, and APWorld version;
- the maintained game-specific setup guide;
- any generated player-specific patch, mod, or other output;
- the room page link, so players can see current connection information and retrieve available data files;
- the server address and port from the current room page;
- the exact slot name from the generated seed;
- the room password, if it uses one;
- the support channel and any synchronized-start rules.

The slot name is the one detail players ask about most. It is the `name` field from that player's own YAML, copied exactly, and it is what the client asks for when connecting. It is not the game name and not their Discord name. The room page lists every slot name in the multiworld, so you can read them off there if a player is unsure.

![An archipelago.gg room page showing the connect line with the address and port, the slot table, and the server log.](/img/guides/hosting-room-page.png)

*The room page carries the connect line players need, the slot table with each slot name and any downloadable data file, and a console for host commands. The port is blanked out here because every room gets its own.*

From there each game's client, mod, or connector takes over. [Setting up an Archipelago game client](/guides/setting-up-a-game-client) explains the common patterns and a pre-play test. Exact installation steps belong in the game-specific guide.

While the game runs, the server console (or the room page on archipelago.gg) accepts commands. Players can ask for hints with their earned hint points, and as host you can release a leaver's remaining items or collect what belongs to a finished player. Type `/help` in the console to see what is available.

## Where to go next

If your players are new to all of this, hand them [Getting started with Archipelago](/guides/getting-started) and the per-game guides on [the guides page](/guides). For keeping an eye on everyone's progress, the room page here shows a live tracker, and [PopTracker](/guides/setting-up-poptracker) covers personal tracking.

Timberborn Archipelago is a mod for Timberborn plus an APWorld for Archipelago. As a player you need the mod and a room to join. Only the person who generates the multiworld needs the APWorld.

## What you need

- **Timberborn 1.1.** The mod is built for Timberborn 1.1; earlier game versions are not supported.
- **The Timberborn Archipelago mod**, from the [download page](/timberborn/download).
- **Room details from your host:** the address and port, your slot name, and the password if there is one.
- **Your YAML**, the file with your options. The [Timberborn YAML Builder](/yaml-builder/timberborn) makes one, and your host needs it before generating.

## Step 1: Install the mod

**From mod.io or Steam Workshop.** Subscribe to Timberborn Archipelago there and the game installs it for you.

> **Placeholder for release:** the mod.io and Steam Workshop links go here. The listings go live with the 0.1.0 release; until then, use the zip below.

**Manually from the zip.** Download `Archipelago.zip` and extract it into `Documents/Timberborn/Mods/`. You should end up with a `Mods/Archipelago/` folder, with the mod's files directly inside it.

<p><img src="/img/timberborn/mods-folder.jpg" alt="File Explorer at Documents, Timberborn, Mods, with a single folder named Archipelago" width="940" height="240" loading="lazy" /></p>

The Mods folder with the mod extracted into its own Archipelago folder.

## Step 2: Enable the mod

Start Timberborn. In the **Mods** window on the main menu, make sure **Archipelago Multiworld** is ticked, then click **OK**.

<p><img src="/img/timberborn/mods-dialog.jpg" alt="Timberborn's Mods window with Archipelago Multiworld ticked" width="794" height="915" loading="lazy" style="max-width:420px;margin:0 auto" /></p>

The Mods window with the mod enabled. This picture was taken on a development build, so the version number differs from the release.

## Step 3: Start a colony with your faction

Start a new game with the faction your YAML asks for: Folktails or Iron Teeth. The mod unlocks Iron Teeth for you as soon as a colony loads with the mod enabled, so you don't need to reach well-being 8 in a Folktails game first. If Iron Teeth is still locked on the new-game screen, load any colony once, go back to the main menu and try again.

If the colony's faction doesn't match your YAML, the mod refuses the connection and the Archipelago log says **Wrong faction!** Start a new game with the right faction.

## Step 4: Connect to your room

Click the **Archipelago button** in the bottom toolbar to open the **AP Shop**.

<p><img src="/img/timberborn/ap-button-bottom-bar.jpg" alt="The Archipelago button in Timberborn's bottom toolbar" width="480" height="100" loading="lazy" style="max-width:480px;margin:0 auto" /></p>

The Archipelago button: the round logo with six coloured circles.

Fill in the fields at the bottom of the shop:

- **Host:** the room address without the port, for example `archipelago.gg`. For a server on your own computer, `localhost` works.
- **Port:** the number after the colon in the room address, for example `38281`.
- **Slot:** your slot name, exactly as in your YAML.
- **Password:** leave it empty if the room has none.

Click **Connect**. The shop fills with your seed's four paths and the log shows that you joined.

<p><img src="/img/timberborn/ap-shop-connect.jpg" alt="The AP Shop with paths A to D, each showing ??? and a science price, above the Host, Port, Slot and Password fields" width="820" height="790" loading="lazy" style="max-width:560px;margin:0 auto" /></p>

The AP Shop right after connecting. Every path starts at a small science price.

The save remembers the connection. When you load it again, the mod reconnects by itself.

## Step 5: Play

Earn science as usual and spend it in the AP Shop. Each purchase sends a check to the multiworld, and the blueprints you need arrive from other players. [How it works](/timberborn/reference) explains the shop, the items, goals and every option.

## For the host: generate the seed

The seed is generated on your own computer with the Archipelago Launcher, then hosted on archipelago.gg or your own machine. The [hosting guide](/guides/hosting-a-multiworld) covers every game; these are the Timberborn parts.

1. Install Archipelago 0.6.7 or newer.
2. Download `timberborn.apworld` from the [download page](/timberborn/download) and use **Install APWorld** in the Archipelago Launcher.
3. Collect the players' YAMLs. The [YAML Builder](/yaml-builder/timberborn) and `Timberborn.yaml` from the release both give a valid starting point, and a [collection room](/guides/hosting-on-archipelago-pie) gathers them in one place.
4. Generate locally. archipelago.gg's generator doesn't include the Timberborn APWorld.

Use one version for everything: the mod, the APWorld and the YAMLs come from the same release.

## Troubleshooting

- **Wrong faction!** Your colony is not the faction from your YAML. Start a new colony with the right one.
- **The Archipelago button is missing.** The mod isn't loaded. Check the Mods window on the main menu, and for a manual install check that the files are in `Mods/Archipelago/` and not one folder deeper.
- **Connecting fails.** Check the host and port separately, and the slot name spelling. Rooms on archipelago.gg get a new port when they restart after being idle, so ask your host for the current one.
- **Something else.** Open an issue on [GitHub](https://github.com/dowlle/timberborn-modding/issues) with your faction, the mod version and what happened.

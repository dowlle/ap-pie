# Archipelago Tools - Feature Design Document

## Vision
A single web platform for the full Archipelago multiworld experience: create games, host servers, track progress, and coordinate with other players. Built for both **game hosters** (organizers running multiworld sessions) and **players** (participants connecting to hosted games).

---

## Feature 1: Server Management (Already Built)

### What it does
Launch, monitor, and stop Archipelago game servers from a web dashboard. Each server gets an auto-assigned port from a configurable range. The system tracks process health, captures logs, and persists state across app restarts.

### For hosters
- **One-click server launch**: No terminal commands. Pick a generated game, click "Launch Server", and it's running.
- **Run multiple games simultaneously**: Host a casual game for friends and a competitive race at the same time, each on their own port.
- **Crash detection**: If a server crashes, the dashboard shows it immediately with the status changing from "running" to "crashed". No more wondering why players can't connect.
- **Connection URL display**: The dashboard shows the exact `host:port` that players need to paste into their AP client. Copy-paste it into Discord or share it on stream.
- **Log access**: See the server's output in the UI to debug issues without SSHing into the machine.

### For players
- **Know where to connect**: The game detail page shows the connection URL when a server is running. No more asking the host "what's the port again?"
- **Server status visibility**: Players can check if the server is up before opening their game client.

---

## Feature 2: Game Library & Analysis (Already Built)

### What it does
Scans all generated Archipelago game archives (.zip files containing .archipelago multidata) and their save files (.apsave). Extracts metadata: seed, AP version, player list, per-player game assignments, check completion counts, client status, and timestamps.

### For hosters
- **Browse all your games**: Filterable and sortable list of every game you've generated. Filter by game name, player name, seed, AP version, or save status.
- **Completion tracking**: See overall and per-player completion percentage, which players have reached their goal, and who's still playing.
- **Last played timestamps**: Quickly find which game you were playing last night, or which games have been abandoned.
- **File upload**: Upload game zips generated on another machine. Useful when generation happens on a PC but hosting happens on a server.

### For players
- **Find your game**: Search by your player name to find which games you're in.
- **Check progress**: See how the multiworld is going without opening the game - who's at what percentage, who's finished.

---

## Feature 3: Live Tracker

### What it does
Connects to running AP servers and polls their built-in HTTP tracker endpoint to display real-time game state. Shows which players are connected, their check progress, items received, hints exchanged, and activity timestamps. Auto-refreshes every 10-30 seconds.

### For hosters
- **Monitor game health at a glance**: See which players are connected, who's making progress, and who might be stuck - all without joining the game yourself.
- **Identify problems early**: A player at 5% completion while everyone else is at 40% might need help. A player who hasn't been active in hours might have disconnected.
- **Stream-friendly**: Put the tracker on a second monitor or overlay it on stream. Viewers can follow along without spoilers (configurable what to show).
- **Inactivity alerts**: Configurable thresholds that color-code player activity. Yellow after 2 hours of no checks, red after 6 hours. Helps hosts know when to ping players.

### For players
- **Track the multiworld**: See everyone's progress without being in-game. Check from your phone during a break.
- **Hint visibility**: See which hints have been sent and received across the multiworld. Know if someone found a hint pointing to your world.
- **Completion race**: Watch the completion percentages climb in real-time. Creates excitement and friendly competition.
- **Know when you're blocking someone**: If another player has sent you a hint for an important item, you can see it in the tracker and prioritize finding it.

### Display features (inspired by ANAPtracker + Cheese Trackers)
- **Per-player row**: Slot number, player name, game, checks done/total, completion %, status badge (connected/playing/goal), last activity
- **Progress bars**: Visual completion bars with color coding (green for fast progress, yellow for slow, grey for inactive)
- **Sort options**: By slot, game, completion %, checks remaining, activity time
- **Filter options**: By game, by player, hide completed, hide inactive
- **Hint panel**: Expandable per-player hint list showing received and sent hints with item names

---

## Feature 4: Discord Authentication

### What it does
Players and hosters sign in with their Discord account (OAuth2, "identify" scope only - we only read username and user ID, no messages, no guilds, no email). This creates a persistent identity that enables all collaborative features.

### For hosters
- **Know who's who**: Instead of anonymous visitors, you see Discord usernames. Matches the names players use in your Discord server.
- **Access control**: Lock your tracker so only authenticated users can claim slots. Prevents random people from messing with your game's tracking.
- **Host identity**: You're automatically recognized as the host of games you launch, giving you admin controls over that game's tracker.

### For players
- **Persistent identity**: Claim your slot once, and it stays claimed across sessions. No re-entering your name every time.
- **Cross-session continuity**: Your notes, ping preferences, and slot claims persist because they're tied to your Discord account.
- **Low friction**: Click "Sign in with Discord", approve, done. No new account to create, no password to remember.

---

## Feature 5: Slot Claiming & Player Coordination

### What it does
Players claim their slot in a tracked game ("I am Player 3 - Stardew Valley"). Once claimed, they can add notes, set ping preferences, and see personalized hint information. The tracker shows which slots are claimed, which are open, and who's playing what.

### For hosters
- **See who's committed**: A claimed slot means that player intends to play. Unclaimed slots might mean someone hasn't seen the invite yet.
- **Coordination dashboard**: At a glance, see which slots are taken and which still need players. Useful for large multiworlds where you're recruiting.
- **Ping management**: Set a global ping policy ("only ping for progression items") so players aren't overwhelmed by notifications.
- **Inactivity management**: See which claimed players have gone inactive. Reach out to them or make decisions about forfeiting their slot.

### For players
- **Claim your slot**: Clearly mark which slot is yours. Other players can see what game you're playing and how to reach you.
- **Personal notes**: Add notes to your slot like "stuck after Ganon's Tower, need hookshot" or "available evenings only". Other players can read these to understand your situation.
- **Ping preferences**: Control how aggressively other players should ping you about hints:
  - **Liberally**: Ping me for anything
  - **Sparingly**: Only important stuff
  - **Hints only**: Only when you find a hint pointing to my world
  - **See notes**: Check my notes before pinging
  - **Never**: Don't ping me
- **Hint classification**: Mark received hints as Critical / Progression / Quality of Life / Trash. Helps you prioritize and helps other players understand what you need.

---

## Feature 6: YAML Collection & Game Generation

### What it does
Create a "room" where players upload their YAML configuration files. The system validates each YAML against the installed APWorlds, and when all players are ready, the host clicks "Generate" to create the multiworld game. The output is automatically added to the game library and can be launched as a server with one click.

### For hosters
- **Streamlined setup**: Instead of collecting YAMLs via Discord DMs, email, or file sharing, players upload directly to a room page. No more "did everyone send their YAML?"
- **Automatic validation**: YAMLs are checked before generation, catching errors early. No more generation failures because someone had an invalid option.
- **One-click generation → hosting**: Generate the game, then immediately launch the server. The entire flow from "let's play" to "server is live" happens in one UI.
- **Patch distribution**: After generation, each player gets a download link for their game-specific patch file. No more manually sending patch files.
- **Room management**: Set a closing date, limit YAMLs per player, add a description with rules or theme info.

### For players
- **Easy YAML submission**: Upload your YAML to the room page. See the validation status immediately - green means good, red means there's a problem.
- **Download your patch**: Once the game is generated, download your patch file directly from the room page. No hunting through Discord for the right file.
- **Room visibility**: See who else has submitted their YAML, what games are represented, and whether the room is ready for generation.

---

## Feature 7: Game-Specific Visual Trackers

### What it does
For supported games, replace the generic "checks done / total" display with a game-aware visual tracker. For example, a Pokémon Emerald tracker shows 8 gym badges and 8 HMs as icons that light up when collected. A Hollow Knight tracker shows abilities organized by category with visual progression.

### For hosters
- **Better spectating**: Much more engaging than raw numbers. See that a player just got the Hookshot in Zelda or earned their 5th gym badge in Pokémon.
- **Stream appeal**: Game-specific trackers look great on stream. Viewers can follow individual players' progress through familiar game visuals.

### For players
- **At-a-glance progress**: Instead of "47/310 checks (15%)", see exactly which items you have and which you're missing, laid out in a familiar format for your game.
- **Item awareness**: Quickly see which key items you've received from other players. Did someone send you the Hookshot? The Morph Ball? You can tell instantly.
- **Strategy planning**: Seeing your collected items visually helps you plan what to do next - "I have 3 gym badges and Surf, I can reach the 4th gym now."

### Supported games (initial rollout, based on usage data)
1. **Pokepelago** - Most played game in the library (308 appearances)
2. **Stardew Valley** - Complex item/bundle tracker
3. **Hollow Knight** - Ability and grub tracking
4. **Pokémon Emerald** - Badge and HM grid

Additional games added over time based on player demand.

---

## Feature Summary Matrix

| Feature | Hoster Benefit | Player Benefit | Complexity | Phase |
|---------|---------------|----------------|------------|-------|
| Server Management | Launch/monitor/stop servers | See connection info + status | Done | Done |
| Game Library | Browse/filter all games | Search games, check progress | Done | Done |
| Live Tracker | Monitor game health | Track progress, see hints | Medium | 1 |
| Discord Auth | Know who's who, access control | Persistent identity | Medium | 2 |
| Slot Claiming | See who's committed, coordinate | Claim slot, notes, ping prefs | Medium | 2 |
| YAML Collection | Streamline setup, validate, generate | Easy submission, patch download | High | 3 |
| Game-Specific Trackers | Stream appeal, better spectating | Visual item tracking | High (per game) | 4 |

---

## What We Deliberately Skip

| Feature | Source | Why Skip |
|---------|--------|----------|
| Market/Trading | Cheese Trackers | Low usage, niche feature. Add later if requested. |
| Interactive Options Editor | Archipelago-lobby | 46KB of UI for something AP's built-in tool handles. Players can use Archipelago's OptionsCreator. |
| Full APWorld Management | Archipelago-lobby | Complex indexing system. We just use whatever APWorlds are installed locally. |
| HTML Tracker Scraping | Cheese Trackers | They scrape because they connect to *external* AP servers. We *run* the server, so we have direct access to the data. |

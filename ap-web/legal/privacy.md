Archipelago Pie is run by one person as a hobby project. This page explains exactly what the site records, what it deliberately does not record, and what you can ask for. It is written to be checkable: everything described here corresponds to code you can read in the public repository at [github.com/dowlle/ap-pie](https://github.com/dowlle/ap-pie).

**Last updated:** 2026-09-03

## The short version

There is no cookie banner on this site because there is nothing to consent to. No advertising, no third-party analytics scripts, no tracking pixels, no cross-site profiles, no data sold or shared with anyone. The site keeps a small first-party event log; activity may carry your internal account id while you are signed in, and otherwise has no durable visitor identifier.

## Who is responsible

Archipelago Pie is operated by Dowlle, an individual developer in the Netherlands. For any question or request about your data, contact Appie (Dowlle) on Discord.

## What the site records

### Analytics events

The site keeps a server-side log of things that happen on it, so its own funnel can be improved: which guides get read, which games people open the YAML builder for, why a YAML submission was rejected, whether a login round-trip finished, whether a download link was used. Each entry holds:

- what happened, as a short code such as `guide_view` or `submit_rejected`
- when it happened
- the page path it happened on
- which page on this site you came from, as a bare path such as `/guides/ctr`. On the app's first page view, an outside source is reduced in your browser to `search`, `community`, `other_external`, or `direct`. The source address is discarded and never sent because it can contain search terms
- a two-letter country code, supplied by Cloudflare
- whether the device looked like a desktop, a mobile, a bot, or a recognised synthetic test
- a small set of technical details for that event type, such as a game name, a version number, a rejection reason code, whether a YAML was hand-edited rather than built from the form, or that a community preset was used. Builder events may also carry a random attempt value so one opening, its furthest stage, and its outcome are counted together
- your account id, **only if you were signed in**

Guide arrivals have one additional, aggregate-only measurement. When a guide
loads, the referring address is examined briefly in server memory and reduced
to one of eight fixed categories: internal, direct, search, community, project
or release, Archipelago ecosystem, other external, or unknown. The raw address
and hostname are then discarded. Postgres receives only a daily counter keyed
by date, guide slug, and category. That counter has no exact time, account id,
request id, country, device class, visit value, or other request-level data.
Requests carrying Global Privacy Control or Do Not Track do not contribute to
this acquisition counter at all.

That is the whole record. In particular it does **not** contain:

- **your IP address.** It is used momentarily to apply rate limits and is never written to the database
- **your browser's User-Agent string.** Only the three-way desktop / mobile / bot classification is kept
- **any tracking identifier on your device.** No analytics cookie, no localStorage, no sessionStorage, no fingerprint. To measure how far people get in a single visit, the page generates a random value that lives only in the browser tab's memory and disappears the moment you reload or close it. It cannot connect two visits, two devices, or two browsers
- **the address of the site that sent you here**, when that site is not this one. Only a broad source category is recorded
- **the contents of anything you write.** YAML files, room names, room descriptions and player names never enter the analytics log

Because the visit and Builder attempt values cannot survive a page load, the log has no concept of a durable session. It can connect steps inside the current page load, but cannot follow one person across reloads, tabs, devices, or later visits. That limitation is deliberate.

If you are signed in, page views on the guides and the Crash Team Racing pages are recorded with your account id, the same as the rest of your activity on the site. Signed out, they are not linked to anything.

### Poképelago

The Poképelago game client at pokepelago.ap-pie.com sends a few technical events to this same log: whether connecting to an Archipelago server worked (as a short reason code such as `unreachable`, never the server's address or your slot name), which generation of the game data was in use, whether sprite images were being blocked by a browser extension, and that a game goal was completed. These events are always recorded anonymously: even if you are signed in to ap-pie.com, your account id is never attached to them. Nothing about what you guess or how you play is recorded.

### Signing in with Discord

If you sign in, the site stores your Discord user id and display name so it can show you as the owner of your rooms and submissions, and sets one session cookie so you stay signed in. That cookie is strictly necessary for the login to work and is used for nothing else. Signing in is optional: rooms can be viewed, YAMLs can be built and submitted, and everything on the guides and downloads pages works without an account.

### Things you create

Rooms you host and YAML files you submit are stored so the site can do its job. Those are visible to the room's host and, depending on the room's settings, to other players in that room. Saved YAMLs, private and published presets, and room templates are tied to your account so you can reuse and manage them from the My area.

Room activity records short human-readable messages such as who uploaded, edited, claimed, released or deleted a YAML. New entries also keep structured account and YAML references so an account deletion can remove the right history without relying only on the message text.

Starting the destructive account flow is limited to five attempts per 15 minutes. The current window time and count are stored against your account only to enforce that limit, are included in your account export, and disappear with the account.

### Operational request logs

The application keeps a small rotating server log so failures and attacks can be diagnosed. A request line contains the time, request method, path, HTTP version, response status, response size and duration. Query strings, browser User-Agent strings, referrers and account ids are deliberately excluded; this also keeps Discord OAuth codes out of the log. The application container is capped at three log files of 10 MB each rather than keeping an unlimited history.

## Why the site is allowed to do this

The analytics log is processed on the basis of legitimate interest (Article 6(1)(f) GDPR): understanding whether a hobby site's own pages work is a genuine interest, the data is minimised to the point where it identifies almost nobody, and none of it is shared or used to target anyone. Your account data is processed to perform the service you signed up for (Article 6(1)(b)).

## Opting out

If your browser sends a Global Privacy Control (`Sec-GPC`) or Do Not Track (`DNT`) signal, the site honours it: events from that request are recorded with no account id and no visit value, which reduces them to an anonymous counter that cannot be tied back to you. You do not need to ask, and nothing on the site stops working.

## How long it is kept

Raw analytics rows are deleted automatically after 180 days. Builder rows carrying an attempt value are deleted after 30 days. What survives is a daily table of counts per event type and traffic class, which contains no account ids, room ids, visit values, or attempt values.

Your account and the things you create are kept until you delete them or schedule account deletion. Scheduling deletion locks the account immediately and starts a seven-day recovery period. No account data is removed during those seven days: signing in again with the same Discord identity lets you cancel the request. After the displayed deadline, the account and the personal content controlled by Archipelago Pie are permanently deleted from the live service and can no longer be restored through the site.

Encrypted database backups are kept for 14 days and are not edited in place. A short-lived erasure receipt containing the internal account id, owned seed ids and deletion time is kept outside the database for 16 days, giving the nightly rotation enough overlap to remove the last older dump. If an older backup is restored, that receipt makes the service reapply the deletion before reopening the account. The receipt is removed after that overlap once deletion and file cleanup are confirmed.

If room creation was blocked for abuse prevention when an account is deleted, the site keeps a keyed, pseudonymous form of the Discord id for up to 180 days so deleting and recreating the account does not bypass the block. It is not used for analytics or advertising and cannot be used without the server-side key. It is still personal data, not anonymous data.

Deleting an account cannot recall YAMLs, patches or ZIP files that another person already downloaded, and it does not delete data held independently by Discord, GitHub or another external service.

## Other services involved

- **Cloudflare** sits in front of the site to serve it and block attacks, and provides basic visitor counts at the network level. Cloudflare's own analytics work without cookies.
- **Discord** handles login, if you choose to sign in.
- **Hetzner** hosts the server, in Germany.
- **GitHub** hosts the downloads. Clicking a download link sends you to GitHub, and GitHub sees that request.
- **YouTube** videos on guide pages do not load until you click them. Nothing is requested from Google before that click.

## Your rights

The Account tab in the My area lets you download a copy of your AP-Pie account data and schedule deletion. You can also ask for a copy, correction or deletion, object to the analytics processing, or raise an exceptional request directly with Appie (Dowlle) on Discord. Requests are normally handled within a few days. If you are unhappy with the outcome you can complain to the Dutch Data Protection Authority, the Autoriteit Persoonsgegevens.

## Changes

If what the site records changes, this page changes in the same release. The date at the top says when that last happened.

Archipelago Pie is run by one person as a hobby project. This page explains exactly what the site records, what it deliberately does not record, and what you can ask for. It is written to be checkable: everything described here corresponds to code you can read in the public repository at [github.com/dowlle/ap-pie](https://github.com/dowlle/ap-pie).

**Last updated:** 2026-08-17

## The short version

There is no cookie banner on this site because there is nothing to consent to. No advertising, no third-party analytics scripts, no tracking pixels, no cross-site profiles, no data sold or shared with anyone. The site keeps a small log of what happens on it, stripped of anything that identifies you.

## Who is responsible

Archipelago Pie is operated by Dowlle, an individual developer in the Netherlands. For any question or request about your data, contact Appie (Dowlle) on Discord.

## What the site records

### Analytics events

The site keeps a server-side log of things that happen on it, so its own funnel can be improved: which guides get read, which games people open the YAML builder for, why a YAML submission was rejected, whether a login round-trip finished, whether a download link was used. Each entry holds:

- what happened, as a short code such as `guide_view` or `submit_rejected`
- when it happened
- the page path it happened on
- which page on this site you came from, as a bare path such as `/guides/ctr`. If you arrived from somewhere else on the internet, the record says only the word `external`; the address you came from is discarded and never stored, because it can contain search terms
- a two-letter country code, supplied by Cloudflare
- whether the device looked like a desktop, a mobile, or a bot
- a small set of technical details for that event type, such as a game name, a version number, a rejection reason code, whether a YAML was hand-edited rather than built from the form, or that a community preset was used
- your account id, **only if you were signed in**

That is the whole record. In particular it does **not** contain:

- **your IP address.** It is used momentarily to apply rate limits and is never written to the database
- **your browser's User-Agent string.** Only the three-way desktop / mobile / bot classification is kept
- **any tracking identifier on your device.** No analytics cookie, no localStorage, no sessionStorage, no fingerprint. To measure how far people get in a single visit, the page generates a random value that lives only in the browser tab's memory and disappears the moment you reload or close it. It cannot connect two visits, two devices, or two browsers
- **the address of the site that sent you here**, when that site is not this one. Only the word `external` is recorded
- **the contents of anything you write.** YAML files, room names, room descriptions and player names never enter the analytics log

Because the visit value cannot survive a page load, the log has no concept of a session. It can say that fifty people arrived at a page from a guide; it cannot follow one person from one page to the next. That limitation is deliberate, and it is what the site gives up in exchange for having no cookie banner.

If you are signed in, page views on the guides and the Crash Team Racing pages are recorded with your account id, the same as the rest of your activity on the site. Signed out, they are not linked to anything.

### Signing in with Discord

If you sign in, the site stores your Discord user id and display name so it can show you as the owner of your rooms and submissions, and sets one session cookie so you stay signed in. That cookie is strictly necessary for the login to work and is used for nothing else. Signing in is optional: rooms can be viewed, YAMLs can be built and submitted, and everything on the guides and downloads pages works without an account.

### Things you create

Rooms you host and YAML files you submit are stored so the site can do its job. Those are visible to the room's host and, depending on the room's settings, to other players in that room.

## Why the site is allowed to do this

The analytics log is processed on the basis of legitimate interest (Article 6(1)(f) GDPR): understanding whether a hobby site's own pages work is a genuine interest, the data is minimised to the point where it identifies almost nobody, and none of it is shared or used to target anyone. Your account data is processed to perform the service you signed up for (Article 6(1)(b)).

## Opting out

If your browser sends a Global Privacy Control (`Sec-GPC`) or Do Not Track (`DNT`) signal, the site honours it: events from that request are recorded with no account id and no visit value, which reduces them to an anonymous counter that cannot be tied back to you. You do not need to ask, and nothing on the site stops working.

## How long it is kept

Raw analytics rows are deleted automatically after 180 days. What survives is a daily table of counts per event type, which contains no account ids, no room ids and nothing relating to an identifiable person. Your account and the rooms and YAMLs you create are kept until you ask for them to be removed.

## Other services involved

- **Cloudflare** sits in front of the site to serve it and block attacks, and provides basic visitor counts at the network level. Cloudflare's own analytics work without cookies.
- **Discord** handles login, if you choose to sign in.
- **Hetzner** hosts the server, in Germany.
- **GitHub** hosts the downloads. Clicking a download link sends you to GitHub, and GitHub sees that request.
- **YouTube** videos on guide pages do not load until you click them. Nothing is requested from Google before that click.

## Your rights

You can ask for a copy of the data held about you, ask for it to be corrected, ask for it to be deleted, or object to the analytics processing. Ask Appie (Dowlle) on Discord and it will be handled directly, normally within a few days. If you are unhappy with the outcome you can complain to the Dutch Data Protection Authority, the Autoriteit Persoonsgegevens.

## Changes

If what the site records changes, this page changes in the same release. The date at the top says when that last happened.

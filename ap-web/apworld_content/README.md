# Reviewed APWorld metadata

This directory is AP-Pie's reviewed editorial overlay for the upstream
Archipelago index. It does not replace the index and it does not contain player
YAML files. Each direct child TOML file describes one integration using its
stable upstream `apworld_name`.

The loader in `apworld_editorial.py` reads only TOML files in this directory,
not nested directories. `fixtures-invalid/` deliberately holds rejected test
examples and must never be copied into the live root.

## What belongs here

- Source records: URL, source kind, optional immutable revision and date checked.
- Small atomic claims, each connected to its source IDs and applicable versions.
- Review state, reviewer and next review date.
- An explicit route override when AP-Pie already has a better authority page.

## What does not belong here

- Copied README, wiki or guide paragraphs.
- Guessed platform, maintainer, compatibility or setup details.
- A player YAML, generated file or APWorld package.
- An unqualified setup-guide promise derived from the upstream index.

Published prose is independently written from the reviewed claims. It must not
follow a source's sentence order or distinctive wording. Technical identifiers,
filenames, commands and versions may be exact when accuracy requires them.

## States and publication

No TOML file means `absent`. A file may be `draft`, `reviewed`, `stale`, or
`retired`. Only a `reviewed` record with `publication_status = "published"`,
an approved-original copy review, and a qualifying source may expose a
production detail route or reviewed catalogue signal. Stale and retired records
cannot publish.

`publication_status = "beta_preview"` is deliberately not production-public.
The default loader join withholds it. A beta-only route must explicitly opt in
with `include_beta_previews=True` and set its own `noindex, nofollow` response
metadata. A beta preview is a review surface, not a promotion shortcut.

Run the focused validator with:

```sh
PYTHONPATH=ap-web python3 scripts/test_apworld_editorial.py
```

The future API integration point is `join_index_record()` in
`apworld_editorial.py`. It intentionally keeps `index`, `editorial`, and
`review_state` in separate namespaces.

"""CTR custom-track name registry (intake, review and read API).

AP-Pie holds the submission queue, Stef's review and the read API. The record
that apworld builds pin is a public CTR-owned registry repository; `export.py`
writes that repository's file layout to a local directory. Generation and the
native client never call this module.

Design: the vault note "CTR custom-track name registry - 2026-10-13".
Everything here sits behind config.FEATURES["ctr_registry"].

Layout:
- rules.py     pure rules: ids, titles, clash suffixes, freeze, validation, limits
- migrations.py  append-only idempotent UP statements and the reversible DOWN
- store.py     Postgres access
- saphi.py     candidate import from Project Saphi's public v2 track endpoints
- hashing.py   hook for the later Atlas CTR-verifier step
- export.py    registry repository file layout, written to a local directory
- seed.py      load a registry directory into the database (the repository is the record)
- check.py     stdlib-only registry checker (copied into the export as tools/)
- notify.py    Home Assistant push (stub unless configured)
- cli.py       `python -m ctr_registry.cli ...` for the Atlas-side jobs
"""

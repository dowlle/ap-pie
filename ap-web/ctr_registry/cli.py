"""Atlas-side jobs for the registry: `python -m ctr_registry.cli <command>`.

    import-saphi [--limit N]   read Saphi's public track endpoints, add candidates
    export DIR                 write the registry repository files to DIR
    seed-from-registry DIR [--dry-run]  load a registry directory into the database
    pending-hashes             list revisions waiting for the CTR verifier
    attach-evidence FILE       store one verifier result (see ctr_registry.hashing)
    migrate-down --yes         drop the registry tables (reversible UP is automatic)

Needs DATABASE_URL. Each command prints one JSON document.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ctr_registry.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("import-saphi")
    p.add_argument("--limit", type=int)
    p = sub.add_parser("export")
    p.add_argument("out_dir")
    p = sub.add_parser("seed-from-registry")
    p.add_argument("registry_dir")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("pending-hashes")
    p = sub.add_parser("attach-evidence")
    p.add_argument("file")
    p = sub.add_parser("migrate-down")
    p.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    import db
    db.init_db(os.environ["DATABASE_URL"])
    from ctr_registry import export, hashing, migrations, saphi, seed, store

    if args.cmd == "import-saphi":
        out = saphi.run_import(limit=args.limit)
    elif args.cmd == "export":
        out = export.write_export(store.record_entries(), args.out_dir)
    elif args.cmd == "seed-from-registry":
        try:
            out = seed.seed_from_directory(args.registry_dir, dry_run=args.dry_run)
        except seed.SeedError as exc:
            print(json.dumps({"error": "seed refused", "problems": exc.problems}, indent=2), file=sys.stderr)
            return 1
    elif args.cmd == "pending-hashes":
        out = store.json_safe(hashing.pending())
    elif args.cmd == "attach-evidence":
        out = store.json_safe(hashing.attach_from_file(args.file))
    else:
        if not args.yes:
            print("migrate-down drops the registry tables and their rows; pass --yes", file=sys.stderr)
            return 2
        conn = db._get_conn()
        with conn.cursor() as cur:
            migrations.apply_down(cur)
        conn.commit()
        out = {"dropped": list(migrations.TABLES)}
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

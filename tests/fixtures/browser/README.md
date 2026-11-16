# Browser fixtures

The local Flask browser harness uses these files instead of fetching the live index or downloading APWorld releases. The index files and selected lock entries are copied from `dowlle/Archipelago-index` at `689cfc865defbfcf4ed913195373e4ea440090bb`. They cover custom and built-in worlds, long names, a slash-bearing version and a retired world. Other catalog states are mocked by the specs.

The schema JSON files contain parser format 10 output from the checksum-verified CTR 0.1.5 and Pokepelago 0.6.3 archives. Each records its source release URL and the archive checksum from that index commit. Archive code is never executed. The harness inserts the schemas into the real database cache and rejects cold archive fetches. Update the fixtures deliberately when changing the schema format, retaining source URLs and checksums.

After installing Python dependencies from `ap-web/requirements.txt` and `./ap-lib`, run `npm ci --include=dev`, `npm run build` and `npx playwright install chromium` in `ap-web/frontend`. Start a disposable local Postgres database, then run from the repository root:

```sh
BROWSER_TEST_DATABASE_URL=postgresql://archipelago:browser-test-only@localhost:5432/archipelago python scripts/run_browser_tests.py
```

The database is migrated and schema-cache fixtures are inserted. Never point this at a database you want to keep. Only loopback database hosts are accepted. The test server uses an ephemeral port and shuts down before the command returns. The temporary local index clone and runtime files are removed. Playwright results go to `ap-web/frontend/test-results/`.

The beta label enables the style guide; the public canonical origin remains `https://ap-pie.com`. Timberborn is disabled explicitly so its unfinished release does not enter unrelated SEO assertions. Discord uses dummy local settings. No sign-in request is sent to Discord. Additional Playwright arguments can follow the script name.

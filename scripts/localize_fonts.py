"""Turn the Google Fonts css2 response into a self-hosted stylesheet.

Reads gf.css (fetched with a woff2-capable UA), downloads every referenced
woff2 into ap-web/frontend/public/fonts/, and writes src/fonts.css with the
identical @font-face declarations pointing at the local copies.
"""
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

SRC = Path(sys.argv[1])
PUBLIC = Path(sys.argv[2])
OUT = Path(sys.argv[3])

css = SRC.read_text()

block_re = re.compile(
    r"/\* (?P<subset>[a-z-]+) \*/\s*@font-face \{(?P<body>.*?)\}", re.S
)

blocks = []
for m in block_re.finditer(css):
    body = m.group("body")
    family = re.search(r"font-family: '([^']+)'", body).group(1)
    weight = re.search(r"font-weight: (\d+)", body).group(1)
    url = re.search(r"src: url\((https://[^)]+)\)", body).group(1)
    blocks.append(
        {"subset": m.group("subset"), "body": body, "family": family,
         "weight": weight, "url": url}
    )

if not blocks:
    raise SystemExit("no @font-face blocks parsed")

# One woff2 file can back several declared weights (variable fonts), so name
# files by what they actually are rather than by the first rule that hit them.
weights_per_url = defaultdict(set)
for b in blocks:
    weights_per_url[b["url"]].add(b["weight"])

def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

names = {}
for b in blocks:
    if b["url"] in names:
        continue
    weights = weights_per_url[b["url"]]
    tail = "variable" if len(weights) > 1 else next(iter(weights))
    names[b["url"]] = f"{slug(b['family'])}-{b['subset']}-{tail}.woff2"

PUBLIC.mkdir(parents=True, exist_ok=True)
total = 0
for url, name in names.items():
    dest = PUBLIC / name
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    dest.write_bytes(data)
    total += len(data)

lines = [
    "/* Self-hosted copy of the type system.",
    " *",
    " * Generated from the Google Fonts css2 response for:",
    " *   Bricolage Grotesque 500/800, Inter Tight 400-700, JetBrains Mono 400/500",
    " *",
    " * The declarations are byte-for-byte the ones Google serves (same weights,",
    " * same font-display, same unicode-range subsetting) with the src rewritten",
    " * to /fonts/. Hosting them ourselves removes a render-blocking stylesheet",
    " * on a third-party origin from the critical path: the browser no longer has",
    " * to resolve DNS, complete a TLS handshake and parse a remote stylesheet",
    " * before it can paint. All three families are SIL Open Font License 1.1.",
    " *",
    " * To refresh, re-run scripts/localize_fonts.py against a fresh css2 fetch.",
    " */",
    "",
]
for b in blocks:
    body = b["body"].replace(b["url"], f"/fonts/{names[b['url']]}")
    lines.append(f"/* {b['subset']} */")
    lines.append("@font-face {" + body + "}")
OUT.write_text("\n".join(lines) + "\n")

print(f"{len(names)} files, {total / 1024:.1f} KiB -> {PUBLIC}")
print(f"{len(blocks)} @font-face rules -> {OUT}")

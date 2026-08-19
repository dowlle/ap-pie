#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

state_dir="${AP_PIE_CF_STATE_DIR:-/var/lib/ap-pie-origin-firewall}"
state_file="$state_dir/cloudflare-ranges"
temporary="$(mktemp)"
trap 'rm -f "$temporary"' EXIT

curl --fail --silent --show-error https://www.cloudflare.com/ips-v4 > "$temporary.v4"
curl --fail --silent --show-error https://www.cloudflare.com/ips-v6 > "$temporary.v6"
cat "$temporary.v4" > "$temporary"
printf '\n' >> "$temporary"
cat "$temporary.v6" >> "$temporary"
printf '\n' >> "$temporary"
rm -f "$temporary.v4" "$temporary.v6"

python3 - "$temporary" <<'PY'
import ipaddress
import pathlib
import sys

rows = [line.strip() for line in pathlib.Path(sys.argv[1]).read_text().splitlines() if line.strip()]
networks = [ipaddress.ip_network(row, strict=True) for row in rows]
if len({str(network) for network in networks}) != len(networks):
    raise SystemExit("duplicate Cloudflare network")
if sum(network.version == 4 for network in networks) < 10:
    raise SystemExit("implausibly short Cloudflare IPv4 list")
if sum(network.version == 6 for network in networks) < 5:
    raise SystemExit("implausibly short Cloudflare IPv6 list")
PY

install -d -m 700 "$state_dir"
touch "$state_file"

# Add the complete new allowlist before removing anything. A failed refresh
# therefore leaves the prior working rules in place rather than exposing or
# taking down the origin.
while IFS= read -r network; do
    [[ -n "$network" ]] || continue
    ufw allow proto tcp from "$network" to any port 80,443 \
        comment 'AP-Pie Cloudflare origin' >/dev/null
done < "$temporary"

while IFS= read -r network; do
    [[ -n "$network" ]] || continue
    if ! grep -Fxq "$network" "$temporary"; then
        ufw --force delete allow proto tcp from "$network" to any port 80,443 >/dev/null
    fi
done < "$state_file"

install -m 600 "$temporary" "$state_file"

# Remove the legacy world-open rules only after the allowlist is installed.
ufw --force delete allow 80/tcp >/dev/null 2>&1 || true
ufw --force delete allow 443/tcp >/dev/null 2>&1 || true

#!/bin/sh
# Fix ownership of mounted volumes (created as root by Docker)
chown -R apweb:apweb /app/.state /opt/archipelago-custom/worlds 2>/dev/null || true

exec gosu apweb "$@"

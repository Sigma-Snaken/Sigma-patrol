#!/bin/sh
set -e

# Fix ownership of mounted volumes (they may be created as root by Docker)
chown -R appuser:appuser /app/data /app/logs 2>/dev/null || true

# Drop privileges and exec the main process
exec gosu appuser "$@"

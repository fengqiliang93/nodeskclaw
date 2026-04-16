#!/bin/sh
ENV_FILE="/host-config/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    . "$ENV_FILE"
    set +a
fi
exec "$@"

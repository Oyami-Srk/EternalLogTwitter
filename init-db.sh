#! /usr/bin/env bash
secs=${wait_seconds:-10}
echo "Wait $secs seconds for DB startup..."
sleep $secs
exec alembic upgrade head

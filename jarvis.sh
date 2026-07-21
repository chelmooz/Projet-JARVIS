#!/usr/bin/env bash
# JARVIS Portable — redirection vers le lanceur principal
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/launchers/JARVIS.sh" "$@"

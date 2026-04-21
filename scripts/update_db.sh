#!/usr/bin/env bash
set -e

help() {
    echo "Update the database definitions"
    echo ""
    echo "Usage:"
    echo "  $0 [-f|--force] <update_description>"
    echo ""
    echo "Args:"
    echo "  -f|--force  Update and upgrade the database."
    echo ""
}

opts=$(getopt -o fh --long force,help -- "$@") || exit 1
eval set -- "$opts"

FORCE=0
while true; do
    case "$1" in
        -f|--force)
            FORCE=1;
            shift ;;
        -h|--help)
            help;
            exit 0 ;;
        --)
            shift;
            break ;;
    esac
done

description="$1"
while [ -z "$description" ]; do
    read -rp "Update description: " description
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")/backend"

cd "$BACKEND_DIR"
alembic revision --autogenerate -m "$description"

if [ $FORCE -eq 1 ]; then
    alembic upgrade head
fi
#!/bin/sh
# Pull the generated dakit tokens and fonts from a sibling dakit checkout.
#
# Dakit is the shared design system (github: ../dakit): tokens in, CSS out.
# This app vendors its build output — dakit-tokens.css plus the self-hosted
# fonts — rather than depending on it at runtime; there is no build step here
# to resolve a package. Re-run after pulling dakit and rebuild it first:
#
#   (cd ../dakit && node build.mjs) && scripts/sync_dakit.sh
#
# Commit the vendored files together with whatever app change adapts to them.
set -e
here=$(cd "$(dirname "$0")" && pwd)
dakit="${1:-$here/../../dakit}"
web="$here/../src/web"

test -f "$dakit/dist/tokens.css" || { echo "dakit build output not found at $dakit/dist — run node build.mjs there" >&2; exit 1; }

cp "$dakit/dist/tokens.css" "$web/dakit-tokens.css"
mkdir -p "$web/fonts"
cp "$dakit/fonts/"*.woff2 "$dakit/fonts/LICENSE.md" "$web/fonts/"

echo "synced dakit-tokens.css and fonts/ from $dakit"

#!/bin/sh
# Pull the generated dakit CSS and fonts from a sibling dakit checkout.
#
# Dakit is the shared design system (github: ../dakit): tokens in, CSS out.
# This app vendors its build output — the tokens, the base layer, the .dk-*
# component classes, and the self-hosted fonts — rather than depending on it
# at runtime; there is no build step here to resolve a package. Re-run after
# pulling dakit and rebuild it first:
#
#   (cd ../dakit && node build.mjs) && scripts/sync_dakit.sh
#
# The base layer ships from css/base.css with one edit: its @font-face URLs
# are relative to dakit's dist/ ("../fonts/…"), and this app serves the fonts
# from /assets/fonts/ next to the stylesheet, so the prefix is rewritten to
# "fonts/…". Nothing else in the layer is touched.
#
# Commit the vendored files together with whatever app change adapts to them.
set -e
here=$(cd "$(dirname "$0")" && pwd)
dakit="${1:-$here/../../dakit}"
web="$here/../src/web"

test -f "$dakit/dist/tokens.css" || { echo "dakit build output not found at $dakit/dist — run node build.mjs there" >&2; exit 1; }
test -f "$dakit/css/base.css" && test -f "$dakit/css/components.css" || { echo "dakit css/ layers not found — pull a current dakit" >&2; exit 1; }

cp "$dakit/dist/tokens.css" "$web/dakit-tokens.css"
sed 's|\.\./fonts/|fonts/|g' "$dakit/css/base.css" > "$web/dakit-base.css"
cp "$dakit/css/components.css" "$web/dakit-components.css"
mkdir -p "$web/fonts"
cp "$dakit/fonts/"*.woff2 "$dakit/fonts/LICENSE.md" "$web/fonts/"

echo "synced dakit-tokens.css, dakit-base.css, dakit-components.css and fonts/ from $dakit"

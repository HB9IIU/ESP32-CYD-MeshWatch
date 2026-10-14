#!/usr/bin/env bash
# Assembles the web flasher site (published to GitHub Pages) from the PlatformIO
# build output. Used by the GitHub workflow and for local testing.
#
# Usage: tools/build_site.sh <version>     e.g. tools/build_site.sh 1.0.0
# Output: site/index.html, site/manifest.json, site/firmware/meshwatch-<version>.bin
set -euo pipefail

version="${1:?usage: tools/build_site.sh <version>}"
root="$(cd "$(dirname "$0")/.." && pwd)"
build="$root/.pio/build/esp32-cyd"
site="$root/site"
image="$build/firmware.factory.bin"  # bootloader + partitions + boot_app0 + app, flashed at 0x0

if [[ ! -f "$image" ]]; then
  echo "Missing $image - run 'pio run -e esp32-cyd' first" >&2
  exit 1
fi

rm -rf "$site"
mkdir -p "$site/firmware"
cp "$root/web/index.html" "$root/web/splash.png" "$site/"
cp "$image" "$site/firmware/meshwatch-$version.bin"

cat > "$site/manifest.json" <<EOF
{
  "name": "MeshWatch",
  "version": "$version",
  "new_install_prompt_erase": true,
  "builds": [
    {
      "chipFamily": "ESP32",
      "parts": [{ "path": "firmware/meshwatch-$version.bin", "offset": 0 }]
    }
  ]
}
EOF

echo "Site ready in $site (version $version)"

#!/bin/sh
# Build the app zip: build/app.zip. Needs only `zip`.
set -eu
cd "$(dirname "$0")"
mkdir -p build
rm -f build/app.zip
zip -qr build/app.zip manifest source components data images -x '*.DS_Store'
echo "build/app.zip"

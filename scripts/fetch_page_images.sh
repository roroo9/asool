#!/bin/sh
# Page images for running Asool locally. They are not in the repository (the 1956 typesetting's
# copyright is unverified), so this downloads the public scan from archive.org (item `rsnawwy`,
# file rs-mohaqaq.pdf), renders printed pages 12-41 and copies the web versions to
# web/public/pages/. Everything stays on your machine (data/raw and data/pages are git-ignored).
set -e
cd "$(dirname "$0")/.."
mkdir -p data/raw web/public/pages
if [ ! -f data/raw/rs-mohaqaq.pdf ]; then
  curl -fL -o data/raw/rs-mohaqaq.pdf https://archive.org/download/rsnawwy/rs-mohaqaq.pdf
fi
uv run python -m pipeline.rasterize
cp data/pages/*.webp web/public/pages/
echo "page images ready: $(ls web/public/pages/*.webp | wc -l | tr -d ' ') files in web/public/pages"

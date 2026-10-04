#!/bin/sh
# Download reference data that we do not redistribute in the repo.
set -e
cd "$(dirname "$0")/.."
D=data/reference/quran/kfgqpc
if [ ! -f "$D/hafs_v30/kfgqpc_hafs_v30-data/kfgqpc_hafs_v30.json" ]; then
  mkdir -p "$D"
  curl -sSL -o "$D/hafs.zip" https://download.qurancomplex.gov.sa/resources_dev/kfgqpc_hafs_v30.zip
  unzip -o -q "$D/hafs.zip" -d "$D/hafs_v30" && rm "$D/hafs.zip"
fi
echo "references ready"

#!/usr/bin/env bash
# Drive batch_menus.py one venue per subprocess so GNU timeout can hard-kill
# a hung host. In-process signal.alarm was unreliable: library code swallowed the
# exception and a single slow PDF stalled the whole queue.
set -u
cd /opt/thaidata-repo
PY=/root/.hermes/installs/76f6e7e5145b5f39/environments/644bcace9cc140448341e2379c3152ce/venv/bin/python3
START=${1:-1}
END=${2:-329}
LOG=/tmp/menu_batch/driver.log
for i in $(seq "$START" "$END"); do
  out=$(timeout -k 10 120 "$PY" scripts/batch_menus.py --only "$i" 2>&1 | grep -E '^\[' || true)
  if [ -z "$out" ]; then
    out="[$i/329] (timeout or crash)"
  fi
  echo "idx=$i $out" >> "$LOG"
  echo "idx=$i $out"
done
echo "DRIVER DONE" >> "$LOG"

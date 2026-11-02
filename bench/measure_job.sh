#!/bin/bash
# Time one image from `docker run` to exit, the way the job really runs it. Usage: measure_job.sh IMAGE AUDIO_DIR OUT.tsv [REPEATS]
# AUDIO_DIR holds he-5s.ogg, he-60s.ogg, en-5s.ogg, en-60s.ogg from make_timing_clips.py. Every line records the load average. SHORT=1 runs two of the cases.
set -euo pipefail
image=$1; audio=$(cd "$2" && pwd); out=$3; repeats=${4:-3}
run() {  # label file language...
  label=$1; file=$2; shift 2
  for i in $(seq "$repeats"); do
    load=$(cut -d' ' -f1 /proc/loadavg)
    t0=$(date +%s.%N)
    json=$(docker run --rm --network none --read-only --cap-drop ALL -v "$audio:/in:ro" "$image" "/in/$file" "$@" 2>/dev/null)
    t1=$(date +%s.%N)
    printf '%s\t%s\t%.2f\t%s\t%s\t%s\n' "$image" "$label" "$(echo "$t1 - $t0" | bc)" \
      "$(jq -r .peak_memory_mb <<<"$json")" "$(jq -r .model <<<"$json")/$(jq -r .language <<<"$json")" "$load" >> "$out"
  done
}
run he-5s-given he-5s.ogg he
run en-60s-given en-60s.ogg en
[ -n "${SHORT:-}" ] && exit 0  # enough to compare candidates
run he-60s-given he-60s.ogg he
run en-5s-given en-5s.ogg en
run he-5s-auto he-5s.ogg
run en-5s-auto en-5s.ogg

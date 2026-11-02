#!/bin/bash
# Print an image's sizes in MB: files inside it, what `docker images` shows, compressed download (docker save | gzip -1).
image=$1
files=$(docker run --rm --entrypoint sh --network none "$image" -c 'du -smx / 2>/dev/null | cut -f1')
shown=$(docker image inspect "$image" --format '{{.Size}}'); gz=$(docker save "$image" | gzip -1 | wc -c)
printf '%s\tfiles=%s\tdocker_images=%s\tcompressed=%s\n' "$image" "$files" "$((shown / 1000000))" "$((gz / 1000000))"

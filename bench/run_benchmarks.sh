#!/bin/bash
# Reproduce the README's measurements. Usage: bench/run_benchmarks.sh SCRATCH_DIR   (run from the repository root)
# Needs Docker, jq, bc, about 40 GB of disk, and many hours on 4 cores: every clip costs a full 30 s encoder pass.
# Re-running resumes: finished clips are skipped.
set -euo pipefail
S=$(mkdir -p "$1" && cd "$1" && pwd); R=$PWD
OTHERS=en,es,pt,ar,ru,fr
bench/fetch_data.sh "$S"
mkdir -p "$S/work/out" "$S/work/hf" "$S/work/timing"; chmod -R a+rwX "$S/work"
python3 -I bench/prepare_real.py "$S/data" "$S/work" --clips bench/clips.tsv

docker build -t whisper-bench:tts -f bench/tts.Dockerfile bench
docker run --rm --user 65532 -e HF_HOME=/work/hf -e HOME=/tmp -v "$R/bench:/bench:ro" -v "$S/work:/work" \
  whisper-bench:tts python -I /bench/generate_tts.py /bench/sentences.json /work

printf 'FROM python:3.12-slim\nRUN pip install --no-cache-dir faster-whisper==1.2.1 av==19.0.2 ctranslate2==4.8.4 onnxruntime==1.31.1 requests==2.34.2 tokenizers==0.23.3 huggingface_hub==2.4.0 numpy==2.5.4\n' \
  | docker build -t whisper-bench:libs -

run() {  # model output [run_models.py arguments]
  m=$1; o=$2; shift 2
  docker run --rm --network none --read-only --user 65532 -v "$R/bench:/bench:ro" -v "$S/models/$m:/model:ro" \
    -v "$S/work:/work:ro" -v "$S/work/out:/out" whisper-bench:libs python -I /bench/run_models.py --model-dir /model \
    --name "$m" --manifest "/work/${MANIFEST:-manifest.jsonl}" --root /work/clips --out "/out/$o" --threads "${THREADS:-4}" "$@"
}

# Real speech. The clip order is fixed, so a smaller limit is a subset of a larger one.
for m in small medium turbo large-v3 ivrit-turbo ivrit-large-v3 ivrit-v2-d4; do run "$m" "$m.jsonl" --langs he --limit 40 --detect-limit 10; done
run ivrit-turbo ivrit-turbo.jsonl --langs he --limit 200
run turbo turbo.jsonl --langs he --limit 50
run small small.jsonl --langs "$OTHERS" --limit 50 --detect-limit 25
run turbo turbo.jsonl --langs "$OTHERS" --limit 20 --detect-limit 15
run ivrit-turbo ivrit-turbo.jsonl --langs "$OTHERS" --limit 5 --detect-limit 5
for m in medium large-v3; do run "$m" "$m.jsonl" --langs "$OTHERS" --limit 5; done

# Generated speech.
export MANIFEST=manifest-mms.jsonl
for m in turbo small ivrit-turbo; do run "$m" "mms-$m.jsonl"; done
for m in medium large-v3 ivrit-large-v3 ivrit-v2-d4; do run "$m" "mms-$m.jsonl" --langs he,en; done
unset MANIFEST

# Timing, memory and size of the real images. Run this part on a quiet machine, and repeat what ran under load.
docker build -t whisper-job .
docker build -t whisper-job:general --build-arg HEBREW_REPO= .
docker build -t whisper-job:small --build-arg GENERAL_REPO=openai/whisper-small \
  --build-arg GENERAL_REV=973afd24965f72e36ca33b3055d56a652f456b4d --build-arg HEBREW_REPO= .
docker run --rm --network none --user 65532 --entrypoint python -v "$R/bench:/bench:ro" -v "$S/work:/work" whisper-job -I /bench/make_timing_clips.py /work
bench/measure_job.sh whisper-job "$S/work/timing" "$S/timing.tsv" 3
for i in whisper-job:general whisper-job:small; do SHORT=1 bench/measure_job.sh "$i" "$S/work/timing" "$S/timing.tsv" 3; done
for i in whisper-job whisper-job:general whisper-job:small; do bench/image_size.sh "$i"; done
for m in small medium turbo large-v3 ivrit-turbo ivrit-large-v3 ivrit-v2-d4; do
  c=$(mktemp -d); cp transcribe.py "$c/"; cp -r "$S/models/$m" "$c/model"
  docker build -t "whisper-bench:$m" -f bench/candidate.Dockerfile "$c"; rm -rf "$c"
  SHORT=1 bench/measure_job.sh "whisper-bench:$m" "$S/work/timing" "$S/timing.tsv" 3
  bench/image_size.sh "whisper-bench:$m"
done

# The int8 models in the image, against the original conversions.
id=$(docker create whisper-job)
docker cp "$id:/model/general" "$S/models/turbo-int8"; docker cp "$id:/model/he" "$S/models/ivrit-turbo-int8"; docker rm "$id"
run ivrit-turbo-int8 ivrit-turbo-int8.jsonl --langs he --limit 25
run turbo-int8 turbo-int8.jsonl --langs en,es --limit 10

python3 -I bench/score.py "$S/work" --md --json "$S/results.json"

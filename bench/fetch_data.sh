#!/bin/bash
# Download the public test sets and the candidate models. Usage: fetch_data.sh SCRATCH_DIR. About 6 GB of audio and 13 GB of models.
# No account or token is needed. The audio is not part of this repository.
set -euo pipefail
S=$1; mkdir -p "$S/data" "$S/models"
FLEURS=70bb2e84b976b7e960aa89f1c648e09c59f894dd   # google/fleurs, CC BY 4.0
CV=ae911de250fe9375d08e2daa2105b671d659d446       # fsicoli/common_voice_22_0, an unofficial mirror of Common Voice 22.0, CC0
get() { curl -fsSL --retry 5 -o "$2" "$1"; }
for l in he_il en_us es_419 pt_br ar_eg ru_ru fr_fr; do
  d=$S/data/fleurs/$l; mkdir -p "$d"
  get "https://huggingface.co/datasets/google/fleurs/resolve/$FLEURS/data/$l/test.tsv" "$d/test.tsv"
  get "https://huggingface.co/datasets/google/fleurs/resolve/$FLEURS/data/$l/audio/test.tar.gz" "$d/test.tar.gz"
done
for l in he en es pt ar ru fr; do
  d=$S/data/cv22/$l; mkdir -p "$d"
  get "https://huggingface.co/datasets/fsicoli/common_voice_22_0/resolve/$CV/transcript/$l/test.tsv" "$d/test.tsv"
  get "https://huggingface.co/datasets/fsicoli/common_voice_22_0/resolve/$CV/audio/$l/test/${l}_test_0.tar" "$d/test.tar"
done
model() {
  d=$S/models/$1; mkdir -p "$d"
  for f in config.json model.bin tokenizer.json preprocessor_config.json vocabulary.json vocabulary.txt; do
    code=$(curl -sSL --retry 5 -o "$d/$f" -w '%{http_code}' "https://huggingface.co/$2/resolve/$3/$f")
    [ "$code" = 200 ] || rm -f "$d/$f"
  done
}
model small Systran/faster-whisper-small 536b0662742c02347bc0e980a01041f333bce120
model medium Systran/faster-whisper-medium 08e178d48790749d25932bbc082711ddcfdfbc4f
model turbo dropbox-dash/faster-whisper-large-v3-turbo 0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf
model large-v3 Systran/faster-whisper-large-v3 edaa852ec7e145841d8ffdb056a99866b5f0a478
model ivrit-turbo ivrit-ai/whisper-large-v3-turbo-ct2 72ad623a37947395efcc3933132353790e5a12f5
model ivrit-large-v3 ivrit-ai/whisper-large-v3-ct2 e9ed4a4a98d761b0f617d668303de2c514236c66
model ivrit-v2-d4 ivrit-ai/faster-whisper-v2-d4 45ef6dd536dfbf6e8633796157cad00f428142cc

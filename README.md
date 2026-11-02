# whisper-job

Whisper as a one-shot container. It starts when called, transcribes one audio file on the CPU with no network,
prints JSON and exits. Nothing stays running between jobs, so a rarely used transcription costs nothing while idle.

It is a Dockerfile and one small script around [faster-whisper](https://github.com/SYSTRAN/faster-whisper). The
models are inside the image, so nothing is downloaded when it runs.

The default image holds two models and picks by language: a Hebrew-tuned model for Hebrew, and OpenAI's
large-v3-turbo for every other language. The reasons, with the numbers, are under [Which model](#which-model).

## Build
| Variant | Command | Compressed download | Languages |
|---|---|---|---|
| Default, two models | `docker build -t whisper-job .` | 1.55 GB | Hebrew-tuned for `he`, turbo for the rest |
| No Hebrew model | `docker build -t whisper-job:general --build-arg HEBREW_REPO= .` | 864 MB | turbo for everything; Hebrew is clearly worse |
| Small | `docker build -t whisper-job:small --build-arg GENERAL_REPO=openai/whisper-small --build-arg GENERAL_REV=973afd24965f72e36ca33b3055d56a652f456b4d --build-arg HEBREW_REPO= .` | 395 MB | fastest, and much less accurate |

The build converts the models from their source weights to int8, which halves their size and did not measurably change
their accuracy. It needs the network, downloads several GB of weights and PyTorch, and took about 6.5 minutes here on
a busy machine. None of that ends up in the image. The source repository and revision are build arguments and are pinned.

## Run
```
docker run --rm --network none --read-only -v "$PWD/testdata:/in:ro" whisper-job /in/speech-3s.ogg en
```
```json
{"text": "This is a generated test message about the building.", "language": "en", "duration": 3.01, "model": "general", "load_seconds": 1.17, "transcribe_seconds": 7.66, "peak_memory_mb": 1634}
```
The first argument is the file (anything FFmpeg reads: Ogg/Opus, WebM, MP4/AAC, WAV). The second is the language
code, for example `he`. Give it when you know it: leaving it out costs about 8 s more, because the language is detected
with the general model, and for Hebrew the second model is then loaded.

`model` says which model did the work, `general` or `he`. The job runs as a non-root user and works with a read-only root and no network.

| Setting | Default | Meaning |
|---|---|---|
| `WHISPER_THREADS` | 0 (all cores) | CPU threads |
| `WHISPER_BEAM` | 5 | Beam size; lower is faster and may be less accurate |

The exit code is 0 on success. Errors go to stderr.

## Start it only when there is work
Something small watches for work and starts the container:
- **One machine:** `docker run --rm ...` per job.
- **Google:** a Cloud Run Job.
- **AWS:** an ECS `RunTask` or AWS Batch.
- **Kubernetes:** a Job, or KEDA scaling from zero on the queue's length.

## Accuracy
Word error rate (WER): lower is better. **These are real people reading sentences aloud**, from two public test sets.
Brackets are a 95% interval over the clips. Half the clips were read from a script on people's own devices (Common
Voice), half are read Wikipedia-style text (FLEURS).

| Language | Common Voice | clips | FLEURS | clips |
|---|---|---|---|---|
| Hebrew, `ivrit-turbo` | 9.7% [7.6-11.9] | 200 | 16.6% [14.2-19.1] | 200 |
| English, `turbo` | 10.1% [4.2-18.3] | 20 | 4.3% [2.5-6.4] | 20 |
| Spanish, `turbo` | 3.6% [0.5-7.8] | 20 | 3.9% [1.9-7.0] | 20 |
| Portuguese, `turbo` | 2.3% [0.0-5.6] | 20 | 2.9% [1.0-5.6] | 20 |
| Arabic, `turbo` | 11.5% [4.3-19.8] | 20 | 8.6% [4.4-13.8] | 20 |
| Russian, `turbo` | 4.6% [0.0-11.8] | 20 | 3.3% [1.4-5.6] | 20 |
| French, `turbo` | 20.1% [9.2-36.3] | 20 | 7.7% [3.1-13.3] | 20 |

Spanish, Portuguese and Russian come out well, English is good, and Arabic is usable but weaker.

**Read these with care:**
- **Hebrew** is measured on 400 clips. The other languages have only 40 each, so their intervals are wide and small
  differences between them mean nothing.
- **Hebrew on FLEURS (16.6%) is mediocre**: about one word in six is wrong. This text is full of foreign names and technical words.
- **French on Common Voice (20.1%) is mostly one clip**, which accounts for 18 of the 44 errors; its interval is 9-36%.
- **Common Voice Hebrew is thin:** its test set has 30 speakers and five of them gave 82% of its clips. The sample takes
  speakers in turn, and five of them still gave 65% of the 200 clips. Do not take it as representing Hebrew speakers in general.

**Not proven:** voice messages recorded on a phone in a noisy flat, or any noisy speech. People talking over each other,
accents and dialects, and speech mixing two languages (one model handles the whole file) were not measured either.
Long files with long silences were not tested.

## Which model
Hebrew, the same 40 clips per test set for all seven models:

| Model | Common Voice | FLEURS | Time per 5 s clip | Peak memory | Compressed image |
|---|---|---|---|---|---|
| `ivrit-turbo` | 5.4% | 17.0% | 10.9 s | 2.0 GB | 1.68 GB |
| `ivrit-large-v3` | 6.0% | 15.1% | 15.6 s | 3.8 GB | 3.04 GB |
| `ivrit-v2-d4` | 15.8% | 21.8% | 15.5 s | 3.8 GB | 3.04 GB |
| `turbo` | 15.8% | 26.9% | 10.9 s | 2.0 GB | 1.68 GB |
| `large-v3` | 18.1% | 24.3% | 15.7 s | 3.8 GB | 3.04 GB |
| `medium` | 22.8% | 30.6% | 8.4 s | 2.0 GB | 1.60 GB |
| `small` | 32.2% | 42.0% | 3.2 s | 0.7 GB | 0.63 GB |

(The 5.4% for `ivrit-turbo` was a lucky subset; on 200 clips it is 9.7%, as in the first table. On 40 clips per set, a difference of a few points is not meaningful.)

**The decision:**
- **Hebrew: `ivrit-turbo`.** On the larger samples it cuts Hebrew errors by about 40% against plain turbo, at the same
  speed (9.7% against 17.3% on Common Voice, 16.6% against 27.5% on FLEURS; the intervals do not overlap). `ivrit-large-v3` is
  within the noise of it and costs about 1.4 times the time and 1.8 times the size. `ivrit-v2-d4` is worse and cannot detect languages (0 of 20).
- **Everything else: `turbo`.** On the same 20 clips per set, it beat `small` in every language and set, often by half
  (the gap is smallest for English, and many intervals overlap). Against `medium` and `large-v3` the sample is too small to separate them (5 clips per set).
  `large-v3` takes more time on a short clip and 1.8 times the size, though it was faster on the one 60 s file (44 s against 50 s). `medium` is faster (8.4 s and 23 s) and
  clearly worse on Hebrew, but Hebrew has its own model here, so for the other languages `medium` remains an untested alternative.
- **Not one model for both:** `ivrit-turbo` cannot do other languages. On non-Hebrew real speech its WER was 40-117%, mostly output
  in Hebrew, and it detected every other language wrongly (0 of 60). Its own model card warns about this, and it is why only the
  general model detects the language.
- **One image, not two:** the point of the job is to take any language, and detecting then choosing needs both models together. If you only need
  one language family, use a smaller variant.

**The cost:** against `small`, the default takes 3 times as long on a short clip and 6 times on a minute of English, with 2-3 times the memory and 3.9 times the download.

### Speed, memory and size
Total time from `docker run` to exit, median of 3 runs, on 4 CPU cores shared with other work (load average 3-5; runs at
load 7-11 were discarded and repeated). Figures are good to about 10%. The model was already in the disk cache: a cold
disk, and a new machine that must download the image, will be slower.

| Default image | 5 s clip | 60 s of audio | Peak memory |
|---|---|---|---|
| Hebrew, language given | 9.8 s | 30.8 s | 1.6 GB |
| English, language given | 9.5 s | 52.9 s | 1.6 GB |
| Hebrew, detected | 18.0 s | not measured | 2.0 GB |
| English, detected | 17.6 s | not measured | 1.6 GB |

A 5 s clip costs a whole encoding pass, because Whisper always encodes a full 30 s window. The two 60 s files are different audio, so
that gap is not a difference between the languages.

It ran with `--memory=1700m` with the language given and `--memory=2100m` with Hebrew detected. Those are single runs: allow a margin.

| Image | Files inside | `docker images` | Compressed (`docker save \| gzip -1`) |
|---|---|---|---|
| **Default** (two int8 models) | 2.15 GB | 3.81 GB | 1.55 GB |
| No Hebrew model (one int8 model) | 1.37 GB | 2.30 GB | 864 MB |
| Small (int8) | 825 MB | 1.27 GB | 395 MB |

Small takes 3.1 s on the 5 s Hebrew clip and 8.6 s on 60 s of English, with a peak of 790 MB. Converted to int8, the turbo models
peak at 1.6 GB rather than 2.0 GB and finish a short clip about a second sooner. Their results matched the original float16 conversion within the noise: on 50 Hebrew clips, 40
transcripts were identical and WER was 5.2% against 4.7% (Common Voice) and 20.2% against 20.2% (FLEURS); on 40 English and Spanish clips 39 transcripts were identical, and the errors differed by one word.

## All results
Each cell is WER, then the number of clips. **Compare only cells with similar clip counts**: the rows with few clips are thin, and
the same clip counts mean the same clips, since every run takes the first N of a fixed order.
Empty cells were not run, to save time; each clip takes 10-30 s on this machine.
`ivrit-turbo-int8` and `turbo-int8` are the conversions the default image uses. Exact numbers are in [`bench/results.json`](bench/results.json).

### Real speech: Common Voice
| | ivrit-turbo | ivrit-turbo-int8 | ivrit-large-v3 | ivrit-v2-d4 | turbo | turbo-int8 | large-v3 | medium | small |
|---|---|---|---|---|---|---|---|---|---|
| he | 9.7% (200) | 5.2% (25) | 6.0% (40) | 15.8% (40) | 17.3% (54) | - | 18.1% (40) | 22.8% (40) | 32.2% (40) |
| en | 52.1% (5) | - | - | - | 10.1% (20) | 8.4% (10) | 6.2% (5) | 4.2% (5) | 12.6% (50) |
| es | 100.0% (5) | - | - | - | 3.6% (20) | 3.6% (10) | 2.0% (5) | 8.0% (5) | 8.2% (50) |
| pt | 100.0% (5) | - | - | - | 2.3% (20) | - | 6.9% (5) | 6.9% (5) | 13.1% (50) |
| ar | 105.0% (5) | - | - | - | 11.5% (20) | - | 15.0% (5) | 25.0% (5) | 38.5% (50) |
| ru | 117.2% (5) | - | - | - | 4.6% (20) | - | 0.0% (5) | 0.0% (5) | 12.1% (50) |
| fr | 100.0% (5) | - | - | - | 20.1% (20) | - | 41.1% (5) | 46.4% (5) | 23.3% (50) |

### Real speech: FLEURS
| | ivrit-turbo | ivrit-turbo-int8 | ivrit-large-v3 | ivrit-v2-d4 | turbo | turbo-int8 | large-v3 | medium | small |
|---|---|---|---|---|---|---|---|---|---|
| he | 16.6% (200) | 20.2% (25) | 15.1% (40) | 21.8% (40) | 27.5% (53) | - | 24.3% (40) | 30.6% (40) | 42.0% (40) |
| en | 39.6% (5) | - | - | - | 4.3% (20) | 3.6% (10) | 2.0% (5) | 2.0% (5) | 7.9% (50) |
| es | 100.0% (5) | - | - | - | 3.9% (20) | 4.1% (10) | 5.1% (5) | 7.4% (5) | 5.0% (50) |
| pt | 100.0% (5) | - | - | - | 2.9% (20) | - | 3.5% (5) | 3.5% (5) | 6.9% (50) |
| ar | 117.4% (5) | - | - | - | 8.6% (20) | - | 6.5% (5) | 10.9% (5) | 24.9% (50) |
| ru | 102.5% (5) | - | - | - | 3.3% (20) | - | 1.2% (5) | 7.4% (5) | 10.2% (50) |
| fr | 100.0% (5) | - | - | - | 7.7% (20) | - | 3.6% (5) | 2.4% (5) | 13.8% (50) |

### Language detection, real speech
Correct / clips, half from each set, using each model on its own.

| | he | en | es | pt | ar | ru | fr |
|---|---|---|---|---|---|---|---|
| ivrit-turbo | 20/20 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 |
| ivrit-large-v3 | 20/20 | - | - | - | - | - | - |
| ivrit-v2-d4 | 0/20 | - | - | - | - | - | - |
| turbo | 20/20 | 29/30 | 30/30 | 30/30 | 29/30 | 30/30 | 29/30 |
| large-v3 | 20/20 | - | - | - | - | - | - |
| medium | 20/20 | - | - | - | - | - | - |
| small | 19/20 | 48/50 | 48/50 | 49/50 | 49/50 | 49/50 | 49/50 |

The default image detects with `turbo`. It also chose the right model on one end-to-end test clip per language.

### Generated speech (secondary check)
Eight invented sentences per language with numbers, dates and everyday building wording, spoken by Meta's MMS-TTS.
Generated speech is different from real phone recordings, so a good score here is not proof for real speech. It is usually thought of as an
easier upper bound, but **these results do not behave like one**: with `turbo`, Hebrew, Portuguese, Arabic and Russian scored worse here than on real speech, and Hebrew was worse than Common
Voice for every model. The mistakes ("עמלית" for "המעלית") suggest the Hebrew voice itself is poor. Treat this table as a check on numbers and dates, on about 60-100 words per language, and not as a ranking.

| | ivrit-turbo | ivrit-large-v3 | ivrit-v2-d4 | turbo | large-v3 | medium | small |
|---|---|---|---|---|---|---|---|
| he | 22.6% (8) | 25.8% (8) | 33.9% (8) | 29.0% (8) | 24.2% (8) | 32.3% (8) | 40.3% (8) |
| en | 14.6% (8) | 28.3% (8) | 5.2% (8) | 3.1% (8) | 4.2% (8) | 5.1% (8) | 6.2% (8) |
| es | 99.0% (8) | - | - | 1.0% (8) | - | - | 5.1% (8) |
| pt | 100.0% (8) | - | - | 5.5% (8) | - | - | 7.7% (8) |
| ar | 108.8% (8) | - | - | 25.0% (8) | - | - | 38.8% (8) |
| ru | 119.7% (8) | - | - | 13.3% (8) | - | - | 20.0% (8) |
| fr | 101.1% (8) | - | - | 5.6% (8) | - | - | 13.2% (8) |

## Method
- **Test sets.** [FLEURS](https://huggingface.co/datasets/google/fleurs) (Google, CC BY 4.0), test split: he_il, en_us, es_419, pt_br, ar_eg, ru_ru, fr_fr. Common Voice 22.0 (Mozilla, CC0) through
  [an unofficial mirror](https://huggingface.co/datasets/fsicoli/common_voice_22_0), not checked against the original, since Mozilla now distributes it only through its Data Collective; test split, clips with at
  least 2 up votes and no down votes. No audio or speaker data is in this repository. [`bench/clips.tsv`](bench/clips.tsv) lists the clip IDs.
- **Sampling.** Fixed seed; 200 clips per set and language are chosen, one per sentence on FLEURS, and speakers taken in turn on Common Voice. Most models ran only on the first part of that list.
- **Normalisation** ([`bench/score.py`](bench/score.py)). Unicode NFKC, lower case, punctuation and symbols removed. Hebrew: niqqud and cantillation
  removed, maqaf splits words, geresh and gershayim dropped. Arabic: harakat and tatweel removed, alef, yeh and ta marbuta forms merged, Arabic digits to Latin. Russian: ё to е.
  French splits at apostrophes; the other languages join. A prefix on a number is split (ב-15 and ב15 are the same). Accents are kept.
- **WER** is the errors summed over a cell's clips divided by its reference words. The interval is a bootstrap over clips, so it does not cover speakers or the choice of test set.
- **What this overstates.** On real speech spelling variants count as errors (היתה and הייתה), and so do numbers written differently (a reference that spells out a date, a model
  that writes digits). Only the generated-speech sentences accept both forms.
- **Decoding.** `beam_size=5`, int8 on CPU, no VAD, faster-whisper 1.2.1, the same as the job. Detection uses `detect_language` on the whole clip.
- **Possible overlap.** ivrit.ai's model card lists its training sets, and neither test set is among them. That does not rule out the same sentences being used, and OpenAI does not publish Whisper's training data.

To reproduce: `bench/run_benchmarks.sh SCRATCH_DIR`. It needs about 40 GB and many hours, and it resumes if stopped.

## Licences
This repository is MIT. These are not part of the repository; the default image contains the first three.

| What | Licence | Where it is used |
|---|---|---|
| [openai/whisper-large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo) | MIT | Default and no-Hebrew images |
| [ivrit-ai/whisper-large-v3-turbo](https://huggingface.co/ivrit-ai/whisper-large-v3-turbo) | Apache-2.0 | Default image |
| faster-whisper, CTranslate2 and the other libraries | Their own | All images |
| [openai/whisper-small](https://huggingface.co/openai/whisper-small) | Apache-2.0 | Small image |
| FLEURS | CC BY 4.0 | Measuring only |
| Common Voice | CC0 | Measuring only |
| Meta MMS-TTS | CC BY-NC 4.0 (non-commercial) | Measuring only; its audio is generated by the script and not committed |

**Not used:** ivrit.ai's own evaluation sets, including one named WhatsApp (54 clips; its contents were not seen). They need an account
and accepted terms, and their licence (ivrit.ai v2) limits use to training models or academic research. Check those terms first if you want them for Hebrew.

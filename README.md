# whisper-job

Whisper as a one-shot container. It starts when called, transcribes one audio file on the CPU with no network,
prints JSON and exits. Nothing stays running between jobs, so a rarely used transcription costs nothing while idle.

It is a Dockerfile and one small script around [faster-whisper](https://github.com/SYSTRAN/faster-whisper). The
model is inside the image, so nothing is downloaded when it runs.

## Build
```
docker build -t whisper-job .                         # the "small" model
docker build -t whisper-job:medium --build-arg MODEL=medium .
```

## Run
```
docker run --rm --network none --read-only -v "$PWD/testdata:/in:ro" whisper-job /in/speech-3s.ogg en
```
```json
{"text": "This is a generated test message about the building.", "language": "en", "duration": 3.01, "load_seconds": 1.34, "transcribe_seconds": 1.55}
```
The first argument is the file (anything FFmpeg reads: Ogg/Opus, WebM, MP4/AAC, WAV). The second is the language
code, for example `he`; leave it out to detect the language.

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

## Measured
`small` model, 4 CPU cores, on a machine that was also running other work. Generated English speech in
`testdata/`, 24 kb/s Opus. Each figure is from two runs, which agreed closely.

| | 3 s of audio | 60 s of audio |
|---|---|---|
| Total time, from `docker run` to exit | 3.3 s | 10.4 s |
| Peak memory | 660 MB | 720 MB |

Loading the program and the model takes about 1.3 s of that. Starting needs the image on the machine: a new machine
downloads it first.

| Image size | |
|---|---|
| Compressed download (`docker save \| gzip -1`) | 602 MB |
| Files in the image (model 486 MB, libraries 482 MB, Python and Debian 135 MB) | 1.1 GB |
| What `docker images` showed (containerd image store) | 1.73 GB |

Compared on the same files with whisper.cpp (`small`, plus a static FFmpeg): 5.9-6.3 s and 14.8 s, peak 920 MB,
486 MB compressed. faster-whisper was faster and used less memory; whisper.cpp's image was smaller.

**Not measured:** accuracy, Hebrew or otherwise. The test audio is generated English speech. Compare models on real
speech in your language before choosing one.

## Licence
MIT. The model and libraries keep their own licences.

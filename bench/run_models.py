"""Run one model over the manifest inside the image's Python, one process per model. Resumable.

Usage: run_models.py --model-dir /models/turbo --name turbo --manifest M --root /work/clips-root --out OUT.jsonl
         [--langs he,en] [--datasets cv22,fleurs] [--limit 50] [--detect-limit 30] [--threads 2] [--vad]
Same decoding settings as transcribe.py (int8, beam 5, no VAD unless asked). --limit takes the first N of each set, and
the sets are in a fixed order, so a smaller run is a subset of a larger one.
"""
import argparse, json, os, sys, time
import av, numpy as np
from faster_whisper import WhisperModel


def load(path):
    out = []
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    with av.open(path) as container:
        for frame in container.decode(audio=0):
            for f in resampler.resample(frame):
                out.append(f.to_ndarray().reshape(-1))
    return np.concatenate(out).astype(np.float32) / 32768.0


p = argparse.ArgumentParser()
p.add_argument("--model-dir", required=True); p.add_argument("--name", required=True)
p.add_argument("--manifest", required=True); p.add_argument("--root", required=True); p.add_argument("--out", required=True)
p.add_argument("--langs", default=""); p.add_argument("--datasets", default="")
p.add_argument("--limit", type=int, default=10**9); p.add_argument("--detect-limit", type=int, default=0)
p.add_argument("--threads", type=int, default=2); p.add_argument("--vad", action="store_true")
a = p.parse_args()

done = set()
if os.path.exists(a.out):
    with open(a.out, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            done.add((r["clip"], r["kind"]))

jobs = []
with open(a.manifest, encoding="utf-8") as f:
    for line in f:
        e = json.loads(line)
        if a.langs and e["lang"] not in a.langs.split(","):
            continue
        if a.datasets and e["dataset"] not in a.datasets.split(","):
            continue
        if e["rank"] < a.limit and (e["clip"], "transcribe") not in done:
            jobs.append((e, "transcribe"))
        if e["rank"] < a.detect_limit and (e["clip"], "detect") not in done:
            jobs.append((e, "detect"))
# Round-robin over the sets, so an interrupted run still covers every language evenly.
jobs.sort(key=lambda j: (j[0]["rank"], j[0]["dataset"], j[0]["lang"]))
print(a.name, "jobs", len(jobs), flush=True)
if not jobs:
    sys.exit()

model = WhisperModel(a.model_dir, device="cpu", compute_type="int8", cpu_threads=a.threads)
with open(a.out, "a", encoding="utf-8") as out:
    for e, kind in jobs:
        audio = load(os.path.join(a.root, e["clip"]))
        t = time.time()
        rec = {"model": a.name, "clip": e["clip"], "kind": kind, "vad": a.vad}
        if kind == "transcribe":
            segments, info = model.transcribe(audio, language=e["lang"], beam_size=5, vad_filter=a.vad)
            rec["hyp"] = " ".join(s.text.strip() for s in segments)
        else:
            lang, prob, _ = model.detect_language(audio)
            rec.update(detected=lang, prob=round(float(prob), 3))
        rec["seconds"] = round(time.time() - t, 2)
        rec["audio_seconds"] = round(len(audio) / 16000, 2)
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()

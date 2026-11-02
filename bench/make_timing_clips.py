"""Join real test clips into a file of about a minute per language, for the docker-run-to-exit timings.

Usage: make_timing_clips.py WORK [SECONDS]   (run inside the job's image, it needs av). Writes WORK/timing/<lang>-60s.ogg and <lang>-5s.ogg.
"""
import json, os, sys
import av, numpy as np


def decode(path):
    out = []
    r = av.AudioResampler(format="s16", layout="mono", rate=48000)
    with av.open(path) as c:
        for frame in c.decode(audio=0):
            for f in r.resample(frame):
                out.append(f.to_ndarray().reshape(-1))
    return np.concatenate(out)


def write(path, pcm):
    with av.open(path, "w", format="ogg") as c:
        s = c.add_stream("libopus", rate=48000, layout="mono")
        s.bit_rate = 24000
        frame = av.AudioFrame.from_ndarray(pcm.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = 48000
        r = av.AudioResampler(format="s16", layout="mono", rate=48000)
        for f in r.resample(frame) + r.resample(None):
            c.mux(s.encode(f))
        c.mux(s.encode(None))


work = sys.argv[1]
os.makedirs(f"{work}/timing", exist_ok=True)
entries = [json.loads(line) for line in open(f"{work}/manifest.jsonl", encoding="utf-8")]
for lang in ("he", "en"):
    clips = [e for e in entries if e["lang"] == lang and e["dataset"] == "cv22"]
    pcm, seconds = [], 0
    for e in clips:
        x = decode(f"{work}/clips/{e['clip']}")
        if not pcm and 4 <= len(x) / 48000 <= 7:
            write(f"{work}/timing/{lang}-5s.ogg", x)
        pcm += [x, np.zeros(24000, dtype=x.dtype)]
        seconds += len(x) / 48000 + 0.5
        if seconds >= 60:
            break
    write(f"{work}/timing/{lang}-60s.ogg", np.concatenate(pcm))

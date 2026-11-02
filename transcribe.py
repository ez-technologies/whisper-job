"""One-shot: transcribe one file, print JSON, exit. Usage: transcribe.py FILE [LANGUAGE]"""
import json, os, sys, time
start = time.time()
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
threads = int(os.environ.get("WHISPER_THREADS", "0"))
model = WhisperModel("/model", device="cpu", compute_type="int8", cpu_threads=threads)
loaded = time.time()
lang = sys.argv[2] if len(sys.argv) > 2 else None
segments, info = model.transcribe(load(sys.argv[1]), language=lang, beam_size=int(os.environ.get("WHISPER_BEAM", "5")))
text = " ".join(s.text.strip() for s in segments)
print(json.dumps({"text": text, "language": info.language, "duration": info.duration,
                  "load_seconds": round(loaded - start, 2), "transcribe_seconds": round(time.time() - loaded, 2)}, ensure_ascii=False))

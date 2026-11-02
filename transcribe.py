"""One-shot: transcribe one file, print JSON, exit. Usage: transcribe.py FILE [LANGUAGE]"""
import json, os, resource, sys, time
start = time.time()
import av, numpy as np
from faster_whisper import WhisperModel
GENERAL, HEBREW = "/model/general", "/model/he"
def load(path):
    out = []
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    with av.open(path) as container:
        for frame in container.decode(audio=0):
            for f in resampler.resample(frame):
                out.append(f.to_ndarray().reshape(-1))
    return np.concatenate(out).astype(np.float32) / 32768.0
def open_model(path):
    return WhisperModel(path, device="cpu", compute_type="int8", cpu_threads=int(os.environ.get("WHISPER_THREADS", "0")))
def path_for(lang):
    return HEBREW if lang == "he" and os.path.isdir(HEBREW) else GENERAL
audio = load(sys.argv[1])
lang = sys.argv[2] if len(sys.argv) > 2 else None
# Only the general model detects languages: the Hebrew-tuned one was not trained to, and its card says so.
path = path_for(lang) if lang else GENERAL
model = open_model(path)
load_seconds = time.time() - start
if not lang:
    lang = model.detect_language(audio)[0]
    if path_for(lang) != path:
        path = path_for(lang)
        del model
        t = time.time()
        model = open_model(path)
        load_seconds += time.time() - t
t = time.time()
segments, info = model.transcribe(audio, language=lang, beam_size=int(os.environ.get("WHISPER_BEAM", "5")))
text = " ".join(s.text.strip() for s in segments)
print(json.dumps({"text": text, "language": info.language, "duration": info.duration, "model": os.path.basename(path),
                  "load_seconds": round(load_seconds, 2), "transcribe_seconds": round(time.time() - t, 2),
                  "peak_memory_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024}, ensure_ascii=False))

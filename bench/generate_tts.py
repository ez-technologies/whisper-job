"""Generate the secondary test audio with Meta's MMS-TTS models, from sentences.json.

Run with tts.Dockerfile (see run_benchmarks.sh). Writes WORK/clips/mms/<lang>/NN.ogg (Opus 24 kb/s, like a voice message)
and WORK/manifest-mms.jsonl. The models are CC BY-NC 4.0, so the audio stays out of this repository; only this script is here.
"""
import json, os, re, sys
import av, numpy as np, torch
from transformers import AutoTokenizer, VitsModel

MODELS = {  # language: (repository, pinned revision)
    "he": ("facebook/mms-tts-heb", "28f1fce7cf56b2a3a56e19a4a1405ed70b454853"),
    "en": ("facebook/mms-tts-eng", "c71de0fe7204c83f1c10820a7d696d0b450048ba"),
    "es": ("facebook/mms-tts-spa", "833b96c0278c85cf09776d565ba8f1cb2819f7ec"),
    "pt": ("facebook/mms-tts-por", "7908d3953d285b6da2582b5105448b6e56e70e82"),
    "ar": ("facebook/mms-tts-ara", "afba26a4b470f9ae64aeeea91b99f080dee410de"),
    "ru": ("facebook/mms-tts-rus", "a6f0f76c028c49175f42074ee79bd3e17ee1dd47"),
    "fr": ("facebook/mms-tts-fra", "5806d92d6247218c0e81e5f1a7462f6f636f70a2"),
}


def spoken(text):
    return re.sub(r"\{([^|}]*)(\|[^}]*)?\}", r"\1", text)


def write_opus(path, wave, rate):
    with av.open(path, "w", format="ogg") as c:
        s = c.add_stream("libopus", rate=48000, layout="mono")
        s.bit_rate = 24000
        frame = av.AudioFrame.from_ndarray((wave * 32767).astype(np.int16).reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = rate
        r = av.AudioResampler(format="s16", layout="mono", rate=48000)
        for f in r.resample(frame):
            c.mux(s.encode(f))
        for f in r.resample(None):
            c.mux(s.encode(f))
        c.mux(s.encode(None))


def main(sentences_path, work):
    sentences = json.load(open(sentences_path, encoding="utf-8"))
    torch.manual_seed(20261102)
    with open(f"{work}/manifest-mms.jsonl", "w", encoding="utf-8") as m:
        for lang, (repo, rev) in MODELS.items():
            tok = AutoTokenizer.from_pretrained(repo, revision=rev)
            model = VitsModel.from_pretrained(repo, revision=rev, use_safetensors=True).eval()
            os.makedirs(f"{work}/clips/mms/{lang}", exist_ok=True)
            for i, text in enumerate(sentences[lang]):
                with torch.no_grad():
                    wave = model(**tok(spoken(text), return_tensors="pt")).waveform[0].numpy()
                clip = f"mms/{lang}/{i:02d}.ogg"
                write_opus(f"{work}/clips/{clip}", wave / max(abs(wave).max(), 1e-6) * 0.9, model.config.sampling_rate)
                m.write(json.dumps({"dataset": "mms", "lang": lang, "rank": i, "clip": clip, "ref": text}, ensure_ascii=False) + "\n")
                print(clip, round(len(wave) / model.config.sampling_rate, 1), "s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

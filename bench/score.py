"""Score transcripts against references. Standard library only; run with python3 -I.

Usage: score.py WORK_DIR [--md] [--max-rank N] [--json FILE]   reads WORK_DIR/manifest*.jsonl and WORK_DIR/out/*.jsonl

WER = (substitutions + deletions + insertions) / reference words, summed over the clips of a cell, not averaged per
clip. The 95% interval is a percentile bootstrap over clips (2000 resamples, fixed seed), so it covers clip sampling
only. CER is the same on characters, spaces removed.
"""
import argparse, collections, glob, itertools, json, os, random, re, unicodedata

MODEL_ORDER = ["ivrit-turbo", "ivrit-turbo-int8", "ivrit-large-v3", "ivrit-v2-d4", "turbo", "turbo-int8", "large-v3", "medium", "small"]
HEB_MARKS = re.compile("[֑-ׇֽֿׁׂׅׄ]")  # niqqud and cantillation
AR_MARKS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")  # harakat, Quranic marks, tatweel
AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي", "ء": ""})
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
# Apostrophes join in these languages ("don't", Hebrew geresh in צ'יפס) and separate in the others ("l'eau").
JOIN_APOSTROPHE = {"en", "he", "es", "pt", "ru", "ar"}
APOSTROPHES = "'’ʼ`´׳׳"


def normalise(text, lang):
    """Lower-case words without punctuation. Spelling is otherwise left alone: a wrong accent or full spelling counts."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.translate(AR_DIGITS)
    if lang == "he":
        text = text.replace("־", " ")  # maqaf separates words
        text = text.replace("״", "").replace('"', "")  # gershayim in acronyms
        text = HEB_MARKS.sub("", text)
    elif lang == "ar":
        text = AR_MARKS.sub("", text).translate(AR_MAP)
    elif lang == "ru":
        text = text.replace("ё", "е")
    if lang in JOIN_APOSTROPHE:
        text = "".join("" if c in APOSTROPHES else c for c in text)
    # A prefix on a number is a separate word either way: ב-15, ב15 -> ב 15.
    text = re.sub(r"(?<=\D)(?=\d)|(?<=\d)(?=\D)", " ", text)
    out = []
    for c in text:
        cat = unicodedata.category(c)
        out.append(" " if cat[0] in "PSZC" else c)
    return "".join(out).split()


def edits(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def interval(pairs, seed=7, n=2000):
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        e = w = 0
        for _ in pairs:
            a, b = rng.choice(pairs)
            e += a; w += b
        vals.append(e / max(w, 1))
    vals.sort()
    return vals[int(n * 0.025)], vals[int(n * 0.975)]


def references(text, lang):
    """All written forms of a reference: {a|b} in the generated-speech sentences lists accepted forms of one phrase."""
    parts = re.split(r"\{([^}]*)\}", text)
    options = [p.split("|") if i % 2 else [p] for i, p in enumerate(parts)]
    return [normalise("".join(c), lang) for c in itertools.product(*options)]


def load(work):
    manifest = {}
    for path in glob.glob(f"{work}/manifest*.jsonl"):
        with open(path, encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                manifest[e["clip"]] = e
    results = collections.defaultdict(dict)
    for path in glob.glob(f"{work}/out/*.jsonl"):
        if os.path.basename(path).startswith("pilot"):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                results[r["model"], r["kind"]][r["clip"]] = r
    return manifest, results


def cell(manifest, rs, clips):
    pairs, cpairs, secs = [], [], []
    for c in clips:
        e, r = manifest[c], rs[c]
        hyp = normalise(r["hyp"], e["lang"])
        ref = min(references(e["ref"], e["lang"]), key=lambda x: edits(x, hyp))
        pairs.append((edits(ref, hyp), len(ref)))
        cpairs.append((edits("".join(ref), "".join(hyp)), len("".join(ref))))
        secs.append(r["seconds"])
    words = sum(p[1] for p in pairs)
    return {"n": len(pairs), "words": words, "wer": sum(p[0] for p in pairs) / max(words, 1),
            "cer": sum(p[0] for p in cpairs) / max(sum(p[1] for p in cpairs), 1),
            "ci": interval(pairs), "s_per_clip": sum(secs) / max(len(secs), 1)}


def print_tables(rows, det):
    """Markdown: one table per test set, a row per language, a column per model, each cell "WER (clips)"."""
    langs = ["he", "en", "es", "pt", "ar", "ru", "fr"]
    for ds in ("cv22", "fleurs", "mms"):
        cells = {(r["lang"], r["model"]): r for r in rows if r["dataset"] == ds}
        models = [m for m in MODEL_ORDER if any(k[1] == m for k in cells)]
        print(f"\n{ds}\n\n| | " + " | ".join(models) + " |\n|---|" + "---|" * len(models))
        for l in langs:
            row = [f"{cells[l, m]['wer']*100:.1f}% ({cells[l, m]['n']})" if (l, m) in cells else "-" for m in models]
            print(f"| {l} | " + " | ".join(row) + " |")
    print("\ndetection\n\n| | " + " | ".join(langs) + " |\n|---|" + "---|" * len(langs))
    for d in sorted(det, key=lambda x: MODEL_ORDER.index(x["model"]) if x["model"] in MODEL_ORDER else 99):
        print(f"| {d['model']} | " + " | ".join("/".join(map(str, d["by_lang"].get(l, ["-"]))) for l in langs) + " |")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("work"); p.add_argument("--max-rank", type=int, default=None)
    p.add_argument("--json"); p.add_argument("--md", action="store_true")
    a = p.parse_args()
    manifest, results = load(a.work)
    models = sorted({m for m, _ in results})
    keyed = collections.defaultdict(list)
    for c, e in manifest.items():
        keyed[e["lang"], e["dataset"]].append(c)
    rows = []
    for (lang, ds), clips in sorted(keyed.items()):
        for m in models:
            rs = results.get((m, "transcribe"), {})
            have = [c for c in clips if c in rs and (a.max_rank is None or manifest[c]["rank"] < a.max_rank)]
            if not have:
                continue
            x = cell(manifest, rs, have)
            rows.append({"lang": lang, "dataset": ds, "model": m, **x})
            print(f"{lang} {ds:7} {m:15} n={x['n']:4} words={x['words']:5} WER={x['wer']*100:5.1f}% "
                  f"[{x['ci'][0]*100:.1f}-{x['ci'][1]*100:.1f}] CER={x['cer']*100:5.1f}% {x['s_per_clip']:.1f}s/clip")
    print()
    det = []
    for m in models:
        rs = results.get((m, "detect"), {})
        by = collections.defaultdict(lambda: [0, 0])
        wrong = collections.Counter()
        for c, r in rs.items():
            lang = manifest[c]["lang"]
            by[lang][1] += 1
            by[lang][0] += r["detected"] == lang
            if r["detected"] != lang:
                wrong[lang, r["detected"]] += 1
        if rs:
            print(f"detect {m:15}", {l: f"{v[0]}/{v[1]}" for l, v in sorted(by.items())}, dict(wrong.most_common(5)))
            det.append({"model": m, "by_lang": {l: v for l, v in by.items()}})
    if a.md:
        print_tables(rows, det)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"wer": rows, "detect": det}, f, indent=1)


if __name__ == "__main__":
    main()

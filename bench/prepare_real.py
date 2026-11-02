"""Pick test clips from the downloaded public test sets and extract only those clips.

Usage: python3 -I bench/prepare_real.py DATA_DIR WORK_DIR [--clips bench/clips.tsv] [--per-set N]

DATA_DIR holds fleurs/<locale>/test.{tsv,tar.gz} and cv22/<lang>/test.{tsv,tar} (see fetch_data.sh).
Writes WORK_DIR/clips/<dataset>/<lang>/<clip> and WORK_DIR/manifest.jsonl with the reference texts.
Speaker fields in the Common Voice table are used to spread the sample over speakers and are never written out.
With --clips the choice in that file is reused, so everyone measures the same clips.
"""
import argparse, collections, csv, json, os, random, tarfile

LOCALES = {"he": "he_il", "en": "en_us", "es": "es_419", "pt": "pt_br", "ar": "ar_eg", "ru": "ru_ru", "fr": "fr_fr"}
SEED = 20261102
csv.field_size_limit(10**7)


def pick_cv(rows, rng, n):
    """Validated clips (2+ up votes, no down votes), taking one per speaker in turn so few speakers cannot dominate."""
    speakers = collections.defaultdict(list)
    for r in rows:
        if int(r["up_votes"]) >= 2 and int(r["down_votes"]) == 0 and r["sentence"].strip():
            speakers[r["client_id"]].append(r)
    order = sorted(speakers)
    rng.shuffle(order)
    for s in order:
        rng.shuffle(speakers[s])
    picked = []
    while len(picked) < n and any(speakers.values()):
        for s in order:
            if speakers[s] and len(picked) < n:
                picked.append(speakers[s].pop())
    return [(r["path"], r["sentence"]) for r in picked]


def pick_fleurs(rows, rng, n):
    """FLEURS has several recordings of one sentence; take one recording per sentence."""
    by_sentence = collections.defaultdict(list)
    for r in rows:
        by_sentence[r[0]].append(r)
    ids = sorted(by_sentence)
    rng.shuffle(ids)
    return [(r[1], r[2]) for r in (rng.choice(sorted(by_sentence[i])) for i in ids[:n])]


def read_tables(data):
    tables = {}
    for lang, locale in LOCALES.items():
        with open(f"{data}/cv22/{lang}/test.tsv", encoding="utf-8", newline="") as f:
            tables["cv22", lang] = list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))
        with open(f"{data}/fleurs/{locale}/test.tsv", encoding="utf-8", newline="") as f:
            tables["fleurs", lang] = list(csv.reader(f, delimiter="\t"))
    return tables


def extract(tar_path, wanted, dest):
    """Copy the wanted members by base name. Nothing else in the archive is written or run."""
    os.makedirs(dest, exist_ok=True)
    left = set(wanted)
    with tarfile.open(tar_path) as tar:
        for m in tar:
            name = os.path.basename(m.name)
            if m.isfile() and name in left:
                with tar.extractfile(m) as src, open(os.path.join(dest, name), "wb") as out:
                    out.write(src.read())
                left.discard(name)
                if not left:
                    break
    if left:
        raise SystemExit(f"{tar_path}: {len(left)} clips missing, for example {sorted(left)[0]}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("data"); p.add_argument("work")
    p.add_argument("--clips"); p.add_argument("--write-clips"); p.add_argument("--per-set", type=int, default=200)
    a = p.parse_args()
    tables = read_tables(a.data)
    fixed = None
    if a.clips:
        with open(a.clips, encoding="utf-8") as f:
            fixed = collections.defaultdict(list)
            for ds, lang, clip in (line.split() for line in f.read().splitlines()[1:]):
                fixed[ds, lang].append(clip)
    entries = []
    for (ds, lang), rows in tables.items():
        if ds == "cv22":
            text = {r["path"]: r["sentence"] for r in rows}
        else:
            text = {r[1]: r[2] for r in rows}
        if fixed:
            chosen = [(c, text[c]) for c in fixed[ds, lang]]
        else:
            rng = random.Random(f"{SEED}-{ds}-{lang}")
            chosen = pick_cv(rows, rng, a.per_set) if ds == "cv22" else pick_fleurs(rows, rng, a.per_set)
        archive = f"{a.data}/cv22/{lang}/test.tar" if ds == "cv22" else f"{a.data}/fleurs/{LOCALES[lang]}/test.tar.gz"
        extract(archive, [c for c, _ in chosen], f"{a.work}/clips/{ds}/{lang}")
        for rank, (clip, ref) in enumerate(chosen):
            entries.append({"dataset": ds, "lang": lang, "rank": rank, "clip": f"{ds}/{lang}/{clip}", "ref": ref})
        print(ds, lang, len(chosen), flush=True)
    with open(f"{a.work}/manifest.jsonl", "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    if a.write_clips:
        with open(a.write_clips, "w", encoding="utf-8") as f:
            f.write("dataset\tlang\tclip\n")
            for e in entries:
                f.write(f"{e['dataset']}\t{e['lang']}\t{os.path.basename(e['clip'])}\n")


if __name__ == "__main__":
    main()

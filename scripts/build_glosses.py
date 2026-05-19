"""
Build data/glosses.json from scripts/glosses.py.
Also reports coverage stats.
"""
import json
import sys
import os
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from glosses import GLOSSES


def main():
    root = os.path.dirname(os.path.dirname(__file__))
    questions_path = os.path.join(root, "data/questions.json")
    out_path = os.path.join(root, "data/glosses.json")
    qs = json.load(open(questions_path))
    counts = Counter(q["lemma"] for q in qs)
    used_lemmas = set(counts.keys())
    glosses_for_used = {lem: GLOSSES.get(lem) for lem in used_lemmas}
    covered = sum(counts[l] for l in used_lemmas if GLOSSES.get(l))
    total = sum(counts.values())
    print(f"Total glosses defined:      {len(GLOSSES)}")
    print(f"Unique lemmas in pool:      {len(used_lemmas)}")
    print(f"Lemma gloss coverage:       {sum(1 for l in used_lemmas if GLOSSES.get(l))}/{len(used_lemmas)} = {100*sum(1 for l in used_lemmas if GLOSSES.get(l))/len(used_lemmas):.1f}%")
    print(f"Question gloss coverage:    {covered}/{total} = {100*covered/total:.1f}%")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(glosses_for_used, f, ensure_ascii=False, separators=(",", ":"))
    # Also write the JS-loadable wrapper
    js_path = os.path.join(root, "data/glosses.json.js")
    with open(js_path, "w", encoding="utf-8") as f:
        content = json.dumps(glosses_for_used, ensure_ascii=False, separators=(",", ":"))
        f.write("window.GLOSSES = " + content + ";")
    print(f"Written to {out_path} ({os.path.getsize(out_path)/1024:.1f} KB)")


if __name__ == "__main__":
    main()

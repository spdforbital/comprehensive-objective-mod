"""Merges tools/patches/*.json into objectives/*.json (stage-level replacement).

Usage: python3 apply_patches.py [--dry] [patch.json ...]     (default: every file in patches/)
Applied patch files are moved to patches/applied/.
"""
import glob, json, os, sys, shutil
from patching import apply_patch

HERE = os.path.dirname(os.path.abspath(__file__))
OBJ_DIR = os.path.join(os.path.dirname(HERE), 'objectives')
PDIR = os.path.join(HERE, 'patches')

def main():
    dry = '--dry' in sys.argv
    files = [a for a in sys.argv[1:] if not a.startswith('--')] or sorted(glob.glob(os.path.join(PDIR, '*.json')))
    patches = {}
    for pf in files:
        try:
            raw = json.load(open(pf))
        except Exception as e:
            print('SKIP (bad JSON)', pf, e); continue
        for q, v in raw.items():
            if q.lower() in patches: print('note: quest patched twice, later file wins:', q)
            patches[q.lower()] = (v, pf)
    done, stages = set(), 0
    for f in sorted(glob.glob(os.path.join(OBJ_DIR, '*.json'))):
        data = json.load(open(f)); changed = False
        for qid in list(data.get('quests', {})):
            p = patches.get(qid.lower())
            if not p: continue
            data['quests'][qid] = apply_patch(data['quests'][qid], p[0])
            stages += sum(len(str(k).split(',')) for k in p[0].get('stages', {}))
            stages += sum(len(str(k).split(',')) for vd in (p[0].get('variant') or {}).values() for k in vd.get('stages', {}))
            done.add(qid.lower()); changed = True
        if changed and not dry:
            tmp = f + '.tmp'
            json.dump(data, open(tmp, 'w'), indent=1, ensure_ascii=False)
            os.replace(tmp, f)
    for q in patches:
        if q not in done: print('NOT FOUND in objectives:', q, 'from', patches[q][1])
    print(f'{len(done)} quests, {stages} stages patched from {len(files)} files' + (' (dry run)' if dry else ''))
    if not dry:
        os.makedirs(os.path.join(PDIR, 'applied'), exist_ok=True)
        for pf in files:
            shutil.move(pf, os.path.join(PDIR, 'applied', os.path.basename(pf)))

if __name__ == '__main__': main()

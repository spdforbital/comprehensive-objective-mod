"""Builds review worklists: stages whose markers / sub-objectives look incomplete,
each with what the game files say about that stage.

Usage: python3 worklist.py [file.json ...]   -> worklists/<file>.<nn>.json  (+ prints counts)
"""
import glob, json, os, sys, collections
from world import world, cell_label
from questgraph import graph, stage_ok
import audit, mentions

HERE = os.path.dirname(os.path.abspath(__file__))
OBJ_DIR = os.path.join(os.path.dirname(HERE), 'objectives')
OUT = os.path.join(HERE, 'worklists')
W = world(); G = graph()['quests']
CHUNK = 70


def placed_at(rid):
    cs = sorted({cell_label(ck) for ck, _ in W['placed'].get(rid, [])})
    return cs[:3] + (['...'] if len(cs) > 3 else [])


def name_of(rid):
    o = W['objs'].get(rid)
    return (o or {}).get('name') or rid


def transitions(qid, nums):
    g = G.get(qid.lower())
    if not g: return []
    out = []
    for r in g['talk']:
        if not any(r['sets'] > n and stage_ok(r['stage'], n) for n in nums): continue
        who = r['speaker'] or '(anyone: ' + ', '.join(f"{k}={r[k]}" for k in ('cell', 'faction', 'class', 'race') if r[k]) + ')'
        s = f"-> stage {r['sets']}: talk to {who} about '{r['topic']}'"
        if r['stage']: s += ' when stage ' + ' and '.join(f'{op}{v}' for op, v in r['stage'])
        if r['items']: s += '; needs items ' + ', '.join(f"{i} ({name_of(i)}) {op}{v}" for i, op, v in r['items'])
        if r['dead']: s += '; needs dead ' + ', '.join(f"{i} {op}{v}" for i, op, v in r['dead'])
        if r['takes']: s += '; takes ' + ', '.join(f'{i} x{c}' for i, c in r['takes'])
        if r['gives']: s += '; gives ' + ', '.join(f'{i} x{c}' for i, c in r['gives'])
        if r['choice']: s += '; (dialogue choice)'
        if r['otherq']: s += '; other quests ' + ', '.join(f'{q}{op}{v}' for q, op, v in r['otherq'])
        if r['speaker']: s += f"; {r['speaker']} is at {placed_at(r['speaker']) or 'NOT PLACED (script moves them)'}"
        out.append((r['sets'], s))
    for r in g['script']:
        if not any(r['sets'] > n and stage_ok(r['stage'], n) for n in nums): continue
        s = f"-> stage {r['sets']}: script {r['script']}"
        if r['owners']: s += ' on ' + ', '.join(f"{o} ({name_of(o)}) at {placed_at(o)}" for o in r['owners'][:3])
        if r['stage']: s += ' when stage ' + ' and '.join(f'{op}{v}' for op, v in r['stage'])
        if r['items']: s += '; needs items ' + ', '.join(f'{i} {op}{v}' for i, op, v in r['items'])
        if r['dead']: s += '; needs dead ' + ', '.join(f'{i} {op}{v}' for i, op, v in r['dead'])
        if r['cells']: s += '; player in ' + ', '.join(r['cells'])
        if r['flags']: s += '; ' + ','.join(r['flags'])
        if r['conds']: s += ' | if ' + ' / '.join(c[:90] for c in r['conds'][-2:])
        out.append((r['sets'], s))
    out.sort(key=lambda x: x[0])
    seen, res = set(), []
    for _, s in out:
        if s not in seen:
            seen.add(s); res.append(s)
    return res[:14]


def main():
    only = set(sys.argv[1:])
    os.makedirs(OUT, exist_ok=True)
    totals = collections.Counter()
    for f in sorted(glob.glob(os.path.join(OBJ_DIR, '*.json'))):
        base = os.path.basename(f)
        if only and base not in only: continue
        data = json.load(open(f)); L = data.get('lists', {})
        quests = []
        for qid, qd in data.get('quests', {}).items():
            if qd.get('hide') or not qd.get('stages'): continue
            j = W['journal'].get(qid.lower())
            if not j: continue
            per = {}
            for skey, objs in qd['stages'].items():
                for s in str(skey).split(','):
                    per[int(s)] = (skey, objs)
            earlier = set()
            flagged = {}
            for n in sorted(per):
                skey, raw = per[n]
                objs = audit.expand(raw, L)
                fa = audit.audit_stage(qid, n, objs, earlier)
                ms = mentions.stage_mentions(objs)
                for o in objs:
                    t = o.get('target') or {}
                    for k in ('npc', 'creature', 'item', 'object'):
                        if k in t: earlier.update(audit._l(t[k]))
                    audit.cond_ids(o.get('doneIf'), earlier)
                flags = {k: fa[k] for k in ('no_target', 'unrelated_target', 'missing_item', 'missing_dead') if k in fa}
                if fa.get('no_target') and not fa.get('actors') and not ms:
                    flags.pop('no_target')      # "wait a week": nothing to mark
                if not flags and not ms: continue
                e = flagged.setdefault(skey, {'stages': skey, 'journal': {}, 'objectives': raw, 'flags': {}, 'unmarked': [], 'nums': []})
                e['nums'].append(n)
                e['journal'][str(n)] = (j['stages'].get(n) or '')[:420]
                for k, v in flags.items():
                    e['flags'][k] = sorted(v) if isinstance(v, set) else v
                for idx, name, cands in ms:
                    row = {'objective': idx, 'name': name,
                           'candidates': [{'kind': k, 'id': i, 'at': placed_at(i) if k in ('actor', 'item') else None} for k, i in cands[:4]]}
                    if row not in e['unmarked']: e['unmarked'].append(row)
            if not flagged: continue
            for e in flagged.values():
                e['game'] = transitions(qid, e.pop('nums'))
            others = {k: [o['do'] if isinstance(o, dict) else o for o in v] for k, v in qd['stages'].items() if k not in flagged}
            quests.append({'quest': qid, 'name': j.get('name'), 'review': list(flagged.values()), 'other_stages': others})
            totals[base] += len(flagged)
        # chunk by quests
        chunk, n, idx = [], 0, 1
        def flush():
            nonlocal chunk, n, idx
            if chunk:
                json.dump(chunk, open(os.path.join(OUT, f'{base[:-5]}.{idx:02d}.json'), 'w'), indent=1, ensure_ascii=False)
                idx += 1; chunk = []; n = 0
        for q in quests:
            if n and n + len(q['review']) > CHUNK: flush()
            chunk.append(q); n += len(q['review'])
        flush()
        totals[base + ' chunks'] = idx - 1
    for k, v in sorted(totals.items()): print(f'{k:36s} {v}')
    print('total stages', sum(v for k, v in totals.items() if not k.endswith('chunks')), 'chunks', sum(v for k, v in totals.items() if k.endswith('chunks')))

if __name__ == '__main__': main()

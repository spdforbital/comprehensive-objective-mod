"""Checks the authored objectives against what the game files say moves each quest.

Usage: python3 audit.py [QuestId ...]     # no ids: summary over everything + audit.json
"""
import glob, json, os, sys, collections
from world import world
from questgraph import graph, stage_ok

HERE = os.path.dirname(os.path.abspath(__file__))
OBJ_DIR = os.path.join(os.path.dirname(HERE), 'objectives')
W = world()
G = graph()['quests']
KINDS = ('npc', 'creature', 'item', 'object', 'cell', 'place')


def expand(objs, lists):
    out = []
    for o in objs:
        if isinstance(o, str):
            out += expand(lists.get(o[1:], []), lists)
        else:
            out.append(o)
    return out


def cond_ids(c, acc):
    if not isinstance(c, dict): return
    for k, v in c.items():
        if k in ('any', 'all'):
            for x in v: cond_ids(x, acc)
        elif k in ('has', 'dead'):
            acc.add(v.lower())


def advancers(qid, n):
    """transitions that can fire while quest qid is at stage n and move it on"""
    g = G.get(qid.lower())
    if not g:
        return [], []
    talk = [r for r in g['talk'] if r['sets'] > n and stage_ok(r['stage'], n)]
    scr = [r for r in g['script'] if r['sets'] > n and stage_ok(r['stage'], n)]
    return talk, scr


def cells_of(rid):
    return {ck for ck, _ in W['placed'].get(rid, [])}


def _l(v):
    return [x.lower() for x in (v if isinstance(v, list) else [v]) if isinstance(x, str)]


def audit_stage(qid, n, objs, earlier=()):
    """returns dict of findings for one authored stage; earlier = ids already handled in lower stages"""
    talk, scr = advancers(qid, n)
    ids, cells, done_ids = set(), set(), set()
    place = False
    for o in objs:
        t = o.get('target') or {}
        for k in ('npc', 'creature', 'item', 'object'):
            if k in t: ids.update(_l(t[k]))
        if 'cell' in t: cells.update(('i', c) for c in _l(t['cell']))
        if 'place' in t: place = True
        if isinstance(t.get('in'), str): cells.add(('i', t['in'].lower()))
        cond_ids(o.get('doneIf'), done_ids)
    # holders of targeted items count as targeted
    for i in list(ids):
        for oid, ob in ():  # placeholder (holders are resolved by the builder)
            pass
    actors = set()      # ids that take part in any advancing transition
    need_items, need_dead = {}, set()
    for r in talk:
        if r['speaker']: actors.add(r['speaker'])
        for i, op, v in r['items']:
            if op in ('>=', '>', '==') and (v > 0 or op == '>'):
                need_items[i] = max(need_items.get(i, 0), v + (1 if op == '>' else 0))
        for i, op, v in r['dead']:
            if op in ('>=', '>', '==') and (v > 0 or op == '>'): need_dead.add(i)
    for r in scr:
        actors.update(r['owners'])
    # a speaker being dead is a failure branch, not a step
    need_dead -= actors
    rel = actors | set(need_items) | need_dead
    rel_cells = set()
    for a in rel:
        rel_cells |= cells_of(a)
    f = {'talk': len(talk), 'script': len(scr)}
    if not talk and not scr:
        f['no_transition'] = True
        return f
    specific = [r for r in talk if r['speaker']] + [r for r in scr if r['owners']]
    targeted = ids | done_ids
    hit = bool(targeted & rel) or bool(cells & rel_cells) or any(cells_of(i) & rel_cells for i in ids)
    if not ids and not cells and not place:
        f['no_target'] = True
    elif place and not ids and not cells:
        pass
    elif specific and not hit:
        f['unrelated_target'] = sorted(ids) + [c[1] for c in cells]
    f['actors'] = sorted(actors)
    miss_items = {i: c for i, c in need_items.items() if i not in targeted and i not in earlier and i != 'gold_001'}
    miss_dead = {i for i in need_dead if i not in targeted and i not in earlier}
    if miss_items: f['missing_item'] = miss_items
    if miss_dead: f['missing_dead'] = sorted(miss_dead)
    return f


def main():
    only = {a.lower() for a in sys.argv[1:]}
    stats = collections.Counter()
    rows = []
    for fpath in sorted(glob.glob(os.path.join(OBJ_DIR, '*.json'))):
        data = json.load(open(fpath))
        lists = data.get('lists', {})
        for qid, qd in data.get('quests', {}).items():
            if only and qid.lower() not in only: continue
            if qd.get('hide'): continue
            for skey, objs in (qd.get('stages') or {}).items():
                objs = expand(objs, lists)
                for s in str(skey).split(','):
                    n = int(s)
                    f = audit_stage(qid, n, objs)
                    stats['stages'] += 1
                    for k in ('no_transition', 'no_target', 'unrelated_target', 'missing_item', 'missing_dead'):
                        if k in f: stats[k] += 1
                    if any(k in f for k in ('no_target', 'unrelated_target', 'missing_item', 'missing_dead')):
                        rows.append({'file': os.path.basename(fpath), 'quest': qid, 'stage': n,
                                     'do': [o['do'] for o in objs], **{k: (sorted(v) if isinstance(v, set) else v) for k, v in f.items()}})
                    if only:
                        print(qid, n, [o['do'] for o in objs], f)
    print(dict(stats))
    if not only:
        json.dump(rows, open(os.path.join(HERE, 'audit.json'), 'w'), indent=1)
        byfile = collections.Counter((r['file'], k) for r in rows for k in ('no_target', 'unrelated_target', 'missing_item', 'missing_dead') if k in r)
        for (f, k), v in sorted(byfile.items()): print(f'{f:28s} {k:18s} {v}')


if __name__ == '__main__':
    main()

"""Finds people / items / places named in objective text that have no marker of their own."""
import glob, json, os, re, sys, collections
from world import world
HERE = os.path.dirname(os.path.abspath(__file__))
OBJ_DIR = os.path.join(os.path.dirname(HERE), 'objectives')
W = world()
ITEM_TYPES = {'WEAP', 'ARMO', 'CLOT', 'BOOK', 'MISC', 'ALCH', 'INGR', 'APPA', 'LOCK', 'PROB', 'REPA', 'LIGH'}
STOP = {'report', 'gold', 'key', 'note', 'letter', 'book', 'guard', 'ordinator', 'slave', 'rat', 'scroll', 'ring',
        'amulet', 'skull', 'bandit', 'smuggler', 'hunter', 'pilgrim', 'priest', 'healer', 'trader', 'publican',
        'master', 'dreamer', 'journal', 'orders', 'message', 'bread', 'sword', 'shield', 'helm', 'pick', 'probe'}

def build_index():
    names = collections.defaultdict(set)   # display name -> {(kind, id)}
    for oid, o in W['objs'].items():
        n = (o.get('name') or '').strip()
        if len(n) < 4 or n.lower() in STOP: continue
        if o['type'] in ('NPC_', 'CREA'):
            if oid in W['placed'] or True:
                names[n].add(('actor', oid))
        elif o['type'] in ITEM_TYPES:
            if ' ' in n or len(n) >= 7:
                names[n].add(('item', oid))
    for ck, m in W['cells'].items():
        n = (m.get('name') or '').strip()
        if not n: continue
        if ck[0] == 'i':
            names[n].add(('cell', n.lower()))
            parts = [p.strip() for p in n.split(',')]
            if len(parts) == 2 and len(parts[1]) >= 8:
                names[parts[1]].add(('cell', n.lower()))
                names[parts[1] + ', ' + parts[0]].add(('cell', n.lower()))
        else:
            if len(n) >= 5: names[n].add(('place', n.lower()))
    return names

NAMES = build_index()
# one regex over all names, longest first
_sorted = sorted(NAMES, key=len, reverse=True)
BIG = re.compile(r'(?<![A-Za-z])(' + '|'.join(re.escape(n) for n in _sorted) + r')(?![A-Za-z])')

def expand(objs, lists):
    out = []
    for o in objs:
        out += expand(lists.get(o[1:], []), lists) if isinstance(o, str) else [o]
    return out

def tids(t):
    out = []
    for k in ('npc', 'creature', 'item', 'object', 'cell', 'place'):
        v = t.get(k)
        if v is None: continue
        for x in (v if isinstance(v, list) else [v]):
            out.append((k, x.lower()))
    return out

def cond_ids(c, acc):
    if isinstance(c, dict):
        for k, v in c.items():
            if k in ('any', 'all'):
                for x in v: cond_ids(x, acc)
            elif k in ('has', 'dead') and isinstance(v, str): acc.add(v.lower())

def stage_mentions(objs):
    """returns list of (objective index, name, candidates) not covered by any target in the stage"""
    covered_ids, covered_cells, covered_names = set(), set(), set()
    for o in objs:
        t = o.get('target') or {}
        for k, x in tids(t):
            if k in ('cell', 'place'):
                covered_cells.add(x)
            else:
                covered_ids.add(x)
                for ck, _ in W['placed'].get(x, []):
                    covered_cells.add((W['cells'][ck]['name'] or '').lower())
                # who carries / contains the item
                for oid, ob in ():
                    pass
        if t.get('in'): covered_cells.add(t['in'].lower())
        if t.get('via'): covered_cells.add(t['via'].lower())
        acc = set(); cond_ids(o.get('doneIf'), acc); covered_ids |= acc
    for i in covered_ids:
        n = (W['objs'].get(i) or {}).get('name')
        if n: covered_names.add(n)
    out = []
    for idx, o in enumerate(objs):
        seen = set()
        text = o['do']
        has_target = any(x.get('target') for x in objs)
        for m in BIG.finditer(text):
            n = m.group(1)
            if n in seen or n in covered_names: continue
            seen.add(n)
            cands = NAMES[n]
            kinds = {k for k, _ in cands}
            if text[m.end():m.end() + 2] in ("'s", "\u2019s"): continue          # "Neloth's captain"
            in_paren = text.count('(', 0, m.start()) > text.count(')', 0, m.start())
            if kinds <= {'place', 'cell'} and (in_paren or (kinds == {'place'} and has_target)): continue
            if any(k in ('cell', 'place') and i in covered_cells for k, i in cands): continue
            if any(k in ('actor', 'item') and i in covered_ids for k, i in cands): continue
            # a place name that is just the town of a covered cell ("..., Vivec")
            if all(k == 'place' for k, i in cands) and any(c.startswith(n.lower()) or c.endswith(n.lower()) for c in covered_cells): continue
            out.append((idx, n, sorted(cands)[:6]))
    return out

def main():
    stats = collections.Counter(); rows = []
    for f in sorted(glob.glob(os.path.join(OBJ_DIR, '*.json'))):
        d = json.load(open(f)); L = d.get('lists', {})
        for qid, q in d.get('quests', {}).items():
            if q.get('hide'): continue
            for skey, objs in (q.get('stages') or {}).items():
                objs = expand(objs, L)
                ms = stage_mentions(objs)
                stats['stages'] += 1
                if ms:
                    stats['flagged'] += 1; stats[os.path.basename(f)] += 1
                    rows.append((os.path.basename(f), qid, skey, [o['do'] for o in objs], [(i, n, [c[0] for c in cs][:1]) for i, n, cs in ms]))
    print(dict(stats))
    import random; random.seed(5)
    for r in random.sample(rows, 25): print(r[1], r[2], r[3], '=>', r[4])
if __name__ == '__main__': main()

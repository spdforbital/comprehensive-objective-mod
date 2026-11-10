"""List every journal quest in the load order: id, quest name, plugin, stage count."""
import json, sys
from esm import load_order, records, subs, zstr

quests = {}
for plugin, path in load_order():
    cur = None
    for tag, body in records(path):
        if tag == 'DIAL':
            name = None; typ = None
            for st, v in subs(body):
                if st == 'NAME': name = zstr(v)
                elif st == 'DATA' and len(v) >= 1: typ = v[0]
            cur = name if typ == 4 else None
            if cur:
                q = quests.setdefault(cur.lower(), {'id': cur, 'plugin': plugin, 'name': None, 'stages': set()})
        elif tag == 'INFO' and cur:
            q = quests[cur.lower()]
            idx = None; isname = False
            for st, v in subs(body):
                if st == 'DATA' and len(v) >= 12: idx = int.from_bytes(v[4:8], 'little', signed=True)
                elif st == 'QSTN': isname = True
                elif st == 'NAME' and isname is False: text = v
            if isname:
                for st, v in subs(body):
                    if st == 'NAME': q['name'] = zstr(v)
            elif idx is not None:
                q['stages'].add(idx)

out = [{'id': q['id'], 'name': q['name'], 'plugin': q['plugin'], 'stages': sorted(q['stages'])} for q in quests.values()]
json.dump(out, open(sys.argv[1], 'w'), indent=1)
from collections import Counter
c = Counter(q['plugin'] for q in out)
print(len(out), 'quest ids')
for p, n in c.most_common(): print(f'{n:5}  {p}')

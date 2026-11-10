"""Builds an index of the game world from the active load order.

Answers: where is this NPC / creature / item / object placed, which doors lead
into a cell, what does a quest's journal say at each stage. Later plugins
override earlier ones the same way the game does (by reference number), so
mods that move doors or people are respected.

Usage:
  python3 world.py build            # (re)build cache: world.pickle
  python3 world.py find <text>      # search records by id or display name
  python3 world.py where <id>       # placed locations of a record id
  python3 world.py journal <questId># journal text for every stage
  python3 world.py cell <cell name> # doors leading into a cell
  python3 world.py mods <questId>   # which mods change a quest's journal
  python3 world.py talk <questId>   # dialogue (topic + speaker) and scripts that move a quest
"""
import os, pickle, struct, sys
from esm import load_order, records, subs, zstr

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'world.pickle')

NAMED_TYPES = {'NPC_', 'CREA', 'WEAP', 'ARMO', 'CLOT', 'BOOK', 'MISC', 'ALCH',
               'INGR', 'APPA', 'LOCK', 'PROB', 'REPA', 'LIGH', 'CONT', 'ACTI', 'DOOR'}
ITEM_TYPES = {'WEAP', 'ARMO', 'CLOT', 'BOOK', 'MISC', 'ALCH', 'INGR', 'APPA',
              'LOCK', 'PROB', 'REPA', 'LIGH'}


def build():
    objs = {}       # id.lower() -> {id, type, name, plugin, inventory:{item:count}}
    cells = {}      # cellkey -> {name, interior, grid, refs:{refkey: ref}}
    journal = {}    # questId.lower() -> {id, name, stages:{idx: text}}
    talk = {}       # questId.lower() -> [ {topic, speaker, text, sets, plugin} ] dialogue that changes the journal
    scripted = {}   # questId.lower() -> [ {script, sets, plugin} ] scripts that change the journal
    import re
    JRE0 = re.compile(r'journal\s*,?\s*(?:"([^"]+)"|([A-Za-z0-9_\-\']+))\s*,?\s*(-?\d+)', re.I)
    class _J:  # findall -> (questId, stage)
        @staticmethod
        def findall(t):
            return [((a or b), n) for a, b, n in JRE0.findall(t)]
    JRE = _J
    for plugin, path in load_order():
        masters = []
        dial = None
        anyDial = None
        for tag, body in records(path):
            if tag == 'TES3':
                masters = [zstr(v) for st, v in subs(body) if st == 'MAST']
            elif tag in NAMED_TYPES:
                rid = name = None
                inv = {}
                deleted = False
                for st, v in subs(body):
                    if st == 'NAME' and rid is None: rid = zstr(v)
                    elif st == 'FNAM': name = zstr(v)
                    elif st == 'DELE': deleted = True
                    elif st in ('NPCO', 'CNTO') and len(v) >= 36:
                        cnt = struct.unpack('<i', v[:4])[0]
                        inv[zstr(v[4:36]).lower()] = cnt
                if not rid: continue
                if deleted:
                    objs.pop(rid.lower(), None); continue
                old = objs.get(rid.lower(), {})
                objs[rid.lower()] = {'id': rid, 'type': tag, 'name': name or old.get('name'),
                                     'plugin': plugin, 'inventory': inv or old.get('inventory', {})}
            elif tag == 'CELL':
                cname = None; interior = False; grid = None
                refs = []; cur = None
                for st, v in subs(body):
                    if cur is None and st == 'NAME' and cname is None: cname = zstr(v)
                    elif cur is None and st == 'DATA' and len(v) >= 12:
                        flags, gx, gy = struct.unpack('<Iii', v[:12])
                        interior = bool(flags & 1); grid = (gx, gy)
                    elif st == 'FRMR':
                        rn = struct.unpack('<I', v[:4])[0]
                        mi = rn >> 24
                        origin = plugin if mi == 0 else (masters[mi - 1] if mi - 1 < len(masters) else plugin)
                        cur = {'key': (origin.lower(), rn & 0xFFFFFF)}
                        refs.append(cur)
                    elif cur is not None:
                        if st == 'NAME': cur['id'] = zstr(v)
                        elif st == 'DATA' and len(v) >= 24: cur['pos'] = struct.unpack('<6f', v[:24])
                        elif st == 'DODT' and len(v) >= 24: cur['dest'] = struct.unpack('<6f', v[:24])
                        elif st == 'DNAM': cur['destCell'] = zstr(v)
                        elif st == 'DELE': cur['deleted'] = True
                if interior:
                    ck = ('i', (cname or '').lower())
                else:
                    ck = ('e', grid)
                c = cells.setdefault(ck, {'name': cname or '', 'interior': interior, 'grid': grid, 'refs': {}})
                if cname: c['name'] = cname
                for r in refs:
                    if r.get('deleted'):
                        c['refs'].pop(r['key'], None)
                    elif 'id' in r:
                        prev = c['refs'].get(r['key'], {})
                        prev.update(r)
                        c['refs'][r['key']] = prev
            elif tag == 'DIAL':
                name = typ = None
                for st, v in subs(body):
                    if st == 'NAME': name = zstr(v)
                    elif st == 'DATA' and len(v) >= 1: typ = v[0]
                dial = name if typ == 4 else None
                anyDial = name
                if dial:
                    journal.setdefault(dial.lower(), {'id': dial, 'name': None, 'stages': {}, 'finished': set()})
            elif tag == 'INFO' and not dial and anyDial:
                speaker = text = result = None
                for st, v in subs(body):
                    if st == 'ONAM': speaker = zstr(v)
                    elif st == 'NAME': text = zstr(v)
                    elif st == 'BNAM': result = zstr(v)
                if result:
                    for qid, n in JRE.findall(result):
                        talk.setdefault(qid.strip().lower(), []).append(
                            {'topic': anyDial, 'speaker': speaker, 'text': (text or '')[:160], 'sets': int(n), 'plugin': plugin})
            elif tag == 'SCPT':
                sname = None; stext = None
                for st, v in subs(body):
                    if st == 'SCHD' and len(v) >= 32: sname = zstr(v[:32])
                    elif st == 'SCTX': stext = zstr(v)
                if sname and stext:
                    for qid, n in JRE.findall(stext):
                        scripted.setdefault(qid.strip().lower(), []).append({'script': sname, 'sets': int(n), 'plugin': plugin})
            elif tag == 'INFO' and dial:
                q = journal[dial.lower()]
                idx = None; text = None; isname = fin = False
                for st, v in subs(body):
                    if st == 'DATA' and len(v) >= 12: idx = struct.unpack('<i', v[4:8])[0]
                    elif st == 'NAME': text = zstr(v)
                    elif st == 'QSTN': isname = True
                    elif st == 'QSTF': fin = True
                if isname: q['name'] = text
                elif idx is not None:
                    q['stages'][idx] = text
                    if fin: q['finished'].add(idx)
                    q.setdefault('byPlugin', {}).setdefault(plugin, {})[idx] = text

    # placed locations and door graph
    placed = {}   # id.lower() -> [(cellkey, pos)]
    doors_into = {}  # target cellkey -> [(fromcellkey, doorpos)]
    for ck, c in cells.items():
        for r in c['refs'].values():
            if 'pos' not in r: continue
            placed.setdefault(r['id'].lower(), []).append((ck, r['pos'][:3]))
            if 'dest' in r:
                if r.get('destCell'):
                    tk = ('i', r['destCell'].lower())
                else:
                    gx = int(r['dest'][0] // 8192); gy = int(r['dest'][1] // 8192)
                    tk = ('e', (gx, gy))
                doors_into.setdefault(tk, []).append((ck, r['pos'][:3], r['dest'][:3]))
    cellmeta = {ck: {'name': c['name'], 'interior': c['interior'], 'grid': c['grid']} for ck, c in cells.items()}
    data = {'objs': objs, 'placed': placed, 'doors_into': doors_into, 'cells': cellmeta, 'journal': journal,
            'talk': talk, 'scripted': scripted}
    tmp = CACHE + '.tmp'
    pickle.dump(data, open(tmp, 'wb'))
    os.replace(tmp, CACHE)   # atomic: other tools may be reading the cache
    print(f"objects {len(objs)}, placed ids {len(placed)}, cells {len(cells)}, quests {len(journal)}")


_W = None
def world():
    global _W
    if _W is None:
        _W = pickle.load(open(CACHE, 'rb'))
    return _W


def cell_label(ck):
    m = world()['cells'].get(ck, {})
    if ck[0] == 'i':
        return m.get('name') or ck[1]
    name = m.get('name') or 'Wilderness'
    return f"{name} {ck[1]}"


def entrances(ck, max_depth=6):
    """Doors on the shortest routes from outdoors into cell ck.
    Returns list of (cellkey, doorpos): each door you walk through, in the cell it is in,
    from the outdoor door down to the door into ck."""
    if ck[0] == 'e':
        return []
    w = world()
    level = {ck}
    seen = {ck}
    parents = {}   # cell -> [(child cell it leads into, doorpos)]
    found = set()
    for _ in range(max_depth):
        nxt = set()
        for c in level:
            for frm, dpos, _dest in w['doors_into'].get(c, []):
                if frm in seen and frm not in nxt:
                    continue
                parents.setdefault(frm, []).append((c, dpos))
                if frm[0] == 'e':
                    found.add(frm)
                else:
                    nxt.add(frm)
        if found:
            break
        seen |= nxt
        level = nxt
        if not level:
            break
    # walk back from the outdoor cells to the target, keeping only doors on those routes
    out, stack, used = [], list(found), set()
    while stack:
        c = stack.pop()
        for child, dpos in parents.get(c, []):
            if (c, dpos) in used:
                continue
            used.add((c, dpos))
            out.append((c, dpos))
            if child != ck:
                stack.append(child)
    return out


def where(rid):
    w = world()
    rid = rid.lower()
    res = list(w['placed'].get(rid, []))
    holders = []
    for oid, o in w['objs'].items():
        if rid in o.get('inventory', {}):
            holders.append(oid)
            res += [(ck, p) for ck, p in w['placed'].get(oid, [])]
    return res, holders


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'build':
        build(); return
    w = world()
    arg = ' '.join(sys.argv[2:])
    if cmd == 'find':
        a = arg.lower()
        n = 0
        for oid, o in w['objs'].items():
            if a in oid or a in (o['name'] or '').lower():
                locs = w['placed'].get(oid, [])
                where_s = '; '.join(sorted({cell_label(ck) for ck, _ in locs})[:3]) or 'not placed (spawned by script/list?)'
                print(f"{o['type']} {o['id']!r} \"{o['name']}\" [{o['plugin']}] -> {where_s}")
                n += 1
                if n >= 40: break
    elif cmd == 'where':
        res, holders = where(arg)
        o = w['objs'].get(arg.lower())
        print(f"{o['type'] if o else '?'} {arg} \"{o['name'] if o else ''}\"")
        if holders: print('  carried/contained by:', ', '.join(holders[:15]))
        for ck, p in res[:25]:
            print(f"  {cell_label(ck)}  pos=({p[0]:.0f},{p[1]:.0f},{p[2]:.0f})")
        if not res: print('  NOT PLACED in any cell')
    elif cmd == 'journal':
        q = w['journal'].get(arg.lower())
        if not q: print('no such quest'); return
        print(f"{q['id']} — {q['name']}")
        for i in sorted(q['stages']):
            f = ' [FINISHES QUEST]' if i in q['finished'] else ''
            print(f"  {i}{f}: {q['stages'][i]}")
    elif cmd == 'talk':
        # who you talk to / which scripts move this quest, and to which stage
        q = arg.lower()
        rows = w.get('talk', {}).get(q, [])
        srows = w.get('scripted', {}).get(q, [])
        if not rows and not srows: print('no dialogue or script found that changes', arg); return
        for r in sorted(rows, key=lambda r: r['sets']):
            print(f"  stage {r['sets']}: talk to {r['speaker'] or '(anyone)'} about '{r['topic']}' [{r['plugin']}]  \"{r['text']}\"")
        for r in sorted(srows, key=lambda r: r['sets']):
            print(f"  stage {r['sets']}: set by script {r['script']} [{r['plugin']}]")
    elif cmd == 'mods':
        # which plugins write journal entries for this quest, and what they change
        q = w['journal'].get(arg.lower())
        if not q: print('no such quest'); return
        bp = q.get('byPlugin', {})
        plugins = list(bp)
        base = plugins[0] if plugins else None
        print(f"{q['id']} — defined by {base}")
        for p in plugins[1:]:
            changed = [i for i, t in bp[p].items() if bp[base].get(i) != t]
            new = [i for i in bp[p] if i not in bp[base]]
            print(f"  {p}: touches stages {sorted(bp[p])}; text changed {sorted(set(changed)-set(new))}; new stages {sorted(new)}")
        if len(plugins) == 1: print('  no other mod changes this quest')
    elif cmd == 'cell':
        ck = ('i', arg.lower())
        if ck not in w['cells']:
            print('no interior cell named', arg); return
        for frm, dpos in entrances(ck):
            print(f"  door in {cell_label(frm)} at ({dpos[0]:.0f},{dpos[1]:.0f},{dpos[2]:.0f})")
    else:
        print(__doc__)


if __name__ == '__main__':
    main()

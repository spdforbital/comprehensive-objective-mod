"""Builds scripts/comprehensive_objectives/quest_starts.lua for the Collector's Ledger's Quests tab:
for every named quest, how it starts (who to talk to and about what, or what to use / find / enter),
where that is, what the start needs (other quests, faction, level, items), and which plugin it comes from.

Usage (from tools/): python3 build_quest_starts.py     (needs world.pickle and questgraph.pickle:
                     python3 world.py build; python3 questgraph.py build)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import world as Wm
from questgraph import graph, stage_ok, parse_scvr
import bisect, re, struct
from esm import load_order, records, subs, zstr

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'comprehensive_objectives', 'quest_starts.lua')
BASE = {'morrowind.esm': 'Morrowind', 'tribunal.esm': 'Tribunal', 'bloodmoon.esm': 'Bloodmoon'}
NICE = {'tr_mainland.esm': 'Tamriel Rebuilt', 'tamriel_data.esm': 'Tamriel Rebuilt',
        'cyr_main.esm': 'Project Cyrodiil', 'sky_main.esm': 'Skyrim: Home of the Nords'}
MAX_OPTS = 3
DIAL_GREETING = 2


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', ' ') + '"'


def mod_name(plugin):
    p = plugin.lower()
    if p in BASE: return BASE[p]
    if p in NICE: return NICE[p]
    return os.path.splitext(plugin)[0]


ADDTOPIC = re.compile(r'addtopic\s*,?\s*(?:"([^"]+)"|([A-Za-z][\w\']*))', re.I)
GENERIC_SPEAKER = None


def scan_infos():
    """every dialogue line in the load order (later plugins override), with its journal conditions"""
    infos = {}
    for plugin, path in load_order():
        cur = typ = None
        for tag, body in records(path):
            if tag == 'DIAL':
                cur = typ = None
                for st, v in subs(body):
                    if st == 'NAME': cur = zstr(v)
                    elif st == 'DATA' and len(v) >= 1: typ = v[0]
            elif tag == 'INFO' and cur is not None:
                d = {'dial': cur, 'type': typ, 'conds': []}
                pend = None; dele = False
                for st, v in subs(body):
                    if st == 'INAM': d['id'] = zstr(v)
                    elif st == 'ONAM': d['speaker'] = zstr(v).lower()
                    elif st == 'FNAM': d['faction'] = zstr(v)
                    elif st == 'ANAM': d['cell'] = zstr(v)
                    elif st == 'NAME': d['text'] = zstr(v)
                    elif st == 'BNAM': d['result'] = zstr(v)
                    elif st == 'DELE': dele = True
                    elif st == 'SCVR': pend = v
                    elif st in ('INTV', 'FLTV') and pend is not None:
                        val = struct.unpack('<i' if st == 'INTV' else '<f', v[:4])[0]
                        c = parse_scvr(pend, val)
                        if c and c['kind'] == 'journal': d['conds'].append((c['name'].lower(), c['op'], int(val)))
                        pend = None
                if 'id' not in d: continue
                key = (cur.lower(), d['id'])
                if dele: infos.pop(key, None)
                else: infos[key] = d
            elif tag != 'INFO':
                cur = None
    return [d for d in infos.values() if d.get('type') in (0, 2, 3)]


def topic_sources(want, name_of):
    """how the player learns each wanted topic: lines that AddTopic it or say it (a hyperlink teaches it)"""
    infos = scan_infos()
    src = {t: [] for t in want}
    for d in infos:
        for a, b in ADDTOPIC.findall(d.get('result') or ''):
            t = (a or b).strip().lower()
            if t in src: src[t].append(('add', d))
    texts = [(d.get('text') or '').lower() for d in infos]
    starts, pos = [], 0
    for t in texts:
        starts.append(pos); pos += len(t) + 1
    big = '\x00'.join(texts)
    for t in want:
        if len(t) < 3: continue
        i, found = big.find(t), 0
        while i >= 0 and found < 40:
            k = bisect.bisect_right(starts, i) - 1
            d = infos[k]
            before = big[i - 1] if i > 0 else ' '
            after = big[i + len(t)] if i + len(t) < len(big) else ' '
            if not (before.isalnum() or after.isalnum()) and d['dial'].lower() != t:
                src[t].append(('said', d)); found += 1
            i = big.find(t, i + 1)
    out = {}
    for t, lst in src.items():
        rows = []
        for via, d in lst:
            sp = d.get('speaker')
            who = name_of(sp) if sp else ('members of ' + d['faction'] if d.get('faction') else
                                          ('anyone in ' + d['cell'] if d.get('cell') else 'anyone'))
            rows.append({'via': via, 'sp': sp, 'w': who, 't': d['dial'], 'g': d.get('type') == 2,
                         'q': [c for c in d['conds'] if c[0] != '']})
        out[t] = rows
    return out


def main():
    W = Wm.world()
    G = graph()['quests']
    cell_idx, cell_rows = {}, []

    def outdoor_name(gx, gy):
        return W['cells'].get(('e', (gx, gy)), {}).get('name') or ''

    def cidx(ck):
        if ck in cell_idx: return cell_idx[ck]
        if ck[0] == 'e':
            row = {'n': outdoor_name(*ck[1]) or 'Wilderness', 'e': True}
        else:
            row = {'n': W['cells'].get(ck, {}).get('name') or ck[1], 'id': ck[1], 'D': []}
            try:
                route = Wm.entrances(ck)
            except Exception:
                route = []
            for dck, dpos in route[:12]:
                row['D'].append((dck[0] == 'e', dck, dpos))
            for dck, dpos in route:
                if dck[0] == 'e':
                    row['near'] = outdoor_name(int(dpos[0] // 8192), int(dpos[1] // 8192))
                    break
        cell_rows.append(row)
        cell_idx[ck] = len(cell_rows)
        return cell_idx[ck]

    def name_of(rid):
        o = W['objs'].get(rid.lower())
        return (o and o.get('name')) or rid

    def place(rid):
        pl = W['placed'].get(rid.lower(), [])
        if not pl: return None
        ck, p = pl[0]
        return cidx(ck), p

    def journal_name(qid):
        j = W['journal'].get(qid)
        return j and j.get('name')

    def needs(r):
        """start conditions of a dialogue line, as data for the ledger"""
        out = {}
        oq = [(oq_, op, v) for oq_, op, v in r['otherq']]
        if oq: out['q'] = oq
        if r.get('pcfaction'): out['f'] = (r['pcfaction'], r.get('pcrank', -1))
        items = [(i, op, v) for i, op, v in r['items'] if i != 'gold_001' or v > 0]
        if items: out['i'] = items
        for f, op, v in r.get('funcs', []):
            if f == '06': out['l'] = (op, int(v))
        if r.get('disp', 0) > 0: out['d'] = r['disp']
        hidden = []
        if r['dead']: hidden.append('someone must be dead')
        if r.get('globals'): hidden.append('a game condition')
        if any(f not in ('50', '06', '63', '64', '65', '73') for f, _, _ in r.get('funcs', [])): hidden.append('a stat or standing')
        if hidden: out['h'] = ', '.join(sorted(set(hidden)))
        return out

    import json
    QP = {x['id'].lower(): x.get('plugin') or '' for x in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quests.json')))}
    quests = []
    counts = {'talk': 0, 'use': 0, 'death': 0, 'cell': 0, 'auto': 0, 'none': 0}
    for qid, j in W['journal'].items():
        name = (j.get('name') or '').strip()
        if not name or name.lower() == 'none': continue
        g = G.get(qid)
        if not g: counts['none'] += 1; continue
        opts = []
        talk = [r for r in g['talk'] if r['sets'] > 0 and stage_ok(r['stage'], 0)]
        if talk:
            m = min(r['sets'] for r in talk)
            seen = set()
            for r in sorted(talk, key=lambda r: (r['sets'] != m, r['choice'])):
                if r['sets'] != m: continue
                who_id = r['speaker']
                key = (who_id or r['cell'] or r['faction'] or '', r['topic'].lower())
                if key in seen: continue
                seen.add(key)
                o = {'k': 'talk', 't': r['topic'], 'g': r['type'] == DIAL_GREETING, 'n': needs(r), 'pl': r['plugin']}
                if who_id:
                    o['w'] = name_of(who_id); o['r'] = who_id
                    pp = place(who_id)
                    if pp: o['c'], o['p'] = pp
                else:
                    bits = []
                    if r['faction']: bits.append('a member of ' + r['faction'])
                    if r['class']: bits.append('a ' + r['class'])
                    if r['race']: bits.append('a ' + r['race'])
                    o['w'] = (bits[0] if bits else 'anyone') + (' in ' + r['cell'] if r['cell'] else '')
                    if r['cell'] and ('i', r['cell'].lower()) in W['cells']:
                        o['c'] = cidx(('i', r['cell'].lower()))
                opts.append(o)
                if len(opts) >= MAX_OPTS: break
            counts['talk'] += 1
        else:
            scr = [r for r in g['script'] if r['sets'] > 0 and stage_ok(r['stage'], 0)]
            if not scr: counts['none'] += 1; continue
            m = min(r['sets'] for r in scr)
            for r in scr:
                if r['sets'] != m: continue
                fl = r['flags']
                kind = ('use' if 'onactivate' in fl or 'onpcadd' in fl or 'onpcequip' in fl else
                        'death' if ('ondeath' in fl or 'onmurder' in fl or r['dead']) else
                        'cell' if (r['cells'] or 'getpccell' in fl) else 'auto')
                o = {'k': kind, 'n': {}, 'pl': r['plugin']}
                if r['items']: o['n']['i'] = [(i, op, v) for i, op, v in r['items']]
                own = next((x for x in r['owners'] if W['placed'].get(x)), None)
                if kind == 'cell' and r['cells']:
                    o['w'] = r['cells'][0]
                    ck = ('i', r['cells'][0].lower())
                    if ck in W['cells']: o['c'] = cidx(ck)
                elif kind == 'death' and r['dead']:
                    o['w'] = name_of(r['dead'][0][0]); o['r'] = r['dead'][0][0]
                    pp = place(r['dead'][0][0])
                    if pp: o['c'], o['p'] = pp
                elif own:
                    o['w'] = name_of(own); o['r'] = own
                    pp = place(own)
                    if pp: o['c'], o['p'] = pp
                else:
                    o['w'] = ''
                opts.append(o)
                if len(opts) >= MAX_OPTS: break
            counts[opts[0]['k'] if opts else 'none'] += 1
        if opts:
            plug = QP.get(qid) or opts[0]['pl']
            quests.append((name, j['id'], mod_name(plug), plug.lower() in BASE, opts))
    quests.sort(key=lambda x: (x[0].lower(), x[1]))

    # how each start topic is learned
    want = {o['t'].lower() for *_, opts in quests for o in opts if o['k'] == 'talk' and o.get('t') and not o.get('g')}
    TS = topic_sources(want, name_of)
    easy = 0
    for *_, opts in quests:
        for o in opts:
            if o['k'] != 'talk' or not o.get('t') or o.get('g'): continue
            rows = TS.get(o['t'].lower(), [])
            # learned on the spot: said without conditions by anyone, or by the quest giver themself
            if any(not r['q'] and (r['sp'] is None or r['sp'] == o.get('r')) for r in rows):
                easy += 1; continue
            rows.sort(key=lambda r: (len(r['q']), r['via'] != 'add', r['sp'] is None))
            seen, keep = set(), []
            for r in rows:
                k = (r['w'], r['t'])
                if k in seen: continue
                seen.add(k); keep.append(r)
                if len(keep) >= 3: break
            o['L'] = keep
            o['tk'] = o['t'].lower()
    print('start topics learned on the spot:', easy)

    # one entry per quest name: the game splits some quests into several journal ids
    grouped, order = {}, []
    for name, qid, mod, base, opts in quests:
        key = (name.lower(), base)
        if key not in grouped:
            grouped[key] = [name, [qid], mod, base, []]; order.append(key)
        else:
            grouped[key][1].append(qid)
        g = grouped[key]
        have = {(o['k'], o.get('r'), (o.get('t') or '').lower()) for o in g[4]}
        for o in opts:
            k = (o['k'], o.get('r'), (o.get('t') or '').lower())
            if k not in have and len(g[4]) < 5:
                g[4].append(o); have.add(k)
    quests = [tuple(grouped[k]) for k in order]

    # route-door cells need indices too
    for row in list(cell_rows):
        if row.get('e'): continue
        parts = []
        for ext, dck, dpos in row['D']:
            c = 'e' if ext else str(cidx(dck))
            parts.append(f"{c},{dpos[0]:.0f},{dpos[1]:.0f},{dpos[2]:.0f}")
        row['Ds'] = ';'.join(parts)

    def lt(seq):
        return '{' + ', '.join('{' + ', '.join(q(a) if isinstance(a, str) else str(int(a)) for a in t) + '}' for t in seq) + '}'

    lines = ['-- GENERATED by tools/build_quest_starts.py from the active load order. Do not edit by hand.',
             '-- cells[i] = { n, id, e, near, D } as in people_data.lua',
             "-- quests[i] = { n = name, id = quest id, m = plugin name, b = base game, o = { start options } }",
             "--   option: k = talk|use|death|cell|auto, w = who/what, r = record id, c = cell, x/y/z, t = topic,",
             "--           g = greeting, q = {{quest, op, stage}}, f = {faction, rank}, i = {{item, op, n}},",
             "--           l = {op, level}, d = disposition, h = hidden conditions,",
             "--           tk = topic to learn first, L = { { w = who, t = their topic, g = greeting, a = AddTopic, q = conds } }",
             'local cells = {}']
    for i, row in enumerate(cell_rows, 1):
        f = [f"n = {q(row['n'])}"]
        if row.get('e'): f.append('e = true')
        else:
            f.append(f"id = {q(row['id'])}")
            if row.get('near'): f.append(f"near = {q(row['near'])}")
            if row.get('Ds'): f.append(f"D = {q(row['Ds'])}")
        lines.append(f"cells[{i}] = {{ {', '.join(f)} }}")
    lines.append('local quests = {')
    for name, qids, mod, base, opts in quests:
        os_ = []
        for o in opts:
            f = [f"k = {q(o['k'])}", f"w = {q(o.get('w', ''))}"]
            if o.get('r'): f.append(f"r = {q(o['r'].lower())}")
            if o.get('c'): f.append(f"c = {o['c']}")
            if o.get('p'): f.append(f"x = {o['p'][0]:.0f}, y = {o['p'][1]:.0f}, z = {o['p'][2]:.0f}")
            if o.get('t'): f.append(f"t = {q(o['t'])}")
            if o.get('g'): f.append('g = true')
            n = o['n']
            if n.get('q'): f.append('q = ' + lt(n['q']))
            if n.get('f'): f.append(f"f = {{ {q(n['f'][0].lower())}, {int(n['f'][1])} }}")
            if n.get('i'): f.append('i = ' + lt(n['i']))
            if n.get('l'): f.append(f"l = {{ {q(n['l'][0])}, {n['l'][1]} }}")
            if n.get('d'): f.append(f"d = {int(n['d'])}")
            if n.get('h'): f.append(f"h = {q(n['h'])}")
            if o.get('tk'):
                f.append(f"tk = {q(o['tk'])}")
                ls = []
                for r in o.get('L', []):
                    ls.append('{ ' + ', '.join([f"w = {q(r['w'])}", f"t = {q(r['t'])}"] + (['g = true'] if r['g'] else [])
                                               + ([f"a = true"] if r['via'] == 'add' else [])
                                               + ([f"q = {lt(r['q'])}"] if r['q'] else [])) + ' }')
                f.append('L = { ' + ', '.join(ls) + ' }')
            os_.append('{ ' + ', '.join(f) + ' }')
        ids = '{ ' + ', '.join(q(x.lower()) for x in qids) + ' }'
        lines.append(f"  {{ n = {q(name)}, id = {q(qids[0].lower())}, ids = {ids}, m = {q(mod)}{', b = true' if base else ''}, o = {{ {', '.join(os_)} }} }},")
    lines.append('}')
    # names of every quest a requirement refers to
    ref = set()
    for _n, _ids, _m, _b, opts in quests:
        for o in opts:
            ref |= {c[0] for c in o['n'].get('q', [])}
            for r in o.get('L', []): ref |= {c[0] for c in r['q']}
    lines.append('local names = {')
    for rid in sorted(ref):
        nm = (W['journal'].get(rid) or {}).get('name')
        if nm and nm.strip() and nm.strip().lower() != 'none':
            lines.append(f"  [{q(rid)}] = {q(nm.strip())},")
    lines.append('}')
    lines.append('return { cells = cells, quests = quests, names = names }')
    tmp = OUT + '.tmp'
    open(tmp, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    os.replace(tmp, OUT)
    print(f"quests {len(quests)} (starts: {counts}), cells {len(cell_rows)}, "
          f"{os.path.getsize(OUT) / 1e6:.2f} MB -> {OUT}")


if __name__ == '__main__':
    main()

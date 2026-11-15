"""Builds scripts/comprehensive_objectives/quest_starts.lua for the Collector's Ledger's Quests tab:
for every named quest, how it starts (who to talk to and about what, or what to use / find / enter),
where that is, what the start needs (other quests, faction, level, items), and which plugin it comes from.

Usage (from tools/): python3 build_quest_starts.py     (needs world.pickle and questgraph.pickle:
                     python3 world.py build; python3 questgraph.py build)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import world as Wm
from questgraph import graph, stage_ok

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
             "--           l = {op, level}, d = disposition, h = hidden conditions",
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
    for name, qid, mod, base, opts in quests:
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
            os_.append('{ ' + ', '.join(f) + ' }')
        lines.append(f"  {{ n = {q(name)}, id = {q(qid.lower())}, m = {q(mod)}{', b = true' if base else ''}, o = {{ {', '.join(os_)} }} }},")
    lines.append('}')
    lines.append('return { cells = cells, quests = quests }')
    tmp = OUT + '.tmp'
    open(tmp, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    os.replace(tmp, OUT)
    print(f"quests {len(quests)} (starts: {counts}), cells {len(cell_rows)}, "
          f"{os.path.getsize(OUT) / 1e6:.2f} MB -> {OUT}")


if __name__ == '__main__':
    main()

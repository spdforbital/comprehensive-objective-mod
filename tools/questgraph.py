"""Extracts from the active load order what actually moves each quest forward.

For every quest: the dialogue lines and scripts that set its journal, with their
conditions (which stage must hold, which items / kills are required, who speaks).
build_objectives.py and audit.py use this to check and complete the authored objectives.

Usage:
  python3 questgraph.py build          # writes questgraph.pickle
  python3 questgraph.py show <QuestId> # transitions of one quest
"""
import os, pickle, re, struct, sys
from esm import load_order, records, subs, zstr

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'questgraph.pickle')

JRE = re.compile(r'journal\s*,?\s*(?:"([^"]+)"|([A-Za-z0-9_\-\']+))\s*,?\s*(-?\d+)', re.I)
OPS = {'0': '==', '1': '!=', '2': '>', '3': '>=', '4': '<', '5': '<='}
SCRIPTED_TYPES = {'NPC_', 'CREA', 'ACTI', 'CONT', 'DOOR', 'WEAP', 'ARMO', 'CLOT', 'BOOK', 'MISC', 'ALCH',
                  'INGR', 'APPA', 'LOCK', 'PROB', 'REPA', 'LIGH'}

ITEM_RE = re.compile(r'(?:player\s*->\s*)?(additem|removeitem)\s*,?\s*(?:"([^"]+)"|([A-Za-z0-9_\-\'\.]+))\s*,?\s*(\d+)?', re.I)
# script conditions
C_JIDX = re.compile(r'getjournalindex\s*,?\s*(?:"([^"]+)"|([A-Za-z0-9_\-\']+))\s*\)?\s*(==|!=|>=|<=|>|<)\s*(-?\d+)', re.I)
C_ITEM = re.compile(r'(?:player\s*->\s*)?getitemcount\s*,?\s*(?:"([^"]+)"|([A-Za-z0-9_\-\'\.]+))\s*\)?\s*(==|!=|>=|<=|>|<)\s*(-?\d+)', re.I)
C_DEAD = re.compile(r'getdeadcount\s*,?\s*(?:"([^"]+)"|([A-Za-z0-9_\-\'\.]+))\s*\)?\s*(==|!=|>=|<=|>|<)\s*(-?\d+)', re.I)
C_CELL = re.compile(r'getpccell\s*,?\s*"([^"]+)"', re.I)
C_REFDEAD = re.compile(r'(?:"([^"]+)"|([A-Za-z0-9_\-\'\.]+))\s*->\s*(?:gethealth\s*\)?\s*(?:<=|<|==)\s*[01]\b|ondeath)', re.I)


def parse_scvr(v, val):
    s = v.decode('latin1')
    if len(s) < 5:
        return None
    typ, func, op, name = s[1], s[2:4], OPS.get(s[4], '?'), s[5:].split('\0')[0]
    kind = {'1': 'func', '2': 'global', '3': 'local', '4': 'journal', '5': 'item', '6': 'dead',
            '7': 'notid', '8': 'notfaction', '9': 'notclass', 'A': 'notrace', 'B': 'notcell', 'C': 'notlocal'}.get(typ, typ)
    return {'kind': kind, 'func': func, 'op': op, 'name': name, 'val': val}


def script_journal_calls(text):
    """journal calls in a script with the if-conditions that guard each one"""
    out = []
    stack = []
    for raw in text.splitlines():
        line = raw.split(';')[0].strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith('if ') or low.startswith('if(') or low == 'if':
            stack.append(line[2:].strip())
        elif low.startswith('elseif'):
            if stack:
                stack[-1] = line[6:].strip()
        elif low.startswith('else'):
            if stack:
                stack[-1] = 'else'
        elif low.startswith('endif'):
            if stack:
                stack.pop()
        else:
            for a, b, n in JRE.findall(line):
                out.append({'quest': (a or b).strip().lower(), 'sets': int(n), 'conds': list(stack)})
    return out


def cond_facts(conds, quest):
    """structured facts from the guard conditions of a script journal call"""
    f = {'stage': [], 'items': [], 'dead': [], 'cells': [], 'flags': set()}
    for c in conds:
        low = c.lower()
        for a, b, op, n in C_JIDX.findall(c):
            if (a or b).strip().lower() == quest:
                f['stage'].append((op, int(n)))
        for a, b, op, n in C_ITEM.findall(c):
            f['items'].append(((a or b).lower(), op, int(n)))
        for a, b, op, n in C_DEAD.findall(c):
            f['dead'].append(((a or b).lower(), op, int(n)))
        for cell in C_CELL.findall(c):
            f['cells'].append(cell)
        for a, b in C_REFDEAD.findall(c):
            f['dead'].append(((a or b).lower(), '>=', 1))
        for k in ('ondeath', 'onactivate', 'onpcequip', 'onpcadd', 'onpcdrop', 'getdistance', 'onmurder',
                  'onknockout', 'onpchitme', 'getpccell', 'menumode', 'cellchanged', 'getlos', 'gettarget'):
            if k in low:
                f['flags'].add(k)
    f['flags'] = sorted(f['flags'])
    return f


def build():
    infos = {}        # (dialogue.lower(), INAM) -> info dict (later plugins override)
    dial_type = {}    # dialogue.lower() -> type
    scripts = {}      # script.lower() -> text
    script_plugin = {}
    owners = {}       # script.lower() -> set(object ids)
    obj_script = {}   # object id -> script.lower()
    for plugin, path in load_order():
        cur = None
        for tag, body in records(path):
            if tag == 'DIAL':
                name = typ = None
                for st, v in subs(body):
                    if st == 'NAME': name = zstr(v)
                    elif st == 'DATA' and len(v) >= 1: typ = v[0]
                cur = name
                if name is not None and typ is not None:
                    dial_type[name.lower()] = typ
            elif tag == 'INFO' and cur is not None:
                d = {'dial': cur, 'plugin': plugin, 'conds': []}
                pend = None
                dele = False
                for st, v in subs(body):
                    if st == 'INAM': d['id'] = zstr(v)
                    elif st == 'DATA' and len(v) >= 12:
                        d['disp'] = struct.unpack_from('<i', v, 4)[0]
                        d['rank'], d['gender'], d['pcrank'] = struct.unpack_from('<bbb', v, 8)
                    elif st == 'ONAM': d['speaker'] = zstr(v)
                    elif st == 'RNAM': d['race'] = zstr(v)
                    elif st == 'CNAM': d['class'] = zstr(v)
                    elif st == 'FNAM': d['faction'] = zstr(v)
                    elif st == 'ANAM': d['cell'] = zstr(v)
                    elif st == 'DNAM': d['pcfaction'] = zstr(v)
                    elif st == 'NAME': d['text'] = zstr(v)
                    elif st == 'BNAM': d['result'] = zstr(v)
                    elif st == 'DELE': dele = True
                    elif st == 'SCVR': pend = v
                    elif st in ('INTV', 'FLTV') and pend is not None:
                        val = struct.unpack('<i' if st == 'INTV' else '<f', v[:4])[0]
                        c = parse_scvr(pend, val)
                        if c: d['conds'].append(c)
                        pend = None
                if 'id' not in d:
                    continue
                key = (cur.lower(), d['id'])
                if dele:
                    infos.pop(key, None)
                else:
                    infos[key] = d
            elif tag == 'SCPT':
                sname = stext = None
                for st, v in subs(body):
                    if st == 'SCHD' and len(v) >= 32: sname = zstr(v[:32])
                    elif st == 'SCTX': stext = zstr(v)
                if sname and stext is not None:
                    scripts[sname.lower()] = stext
                    script_plugin[sname.lower()] = plugin
                cur = None
            else:
                if tag in SCRIPTED_TYPES:
                    rid = scr = None
                    for st, v in subs(body):
                        if st == 'NAME' and rid is None: rid = zstr(v)
                        elif st == 'SCRI': scr = zstr(v)
                    if rid:
                        old = obj_script.get(rid.lower())
                        if old and old != (scr or '').lower():
                            owners.get(old, set()).discard(rid.lower())
                        if scr:
                            obj_script[rid.lower()] = scr.lower()
                            owners.setdefault(scr.lower(), set()).add(rid.lower())
                        else:
                            obj_script.pop(rid.lower(), None)
                if tag != 'INFO':
                    cur = None

    quests = {}   # quest.lower() -> {'talk': [...], 'script': [...]}
    for (dl, _), d in infos.items():
        if dial_type.get(dl) == 4 or not d.get('result'):
            continue
        res = '\n'.join(l.split(';')[0] for l in d['result'].splitlines())
        sets = [((a or b).strip().lower(), int(n)) for a, b, n in JRE.findall(res)]
        if not sets:
            continue
        gives = [((a or b).lower(), int(n or 1)) for k, a, b, n in ITEM_RE.findall(res) if k.lower() == 'additem']
        takes = [((a or b).lower(), int(n or 1)) for k, a, b, n in ITEM_RE.findall(res) if k.lower() == 'removeitem']
        for q, n in sets:
            row = {'topic': d['dial'], 'type': dial_type.get(dl), 'speaker': (d.get('speaker') or '').lower() or None,
                   'cell': d.get('cell'), 'faction': d.get('faction'), 'class': d.get('class'), 'race': d.get('race'),
                   'pcfaction': d.get('pcfaction'), 'disp': d.get('disp', 0), 'sets': n, 'plugin': d['plugin'],
                   'text': (d.get('text') or '')[:200],
                   'stage': [(c['op'], int(c['val'])) for c in d['conds'] if c['kind'] == 'journal' and c['name'].lower() == q],
                   'otherq': [(c['name'].lower(), c['op'], int(c['val'])) for c in d['conds'] if c['kind'] == 'journal' and c['name'].lower() != q],
                   'items': [(c['name'].lower(), c['op'], int(c['val'])) for c in d['conds'] if c['kind'] == 'item'],
                   'dead': [(c['name'].lower(), c['op'], int(c['val'])) for c in d['conds'] if c['kind'] == 'dead'],
                   'choice': any(c['kind'] == 'func' and c['func'] == '50' for c in d['conds']),
                   'gives': gives, 'takes': takes}
            quests.setdefault(q, {'talk': [], 'script': []})['talk'].append(row)
    for sname, text in scripts.items():
        for call in script_journal_calls(text):
            f = cond_facts(call['conds'], call['quest'])
            row = {'script': sname, 'sets': call['sets'], 'plugin': script_plugin[sname],
                   'owners': sorted(owners.get(sname, ())), 'conds': call['conds'][-4:], **f}
            quests.setdefault(call['quest'], {'talk': [], 'script': []})['script'].append(row)
    data = {'quests': quests, 'obj_script': obj_script}
    tmp = CACHE + '.tmp'
    pickle.dump(data, open(tmp, 'wb'))
    os.replace(tmp, CACHE)
    print(f"quests with transitions {len(quests)}, dialogue lines {sum(len(q['talk']) for q in quests.values())}, "
          f"script calls {sum(len(q['script']) for q in quests.values())}")


_G = None
def graph():
    global _G
    if _G is None:
        _G = pickle.load(open(CACHE, 'rb'))
    return _G


def stage_ok(conds, n):
    """can a transition with these journal conditions fire while the quest is at stage n?"""
    for op, v in conds:
        if not {'==': n == v, '!=': n != v, '>': n > v, '>=': n >= v, '<': n < v, '<=': n <= v}.get(op, True):
            return False
    return True


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'build':
        build(); return
    if cmd == 'show':
        q = graph()['quests'].get(' '.join(sys.argv[2:]).lower())
        if not q: print('no transitions found'); return
        for r in sorted(q['talk'], key=lambda r: r['sets']):
            who = r['speaker'] or '(' + ', '.join(f"{k}={r[k]}" for k in ('cell', 'faction', 'class', 'race') if r[k]) + ')'
            print(f"  -> {r['sets']}: {who} '{r['topic']}' when {r['stage']} items {r['items']} dead {r['dead']}"
                  f"{' choice' if r['choice'] else ''} takes {r['takes']} gives {r['gives']} [{r['plugin']}]")
        for r in sorted(q['script'], key=lambda r: r['sets']):
            print(f"  -> {r['sets']}: script {r['script']} owners {r['owners'][:4]} when {r['stage']} items {r['items']} "
                  f"dead {r['dead']} cells {r['cells']} {r['flags']} [{r['plugin']}]")
        return
    print(__doc__)


if __name__ == '__main__':
    main()

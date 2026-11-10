"""Build the curated quest objective data for the Objective HUD.

Reads ../objectives/*.json, checks every quest id, stage and target against the
active load order (world.pickle, see world.py), resolves marker positions and
writes:
  ../scripts/comprehensive_objectives/objectives_data.lua   (required by player.lua)
  ../objectives/VALIDATION.md                    (what was checked, what failed)

Usage (from tools/):  python3 build_objectives.py

JSON format (one file may hold many quests):
{
  "lists": { "NAME": [objective, ...] },          # reusable lists, include with "@NAME"
  "quests": {
    "<QuestId>": {
      "parent": "<QuestId>",        # optional: shown nested inside the parent's panel block
      "hide": true,                 # optional: never shown (pure info quests)
      "start":  [objective, ...],   # shown while this quest is not started but a child is
      "stages": { "1": [...], "5,10": [...] },   # objectives while the journal is at that stage
      "after":  [objective, ...]    # shown after the quest finished, until all are done
    }
  }
}
A journal stage without its own key inherits the nearest lower authored stage.
Objective:
  {"do": "Talk to Huleeya", "where": "Black Shalk Cornerclub, ...",
   "target": {"npc"|"creature"|"item"|"object"|"cell"|"place": "<record id / interior cell / outdoor place name>",
              "in": "<interior cell: only placements there / or route to it>",
              "via": "<interior cell whose outdoor route is used when target has none>"},
   "doneIf": {"has": itemId} | {"dead": id} | {"stage": {"quest": id, "atLeast": n}}
             | {"finished": questId} | {"any": [cond, ...]} | {"all": [cond, ...]},
   "optional": true}
"""
import glob, json, os, sys
from world import world, entrances, cell_label, where

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OBJ_DIR = os.path.join(ROOT, 'objectives')
OUT_LUA = os.path.join(ROOT, 'scripts', 'comprehensive_objectives', 'objectives_data.lua')
OUT_REPORT = os.path.join(OBJ_DIR, 'VALIDATION.md')

MAX_PLACEMENTS = 6   # more placements than this = generic object, no positional markers

# distinct colours per quest block (r, g, b 0..1)
PALETTE = [
    (1.00, 0.80, 0.25), (0.40, 0.85, 1.00), (0.55, 1.00, 0.45), (1.00, 0.50, 0.85),
    (1.00, 0.55, 0.30), (0.70, 0.60, 1.00), (0.30, 1.00, 0.80), (1.00, 1.00, 0.45),
    (0.95, 0.40, 0.40), (0.60, 0.80, 0.40),
]

W = world()
errors, warnings, notes = [], [], []
stats = {'quests': 0, 'stages_authored': 0, 'stages_inherited': 0, 'stages_journal': 0,
         'objectives': 0, 'targets': 0, 'targets_resolved': 0, 'targets_unplaced': 0}


def lua_str(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def to_lua(v, ind=0):
    pad = '  ' * ind
    if v is None:
        return 'nil'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(round(v, 1)) if isinstance(v, float) else str(v)
    if isinstance(v, str):
        return lua_str(v)
    if isinstance(v, (list, tuple)):
        if not v:
            return '{}'
        inner = ', '.join(to_lua(x, ind + 1) for x in v)
        if len(inner) < 100 and '\n' not in inner:
            return '{ ' + inner + ' }'
        return '{\n' + ',\n'.join(pad + '  ' + to_lua(x, ind + 1) for x in v) + ',\n' + pad + '}'
    if isinstance(v, dict):
        if not v:
            return '{}'
        items = []
        for k, x in v.items():
            if isinstance(k, int):
                key = f'[{k}]'
            elif isinstance(k, str) and k.isidentifier():
                key = k
            else:
                key = '[' + lua_str(k) + ']'
            items.append(f'{key} = {to_lua(x, ind + 1)}')
        inner = ', '.join(items)
        if len(inner) < 100 and '\n' not in inner:
            return '{ ' + inner + ' }'
        return '{\n' + ',\n'.join(pad + '  ' + it for it in items) + ',\n' + pad + '}'
    raise TypeError(type(v))


def text_hash(t):
    # same hash as player.lua (djb2 mod 2^31-1) over the journal text bytes
    h = 5381
    # the game converts plugin text (Windows-1252) to UTF-8 before scripts see it
    raw = t.encode('latin-1', 'replace').decode('cp1252', 'replace')
    for b in raw.encode('utf-8'):
        h = (h * 33 + b) % 2147483647
    return h


def pos3(p):
    return {'x': round(p[0], 1), 'y': round(p[1], 1), 'z': round(p[2], 1)}


def cell_entry(ck):
    if ck[0] == 'e':
        return {'isExterior': True}
    return {'isExterior': False, 'id': W['cells'][ck]['name']}


def route_positions(ck):
    """door positions from outdoors into interior cell ck: outdoor doors first, then inner doors"""
    out = []
    for frm, dpos in entrances(ck):
        out.append({'cell': cell_entry(frm), 'position': pos3(dpos), 'door': True})
    return out


def interior_key(name):
    if not isinstance(name, str):
        return None
    ck = ('i', name.lower())
    return ck if ck in W['cells'] else None


def resolve_target(t, ctx):
    """returns marker dict (objectIds, positions, itemId, kind) and auto 'where' text"""
    kinds = [k for k in ('npc', 'creature', 'item', 'object', 'cell', 'place') if k in t]
    if len(kinds) != 1:
        errors.append(f'{ctx}: target needs exactly one of npc/creature/item/object/cell: {t}')
        return None, None
    kind = kinds[0]
    rid = t[kind]
    if not isinstance(rid, str) or not isinstance(t.get('in', ''), str) or not isinstance(t.get('via', ''), str):
        errors.append(f'{ctx}: target id / "in" / "via" must be a single string (use separate objectives for alternatives): {t}')
        return None, None
    stats['targets'] += 1
    marker = {'kind': kind, 'positions': []}
    where_txt = None
    restrict = t.get('in')
    rck = None
    if restrict:
        rck = interior_key(restrict)
        if not rck:
            errors.append(f'{ctx}: "in" cell not found: {restrict!r}')
    via = t.get('via')
    vck = interior_key(via) if via else None
    if via and not vck:
        errors.append(f'{ctx}: "via" cell not found: {via!r}')

    if kind == 'place':
        # an outdoor named place (town, camp): centre of the exterior cells with that name
        cs = [k for k, m in W['cells'].items() if k[0] == 'e' and (m['name'] or '').lower() == rid.lower()]
        if not cs:
            errors.append(f'{ctx}: no exterior cell named {rid!r}')
            return None, None
        x = sum((g[1][0] + 0.5) * 8192 for g in cs) / len(cs)
        y = sum((g[1][1] + 0.5) * 8192 for g in cs) / len(cs)
        stats['targets_resolved'] += 1
        marker['positions'] = [{'cell': {'isExterior': True}, 'position': {'x': round(x), 'y': round(y), 'z': 0}}]
        return marker, rid

    if kind == 'cell':
        ck = interior_key(rid)
        if not ck:
            errors.append(f'{ctx}: interior cell not found: {rid!r}')
            return None, None
        pos = route_positions(ck) or (route_positions(vck) if vck else [])
        if not pos:
            warnings.append(f'{ctx}: no outdoor route found into cell {rid!r}')
            stats['targets_unplaced'] += 1
        else:
            stats['targets_resolved'] += 1
        marker['positions'] = pos
        return marker, W['cells'][ck]['name']

    o = W['objs'].get(rid.lower())
    if not o:
        errors.append(f'{ctx}: record id not found in load order: {rid!r}')
        return None, None
    expected = {'npc': {'NPC_'}, 'creature': {'CREA'}, 'object': None,
                'item': {'WEAP', 'ARMO', 'CLOT', 'BOOK', 'MISC', 'ALCH', 'INGR', 'APPA',
                         'LOCK', 'PROB', 'REPA', 'LIGH'}}[kind]
    if expected and o['type'] not in expected:
        warnings.append(f'{ctx}: {rid!r} is a {o["type"]}, authored as {kind}')
    marker['objectIds'] = [rid.lower()]
    if kind == 'item':
        marker['itemId'] = rid.lower()

    res, holders = where(rid)
    placed = list(W['placed'].get(rid.lower(), []))
    if kind == 'item' and holders:
        # items inside containers / carried by actors: track the holder too
        for h in holders:
            hp = W['placed'].get(h, [])
            if rck:
                hp = [x for x in hp if x[0] == rck]
            # only unique holders (a person / a specific desk): generic containers placed
            # all over the world would put markers on every copy
            if hp and len(holders) <= 4 and len(hp) <= 3:
                marker['objectIds'].append(h)
                placed += hp
    if rck:
        placed = [x for x in placed if x[0] == rck]
    cells = sorted({ck for ck, _ in placed})
    if not placed:
        if rck:
            # e.g. a person moved there by script: mark the route into the given cell
            marker['positions'] = route_positions(rck)
            where_txt = W['cells'][rck]['name']
            if marker['positions']:
                stats['targets_resolved'] += 1
                notes.append(f'{ctx}: {rid} not placed in {restrict!r}; using route into that cell')
            else:
                stats['targets_unplaced'] += 1
                warnings.append(f'{ctx}: {rid} has no placement and no route into {restrict!r}')
        else:
            stats['targets_unplaced'] += 1
            warnings.append(f'{ctx}: {rid!r} is not placed anywhere (object marker only)'
                            + (f'; carried by {holders[:4]}' if holders else ''))
        return marker, where_txt
    if len(cells) > MAX_PLACEMENTS:
        stats['targets_unplaced'] += 1
        warnings.append(f'{ctx}: {rid!r} is placed in {len(cells)} cells; no positional markers '
                        f'(add "in" to pick one)')
        return marker, None
    stats['targets_resolved'] += 1
    seen = set()
    for ck, p in placed:
        marker['positions'].append({'cell': cell_entry(ck), 'position': pos3(p)})
        if ck[0] == 'i' and ck not in seen:
            seen.add(ck)
            rp = route_positions(ck)
            if not rp and vck:
                rp = route_positions(vck)
            if not rp:
                warnings.append(f'{ctx}: no outdoor route into {cell_label(ck)!r} (marker works inside only)')
            marker['positions'] += rp
    # dedupe positions
    uniq, keys = [], set()
    for p in marker['positions']:
        k = (p['cell'].get('id'), p['position']['x'], p['position']['y'], p['position']['z'])
        if k not in keys:
            keys.add(k)
            uniq.append(p)
    marker['positions'] = uniq
    where_txt = '; '.join(cell_label(c) for c in cells[:2])
    return marker, where_txt


def check_cond(c, ctx):
    if not isinstance(c, dict) or len(c) != 1:
        errors.append(f'{ctx}: bad doneIf {c!r}')
        return None
    (k, v), = c.items()
    if k in ('any', 'all'):
        subs = [check_cond(x, ctx) for x in v]
        return {'kind': k, 'list': [s for s in subs if s]}
    if k == 'has':
        if v.lower() not in W['objs']:
            errors.append(f'{ctx}: doneIf has: unknown item {v!r}')
        return {'kind': 'has', 'id': v.lower()}
    if k == 'dead':
        if v.lower() not in W['objs']:
            errors.append(f'{ctx}: doneIf dead: unknown actor {v!r}')
        return {'kind': 'dead', 'id': v.lower()}
    if k == 'stage':
        q = W['journal'].get(v['quest'].lower())
        if not q:
            errors.append(f'{ctx}: doneIf stage: unknown quest {v["quest"]!r}')
        elif v['atLeast'] not in q['stages'] and not any(s >= v['atLeast'] for s in q['stages']):
            errors.append(f'{ctx}: doneIf stage: {v["quest"]} has no stage >= {v["atLeast"]}')
        return {'kind': 'stage', 'quest': v['quest'].lower(), 'n': v['atLeast']}
    if k == 'finished':
        if v.lower() not in W['journal']:
            errors.append(f'{ctx}: doneIf finished: unknown quest {v!r}')
        return {'kind': 'finished', 'quest': v.lower()}
    errors.append(f'{ctx}: unknown doneIf kind {k!r}')
    return None


def build_obj(o, ctx, lists):
    if isinstance(o, str) and o.startswith('@'):
        if o[1:] not in lists:
            errors.append(f'{ctx}: unknown list {o}')
            return []
        out = []
        for i, x in enumerate(lists[o[1:]]):
            out += build_obj(x, f'{ctx}{o}[{i}]', lists)
        return out
    if 'do' not in o:
        errors.append(f'{ctx}: objective without "do": {o}')
        return []
    stats['objectives'] += 1
    r = {'text': o['do']}
    where_auto = None
    if 'target' in o:
        m, where_auto = resolve_target(o['target'], ctx)
        if m:
            r['marker'] = m
    w = o.get('where') or where_auto
    if w:
        r['where'] = w
    if o.get('optional'):
        r['optional'] = True
    if 'doneIf' in o:
        c = check_cond(o['doneIf'], ctx)
        if c:
            r['done'] = c
    return [r]


def main():
    files = sorted(glob.glob(os.path.join(OBJ_DIR, '*.json')))
    quests_out = {}
    order = []
    stage_rows = []
    for f in files:
        data = json.load(open(f))
        lists = data.get('lists', {})
        for qid, qd in data.get('quests', {}).items():
            j = W['journal'].get(qid.lower())
            if not j:
                errors.append(f'{os.path.basename(f)}: quest id not in load order: {qid}')
                continue
            stats['quests'] += 1
            ctx0 = qid
            q = {'id': qid, 'name': j['name'] or qid}
            if qd.get('parent'):
                if qd['parent'].lower() not in W['journal']:
                    errors.append(f'{qid}: unknown parent {qd["parent"]}')
                q['parent'] = qd['parent'].lower()
            if qd.get('hide'):
                q['hide'] = True
            for key in ('start', 'after'):
                if key in qd:
                    objs = []
                    for i, o in enumerate(qd[key]):
                        objs += build_obj(o, f'{ctx0}[{key}][{i}]', lists)
                    q[key] = objs
            # stages
            authored = {}
            for skey, objs in qd.get('stages', {}).items():
                for s in str(skey).split(','):
                    s = int(s.strip())
                    if s not in j['stages']:
                        errors.append(f'{qid}: stage {s} does not exist in journal (has {sorted(j["stages"])})')
                    built = []
                    for i, o in enumerate(objs):
                        built += build_obj(o, f'{qid}[{s}][{i}]', lists)
                    authored[s] = built
            stages = {}
            for s in sorted(j['stages']):
                stats['stages_journal'] += 1
                fin = s in j['finished']
                if s in authored:
                    stages[s] = authored[s]
                    stats['stages_authored'] += 1
                    stage_rows.append((qid, s, 'authored', len(authored[s]), fin))
                else:
                    lower = [a for a in authored if a < s]
                    if lower and not fin:
                        stages[s] = authored[max(lower)]
                        stats['stages_inherited'] += 1
                        stage_rows.append((qid, s, f'inherits {max(lower)}', len(stages[s]), fin))
                    else:
                        stage_rows.append((qid, s, 'none' + (' (finishing stage)' if fin else ''), 0, fin))
                        if not fin and not qd.get('hide') and qd.get('stages') is not None:
                            warnings.append(f'{qid}: stage {s} has no objectives')
            q['stages'] = stages
            q['finishing'] = sorted(j['finished'])
            # vanilla journal text fingerprints, so the game can tell when an unknown mod rewrote a step
            bp = j.get('byPlugin', {})
            definer = next(iter(bp), None)
            if qd.get('variant') and definer:
                # base stages were written for vanilla; variants cover the mods
                q['fp'] = {s_: text_hash(t) for s_, t in bp[definer].items() if t}
            else:
                # written against the journal as this load order has it
                q['fp'] = {s_: text_hash(t) for s_, t in j['stages'].items() if t}
            # mod variants: stages that differ when a given plugin is loaded
            for plug, vd in (qd.get('variant') or {}).items():
                vst = {}
                for skey, objs in (vd.get('stages') or {}).items():
                    for s_ in str(skey).split(','):
                        s_ = int(s_.strip())
                        if s_ not in j['stages']:
                            errors.append(f'{qid}: variant {plug}: stage {s_} not in journal')
                        built = []
                        for i, o in enumerate(objs):
                            built += build_obj(o, f'{qid}<{plug}>[{s_}][{i}]', lists)
                        vst[s_] = built
                if plug not in bp:
                    warnings.append(f'{qid}: variant for {plug}, but that plugin does not change this quest here')
                q.setdefault('variants', {})[plug.lower()] = {'stages': vst}
                stats['variants'] = stats.get('variants', 0) + 1
            quests_out[qid.lower()] = q
            order.append(qid.lower())
    # colours per top-level block
    tops = [k for k in order if not quests_out[k].get('parent')]
    for i, k in enumerate(tops):
        r, g, b = PALETTE[i % len(PALETTE)]
        quests_out[k]['color'] = [r, g, b]
    for k in order:
        p = quests_out[k].get('parent')
        if p:
            quests_out[k]['color'] = (quests_out.get(p) or {}).get('color', [1, 1, 1])

    # Each quest sits in its own function: Lua allows at most 65536 constants per function.
    lua = ['-- GENERATED by tools/build_objectives.py from objectives/*.json. Do not edit by hand.',
           'local Q = {}']
    for k in order:
        lua.append('Q[' + lua_str(k) + '] = (function() return ' + to_lua(quests_out[k]) + ' end)()')
    lua.append("return { version = 1, quests = Q }")
    os.makedirs(os.path.dirname(OUT_LUA), exist_ok=True)
    open(OUT_LUA, 'w').write('\n'.join(lua) + '\n')

    rep = ['# Objective data validation', '',
           f'Generated by `tools/build_objectives.py` from {", ".join(os.path.basename(f) for f in files)}.', '',
           '## Counts', '']
    for k, v in stats.items():
        rep.append(f'- {k}: {v}')
    rep += ['', f'## Errors ({len(errors)})', ''] + [f'- {e}' for e in errors]
    rep += ['', f'## Warnings ({len(warnings)})', ''] + [f'- {e}' for e in warnings]
    rep += ['', f'## Notes ({len(notes)})', ''] + [f'- {e}' for e in notes]
    rep += ['', '## Stages', '', '| quest | stage | objectives | count |', '|---|---|---|---|']
    for qid, s, how, n, fin in stage_rows:
        rep.append(f'| {qid} | {s}{" (fin)" if fin else ""} | {how} | {n} |')
    open(OUT_REPORT, 'w').write('\n'.join(rep) + '\n')
    print(json.dumps(stats))
    print(f'{len(errors)} errors, {len(warnings)} warnings -> {OUT_REPORT}')
    for e in errors:
        print('ERROR', e)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())

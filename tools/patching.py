"""Stage-level patches for the objective files.

A patch file is { "<QuestId>": { "stages": { "<stage or 'a,b,c'>": [objective, ...] },
                                 "start": [...], "after": [...] } }.
Only the stages named in the patch are replaced; everything else in the quest stays.
A quest may also carry "variant": { "<Plugin.esp>": { "stages": {...} } } to replace stages of
the list that is shown when that plugin is loaded.
"""
import copy


def split_stages(stages):
    out = {}
    for skey, objs in (stages or {}).items():
        for s in str(skey).split(','):
            out[int(s.strip())] = objs
    return out


def join_stages(per):
    """group stage numbers that share the same objective list back into 'a,b,c' keys"""
    groups = []
    for n in sorted(per):
        for g in groups:
            if g[1] == per[n]:
                g[0].append(n); break
        else:
            groups.append([[n], per[n]])
    return {','.join(str(n) for n in ns): objs for ns, objs in groups}


def apply_patch(qd, patch):
    qd = copy.deepcopy(qd)
    if 'stages' in patch:
        per = split_stages(qd.get('stages'))
        per.update(split_stages(patch['stages']))
        qd['stages'] = join_stages(per)
    for k in ('start', 'after'):
        if k in patch:
            qd[k] = patch[k]
    # stage lists used when a given plugin is loaded
    for plug, vd in (patch.get('variant') or {}).items():
        have = {p.lower(): p for p in (qd.get('variant') or {})}
        if plug.lower() not in have:
            raise ValueError(f'no variant for plugin {plug!r} in this quest')
        v = qd['variant'][have[plug.lower()]]
        per = split_stages(v.get('stages'))
        per.update(split_stages(vd.get('stages')))
        v['stages'] = join_stages(per)
    return qd

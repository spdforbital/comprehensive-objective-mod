"""Builds the Collector's Ledger data (scripts/comprehensive_objectives/ledger_data.lua).

Own pass over the active load order (see esm.py), because world.pickle does not keep
ownership / lock / trap / container-flag / item-stat data. Route doors for interiors
come from world.py (world.pickle).

What counts as a "source" of an item:
  * a reference of the item placed in a cell (loose item), or
  * a fixed (positive count, non-leveled) entry in the inventory of a placed container.
Excluded: NPC / creature inventories, containers owned by merchants (their barter
stock), leveled lists (random loot), anything given by scripts (quest rewards are
never placed, so they never show up).

Reference subrecords (OpenMW CellRef): ANAM owner NPC, BNAM owner global, CNAM owner
faction, INDX faction rank, FLTV lock level, KNAM key, TNAM trap, NAM9 count, DATA pos.

Usage:  python3 build_ledger.py            # build + write the Lua data file
        python3 build_ledger.py report     # also print top entries per category
"""
import math, os, pickle, re, struct, sys, time
from esm import load_order, records, subs, zstr

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)
OUT = os.path.join(MOD, 'scripts', 'comprehensive_objectives', 'ledger_data.lua')
CACHE = os.path.join(HERE, 'ledger_cache.pickle')

ITEM_TYPES = {'WEAP', 'ARMO', 'CLOT', 'BOOK', 'INGR'}

# ---------------------------------------------------------------------------
# hand-kept knowledge used only for the offline pre-selection / report
# (the in-game script computes everything from the live records)
# ---------------------------------------------------------------------------
EFFECTS = ("WaterBreathing SwiftSwim WaterWalking Shield FireShield LightningShield FrostShield Burden "
           "Feather Jump Levitate SlowFall Lock Open FireDamage ShockDamage FrostDamage DrainAttribute "
           "DrainHealth DrainMagicka DrainFatigue DrainSkill DamageAttribute DamageHealth DamageMagicka "
           "DamageFatigue DamageSkill Poison WeaknessToFire WeaknessToFrost WeaknessToShock WeaknessToMagicka "
           "WeaknessToCommonDisease WeaknessToBlightDisease WeaknessToCorprusDisease WeaknessToPoison "
           "WeaknessToNormalWeapons DisintegrateWeapon DisintegrateArmor Invisibility Chameleon Light "
           "Sanctuary NightEye Charm Paralyze Silence Blind Sound CalmHumanoid CalmCreature FrenzyHumanoid "
           "FrenzyCreature DemoralizeHumanoid DemoralizeCreature RallyHumanoid RallyCreature Dispel Soultrap "
           "Telekinesis Mark Recall DivineIntervention AlmsiviIntervention DetectAnimal DetectEnchantment "
           "DetectKey SpellAbsorption Reflect CureCommonDisease CureBlightDisease CureCorprusDisease "
           "CurePoison CureParalyzation RestoreAttribute RestoreHealth RestoreMagicka RestoreFatigue "
           "RestoreSkill FortifyAttribute FortifyHealth FortifyMagicka FortifyFatigue FortifySkill "
           "FortifyMaximumMagicka AbsorbAttribute AbsorbHealth AbsorbMagicka AbsorbFatigue AbsorbSkill "
           "ResistFire ResistFrost ResistShock ResistMagicka ResistCommonDisease ResistBlightDisease "
           "ResistCorprusDisease ResistPoison ResistNormalWeapons ResistParalysis RemoveCurse TurnUndead "
           "SummonScamp SummonClannfear SummonDaedroth SummonDremora SummonAncestralGhost "
           "SummonSkeletalMinion SummonBonewalker SummonGreaterBonewalker SummonBonelord "
           "SummonWingedTwilight SummonHunger SummonGoldenSaint SummonFlameAtronach SummonFrostAtronach "
           "SummonStormAtronach FortifyAttack CommandCreature CommandHumanoid BoundDagger BoundLongsword "
           "BoundMace BoundBattleAxe BoundSpear BoundLongbow ExtraSpell BoundCuirass BoundHelm BoundBoots "
           "BoundShield BoundGloves Corprus Vampirism SummonCenturionSphere SunDamage StuntedMagicka "
           "SummonFabricant SummonWolf SummonBear SummonBonewolf SummonCreature04 SummonCreature05").split()
HARMFUL = set(range(7, 8)) | set(range(14, 39)) | {45, 46, 47, 48, 51, 52, 53, 54} | set(range(85, 90)) | {132, 133, 135, 136}
SKILLS = ("Block Armorer MediumArmor HeavyArmor BluntWeapon LongBlade Axe Spear Athletics Enchant Destruction "
          "Alteration Illusion Conjuration Mysticism Restoration Alchemy Unarmored Security Sneak Acrobatics "
          "LightArmor ShortBlade Marksman Mercantile Speechcraft HandToHand").split()
ATTRS = "Strength Intelligence Willpower Agility Speed Endurance Personality Luck".split()

WEAPON_CAT = {0: 'shortblade', 1: 'longblade', 2: 'longblade', 3: 'blunt', 4: 'blunt', 5: 'blunt',
              6: 'spear', 7: 'axe', 8: 'axe', 9: 'marksman', 10: 'marksman', 11: 'marksman'}
ARMOR_SLOT = {0: 'helmet', 1: 'cuirass', 2: 'pauldrons', 3: 'pauldrons', 4: 'greaves', 5: 'boots',
              6: 'gauntlets', 7: 'gauntlets', 8: 'shield', 9: 'gauntlets', 10: 'gauntlets'}
ARMOR_WEIGHT_GMST = {0: 'iHelmWeight', 1: 'iCuirassWeight', 2: 'iPauldronWeight', 3: 'iPauldronWeight',
                     4: 'iGreavesWeight', 5: 'iBootsWeight', 6: 'iGauntletWeight', 7: 'iGauntletWeight',
                     8: 'iShieldWeight', 9: 'iGauntletWeight', 10: 'iGauntletWeight'}
SET_SLOT = {0: 'helmet', 1: 'cuirass', 2: 'pauldron_l', 3: 'pauldron_r', 4: 'greaves', 5: 'boots',
            6: 'gauntlet_l', 7: 'gauntlet_r', 8: 'shield', 9: 'gauntlet_l', 10: 'gauntlet_r'}
SET_GROUP = {'helmet': 'helmet', 'cuirass': 'cuirass', 'pauldron_l': 'pauldrons', 'pauldron_r': 'pauldrons',
             'greaves': 'greaves', 'boots': 'boots', 'gauntlet_l': 'gauntlets', 'gauntlet_r': 'gauntlets', 'shield': 'shield'}
CLOTH_CAT = {8: 'rings', 9: 'amulets', 3: 'belts'}  # everything else -> 'clothing'

# The player's class (for the offline report only; the game reads the live class)
ANDI = {'major': {'LongBlade', 'HeavyArmor', 'Block', 'Armorer', 'Athletics'},
        'minor': {'MediumArmor', 'Axe', 'Acrobatics', 'Alchemy', 'Restoration'},
        'attrs': {'Strength', 'Endurance'}, 'spec': 'combat'}

# Artifacts and notable uniques: one-line descriptions (checked against UESP, see report).
ARTIFACTS = {}   # filled from artifacts.py-style table below
ARTIFACT_TEXT = os.path.join(HERE, 'ledger_artifacts.txt')


def load_artifacts():
    out = {}
    if os.path.exists(ARTIFACT_TEXT):
        for line in open(ARTIFACT_TEXT, encoding='utf-8'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            rid, _, desc = line.partition('|')
            out[rid.strip().lower()] = desc.strip()
    return out


# ---------------------------------------------------------------------------
# pass over the plugins
# ---------------------------------------------------------------------------
def u32(v, o=0): return struct.unpack_from('<I', v, o)[0]
def i32(v, o=0): return struct.unpack_from('<i', v, o)[0]
def f32(v, o=0): return struct.unpack_from('<f', v, o)[0]


def scan():
    gmst = {}
    mgef = {}           # index -> {cost, flags}
    ench = {}           # id -> {type, cost, charge, effects:[(eff, skill, attr, range, area, dur, mn, mx)]}
    items = {}          # id -> dict(type, name, plugin(origin), last, ...stats)
    conts = {}          # id -> {name, flags, inv:{item:count}, plugin}
    actors = {}         # id -> {services, cls, autocalc}
    classes = {}        # id -> services
    regions = {}        # id -> name
    scripts = {}        # id -> text (only those that add spells)
    extcells = {}       # (gx,gy) -> {name, region}
    intcells = {}       # lower -> name
    refs = {}           # refkey -> ref dict
    plugins = []
    levi = {}           # leveled item list id -> {'none': chance none %, 'items': [ids]}
    doorids = set()     # DOOR record ids
    doorlocks = {}      # (cellkey, rounded x, rounded y) -> lock level of a placed door
    t0 = time.time()
    for plugin, path in load_order():
        plugins.append(plugin)
        masters = []
        for tag, body in records(path):
            if tag == 'TES3':
                masters = [zstr(v) for st, v in subs(body) if st == 'MAST']
            elif tag == 'GMST':
                name = None
                for st, v in subs(body):
                    if st == 'NAME': name = zstr(v)
                    elif st == 'FLTV' and name: gmst[name] = f32(v)
                    elif st == 'INTV' and name: gmst[name] = i32(v)
            elif tag == 'MGEF':
                idx = None
                for st, v in subs(body):
                    if st == 'INDX': idx = i32(v)
                    elif st == 'MEDT' and idx is not None:
                        mgef[idx] = {'school': i32(v, 0), 'cost': f32(v, 4), 'flags': i32(v, 8)}
            elif tag == 'ENCH':
                rid = None; e = {'effects': []}; dele = False
                for st, v in subs(body):
                    if st == 'NAME': rid = zstr(v)
                    elif st == 'DELE': dele = True
                    elif st == 'ENDT' and len(v) >= 16:
                        e['type'], e['cost'], e['charge'], e['flags'] = struct.unpack_from('<iiii', v)
                    elif st == 'ENAM' and len(v) >= 24:
                        eff, sk, at, rng, area, dur, mn, mx = struct.unpack_from('<hbbiiiii', v)
                        e['effects'].append((eff, sk, at, rng, area, dur, mn, mx))
                if rid:
                    if dele: ench.pop(rid.lower(), None)
                    else: ench[rid.lower()] = e
            elif tag in ITEM_TYPES:
                rid = None; d = {'type': tag}; dele = False
                for st, v in subs(body):
                    if st == 'NAME' and rid is None: rid = zstr(v)
                    elif st == 'FNAM': d['name'] = zstr(v)
                    elif st == 'DELE': dele = True
                    elif st == 'ENAM': d['ench'] = zstr(v).lower()
                    elif st == 'SCRI': d['script'] = zstr(v).lower()
                    elif st == 'WPDT' and len(v) >= 28:
                        (d['weight'], d['value'], d['wtype'], d['health'], d['speed'], d['reach'],
                         d['encap']) = struct.unpack_from('<fihHffH', v)
                        d['dmg'] = struct.unpack_from('<6B', v, 22)
                        d['wflags'] = i32(v, 28) if len(v) >= 32 else 0
                    elif st == 'AODT' and len(v) >= 24:
                        d['atype'], d['weight'], d['value'], d['health'], d['encap'], d['ar'] = struct.unpack_from('<ifiiii', v)
                    elif st == 'CTDT' and len(v) >= 12:
                        d['ctype'], d['weight'], d['value'], d['encap'] = struct.unpack_from('<ifhh', v)
                    elif st == 'BKDT' and len(v) >= 20:
                        d['weight'], d['value'], d['scroll'], d['skill'], d['encap'] = struct.unpack_from('<fiiii', v)
                    elif st == 'IRDT' and len(v) >= 8:
                        d['weight'], d['value'] = struct.unpack_from('<fi', v)
                if not rid: continue
                k = rid.lower()
                if dele:
                    items.pop(k, None); continue
                old = items.get(k)
                d['id'] = rid
                d['plugin'] = old['plugin'] if old else plugin
                d['last'] = plugin
                if old and 'name' not in d and 'name' in old: d['name'] = old['name']
                items[k] = d
            elif tag == 'LEVI':
                rid = None; d = {'none': 0, 'items': []}; dele = False
                for st, v in subs(body):
                    if st == 'NAME' and rid is None: rid = zstr(v)
                    elif st == 'NNAM' and v: d['none'] = v[0]
                    elif st == 'INAM': d['items'].append(zstr(v).lower())
                    elif st == 'DELE': dele = True
                if not rid: continue
                if dele: levi.pop(rid.lower(), None); continue
                levi[rid.lower()] = d
            elif tag == 'DOOR':
                for st, v in subs(body):
                    if st == 'NAME':
                        doorids.add(zstr(v).lower()); break
            elif tag == 'CONT':
                rid = None; d = {'inv': {}, 'flags': 0}; dele = False
                for st, v in subs(body):
                    if st == 'NAME' and rid is None: rid = zstr(v)
                    elif st == 'FNAM': d['name'] = zstr(v)
                    elif st == 'FLAG': d['flags'] = i32(v)
                    elif st == 'DELE': dele = True
                    elif st in ('NPCO', 'CNTO') and len(v) >= 36:
                        cnt = i32(v)
                        iid = zstr(v[4:36]).lower()
                        d['inv'][iid] = d['inv'].get(iid, 0) + cnt
                if not rid: continue
                if dele: conts.pop(rid.lower(), None); continue
                d['plugin'] = plugin
                conts[rid.lower()] = d
            elif tag in ('NPC_', 'CREA'):
                rid = None; d = {'services': 0, 'cls': None, 'autocalc': False, 'dead': False, 'inv': {}}
                for st, v in subs(body):
                    if st == 'NAME' and rid is None: rid = zstr(v)
                    elif st == 'FNAM': d['name'] = zstr(v)
                    elif st == 'CNAM' and tag == 'NPC_': d['cls'] = zstr(v).lower()
                    elif st == 'AIDT' and len(v) >= 12: d['services'] = i32(v, 8)
                    elif st == 'FLAG' and tag == 'NPC_': d['autocalc'] = bool(i32(v) & 0x10)
                    elif st == 'NPDT':
                        # placed dead: health 0 in the record (NPC 52-byte NPDT: ushort at 38; creature: int at 40)
                        if tag == 'NPC_' and len(v) >= 52: d['dead'] = struct.unpack_from('<H', v, 38)[0] == 0
                        elif tag == 'CREA' and len(v) >= 44: d['dead'] = i32(v, 40) <= 0
                    elif st == 'NPCO' and len(v) >= 36:
                        cnt = i32(v); iid = zstr(v[4:36]).lower()
                        d['inv'][iid] = d['inv'].get(iid, 0) + cnt
                if rid:
                    if not d['dead']: d['inv'] = {}
                    actors[rid.lower()] = d
            elif tag == 'CLAS':
                rid = None
                for st, v in subs(body):
                    if st == 'NAME': rid = zstr(v)
                    elif st == 'CLDT' and len(v) >= 100 and rid: classes[rid.lower()] = i32(v, 96)
            elif tag == 'REGN':
                rid = name = None
                for st, v in subs(body):
                    if st == 'NAME' and rid is None: rid = zstr(v)
                    elif st == 'FNAM': name = zstr(v)
                if rid: regions[rid.lower()] = name or rid
            elif tag == 'SCPT':
                rid = None; text = ''
                for st, v in subs(body):
                    if st == 'SCHD': rid = zstr(v[:32])
                    elif st == 'SCTX': text = v.decode('latin1', 'replace')
                if rid and re.search(r'\baddspell\b', text, re.I):
                    scripts[rid.lower()] = text
            elif tag == 'CELL':
                cname = None; interior = False; grid = None; region = None
                cur = None; reflist = []
                for st, v in subs(body):
                    if cur is None:
                        if st == 'NAME' and cname is None: cname = zstr(v)
                        elif st == 'DATA' and len(v) >= 12:
                            flags, gx, gy = struct.unpack_from('<Iii', v)
                            interior = bool(flags & 1); grid = (gx, gy)
                        elif st == 'RGNN': region = zstr(v).lower()
                    if st == 'FRMR':
                        rn = u32(v)
                        mi = rn >> 24
                        origin = plugin if mi == 0 else (masters[mi - 1] if mi - 1 < len(masters) else plugin)
                        cur = {'key': (origin.lower(), rn & 0xFFFFFF), 'plugin': plugin}
                        reflist.append(cur)
                    elif st == 'MVRF':
                        cur = {'skip': True}   # the moved ref's data follows under its own FRMR
                    elif cur is not None and not cur.get('skip'):
                        if st == 'NAME': cur['id'] = zstr(v).lower()
                        elif st == 'DATA' and len(v) >= 12: cur['pos'] = struct.unpack_from('<3f', v)
                        elif st == 'DELE': cur['deleted'] = True
                        elif st == 'ANAM': cur['owner'] = zstr(v).lower()
                        elif st == 'BNAM': cur['global'] = zstr(v).lower()
                        elif st == 'CNAM': cur['faction'] = zstr(v).lower()
                        elif st == 'INDX': cur['rank'] = i32(v)
                        elif st == 'FLTV': cur['lock'] = i32(v)
                        elif st == 'KNAM': cur['keyid'] = zstr(v).lower()
                        elif st == 'TNAM': cur['trap'] = zstr(v).lower()
                        elif st == 'NAM9': cur['count'] = i32(v)
                        elif st == 'DODT': cur['tele'] = True
                if interior:
                    ck = ('i', (cname or '').lower())
                    if cname: intcells[ck[1]] = cname
                else:
                    e = extcells.setdefault(grid, {'name': '', 'region': None})
                    if cname: e['name'] = cname
                    if region: e['region'] = region
                for r in reflist:
                    if r.get('skip'): continue
                    key = r['key']
                    if r.get('deleted'):
                        refs.pop(key, None); continue
                    rid = r.get('id')
                    if not rid or 'pos' not in r: continue
                    if rid in doorids:
                        dck = ck if interior else ('e', (int(math.floor(r['pos'][0] / 8192)), int(math.floor(r['pos'][1] / 8192))))
                        doorlocks[(dck, round(r['pos'][0]), round(r['pos'][1]))] = (r.get('lock', 0) or 0, bool(r.get('tele')))
                    if rid not in items and rid not in conts and not (rid in actors and actors[rid]['dead']):
                        refs.pop(key, None)  # overridden by something we don't track
                        continue
                    if interior:
                        r['cell'] = ck
                    else:
                        x, y = r['pos'][0], r['pos'][1]
                        r['cell'] = ('e', (int(math.floor(x / 8192)), int(math.floor(y / 8192))))
                    r['origin'] = refs[key]['origin'] if key in refs else plugin
                    del r['key']
                    refs[key] = r
        print(f"  {plugin}: refs so far {len(refs)}  ({time.time() - t0:.0f}s)", file=sys.stderr) if len(plugins) % 50 == 0 else None
    return dict(gmst=gmst, mgef=mgef, ench=ench, items=items, conts=conts, actors=actors, classes=classes,
                regions=regions, scripts=scripts, extcells=extcells, intcells=intcells, refs=refs, plugins=plugins,
                levi=levi, doorlocks=doorlocks)


# ---------------------------------------------------------------------------
# scoring (mirror of ledger.lua, used for pre-selection and the report)
# ---------------------------------------------------------------------------
def gm(D, k, dflt):
    return D['gmst'].get(k, dflt)


def effect_cost(D, e, ctype):
    eff, sk, at, rng, area, dur, mn, mx = e
    m = D['mgef'].get(eff)
    base = m['cost'] if m else 1.0
    mn = min(100, max(1, mn)); mx = min(100, max(1, mx)); area = max(1, area)
    if ctype == 3:
        dur = gm(D, 'fEnchantmentConstantDurationMult', 100.0)
    cost = ((mn + mx) * dur + area) * base * gm(D, 'fEffectCostMult', 0.5) * 0.05
    cost = max(1.0, cost)
    if rng == 2: cost *= 1.5
    return cost


def class_weight(e, cls):
    eff, sk, at = e[0], e[1], e[2]
    nm = EFFECTS[eff] if 0 <= eff < len(EFFECTS) else ''
    if nm in LOW_VALUE: return LOW_VALUE[nm]
    if cls is None:
        return 1.0
    name = EFFECTS[eff] if 0 <= eff < len(EFFECTS) else ''
    if name in ('FortifySkill', 'RestoreSkill', 'AbsorbSkill'):
        s = SKILLS[sk] if 0 <= sk < len(SKILLS) else ''
        if s in cls['major']: return 1.6
        if s in cls['minor']: return 1.25
        return 0.6
    if name in ('FortifyAttribute', 'RestoreAttribute', 'AbsorbAttribute'):
        a = ATTRS[at] if 0 <= at < len(ATTRS) else ''
        if a in cls['attrs']: return 1.5
        if a in ('Intelligence', 'Willpower') and cls['spec'] == 'combat': return 0.7
        return 1.0
    if name in ('FortifyMagicka', 'FortifyMaximumMagicka', 'RestoreMagicka', 'SpellAbsorption'):
        return 0.6 if cls['spec'] == 'combat' else 1.2
    if name in ('FortifyAttack', 'FortifyHealth', 'FortifyFatigue', 'RestoreHealth', 'RestoreFatigue'):
        return 1.3 if cls['spec'] == 'combat' else 1.0
    return 1.0


def ench_score(D, enchid, cls=None, scroll=False):
    e = D['ench'].get(enchid or '')
    if not e: return 0.0, None
    t = e.get('type', 0)
    total = 0.0
    for ef in e['effects']:
        c = effect_cost(D, ef, t) * class_weight(ef, cls)
        harmful = ef[0] in HARMFUL
        if t == 3 and harmful:   # constant curse on the wearer
            c = -c
        total += c
    if t == 3:
        w = 1.0
    elif t == 1:
        uses = e['charge'] / max(1, e['cost'])
        w = 0.5 * min(1.25, max(0.25, math.sqrt(uses / 20.0)))
    elif t == 2:
        uses = e['charge'] / max(1, e['cost'])
        w = 0.3 * min(1.25, max(0.25, math.sqrt(uses / 10.0)))
    else:
        w = 1.0 if scroll else 0.0
    return total * w, t


LOW_VALUE = {'ResistCommonDisease': 0.3, 'ResistBlightDisease': 0.3, 'ResistCorprusDisease': 0.3, 'SwiftSwim': 0.3,
             'WaterBreathing': 0.3, 'WaterWalking': 0.4, 'DetectAnimal': 0.3, 'DetectEnchantment': 0.3, 'DetectKey': 0.3,
             'NightEye': 0.4, 'Light': 0.3, 'Telekinesis': 0.4, 'SlowFall': 0.5, 'Feather': 0.6, 'Jump': 0.6}
ENCH_WEIGHT = 0.5   # how much the enchantment counts next to damage / armor rating


def weapon_base(it):
    d = it['dmg']
    if it['wtype'] in (9, 10, 11):
        dmg = d[1]
    else:
        dmg = (d[1] + d[3] + d[5]) / 3.0
    return dmg * it['speed'] * (1 + 0.1 * (it['reach'] - 1))


def armor_class(D, it):
    w = gm(D, ARMOR_WEIGHT_GMST[it['atype']], 0)
    if it['weight'] <= w * gm(D, 'fLightMaxMod', 0.6) + 0.0005: return 'light'
    if it['weight'] <= w * gm(D, 'fMedMaxMod', 0.9) + 0.0005: return 'medium'
    return 'heavy'


def score(D, it, cls=None, use_ench=True):
    t = it['type']
    es = ench_score(D, it.get('ench'), cls, scroll=(t == 'BOOK'))[0] if use_ench else 0.0
    if t == 'WEAP': return weapon_base(it) + ENCH_WEIGHT * es
    if t == 'ARMO': return it['ar'] + ENCH_WEIGHT * es
    return es


def category(D, it):
    t = it['type']
    if t == 'WEAP':
        return 'w_' + WEAPON_CAT[it['wtype']] if it.get('wtype') in WEAPON_CAT else None
    if t == 'ARMO':
        if it.get('atype') not in ARMOR_SLOT: return None
        return 'a_' + armor_class(D, it) + '_' + ARMOR_SLOT[it['atype']]
    if t == 'CLOT':
        e = D['ench'].get(it.get('ench') or '')
        if not e or e.get('type') == 0: return None
        return 's_' + CLOTH_CAT.get(it.get('ctype'), 'clothing')
    if t == 'BOOK':
        e = D['ench'].get(it.get('ench') or '')
        if it.get('scroll') and e and e.get('type') == 0: return 'scrolls'
        if it.get('script') in D['scripts']: return 'spellbooks'
        return None
    if t == 'INGR': return 'ingredients'
    return None


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------
BARTER_MASK = 0x37FF & ~0x800    # all "barters ..." service flags (not spells)


def is_merchant(D, owner):
    a = D['actors'].get(owner or '')
    if not a: return False
    s = a['services']
    if a['autocalc'] and a['cls']:
        s = D['classes'].get(a['cls'], s)
    return bool(s & BARTER_MASK)


# developer / test cells and display cases whose items are disabled until a quest enables them
EXCLUDED_CELLS = re.compile(r"(^|[_ ])test|moddtest|toddtest|clutter warehouse|_clutter$|^mournhold, museum of artifacts$")


def levi_items(D, iid, depth=0):
    L = D.get('levi', {}).get(iid)
    if L is None: return [iid]
    if depth > 4: return []
    out = []
    for x in L['items']:
        for y in levi_items(D, x, depth + 1):
            if y not in out: out.append(y)
    return out


def sources(D):
    """item id -> list of source dicts"""
    out = {}
    skipped_merchant = 0
    for key, r in D['refs'].items():
        rid = r['id']
        if r['cell'][0] == 'i' and EXCLUDED_CELLS.search(r['cell'][1]):
            continue
        base = {'cell': r['cell'], 'pos': r['pos'], 'owned': bool(r.get('owner') or r.get('faction')),
                'owner': r.get('owner') or r.get('faction'), 'lock': r.get('lock', 0) or 0,
                'trap': bool(r.get('trap')), 'keyid': r.get('keyid'), 'plugin': r['plugin'],
                'origin': r['origin']}
        if rid in D['items']:
            s = dict(base); s['kind'] = 'loose'; s['count'] = max(1, r.get('count', 1) or 1)
            out.setdefault(rid, []).append(s)
        elif rid in D['actors'] and D['actors'][rid].get('dead'):
            a = D['actors'][rid]
            for iid, cnt in a['inv'].items():
                if cnt <= 0 or iid not in D['items']:
                    continue
                s = dict(base); s['kind'] = 'cont'; s['count'] = cnt; s['body'] = True
                s['cont'] = 'body of ' + (a.get('name') or rid)
                out.setdefault(iid, []).append(s)
        elif rid in D['conts']:
            c = D['conts'][rid]
            if r.get('owner') and is_merchant(D, r['owner']):
                skipped_merchant += 1
                continue
            inv = c['inv']
            if c['flags'] & 1:
                # plants hold a leveled list ('random_marshmerrow'); list every item it can give
                inv = {}
                for iid, cnt in c['inv'].items():
                    for x in levi_items(D, iid):
                        inv[x] = max(inv.get(x, 0), cnt)
            for iid, cnt in inv.items():
                if cnt <= 0 or iid not in D['items']:
                    continue
                s = dict(base); s['kind'] = 'cont'; s['count'] = cnt
                s['cont'] = c.get('name') or rid
                s['organic'] = bool(c['flags'] & 1)
                s['respawn'] = bool(c['flags'] & 2)
                out.setdefault(iid, []).append(s)
    return out, skipped_merchant


# ---------------------------------------------------------------------------
# armor sets
# ---------------------------------------------------------------------------
SLOT_WORDS = {'left', 'right', 'l', 'r', 'cuirass', 'helm', 'helmet', 'closed', 'open', 'pauldron', 'pauldrons',
              'gauntlet', 'gauntlets', 'bracer', 'bracers', 'greaves', 'boots', 'shield', 'tower', 'towershield',
              'buckler', 'mask', 'hood', 'cap', 'cuirras', 'chestplate', 'chest', 'armor', 'armour', 'plate', 'mail',
              'face', 'gloves', 'glove', 'shoes', 'targe', 'kite', 'round', 'heater', 'full', 'half', 'of', 'the',
              'great', 'small', 'large', 'coif', 'visor', 'circlet', 'crown', 'pants', 'leggings', 'legs', 'sabatons'}


def material_of(name):
    words = re.findall(r"[A-Za-z'\-]+", name or '')
    keep = [w for w in words if w.lower() not in SLOT_WORDS]
    return ' '.join(keep).strip()


# ---------------------------------------------------------------------------
# helpers for output
# ---------------------------------------------------------------------------
def per_cell_cap(srcs, per):
    """keep the best `per` sources in every cell (interior, or 8192-unit outdoor cell): nearby copies are never lost.
    best = free and regrowing first, then free, then unlocked, then the rest"""
    def rank(s):
        free = not s['owned'] and not (s['lock'] > 0) and not s.get('trap')
        return (0 if free and s.get('respawn') else 1 if free else 2 if not s['lock'] else 3)
    by = {}
    for s in srcs:
        c = s['cell']
        key = c if c[0] == 'i' else ('e', (int(s['pos'][0] // 8192), int(s['pos'][1] // 8192)))
        by.setdefault(key, []).append(s)
    out = []
    for lst in by.values():
        lst.sort(key=rank)
        out += lst[:per]
    return out


def spread_cap(srcs, cap):
    """keep at most `cap` sources spread over the map (one per area bucket, growing the bucket)."""
    if len(srcs) <= cap: return srcs
    size = 4096.0
    while True:
        seen = {}
        for s in srcs:
            p = s['xy']
            b = (int(p[0] // size), int(p[1] // size))
            # prefer unowned / unlocked in each bucket
            cur = seen.get(b)
            if cur is None or (cur['owned'], cur['lock'] > 0) > (s['owned'], s['lock'] > 0):
                seen[b] = s
        if len(seen) <= cap or size > 2e6: return list(seen.values())[:cap]
        size *= 1.4


def lua_str(s):
    return '"' + (s or '').replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ') + '"'


def main():
    report = 'report' in sys.argv
    t0 = time.time()
    if 'cache' in sys.argv and os.path.exists(CACHE):
        D = pickle.load(open(CACHE, 'rb'))
    else:
        D = scan()
        tmp = CACHE + '.tmp'
        pickle.dump(D, open(tmp, 'wb')); os.replace(tmp, CACHE)
    print(f"scan: items {len(D['items'])}, ench {len(D['ench'])}, conts {len(D['conts'])}, refs {len(D['refs'])} ({time.time()-t0:.0f}s)")
    sys.path.insert(0, HERE)
    import world as W
    w = W.world()
    srcs, skipped = sources(D)
    # display copies (e.g. Tribunal museum 'boots of blinding speed_x'): an '_x' record that has a
    # same-named, same-type real record elsewhere is never listed; the real item is ranked instead
    byname = {}
    for k, it in D['items'].items():
        byname.setdefault((it['type'], (it.get('name') or '').lower()), []).append(k)
    display = [k for k in srcs if k.endswith('_x') and
               any(o != k and not o.endswith('_x') for o in byname.get((D['items'][k]['type'], (D['items'][k].get('name') or '').lower()), []))]
    for k in display: del srcs[k]
    print('display copies dropped:', len(display), sorted(display)[:6])
    nb = sum(1 for l in srcs.values() for s in l if s.get('body'))
    print('sources on dead bodies:', nb, 'dead actors placed:', sum(1 for r in D['refs'].values() if r['id'] in D['actors']))
    print(f"sources for {len(srcs)} item ids; skipped {skipped} merchant-owned containers")

    # lowest lock level the player must open to get from outdoors into each interior
    # (over all routes: a route costs the highest lock on it; the cell gets the cheapest route)
    import heapq
    DL = D.get('doorlocks', {})
    def door_lock(frm, pos):
        v = DL.get((frm, round(pos[0]), round(pos[1])), (0, True))
        return v[0] if isinstance(v, tuple) else v
    # locks on doors between rooms inside an interior (not the doors in / out)
    inner_locks = {}
    for (c, x, y), v in DL.items():
        lk, tele = v if isinstance(v, tuple) else (v, False)
        if c[0] == 'i' and lk > 0 and not tele:
            inner_locks.setdefault(c, set()).add(lk)
    out_edges = {}
    for dest, lst in W.world()['doors_into'].items():
        for frm, pos, _d in lst:
            out_edges.setdefault(frm, []).append((dest, door_lock(frm, pos)))
    entry_lock = {}
    heap = []
    for frm in out_edges:
        if frm[0] == 'e':
            heap.append((0, frm))
    heapq.heapify(heap)
    seen = set()
    while heap:
        lk, c = heapq.heappop(heap)
        if c in seen: continue
        seen.add(c)
        if c[0] == 'i': entry_lock[c] = lk
        for dest, dl in out_edges.get(c, ()):
            if dest not in seen and dest[0] == 'i':
                heapq.heappush(heap, (max(lk, dl), dest))
    print('interiors behind a locked door:', sum(1 for v in entry_lock.values() if v > 0), 'of', len(entry_lock),
          '; interiors with locked doors inside:', len(inner_locks))

    # outdoor anchor (x,y) and route doors for every interior cell with a source
    cellinfo = {}
    def cinfo(ck):
        if ck in cellinfo: return cellinfo[ck]
        if ck[0] == 'e':
            e = D['extcells'].get(ck[1], {})
            name = e.get('name') or D['regions'].get(e.get('region') or '', '') or 'Wilderness'
            ci = {'name': name, 'doors': [], 'anchors': []}
        else:
            ci = {'name': D['intcells'].get(ck[1], ck[1]), 'doors': [], 'anchors': []}
            try:
                route = W.entrances(ck)
            except Exception:
                route = []
            for dck, dpos in route:
                ci['doors'].append((dck, dpos))
                if dck[0] == 'e':
                    ci['anchors'].append(dpos)
            ci['doors'] = ci['doors'][:12]
            # outdoor neighbourhood name for the text
            if ci['anchors']:
                a = ci['anchors'][0]
                g = (int(a[0] // 8192), int(a[1] // 8192))
                e = D['extcells'].get(g, {})
                ci['near'] = e.get('name') or D['regions'].get(e.get('region') or '', '')
        cellinfo[ck] = ci
        return ci

    for iid, lst in srcs.items():
        for s in lst:
            ci = cinfo(s['cell'])
            if s['cell'][0] == 'e':
                s['xy'] = (s['pos'][0], s['pos'][1])
            elif ci['anchors']:
                s['xy'] = (ci['anchors'][0][0], ci['anchors'][0][1])
            else:
                s['xy'] = (1e7, 1e7)   # no route from outdoors (teleport-only)

    # categories and pre-selection
    arts = load_artifacts()
    cats = {}
    for iid, lst in srcs.items():
        it = D['items'][iid]
        cat = category(D, it)
        if not cat: continue
        if cat.startswith('w_') and it.get('wtype') in (12, 13): continue
        cats.setdefault(cat, []).append(iid)
    KEEP = {'w': 70, 'a': 50, 's': 90}
    selected = {}
    for cat, ids in cats.items():
        if cat in ('ingredients', 'scrolls', 'spellbooks'):
            for i in ids: selected[i] = cat
            continue
        k = KEEP[cat[0]]
        keep = set()
        for cls in (None, ANDI):
            for ue in (True, False):
                ranked = sorted(ids, key=lambda i: -score(D, D['items'][i], cls, ue))
                keep.update(ranked[:k])
        for i in keep: selected[i] = cat
    # uniques / artifacts (special category): curated list + enchanted gear with a single source
    uniques = set()
    for iid, lst in srcs.items():
        it = D['items'][iid]
        if it['type'] not in ('WEAP', 'ARMO', 'CLOT'): continue
        if iid in arts:
            uniques.add(iid); continue
        e = D['ench'].get(it.get('ench') or '')
        if not e or e.get('type') == 0: continue
        if len(lst) == 1 and it.get('value', 0) >= 1000 and category(D, it):
            uniques.add(iid)
    for iid in uniques:
        selected.setdefault(iid, category(D, D['items'][iid]) or 's_unique')

    # armor sets: unenchanted pieces grouped by material and weight class
    sets = {}
    for iid, lst in srcs.items():
        it = D['items'][iid]
        if it['type'] != 'ARMO' or it.get('ench') or it.get('atype') not in ARMOR_SLOT: continue
        mat = material_of(it.get('name'))
        if not mat or len(mat) > 28: continue
        key = (mat.lower(), armor_class(D, it))
        s = sets.setdefault(key, {'mat': mat, 'w': key[1], 'slots': {}})
        slot = SET_SLOT[it['atype']]
        s['slots'].setdefault(slot, []).append(iid)
    good_sets = []
    for key, s in sets.items():
        if len({SET_GROUP[k] for k in s['slots']}) < 5: continue
        total = 0
        for slot, ids in s['slots'].items():
            ids.sort(key=lambda i: (-D['items'][i]['ar'], -len(srcs[i])))
            total += D['items'][ids[0]]['ar']
        s['total'] = total
        good_sets.append(s)
    good_sets.sort(key=lambda s: -s['total'])
    good_sets = good_sets[:60]
    for s in good_sets:
        for slot, ids in s['slots'].items():
            s['slots'][slot] = ids[:4]
            for i in ids[:4]: selected.setdefault(i, 'set')

    # ---------------- write Lua ----------------
    plugin_idx = {}
    def pidx(p):
        if p not in plugin_idx: plugin_idx[p] = len(plugin_idx) + 1
        return plugin_idx[p]
    cell_idx = {}
    def cidx(ck):
        if ck not in cell_idx: cell_idx[ck] = len(cell_idx) + 1
        return cell_idx[ck]

    CAP = {'ingredients': 300}
    item_lines = []
    total_src = 0
    counts = {}
    for iid in sorted(selected):
        it = D['items'][iid]
        cat = selected[iid]
        lst = srcs[iid]
        cap = CAP.get(cat, 120)
        n_all = len(lst)
        lst = per_cell_cap(lst, 2) if cat == 'ingredients' else spread_cap(lst, cap)
        total_src += len(lst)
        counts[cat] = counts.get(cat, 0) + 1
        parts = []
        for s in lst:
            c = cidx(s['cell'])
            fl = (1 if s['owned'] else 0) | (2 if s['trap'] else 0) | (4 if s['kind'] == 'cont' else 0) \
                 | (8 if s.get('organic') else 0) | (16 if s.get('respawn') else 0) | (32 if s.get('body') else 0)
            x, y, z = s['pos']
            cont = (s.get('cont') or '').replace(',', ' ').replace(';', ' ')
            parts.append(f"{c},{x:.0f},{y:.0f},{z:.0f},{fl},{s['lock']},{pidx(s['plugin'])},{cont}")
        art = arts.get(iid)
        extra = ''
        if cat == 'spellbooks':
            txt = D['scripts'].get(it.get('script'), '')
            m = re.search(r'addspell\s*,?\s*"?([^"\r\n]+?)"?\s*(\r|\n|;|$)', txt, re.I)
            if m: extra += ', sp = ' + lua_str(m.group(1).strip().lower())
            m = re.search(r'getintelligence\s*>=?\s*(\d+)', txt, re.I)
            if m: extra += f', int = {m.group(1)}'
        if iid in uniques: extra += ', u = true'
        if art: extra += ', d = ' + lua_str(art)
        item_lines.append(f"  [{lua_str(iid)}] = {{ t = {lua_str(it['type'])}, c = {lua_str(cat)}, p = {pidx(it['plugin'])}, n = {n_all}{extra}, L = {lua_str(';'.join(parts))} }},")
    cell_lines = []
    for ck, i in sorted(cell_idx.items(), key=lambda kv: kv[1]):
        ci = cinfo(ck)
        doors = []
        for dck, dpos in ci['doors']:
            if dck[0] == 'e':
                doors.append(f"e,{dpos[0]:.0f},{dpos[1]:.0f},{dpos[2]:.0f}")
            else:
                doors.append(f"{cidx_door(dck, cell_idx, cinfo)},{dpos[0]:.0f},{dpos[1]:.0f},{dpos[2]:.0f}")
        if ck[0] == 'e':
            cell_lines.append(f"  {{ n = {lua_str(ci['name'])}, e = true }},")
        else:
            near = ci.get('near')
            lk = entry_lock.get(ck, 0)
            cell_lines.append(f"  {{ n = {lua_str(ci['name'])}, id = {lua_str(ck[1])}"
                              + (f", near = {lua_str(near)}" if near else '')
                              + (f", K = {lk}" if lk > 0 else '')
                              + (f", I = {lua_str(','.join(str(x) for x in sorted(inner_locks[ck])))}" if ck in inner_locks else '')
                              + (f", D = {lua_str(';'.join(doors))}" if doors else '') + " },")
    # cells referenced only by doors were appended to cell_idx while writing; emit them too
    while len(cell_lines) < len(cell_idx):
        ck = [k for k, v in cell_idx.items() if v == len(cell_lines) + 1][0]
        ci = cinfo(ck)
        cell_lines.append(f"  {{ n = {lua_str(ci['name'])}, id = {lua_str(ck[1])} }},")
    set_lines = []
    for s in good_sets:
        slots = ', '.join(f"{sl} = {{ {', '.join(lua_str(i) for i in ids)} }}" for sl, ids in sorted(s['slots'].items()))
        set_lines.append(f"  {{ m = {lua_str(s['mat'])}, w = {lua_str(s['w'])}, slots = {{ {slots} }} }},")
    plugin_lines = [f"  {lua_str(p)}," for p, i in sorted(plugin_idx.items(), key=lambda kv: kv[1])]

    def chunked(name, lines, keyed):
        # LuaJIT keeps a limit on constants per function: build big tables in chunks
        out = [f"local {name} = {{}}"]
        for k in range(0, len(lines), 1500):
            body = '\n'.join(lines[k:k + 1500])
            if keyed:
                out.append(f"do local t = {{\n{body}\n}} for k, v in pairs(t) do {name}[k] = v end end")
            else:
                out.append(f"do local t = {{\n{body}\n}} for _, v in ipairs(t) do {name}[#{name} + 1] = v end end")
        return '\n'.join(out)

    src = ["-- GENERATED by tools/build_ledger.py from the active load order. Do not edit by hand.",
           "-- items[id].L = 'cell,x,y,z,flags,lock,plugin,container;...'  flags: 1 owned 2 trapped 4 in container 8 plant 16 respawns",
           "-- cells[i] = { n = name, id = interior id (lowercase), e = exterior, D = route doors 'cell|e,x,y,z;...',",
           "--              K = lowest lock level on the way in from outdoors (absent: no lock),",
           "--              I = lock levels of doors between rooms inside, e.g. '80,100' }",
           chunked('plugins', plugin_lines, False),
           chunked('cells', cell_lines, False),
           chunked('items', item_lines, True),
           chunked('sets', set_lines, False),
           f"return {{ version = 1, built = {lua_str(time.strftime('%Y-%m-%d'))}, plugins = plugins, cells = cells, items = items, sets = sets }}",
           ""]
    tmp = OUT + '.tmp'
    open(tmp, 'w', encoding='utf-8').write('\n'.join(src))
    os.replace(tmp, OUT)
    print(f"wrote {OUT}: {os.path.getsize(OUT)/1e6:.2f} MB, items {len(item_lines)}, cells {len(cell_lines)}, "
          f"sources {total_src}, sets {len(set_lines)}, plugins {len(plugin_lines)}")
    print('items per category:', dict(sorted(counts.items())))
    print('spell-teaching book scripts:', len(D['scripts']), 'books with them:',
          sum(1 for it in D['items'].values() if it['type'] == 'BOOK' and it.get('script') in D['scripts']))

    if report:
        do_report(D, srcs, selected, uniques, good_sets, cinfo, arts)


def cidx_door(dck, cell_idx, cinfo):
    if dck not in cell_idx:
        cell_idx[dck] = len(cell_idx) + 1
    return cell_idx[dck]


def where_text(s, cinfo):
    ci = cinfo(s['cell'])
    t = ci['name']
    if s['cell'][0] == 'i' and ci.get('near'): t += f" (near {ci['near']})"
    if s.get('cont'): t += f", in {s['cont']}"
    return t


def do_report(D, srcs, selected, uniques, good_sets, cinfo, arts):
    bycat = {}
    for iid, cat in selected.items():
        bycat.setdefault(cat, []).append(iid)
    for cat in sorted(bycat):
        ids = bycat[cat]
        if cat == 'ingredients':
            print(f"\n== ingredients: {len(ids)} ids; most sources:",
                  ', '.join(f"{D['items'][i].get('name')} ({len(srcs[i])})" for i in sorted(ids, key=lambda i: -len(srcs[i]))[:5]))
            continue
        ranked = sorted(ids, key=lambda i: -score(D, D['items'][i], ANDI))
        print(f"\n== {cat} ({len(ids)} candidates)")
        for i in ranked[:5]:
            it = D['items'][i]
            free = [s for s in srcs[i] if not s['owned']]
            s = (free or srcs[i])[0]
            print(f"  {score(D, it, ANDI):7.1f}  {it.get('name')!s:34} [{i}] {it['plugin']}  x{len(srcs[i])}  e.g. {where_text(s, cinfo)}"
                  + ('  OWNED' if s['owned'] else '') + (f"  lock {s['lock']}" if s['lock'] else ''))
    print('\n== uniques:', len(uniques))
    for i in sorted(uniques, key=lambda i: -score(D, D['items'][i], ANDI))[:25]:
        it = D['items'][i]
        print(f"  {score(D, it, ANDI):7.1f}  {it.get('name')!s:34} [{i}] {it['plugin']}  {where_text(srcs[i][0], cinfo)}")
    print('\n== sets (top 12)')
    for s in good_sets[:12]:
        print(f"  {s['mat']:24} {s['w']:6} total AR {s['total']}  slots {', '.join(f'{k}:{len(srcs[v[0]])}' for k, v in sorted(s['slots'].items()))}")


if __name__ == '__main__':
    main()

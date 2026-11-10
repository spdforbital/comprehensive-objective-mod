"""Small reader for the Morrowind/OpenMW plugin files in the active load order."""
import os, struct

CFG = os.path.expanduser('~/.config/openmw/openmw.cfg')

def load_order():
    lines = open(CFG, encoding='utf-8', errors='replace').read().splitlines()
    datas = [l[5:].strip().strip('"') for l in lines if l.startswith('data=')]
    contents = [l[8:].strip() for l in lines if l.startswith('content=')]
    files = []
    for c in contents:
        if not c.lower().endswith(('.esm', '.esp', '.omwaddon')):
            continue
        for d in reversed(datas):
            p = os.path.join(d, c)
            if os.path.exists(p):
                files.append((c, p))
                break
    return files

def records(path):
    d = open(path, 'rb').read()
    i = 0
    while i + 16 <= len(d):
        tag = d[i:i+4].decode('latin1')
        size = struct.unpack('<I', d[i+4:i+8])[0]
        yield tag, d[i+16:i+16+size]
        i += 16 + size

def subs(body):
    j = 0
    while j + 8 <= len(body):
        st = body[j:j+4].decode('latin1')
        sz = struct.unpack('<I', body[j+4:j+8])[0]
        yield st, body[j+8:j+8+sz]
        j += 8 + sz

def zstr(v):
    return v.split(b'\0')[0].decode('latin1')

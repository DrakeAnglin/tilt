"""Plan a Tilt build and work out its parts, straight from hardware/BOM.md and docs/pcb-build.md.

Used by the inventory skill (.claude/skills/inventory/SKILL.md). It reads the parts lists every time, so it never
holds a copy of a count, a pack size or a link.

  python3 tools/inventory.py parts                    every part the build can use: key, name, pack, link
  python3 tools/inventory.py order [plan] [counts]    the To order table: one combined purchase
  python3 tools/inventory.py new [plan] [--out FILE]  a new inventory.md from the skill's template

Plan:
  --set 3          one set of up to 3 blinds on one controller (repeat per set). A 3rd blind gets a 10 ft cord;
  --set 3:middle   the controller sits in the middle, so the 3rd blind gets a 6.6 ft cord
  --hub 0          the home already has its Tilt Hub (default 1)
  --solar N        N solar panels per controller (default 0: no solar)
  --no-crimper     pre-crimped JST-XH leads in place of the crimp pins
Counts (repeat; KEY from `parts`):
  --have KEY=N       on hand now (In stock + Issued). N can be "kit" or "plenty": the builder's own kit covers it
  --on-order KEY=N   bought and on the way
Standard library only.
"""
import argparse
import math
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
BOM = os.path.join(ROOT, 'hardware', 'BOM.md')
GUIDE = os.path.join(ROOT, 'docs', 'pcb-build.md')
TEMPLATE = os.path.join(ROOT, '.claude', 'skills', 'inventory', 'template.md')

LINK = re.compile(r'\[([^\]]*)\]\(([^)]*)\)')
PART_NO = re.compile(r'\*\*([A-Z0-9][A-Za-z0-9().\-/]*\d[A-Za-z0-9().\-/]*)\*\*')
BARE_PART_NO = re.compile(r'\b([A-Z0-9]+-[A-Z0-9\-]*\d[A-Z0-9\-]*|[0-9][A-Z0-9]*[A-Z][A-Z0-9]{3,})\b')
REFS = re.compile(r'\b([JRCDF])(\d+)(?:[–-]\1?(\d+))?\b')
COVERED = ('kit', 'plenty')
UNITS = ('tilter', 'controller', 'hub')
STORES = (('amazon.', 'Amazon'), ('digikey.', 'DigiKey'), ('adafruit.', 'Adafruit'), ('pcbway.', 'PCBWay'))


class Part:
    """One thing you buy. BOM rows with the same link are one part (the M3 kit, the ESP for controller and hub)."""

    def __init__(self, key, name, url, pack):
        self.key, self.name, self.url, self.pack = key, name, url, pack
        self.per = {}          # unit -> count per unit (int), 'port' for 1 per used port, None for a length or "a little"
        self.where = {}        # unit -> where it goes (PCB labels, or the BOM's note)
        self.amount = {}       # unit -> "about 40 cm" where the BOM gives a length, not a count
        self.mpn = ''
        self.cord = None       # '3.3', '6.6', '10' for the RJ12 cords
        self.optional = None   # 'solar' or 'no-crimper'
        self.shared = False    # listed under Buy once

    @property
    def store(self):
        for host, name in STORES:
            if self.url and host in self.url:
                return name
        return 'any'

    @property
    def counted(self):
        """True when every use has a count, so Need is a number of pieces, not one kit."""
        return bool(self.per) and all(isinstance(v, int) or v == 'port' for v in self.per.values())

    def link(self):
        return f'[{self.name}]({self.url})' if self.url else self.name


def clean(text):
    """Markdown cell to plain words: no bold, links to their text."""
    return LINK.sub(r'\1', text).replace('**', '').strip()


def short_name(text):
    """The part's name for a table: no "(... note ...)", no "; see ..."."""
    text = re.sub(r'\s*\(\[[^\]]*\]\([^)]*\)\)', '', text)
    text = re.sub(r';\s*see\s+\[[^\]]*\]\([^)]*\)', '', text)
    text = clean(text)
    text = re.sub(r'\s+\([^()]*\)', '', text)
    return re.sub(r'\s+', ' ', text).strip(' ,;')


def pack_size(sold_as):
    """'3-pack' -> 3, 'pack of 50' -> 50, 'each' -> 1, 'minimum order 5' -> 5, a kit or roll -> its word."""
    s = clean(sold_as).lower()
    m = re.search(r'(\d+)-pack|pack of (\d+)|(\d+)-piece|minimum order (\d+)', s)
    if m:
        return int(next(g for g in m.groups() if g))
    if s.startswith('each'):
        return 1
    for word in ('kit', 'bag', 'roll', 'tube', 'spool', 'pack'):
        if word in s:
            return word
    return s or None


def per_unit(text):
    """'4 (2 case, 2 tray)' -> 4, '1 per port you use' -> 'port', 'about 40 cm' -> None."""
    s = clean(text)
    if 'per port' in s:
        return 'port'
    m = re.match(r'(\d+)\b(?!\s*(?:cm|mm|m|ft|in)\b)', s)
    return int(m.group(1)) if m else None


def refs_in(text):
    out = []
    for letter, a, b in REFS.findall(clean(text)):
        out += [f'{letter}{n}' for n in range(int(a), int(b or a) + 1)]
    return out


def note_in(text):
    m = re.search(r'\(([^()]*)\)', clean(text))
    return m.group(1) if m else ''


def part_no(*cells):
    for cell in cells:
        m = PART_NO.search(cell)
        if m:
            return m.group(1)
    for cell in cells[:1]:
        found = BARE_PART_NO.findall(clean(cell))
        if found:
            return found[-1]
    return ''


def key_for(name, url, mpn):
    if mpn:
        return mpn
    m = re.search(r'amazon\.com/dp/([A-Z0-9]+)', url or '')
    if m:
        return m.group(1)
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:32]


def table_rows(lines):
    """Yield (header cells, row cells) for each Markdown table row."""
    header = None
    for line in lines:
        if not line.startswith('|'):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if header is None:
            header = [clean(c).lower() for c in cells]
        elif not set(''.join(cells)) <= set('-: '):
            yield header, cells


def pcb_refs(guide_text):
    """docs/pcb-build.md "Parts for one board": part value -> its PCB labels."""
    out = {}
    m = re.search(r'## Parts for one board\n(.*?)\n## ', guide_text, re.S)
    for header, cells in table_rows((m.group(1) if m else '').splitlines()):
        if 'references' in header:
            out[clean(cells[0])] = refs_in(cells[header.index('references')])
    return out


def parse(bom_text, guide_text=''):
    """Every part the BOM lists, in BOM order: {key: Part}."""
    parts, by_url = {}, {}
    unit = sub = None
    section = []
    blocks = []                                    # (unit, sub-heading, lines)
    for line in bom_text.splitlines() + ['## end']:
        if line.startswith('#'):
            blocks.append((unit, sub, section))
            section = []
            level, title = len(line) - len(line.lstrip('#')), line.lstrip('#').strip().lower()
            if level == 2:
                unit = ('tilter' if 'tilter' in title else 'controller' if 'controller' in title else
                        'hub' if 'hub' in title else 'shared' if 'buy once' in title else
                        'optional' if 'optional' in title else None)
                sub = None
            else:
                sub = title
        else:
            section.append(line)

    def add(unit, name_cell, url, sold_as, per_text, extra=''):
        name = short_name(name_cell)
        mpn = part_no(extra, name_cell)
        part = by_url.get(url) if url else None
        if part is None:
            part = Part(key_for(name, url, mpn), name, url, pack_size(sold_as))
            parts[part.key] = part
            if url:
                by_url[url] = part
        elif isinstance(pack_size(sold_as), int) and not isinstance(part.pack, int):
            part.pack = pack_size(sold_as)
        part.mpn = part.mpn or mpn
        if unit == 'shared':
            part.shared = True
            if not part.per or not isinstance(part.pack, int):
                part.name = name
        elif unit:
            n, old = per_unit(per_text), part.per.get(unit, 0)
            if n is None and unit not in part.amount:
                part.amount[unit] = re.sub(r'\s*\([^()]*\)', '', clean(per_text)) or 'a little'
            part.per[unit] = old + n if isinstance(old, int) and isinstance(n, int) else n if unit not in part.per else None
            where = refs_in(per_text) or refs_in(extra)
            where = ', '.join(where) if where else note_in(per_text)
            part.where[unit] = '; '.join(w for w in (part.where.get(unit), where) if w)
        return part

    for unit, sub, lines in blocks:
        if unit is None or (sub or '').startswith(('printed', 'motor speed')):
            continue
        if unit == 'optional' and sub and 'crimper' in sub:
            text = ' '.join(lines)
            mpn, count = PART_NO.search(text), re.search(r'(\d+) per controller', text)
            urls = [u for t, u in LINK.findall(text) if u.startswith('http')]
            if mpn and count and urls:
                part = add('controller', 'Pre-crimped JST-XH lead, ' + mpn.group(1), urls[-1], 'each',
                           count.group(1), f'**{mpn.group(1)}**')
                part.optional = 'no-crimper'
            continue
        for header, cells in table_rows(lines):
            col = {h.split(' ')[0]: i for i, h in enumerate(header)}
            per_col = next((i for i, h in enumerate(header) if h.startswith(('per ', 'uses'))), None)
            sold, link_cell = cells[col['sold']], cells[col['link']]
            urls = [u for _, u in LINK.findall(link_cell)]
            if not clean(sold):
                continue                                 # printed: made, not bought
            url = urls[0] if urls else None
            extra = cells[col['exact']] if 'exact' in col else ''
            target = 'controller' if unit == 'optional' else unit
            part = add(target, cells[col['part']], url, sold, cells[per_col] if per_col is not None else '', extra)
            if unit == 'optional':
                part.optional = 'solar'
            m = re.search(r'(\d+(?:\.\d+)?) ft', clean(cells[col['part']]))
            if sub and 'cord' in sub and m:
                part.cord = m.group(1)

    refs = pcb_refs(guide_text)
    for part in parts.values():
        where = part.where.get('controller')
        if where is None or where:
            continue
        name = part.name.lower()
        letter = 'R' if 'resistor' in name else 'C' if 'ceramic' in name else None
        claimed = {r for p in parts.values() for w in p.where.values() for r in w.split(', ')}
        if letter:
            found = [r for rs in refs.values() for r in rs if r.startswith(letter) and r not in claimed]
        else:
            found = best_match(part.name, refs)
        part.where['controller'] = ', '.join(sorted(set(found), key=lambda r: (r[0], int(r[1:]))))
    return parts


def words(text):
    return {w for w in re.findall(r'[a-z0-9-]+', text.lower()) if len(w) >= 4}


def best_match(name, refs):
    """The PCB labels of the guide row that shares the most words (2 at least) with a part's name."""
    score, found = 1, []
    for value, rs in refs.items():
        n = len(words(name) & words(value))
        if n > score:
            score, found = n, list(rs)
        elif n == score > 1:
            found += rs
    return found


class Plan:
    def __init__(self, sets, hub=1, solar=0, crimper=True):
        self.sets = sets                   # [(blinds, middle)]
        self.hub, self.solar, self.crimper = hub, solar, crimper
        for blinds, _ in sets:
            if not 1 <= blinds <= 3:
                raise ValueError(f'a set has 1 to 3 blinds, not {blinds}')

    @property
    def units(self):
        return {'tilter': sum(b for b, _ in self.sets), 'controller': len(self.sets), 'hub': self.hub}

    def cords(self):
        """3.3 ft for the blind beside the controller, 6.6 ft for the next, 10 ft (6.6 ft in the middle) for a 3rd."""
        out = {'3.3': 0, '6.6': 0, '10': 0}
        for blinds, middle in self.sets:
            out['3.3'] += 1
            out['6.6'] += blinds >= 2
            out['6.6' if middle else '10'] += blinds == 3
        return out


def needs(parts, plan):
    """{key: pieces the plan uses} for every part the plan uses; a kit or roll counts as 1."""
    units, cords, out = plan.units, plan.cords(), {}
    for part in parts.values():
        if part.optional == 'solar' and not plan.solar or part.optional == 'no-crimper' and plan.crimper:
            continue
        if not plan.crimper and 'crimp pin' in part.name.lower():
            continue
        if part.cord:
            n = cords[part.cord]
        elif not part.per:
            n = 1
        elif part.counted:
            n = 0
            for unit, per in part.per.items():
                if part.optional == 'solar' and 'panel' in part.name.lower():
                    per = plan.solar
                n += units['tilter'] if per == 'port' else units[unit] * per
        else:
            n = 1 if any(units[u] for u in part.per) else 0
        if n:
            out[part.key] = n
    return out


def order(parts, plan, have=None, on_order=None):
    """The To order rows: one combined purchase. Each row: (part, packs, pack, have, need, spare)."""
    have, on_order, rows = have or {}, on_order or {}, []
    for key, need in needs(parts, plan).items():
        part, got = parts[key], have.get(key, 0)
        if got in COVERED:
            continue
        short = need - got - on_order.get(key, 0)
        if short <= 0:
            continue
        if isinstance(part.pack, int):
            packs = math.ceil(short / part.pack)
            spare = got + on_order.get(key, 0) + packs * part.pack - need
            rows.append((part, packs, part.pack, got, need, spare))
        else:
            rows.append((part, 1, part.pack or 'each', got, need, '–'))
    return sorted(rows, key=lambda r: [s for _, s in STORES + (('', 'any'),)].index(r[0].store))


def order_table(rows):
    if not rows:
        return '**Nothing left to order.**\n'
    out = ['| Ordered | Part | From | Buy (packs) | Pack of | Have | Need | Spare after |',
           '|---|---|---|---|---|---|---|---|']
    for part, packs, pack, got, need, spare in rows:
        out.append(f'| ☐ | {part.link()} | {part.store} | {packs} | {pack} | {got} | {need} | {spare} |')
    return '\n'.join(out) + '\n'


def per_text(part, unit):
    per = part.per[unit]
    text = '1 per used port' if per == 'port' else str(per) if per is not None else part.amount.get(unit, 'a little')
    others = [f'+{v} per {u}' for u, v in part.per.items() if u != unit and isinstance(v, int)]
    return text + (f' ({", ".join(others)})' if others else '')


def stock_tables(parts, plan):
    """The Stock tables, stage columns empty: tilter, controller, hub, shared supplies."""
    used = needs(parts, plan)
    groups = {u: [] for u in UNITS + ('shared',)}
    for part in parts.values():
        if part.key not in used:
            continue
        on_board = any(refs_in(w) for w in part.where.values())
        if part.cord or part.counted and (on_board or not part.shared):
            unit = 'tilter' if part.cord else next(iter(part.per))
            groups[unit].append(part)
        else:
            groups['shared'].append(part)
    titles = {'tilter': 'Tilter parts', 'controller': 'Controller parts', 'hub': 'Hub parts', 'shared': 'Shared supplies'}
    out = []
    for unit, items in groups.items():
        out += [f'### {titles[unit]}', '']
        if unit == 'shared':
            out += ['Kits, rolls and bags many units draw from. Count them as packs, or write "plenty".', '',
                    '| Part | From | Uses | Pack | In stock |', '|---|---|---|---|---|']
            for p in items:
                uses = ', '.join(per_text(p, u).split(' (')[0] + f' per {u}' for u in p.per) or 'a little'
                out.append(f'| {p.link()} | {p.store} | {uses} | {p.pack or "–"} | |')
        else:
            out += ['| Part | Where it goes | From | MPN | Per unit | Pack | Used | Assembled | Issued | In stock |',
                    '|---|---|---|---|---|---|---|---|---|---|']
            for p in items:
                where = 'by cord rule' if p.cord else p.where.get(unit, '')
                per = f'by cord rule ({p.cord} ft)' if p.cord else per_text(p, unit)
                out.append(f'| {p.link()} | {where} | {p.store} | {p.mpn} | {per} | {p.pack} | | | | |')
        out.append('')
    return '\n'.join(out)


def plan_text(plan):
    u, c = plan.units, plan.cords()
    lines = ['| Set | Blinds | Cords |', '|---|---|---|']
    for i, (blinds, middle) in enumerate(plan.sets, 1):
        cords = ['3.3 ft', '6.6 ft', '6.6 ft' if middle else '10 ft'][:blinds]
        lines.append(f'| {i} | {blinds} | {" + ".join(cords)} |')
    lines += ['', '| Tilters | Controllers | Tilt Hub | RJ12 jacks and fuses | Cords 3.3 / 6.6 / 10 ft |',
              '|---|---|---|---|---|',
              f'| {u["tilter"]} | {u["controller"]} | {u["hub"]} | {u["tilter"]} of each | '
              f'{c["3.3"]} / {c["6.6"]} / {c["10"]} |', '',
              f'**Solar:** {"yes, " + str(plan.solar) + " panel(s) per controller" if plan.solar else "no"}. '
              f'**JST crimper:** {"yes" if plan.crimper else "no (pre-crimped leads)"}.']
    return '\n'.join(lines) + '\n'


def optional_text(parts, plan):
    out = ['| Part | Chosen | From |', '|---|---|---|']
    for p in parts.values():
        if p.optional:
            chosen = bool(plan.solar) if p.optional == 'solar' else not plan.crimper
            out.append(f'| {p.link()} | {"yes" if chosen else "no"} | {p.store} |')
    return '\n'.join(out) + '\n'


def counts(pairs):
    out = {}
    for pair in pairs or []:
        key, _, n = pair.partition('=')
        out[key] = n if n in COVERED else int(n)
    return out


def load():
    with open(BOM) as f:
        bom = f.read()
    guide = ''
    if os.path.exists(GUIDE):
        with open(GUIDE) as f:
            guide = f.read()
    return parse(bom, guide)


def main(argv=None, parts=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=('parts', 'order', 'new'))
    ap.add_argument('--set', action='append', default=[], dest='sets')
    ap.add_argument('--hub', type=int, default=1)
    ap.add_argument('--solar', type=int, default=0)
    ap.add_argument('--no-crimper', action='store_true')
    ap.add_argument('--have', action='append')
    ap.add_argument('--on-order', action='append')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    parts = parts if parts is not None else load()
    if a.command == 'parts':
        print('| Key | Part | Pack | From | Optional |\n|---|---|---|---|---|')
        for p in parts.values():
            print(f'| {p.key} | {p.link()} | {p.pack} | {p.store} | {p.optional or ""} |')
        return 0
    try:
        sets = [(int(s.split(':')[0]), s.endswith(':middle')) for s in a.sets]
        plan = Plan(sets, a.hub, a.solar, not a.no_crimper)
    except ValueError as e:
        print(f'inventory: {e}', file=sys.stderr)
        return 2
    rows = order(parts, plan, counts(a.have), counts(a.on_order))
    if a.command == 'order':
        print(order_table(rows), end='')
        return 0
    with open(TEMPLATE) as f:
        text = f.read()
    text = (text.replace('{{plan}}', plan_text(plan)).replace('{{to_order}}', order_table(rows))
            .replace('{{stock}}', stock_tables(parts, plan)).replace('{{optional}}', optional_text(parts, plan)))
    if not a.out:
        print(text, end='')
        return 0
    if os.path.exists(a.out):
        print(f'inventory: {a.out} already exists; edit it instead', file=sys.stderr)
        return 1
    with open(a.out, 'w') as f:
        f.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())

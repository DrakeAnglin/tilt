"""A small grid router for the controller PCB (pure Python, runs inside KiCad's Python with pcbnew).

Both copper layers are a grid of cells (PITCH mm). Every pad, hole, track and via is painted onto the grid with the
net that owns it; a cell is usable for a new track of net n only if nothing of another net lies within half the track
width plus the clearance. Each net is routed pad by pad with A*: from the next pad to ANY copper the net already has,
so multi-pin nets grow as a tree. Layer changes cost a via. KiCad's own DRC checks the result afterward.
"""
import heapq
import math

import pcbnew

PITCH = 0.125         # mm
CLEAR = 0.2           # copper-to-copper clearance, mm
EDGE = 0.5            # copper-to-board-edge, mm
VIA_D, VIA_DRILL = 0.7, 0.35
VIA_COST = 12.0
BEND_COST = 0.6
BLOCK = -1            # owner value for "nobody may use this cell"
FREE = 0
MM = pcbnew.FromMM
TO = pcbnew.ToMM


class Grid:
    def __init__(self, outline_pts):
        xs = [p[0] for p in outline_pts]
        ys = [p[1] for p in outline_pts]
        self.x0, self.y0 = min(xs), min(ys)
        self.nx = int(math.ceil((max(xs) - self.x0) / PITCH)) + 1
        self.ny = int(math.ceil((max(ys) - self.y0) / PITCH)) + 1
        self.own = [[FREE] * (self.nx * self.ny) for _ in range(2)]       # per layer: 0 F.Cu, 1 B.Cu
        self.outline = outline_pts
        self._offs = {}
        for iy in range(self.ny):                                          # outside the board / too near its edge
            for ix in range(self.nx):
                x, y = self.xy(ix, iy)
                if not self.inside(x, y, EDGE):
                    self.own[0][iy * self.nx + ix] = BLOCK
                    self.own[1][iy * self.nx + ix] = BLOCK

    # geometry helpers
    def xy(self, ix, iy):
        return self.x0 + ix * PITCH, self.y0 + iy * PITCH

    def cell(self, x, y):
        return int(round((x - self.x0) / PITCH)), int(round((y - self.y0) / PITCH))

    def inside(self, x, y, margin):
        """Point in the (axis-aligned, rectilinear) outline and at least 'margin' from every edge."""
        pts = self.outline
        n = len(pts)
        inside = False
        for k in range(n):
            (x0, y0), (x1, y1) = pts[k], pts[(k + 1) % n]
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                inside = not inside
            # distance to this edge segment
            dx, dy = x1 - x0, y1 - y0
            t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / (dx * dx + dy * dy)))
            if math.hypot(x - (x0 + t * dx), y - (y0 + t * dy)) < margin:
                return False
        return inside

    def offsets(self, r):
        """Cell offsets within radius r (mm) of a cell center."""
        k = round(r, 3)
        if k not in self._offs:
            n = int(math.ceil(r / PITCH))
            self._offs[k] = [(dx, dy) for dx in range(-n, n + 1) for dy in range(-n, n + 1)
                             if math.hypot(dx, dy) * PITCH <= r + 1e-9]
        return self._offs[k]

    # painting
    def paint_disc(self, layer, x, y, r, owner):
        cx, cy = self.cell(x, y)
        for dx, dy in self.offsets(r):
            ix, iy = cx + dx, cy + dy
            if 0 <= ix < self.nx and 0 <= iy < self.ny:
                i = iy * self.nx + ix
                if self.own[layer][i] in (FREE, owner) or owner == BLOCK:
                    self.own[layer][i] = owner if self.own[layer][i] != BLOCK else BLOCK

    def paint_rect(self, layer, xa, ya, xb, yb, owner):
        ia, ja = self.cell(xa, ya)
        ib, jb = self.cell(xb, yb)
        for iy in range(max(0, ja), min(self.ny, jb + 1)):
            for ix in range(max(0, ia), min(self.nx, ib + 1)):
                x, y = self.xy(ix, iy)
                if xa - 1e-9 <= x <= xb + 1e-9 and ya - 1e-9 <= y <= yb + 1e-9:
                    i = iy * self.nx + ix
                    if self.own[layer][i] != BLOCK:
                        self.own[layer][i] = owner

    def paint_segment(self, layer, a, b, half_w, owner):
        (x0, y0), (x1, y1) = a, b
        steps = max(1, int(math.hypot(x1 - x0, y1 - y0) / (PITCH / 2)))
        for k in range(steps + 1):
            t = k / steps
            self.paint_disc(layer, x0 + t * (x1 - x0), y0 + t * (y1 - y0), half_w, owner)

    def free_for(self, layer, ix, iy, net, r):
        """Can copper of 'net' with radius r (half width + clearance) be centered on this cell?"""
        own = self.own[layer]
        nx, ny = self.nx, self.ny
        for dx, dy in self.offsets(r):
            jx, jy = ix + dx, iy + dy
            if not (0 <= jx < nx and 0 <= jy < ny):
                return False
            o = own[jy * nx + jx]
            if o != FREE and o != net:
                return False
        return True


HOLE_GAP = 0.3       # drill edge to drill edge, mm (PCBWay asks for >= 0.25)


def via_hole_ok(grid, x, y):
    """A via's drill must keep HOLE_GAP from every other drill, whatever its net."""
    for hx, hy, hr in grid.holes:
        if (x - hx) ** 2 + (y - hy) ** 2 < (hr + VIA_DRILL / 2 + HOLE_GAP) ** 2:
            return False
    return True


def paint_board(board, grid, netcode):
    """Paint every pad and hole already on the board."""
    grid.holes = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            x, y = TO(pad.GetPosition().x), TO(pad.GetPosition().y)
            if pad.GetDrillSize().x > 0:
                grid.holes.append((x, y, TO(pad.GetDrillSize().x) / 2))
            net = netcode.get(pad.GetNetname(), BLOCK) if pad.GetNetname() else BLOCK
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:           # bare holes: keep everything clear
                r = TO(pad.GetDrillSize().x) / 2 + CLEAR
                for layer in (0, 1):
                    grid.paint_disc(layer, x, y, r, BLOCK)
                continue
            sx, sy = TO(pad.GetSize(pcbnew.F_Cu).x), TO(pad.GetSize(pcbnew.F_Cu).y)
            rot = pad.GetOrientationDegrees() % 180
            if rot not in (0, 90):
                sx = sy = max(sx, sy)
            if rot == 90:
                sx, sy = sy, sx
            for layer in (0, 1):
                if pad.GetShape(pcbnew.F_Cu) == pcbnew.PAD_SHAPE_CIRCLE:
                    grid.paint_disc(layer, x, y, sx / 2, net)
                else:
                    grid.paint_rect(layer, x - sx / 2, y - sy / 2, x + sx / 2, y + sy / 2, net)
        # mounting holes: no copper under the screw head (6 mm)
        if fp.GetReference().startswith('H'):
            x, y = TO(fp.GetPosition().x), TO(fp.GetPosition().y)
            for layer in (0, 1):
                grid.paint_disc(layer, x, y, 3.0 + CLEAR, BLOCK)


def pad_cells(grid, pad):
    """Grid cells lying on a pad's copper (both layers: THT)."""
    x, y = TO(pad.GetPosition().x), TO(pad.GetPosition().y)
    s = min(TO(pad.GetSize(pcbnew.F_Cu).x), TO(pad.GetSize(pcbnew.F_Cu).y)) / 2 * 0.7
    cx, cy = grid.cell(x, y)
    return [(cx + dx, cy + dy) for dx, dy in grid.offsets(s)] or [(cx, cy)]


DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


GRID_MARGIN = 0.15           # painted copper can reach this far past a cell center: keep that much extra room


def astar(grid, net, starts, goals, half_w, layers_allowed=(0, 1)):
    """From any start cell (both layers) to any goal cell (layer, ix, iy): the part of the net already connected."""
    r = half_w + CLEAR + GRID_MARGIN
    rv = max(VIA_D / 2 + CLEAR + GRID_MARGIN, r)     # a via is also where a (possibly wide) track starts
    nx = grid.nx
    # a track may only start / end where its full width clears other nets (a wide track ending on a pad's rim could
    # otherwise reach a neighbor); keep at least the pad center
    ok_starts = [c for c in starts if all(grid.free_for(l, c[0], c[1], net, r) for l in layers_allowed)]
    starts = ok_starts or starts[:1]
    start_set = set(starts)
    goals = {g for g in goals if grid.free_for(g[0], g[1], g[2], net, r)} or goals
    if not goals:
        return None
    gpts = [(gx, gy) for _, gx, gy in goals]

    def h(ix, iy):
        return min(abs(ix - gx) + abs(iy - gy) for gx, gy in gpts[:: max(1, len(gpts) // 60)]) * 0.9

    openq, came, cost = [], {}, {}
    for (ix, iy) in starts:
        for l in layers_allowed:
            st = (l, ix, iy, -1)
            cost[st] = 0.0
            heapq.heappush(openq, (h(ix, iy), 0.0, st))
            came[st] = None
    ok_cache = {}
    while openq:
        f, g, st = heapq.heappop(openq)
        if g > cost.get(st, 1e18) + 1e-9:
            continue
        l, ix, iy, d = st
        if (l, ix, iy) in goals:
            path = []
            while st is not None:
                path.append(st[:3])
                st = came[st]
            return path[::-1]
        for k, (dx, dy) in enumerate(DIRS):
            jx, jy = ix + dx, iy + dy
            key = (l, jx, jy)
            if key not in ok_cache:
                ok_cache[key] = (0 <= jx < nx and 0 <= jy < grid.ny and
                                 (key in goals or (jx, jy) in start_set or grid.free_for(l, jx, jy, net, r)))
            if not ok_cache[key]:
                continue
            step = 1.0 if dx == 0 or dy == 0 else 1.4142
            ng = g + step + (BEND_COST if d not in (-1, k) else 0.0)
            ns = (l, jx, jy, k)
            if ng < cost.get(ns, 1e18):
                cost[ns] = ng
                came[ns] = st
                heapq.heappush(openq, (ng + h(jx, jy), ng, ns))
        # via to the other layer
        ol = 1 - l
        if ol in layers_allowed:
            vkey = ('v', ix, iy)
            if vkey not in ok_cache:
                ok_cache[vkey] = (grid.free_for(0, ix, iy, net, rv) and grid.free_for(1, ix, iy, net, rv)
                                  and via_hole_ok(grid, *grid.xy(ix, iy)))
            if ok_cache[vkey]:
                ns = (ol, ix, iy, -1)
                ng = g + VIA_COST
                if ng < cost.get(ns, 1e18):
                    cost[ns] = ng
                    came[ns] = st
                    heapq.heappush(openq, (ng + h(ix, iy), ng, ns))
    return None


def split_at(board, netinfo, layer, pt):
    """If pt lies inside a track of this net on this layer (not at an end), split that track there."""
    p = pcbnew.VECTOR2I(MM(pt[0]), MM(pt[1]))
    for t in list(board.GetTracks()):
        if t.GetClass() != 'PCB_TRACK' or t.GetNetCode() != netinfo.GetNetCode() or t.GetLayer() != layer:
            continue
        a, b = t.GetStart(), t.GetEnd()
        if a == p or b == p:
            return
        # point on the segment (collinear and between the ends, to within 1 um)
        cross = (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x)
        seg = ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5
        if seg and abs(cross) / seg < 1000 and min(a.x, b.x) - 1000 <= p.x <= max(a.x, b.x) + 1000 \
                and min(a.y, b.y) - 1000 <= p.y <= max(a.y, b.y) + 1000:
            t2 = pcbnew.PCB_TRACK(board)
            t2.SetStart(p)
            t2.SetEnd(b)
            t2.SetWidth(t.GetWidth())
            t2.SetLayer(layer)
            t2.SetNet(netinfo)
            board.Add(t2)
            t.SetEnd(p)
            return


def emit(board, grid, net, netinfo, path, half_w):
    """Turn a cell path into straight tracks and vias, add them to the board and paint them."""
    layer_id = (pcbnew.F_Cu, pcbnew.B_Cu)
    pts = [(l, grid.xy(ix, iy)) for l, ix, iy in path]
    runs, cur = [], [pts[0]]
    for prev, p in zip(pts, pts[1:]):
        if p[0] != prev[0]:                             # via
            runs.append(cur)
            runs.append(('via', p[1]))
            cur = [p]
        else:
            cur.append(p)
    runs.append(cur)
    n_tracks = n_vias = 0
    for run in runs:
        if isinstance(run, tuple):
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(MM(run[1][0]), MM(run[1][1])))
            v.SetWidth(MM(VIA_D))
            v.SetDrill(MM(VIA_DRILL))
            v.SetNet(netinfo)
            board.Add(v)
            grid.holes.append((run[1][0], run[1][1], VIA_DRILL / 2))
            for layer in (0, 1):
                grid.paint_disc(layer, run[1][0], run[1][1], VIA_D / 2, net)
            n_vias += 1
            continue
        if len(run) < 2:
            continue
        l = run[0][0]
        # merge collinear points
        corners = [run[0][1]]
        for k in range(1, len(run) - 1):
            (x0, y0), (x1, y1), (x2, y2) = run[k - 1][1], run[k][1], run[k + 1][1]
            if abs((x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)) > 1e-9:
                corners.append(run[k][1])
        corners.append(run[-1][1])
        for end in (corners[0], corners[-1]):
            split_at(board, netinfo, layer_id[l], end)
        for a, b in zip(corners, corners[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
            t.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
            t.SetWidth(MM(2 * half_w))
            t.SetLayer(layer_id[l])
            t.SetNet(netinfo)
            board.Add(t)
            grid.paint_segment(l, a, b, half_w, net)
            n_tracks += 1
    return n_tracks, n_vias


def route(board, outline_pts, widths, order, default_w=0.3, first=None):
    """Route every net in 'order' (net names). widths: {net: track width mm}. first: {net: ([(ref, pad), ...], width)}
    pads joined first, in that order, as one tree of that width (e.g. the motor-return GND). Returns (failures, stats, grid)."""
    grid = Grid(outline_pts)
    nets = board.GetNetsByName()
    netcode = {name: k + 1 for k, name in enumerate(order)}
    paint_board(board, grid, netcode)
    pads_of = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname():
                pads_of.setdefault(pad.GetNetname(), []).append(pad)
    failures, stats = [], [0, 0]
    for name in order:
        pads = pads_of.get(name, [])
        if len(pads) < 2:
            continue
        net = netcode[name]
        half_w = widths.get(name, default_w) / 2
        # grow a tree: start from the first pad, then add the nearest unconnected pad each time; the goal is always the
        # connected tree (its pads and the path cells), so the net never splits into islands
        pre, pre_w = (first or {}).get(name, ([], None))
        key = {(p.GetParentFootprint().GetReference(), p.GetNumber()): p for p in pads}
        pre_pads = [key[k] for k in pre if k in key]
        if pre_pads:
            pads = pre_pads + [p for p in pads if p not in pre_pads]
        tree = {(l, ix, iy) for ix, iy in pad_cells(grid, pads[0]) for l in (0, 1)}
        done = [pads[0]]
        todo = pads[1:]
        while todo:
            if pre_pads and todo[0] in pre_pads:                # the pre-ordered group, in its own order and width
                pad = todo.pop(0)
                cells = pad_cells(grid, pad)
                path = astar(grid, net, cells, tree, pre_w / 2)
                if path is None:
                    failures.append('%s: %s-%s' % (name, pad.GetParentFootprint().GetReference(), pad.GetNumber()))
                else:
                    t, v = emit(board, grid, net, nets[name], path, pre_w / 2)
                    stats[0] += t
                    stats[1] += v
                    tree |= set(path)
                    tree |= {(l, ix, iy) for ix, iy in cells for l in (0, 1)}
                done.append(pad)
                continue
            def dist(p):
                return min((p.GetPosition() - q.GetPosition()).EuclideanNorm() for q in done)
            todo.sort(key=dist)
            pad = todo.pop(0)
            cells = pad_cells(grid, pad)
            path = astar(grid, net, cells, tree, half_w)
            if path is None:
                failures.append('%s: %s-%s' % (name, pad.GetParentFootprint().GetReference(), pad.GetNumber()))
            else:
                t, v = emit(board, grid, net, nets[name], path, half_w)
                stats[0] += t
                stats[1] += v
                tree |= set(path)
                tree |= {(l, ix, iy) for ix, iy in cells for l in (0, 1)}
            done.append(pad)
    return failures, stats, grid


def stitch(board, grid, name, step):
    """GND stitching vias on a 'step' mm grid wherever both layers are free, so the two GND pours act as one."""
    net = grid_net = None
    nets = board.GetNetsByName()
    # the GND code is whatever paint_board / route gave it: read it back from a GND pad
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == name:
                ix, iy = grid.cell(TO(pad.GetPosition().x), TO(pad.GetPosition().y))
                grid_net = grid.own[0][iy * grid.nx + ix]
                break
        if grid_net:
            break
    rv = VIA_D / 2 + CLEAR + GRID_MARGIN + 0.1
    n = 0
    y = grid.y0 + step / 2
    while y < grid.y0 + grid.ny * PITCH:
        x = grid.x0 + step / 2
        while x < grid.x0 + grid.nx * PITCH:
            ix, iy = grid.cell(x, y)
            if 0 <= ix < grid.nx and 0 <= iy < grid.ny and grid.free_for(0, ix, iy, -999, rv) and grid.free_for(1, ix, iy, -999, rv) \
                    and via_hole_ok(grid, x, y):
                grid.holes.append((x, y, VIA_DRILL / 2))
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                v.SetWidth(MM(VIA_D))
                v.SetDrill(MM(VIA_DRILL))
                v.SetNet(nets[name])
                board.Add(v)
                for layer in (0, 1):
                    grid.paint_disc(layer, x, y, VIA_D / 2, grid_net)
                n += 1
            x += step
        y += step
    return n

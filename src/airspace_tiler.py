# (c)2019, Arthur van Hoff

import shapefile, pyproj, affine, math, os, sys, shapely.geometry, panda3d.core, gltf, time, traceback
from geometry import Point, QuadTree, angle, centroid, bearing
import settings, util, tiler, combiner

# moffet overlapping palo alto
# out of memory for NY sectional
# package up more easily
# class E

add_floors = True
add_ceilings = False
add_borders = True
add_verticals = True
add_poles = False
dump_airspaces = False
remove_interior_walls = True
cleanup_airspace_regions = True
airspace_cleanup = True
airspace_self_intersect = True
airspace_intersect = True
airspace_check = True
airspace_class_E = False
airports = None
badairports = None

checkairports = {'KPAO', 'KLAX', 'KSNA', 'KFLD', 'KMCI', 'KOFF', 'KJFK', 'KTPA', 'KSAN', 'KBIG', 'KSEA', 'KENA', 'KTRK', 'KSMF', 'KTUS', 'KDMA', 'KPHX'}
badairports = {'KSTL', 'KSNA', 'KCIC', 'KORH', 'KGRF', 'KJNU', 'KMSY', 'KDTW', 'KBFL', 'KSWF', 'KSCH', 'KDFW', 'KHST', 'KSEA', 'KSUX', 'KADQ', 'KMDT', 'KSLC', 'KPHL', 'KBET', 'KNHK', 'KFMH', 'KJKA', 'KLUF', 'KCLT', 'KDCA', 'KFRI', 'KACT'}
badareas = {'A-MONTAGUE-E5', 'MONTAGUE-E5', 'A-PETERSBURG-E5', 'A-YUMA-E5', 'A-ST.-MICHAEL-E5', 'A-TATITLEK-E5', 'A-MOUNTAIN-HOME-E5', 'A-NEW-STUYAHOK-E5', 'A-WEST-YELLOWSTONE-E5', 'A-WRANGELL-E5'}
#airports = {'KNHK'}
if airports is not None:
    badairports = badairports.difference(airports)

black = (0, 0, 0, 1)
red = (1, 0, 0, 1)
wall_alpha = 0.7
wall_colors = {
    'A': (1.0, 0.5, 0.0, wall_alpha),
    'B': (0.0, 0.5, 1.0, wall_alpha),
    'C': (0.5, 0.0, 1.0, wall_alpha),
    'D': (0.0, 1.0, 0.5, wall_alpha),
    'E': (1.0, 0.5, 0.0, wall_alpha),
    'E2': (1.0, 0.5, 0.2, wall_alpha),
    'E3': (1.0, 0.5, 0.4, wall_alpha),
    'E4': (1.0, 0.5, 0.6, wall_alpha),
    'E5': (1.0, 0.5, 0.8, wall_alpha),
    'G': (1.0, 1.0, 0.0, wall_alpha),
}

floor_alpha = 0.25
floor_colors = {}
for k,v in wall_colors.items():
    floor_colors[k] = (*v[0:3], floor_alpha)

ceiling_alpha = 0.1
ceiling_colors = {}
for k,v in wall_colors.items():
    ceiling_colors[k] = (*v[0:3], ceiling_alpha)

line_alpha = 1.0
line_colors = {}
for k,v in wall_colors.items():
    line_colors[k] = (v[0]/4, v[1]/4, v[2]/4, line_alpha)

#
# Airspace, class B, C, D
# Contains a list of regions.
#

class Counted:
    count = 0

    def __init__(self):
        Counted.count = Counted.count + 1
        self.index = Counted.count

class Airspace(Counted):
    def __init__(self, id, ident, type_code):
        super().__init__()
        self.id = id
        self.ident = ident
        self.type_code = type_code
        self.type_class = type_code[6:]
        self.regions = []
        self.bbox = util.bbox_init()

    def simplify(self):
        for r in self.regions:
            r.simplify()

    def cleanup(self):
        for region in self.regions:
            if True:
                region.cleanup_points()
            if True:
                region.cleanup_straights()

        if True:
            qtree = QuadTree()
            for region in self.regions:
                region.insert_points(qtree, region.make_points(region.points))
                region.check()
            qtree.check_tree()
            if True:
                for region in self.regions:
                    region.cleanup_edges(qtree)
            if True and airspace_self_intersect:
                self.cleanup_self_intersection(qtree)

            if False:
                print("qtree")
                for i, pt in enumerate(qtree.all()):
                    print(i, pt)

    def add_region(self, region):
        self.regions.append(region)
        self.bbox = util.bbox_union(self.bbox, region.bbox)

    def cleanup_self_intersection(self, qtree):
        count = 0

        i = 0
        while i < len(self.regions):
            r1 = self.regions[i]
            i = i + 1
            j = i
            while j < len(self.regions):
                r2 = self.regions[j]
                j = j + 1
                if util.bbox_overlap(r1.bbox, r2.bbox):
                    p1, p2, p3 = util.polygon_intersection(r1.get_polygon(), r2.get_polygon())
                    if util.not_empty(p2):
                        print(f"self intersect {r1} {r2}")
                        #print("self intersection", p1, p2, p3)
                        #r1.dump()
                        #r2.dump()
                        if util.not_empty(p1):
                            for p in p1:
                                r = Region(self, r1.lower, r1.upper)
                                r.set_poly_points(qtree, p)
                                self.add_region(r)
                                #r.dump()
                        for p in p2:
                            r = Region(self, min(r1.lower, r2.lower), max(r1.upper, r2.upper))
                            r.set_poly_points(qtree, p)
                            self.add_region(r)
                            #r.dump()
                        if util.not_empty(p3):
                            for p in p3:
                                r = Region(self, r2.lower, r2.upper)
                                r.set_poly_points(qtree, p)
                                self.add_region(r)
                                #r.dump()

                        r2.clear()
                        j = j - 1
                        del self.regions[j]
                        r1.clear()
                        i = i - 1
                        del self.regions[i]
                        count += 1

                        break
        if count > 0:
            print(f"found {count} self intersections in {self}")
            for region in self.regions:
                region.cleanup_edges(qtree)
            self.check()

    def subtract_airspace(self, qtree, other):
        count = 0
        i = 0
        while i < len(self.regions):
            r1 = self.regions[i]
            i = i + 1
            j = 0
            while j < len(other.regions):
                r2 = other.regions[j]
                j = j + 1
                if util.bbox_overlap(r1.bbox, r2.bbox) and r1.upper > r2.lower:
                    p1, p2, p3 = util.polygon_intersection(r1.get_polygon(), r2.get_polygon())
                    if util.not_empty(p2):
                        print(f"subtract regions {r1} - {r2}")
                        #print("subtract airspace", i, j, self.id, other.id)
                        if util.not_empty(p1):
                            for p in p1:
                                r = Region(self, r1.lower, r1.upper)
                                r.set_poly_points(qtree, p)
                                self.add_region(r)
                        if r1.lower < r2.lower:
                            for p in p2:
                                r = Region(self, r1.lower, min(r2.upper, r2.lower))
                                r.set_poly_points(qtree, p)
                                self.add_region(r)
                        if r1.upper > r2.upper:
                            for p in p2:
                                r = Region(self, max(r1.lower, r2.upper), r2.upper)
                                r.set_poly_points(qtree, p)
                                self.add_region(r)
                        # leave p3 alone
                        r1.clear()
                        i = i - 1
                        del self.regions[i]
                        count += 1
                        break
        # resolve any new self intersections
        if count > 0:
            print(f"subtracted {count} regions {self} - {other}")
            for region in self.regions:
                region.cleanup_edges(qtree)
            for region in other.regions:
                region.cleanup_edges(qtree)
            self.check()


    def draw(self, t, gltf):
        for region in self.regions:
            region.draw(t, gltf)

    def check(self):
        for region in self.regions:
            region.check()

    def dump(self):
        print("airspace", self)
        for region in self.regions:
            region.dump()

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "A[%d,%s,%d]" % (self.index, self.id, len(self.regions))

#
# Region (an area on the map, bounded by a list of points, with a lower and upper elevation)
# Regions consist of closed polygons and must not contain holes
#
class Region(Counted):
    def __init__(self, airspace, lower, upper):
        super().__init__()
        self.airspace = airspace
        self.lower = lower
        self.upper = upper
        self.bbox = util.bbox_init()
        self.polygon = None
        self.points = []

    def simplify(self):
        self.polygon = None
        bb = self.bbox
        self.set_points(self.make_points([
            (bb[0], bb[1]),
            (bb[2], bb[1]),
            (bb[2], bb[3]),
            (bb[0], bb[3]),
        ]))

    def set_points(self, points):
        if len(points) <= 2:
            self.dump()
            print(points)
        assert len(points) > 2
        for point in points:
            assert(self in point.regions)
        self.points = points
        self.bbox = util.bbox_points(points)
        assert not util.bbox_empty(self.bbox)
        self.polygon = None

    def make_points(self, points):
        pts = [Point(pt[0], pt[1], {self}) for pt in points]
        for p0, p1, p2 in util.enumerate_triples(pts):
            p1.angle = angle(p0, p1, p2)
        return pts

    def filter_points(self, points):
        i = 0
        n = len(points)
        while i < n:
            if points[i] is points[(i+1) % n]:
                del points[i]
                n -= 1
            else:
                i += 1
        return points

    def insert_points(self, qtree, points, dist=60):
        self.set_points(self.filter_points([qtree.insert_grouped(pt, dist=dist) for pt in points]))

    def set_poly_points(self, qtree, poly):
        #print("set_poly_points", poly.area, len(list(poly.exterior.coords)))
        coords = poly.exterior.coords
        assert len(coords) > 0, "empty polygon"
        if len(coords) == 0:
            print("EMPTY POLY", poly)
            return []
        if coords[0] != coords[-1]:
            print("OPEN POLY", poly)
        else:
            coords = coords[:-1]

        lp = [(coords[i-1][0], coords[i-1][1]) for i in range(len(coords), 0, -1)]
        #for i, p in enumerate(lp):
        #    print(i, p)
        lp = self.make_points([(c[0], c[1]) for c in coords])
        #for i, p in enumerate(lp):
        #    print(i, p)
        self.insert_points(qtree, lp, dist=60)

    #
    # Delete any duplicate points.
    # Delete any points that are too close together.
    #
    def cleanup_points(self, mindist=75):
        n = 0
        while True:
            pairs = sorted([(p0.distance(p1), p0, p1) for p0, p1 in util.enumerate_pairs(self.points)], key=lambda x: x[0])
            eliminated = set()
            for d, p0, p1 in pairs:
                if d >= mindist:
                    break
                if p0.angle < p1.angle:
                    tmp = p1
                    p1 = p0
                    p0 = tmp
                if p1 not in eliminated:
                    eliminated.add(p1)
                    if p0.is_grouped():
                        p0.group.append(p1)
                    else:
                        p0.group = [p0, p1]
            if len(eliminated) == 0:
                break
            n += len(eliminated)
            self.points = [pt for pt in self.points if pt not in eliminated]
        if n > 0:
            print(f"removed {n} unnecessary points from {self}")

    #
    # Delete any duplicate points.
    # Delete any points that are too close together.
    # Avoid deleting corners
    #
    def cleanup_points_old(self, mindist=100, maxcenterdist=20, maxangle=15):
        print("cleanup", self)
        rc = 0
        i = 0
        c = 0
        n = len(self.points)
        p0 = self.points[-1]
        p1 = self.points[0]
        p2 = self.points[1]
        d01 = p0.distance(p1)
        d12 = p1.distance(p2)
        while c < n:
            if (p0.lon == p1.lon and p0.lat == p2.lat) or (p1.lon == p2.lon and p1.lat == p2.lat) or (d01 < mindist and d12 < mindist and p1.distance(Point((p0.lon + p2.lon)/2, (p0.lat + p2.lat)/2)) < maxcenterdist and p1.angle < maxangle):
                #print(f"delete {i}, {p0}, {p1}, {p2}")
                del self.points[i]
                n -= 1
                i = i % n
                p1 = p2
                p2 = self.points[(i + 1) % n]
                d01 = p0.distance(p1)
                d12 = p1.distance(p2)
                c = 0
                rc += 1
            else:
                i = (i+1) % n
                p0 = p1
                p1 = p2
                p2 = self.points[(i + 1) % n]
                d01 = d12
                d12 = p1.distance(p2)
                c += 1
        if rc > 0:
            print(f"removed {rc} unnecessary points from {self}")

    #
    # Find straight lines between corners
    #
    def cleanup_straights(self, thresh=0.006, maxangle=5):
        prev = None
        prevd = 0
        i = 0
        c = 0
        n = len(self.points)
        p0 = self.points[-1]
        p1 = self.points[0]
        p2 = self.points[1]
        b01 = bearing(p0, p1)
        b12 = bearing(p1, p2)
        while c < 2*n:
            if abs(b12 - b01) > maxangle:
                if prev is not None and i != (prev + 1) % n:
                    pp = self.points[prev]
                    pd = p1.distance(pp)
                    if pd > 0 and (prevd - pd)/pd < thresh:
                        #print(f"straight line in {self} from {prev} to {i}, {prevd:.2f}/{pd:.2f}, {prevd - pd:.2f} {(prevd - pd)/pd:.5f}??")
                        #self.dump()
                        # knock out points inbetween prev and i
                        if prev < i:
                            del self.points[prev+1:i]
                        else:
                            del self.points[prev+1:]
                            del self.points[0:i]
                            prev -= i
                        n = len(self.points)
                        i = (prev + 1) % n
                prev = i
                prevd = 0

            i = (i + 1) % n
            c += 1
            prevd += p1.distance(p2)
            p0 = p1
            p1 = p2
            p2 = self.points[(i + 1) % n]
            b01 = b12
            b12 = bearing(p1, p2)

    #
    # find any points near edges and merge them into the polygon
    #
    def cleanup_edges(self, qtree, maxdist=200):
        #print("cleanup_edges", self)
        count = 0
        i = 0
        n = len(self.points)
        while i < n:
            p0 = self.points[i]
            p1 = self.points[(i + 1) % n]
            ll = p0.distance(p1)
            c = centroid([p0, p1])
            #print("segment", p0, p1, ll, min(ll/2, maxdist), c)
            candidates = []
            for pt in qtree.all_near(c, ll/1.8):
                if self not in pt.regions and self.overlap(pt.regions):
                    ld = pt.distance_line(p0, p1)
                    if ld < min(ll/2, maxdist):
                        d0 = pt.distance(p0)
                        if ld < d0 and ld < pt.distance(p1) and abs(angle(p0, pt, p1)) < 35:
                            candidates.append((d0, pt))

            #print("candidates", candidates)
            if len(candidates) > 0:
                pt = sorted(candidates)[0][1]
                pt.regions.add(self)
                self.points.insert(i+1, pt)
                n += 1
                count += 1

            i += 1
        if count > 0:
            print(f"cleaned up {count} edges in {self}")

    def overlap(self, regions):
        for reg in regions:
            if self.upper > reg.lower and self.lower < reg.upper:
                return True
        return False

    def clear(self):
        for point in self.points:
            point[2].discard(self)
        self.points = []
        self.polygon = None
        self.bbox = util.bbox_init()

    def get_polygon(self):
        if self.polygon is None:
            self.polygon = shapely.geometry.Polygon([(p.lon, p.lat) for p in self.points])
            #if not self.polygon.is_valid:
            #    print('bad points', self.points)
            #    raise Exception("invalid polygon")
        return self.polygon

    def draw(self, t, g):
        self.draw_walls(t, g)

        # floors
        if add_floors and self.airspace.type_class < 'E' and self.lower > util.SFC:
            tr = panda3d.core.Triangulator()
            for p in self.points:
                tr.addVertex(p[0], p[1])
            for i in range(len(self.points)):
                tr.addPolygonVertex(i)
            tr.triangulate()
            for i in range(tr.getNumTriangles()):
                g.add_triangle(
                    t.lla2xyz((*self.points[tr.getTriangleV0(i)][0:2], self.lower)),
                    t.lla2xyz((*self.points[tr.getTriangleV1(i)][0:2], self.lower)),
                    t.lla2xyz((*self.points[tr.getTriangleV2(i)][0:2], self.lower))
                )
            g.add_mesh(g.add_rgba(floor_colors[self.airspace.type_class]))

        # ceilings
        if add_ceilings and self.airspace.type_class < 'E':
            tr = panda3d.core.Triangulator()
            for p in self.points:
                tr.addVertex(p[0], p[1])
            for i in range(len(self.points)):
                tr.addPolygonVertex(i)
            tr.triangulate()
            for i in range(tr.getNumTriangles()):
                g.add_triangle(
                    t.lla2xyz((*self.points[tr.getTriangleV0(i)][0:2], self.upper)),
                    t.lla2xyz((*self.points[tr.getTriangleV1(i)][0:2], self.upper)),
                    t.lla2xyz((*self.points[tr.getTriangleV2(i)][0:2], self.upper))
                )
            g.add_mesh(g.add_rgba(ceiling_colors[self.airspace.type_class]))


    def draw_walls(self, t, g):
        lines = []
        poles = []
        n = len(self.points)
        for i in range(n):
            self.draw_wall(t, g, i, self.points[i], self.points[(i+1) % n], self.points[(i+2) % n], lines, poles)
        g.add_mesh(g.add_rgba(wall_colors[self.airspace.type_class]))

        if add_borders and len(lines) > 0:
            for p1,p2 in lines:
                g.add_line(p1, p2)
            g.add_mesh(g.add_rgba(line_colors[self.airspace.type_class]))
        if add_poles and len(poles) > 0:
            for p1,p2,grp in poles:
                if grp:
                    g.add_line(p1, p2)
            g.add_mesh(g.add_rgba(red))
            for p1,p2,grp in poles:
                if not grp:
                    g.add_line(p1, p2)
            g.add_mesh(g.add_rgba(black))

    def draw_wall(self, t, g, index, p1, p2, p3, lines, poles):
        panels = [[self.lower, self.upper]]
        if remove_interior_walls:
            for r in p1[2].intersection(p2[2]).intersection(self.airspace.regions):
                if r != self and r.connects(p1, p2):
                    for p in panels:
                        if r.lower > p[0] and r.upper < p[1]:
                            panels.append([r.upper, p[1]])
                            p[1] = r.lower
                        elif r.lower < p[0] and r.upper > p[1]:
                            p[1] = p[0]
                        elif r.lower < p[1] and r.upper >= p[1]:
                            p[1] = r.lower
                        elif r.upper > p[0] and r.lower <= p[0]:
                            p[0] = r.upper

        for p in panels:
            self.draw_wall_panel(t, g, index, p1, p2, p3, *p, lines, poles)

    def draw_wall_panel(self, t, g, index, p1, p2, p3, h1, h2, lines, poles):
        if h1 < h2:
            if p1[0] == p2[0] and p1[1] == p2[1]:
                print("bad panel, zero length", self, p1, p2, h1, h2)
                return
            if h1 >= h2:
                print("bad panel, invalid height", self, p1, p2, h1, h2)
                return
            v1 = t.lla2xyz((p1[0], p1[1], self.sfc_elevation(p1, h1)))
            v2 = t.lla2xyz((p2[0], p2[1], self.sfc_elevation(p2, h1)))
            v3 = t.lla2xyz((p2[0], p2[1], h2))
            v4 = t.lla2xyz((p1[0], p1[1], h2))
            g.add_quad(v1, v2, v3, v4)
            lines.append((v1, v2))
            lines.append((v3, v4))
            if add_verticals and abs(angle(p1, p2, p3)) > 35:
                lines.append((v2, v3))

            if add_poles:
                v5 = t.lla2xyz((p1[0], p1[1], h2 + 20))
                poles.append((v1, v5, p1.group is not None))

    def connects(self, p1, p2):
        if self not in p1[2] or self not in p2[2]:
            return False
        i = self.points.index(p1)
        j = self.points.index(p2)
        return ((i+1) % len(self.points)) == j or ((j+1) % len(self.points)) == i

    def check(self):
        assert len(self.points) > 2, f"{self}: too few points, n={len(self.points)}"
        assert not util.bbox_empty(self.bbox), f"{self}: empty bbox"
        for i, p in enumerate(self.points):
            if self not in p[2]:
                print("BAD POINT", self, i, p)
                for j, q in enumerate(self.points):
                    print(j, q)
                raise Exception("bad point")
            if p in self.points[i+1:]:
                print("duplicate", i, i + 1 + self.points[i+1:].index(p), len(self.points), self, p)
                self.dump()
                assert False

    def sfc_elevation(self, lonlat, h):
        return 0 if h == util.SFC else h

    def ht(self, h):
        return "SFC" if h == util.SFC else "%d" % (int(round(h * util.m2f/100)))

    def dump(self):
        print("  region", self)
        n = len(self.points)
        for i, p1 in enumerate(self.points):
            p0 = self.points[(i-1) % n]
            p2 = self.points[(i+1) % n]
            print(f"    {i:4}: {p1.distance(p2):8.1f}, {bearing(p1, p2):5.1f}, {angle(p0, p1, p2):6.1f}, {p1}")

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "R[%d,%s,%s-%s,%d]" % (self.index, self.airspace.id, self.ht(self.lower), self.ht(self.upper), len(self.points))

#
# load and pre-process all the listed airspaces
#

def area_name(name):
    name = name.replace(' ','-').replace('/','-').replace(',','').replace('.','').replace('--','-').replace('-CLASS-', '-')
    return f"A-{name}"

def enumerate_areas():
    shp = shapefile.Reader(settings.nasr_shape_path)
    names = [field[0] for field in shp.fields]
    #print('names', names)
    id_index = names.index('DeletionFlag')
    ident_index = names.index('IDENT')
    type_code_index = names.index('TYPE_CODE')
    lower_desc_index = names.index('LOWER_DESC')
    upper_desc_index = names.index('UPPER_DESC')
    lower_uom_index = names.index('LOWER_UOM')

    # organize all shapes into airspaces
    skipped = set()
    airspaces = {}
    for f in shp.shapeRecords():
        id = f.record[id_index]
        ident = f.record[ident_index]
        type_code = f.record[type_code_index]
        #if id == '':
        #    type_codes.add(f.record[type_code_index])
        #    continue
        if f.shape.points[0] != f.shape.points[-1]:
            #print("shape not closed")
            continue
        if len(id) == 0:
            id = area_name(ident)
        elif type_code < 'CLASS_E':
            continue
        else:
            id = f"K{id}-{type_code[6:]}"

        # limit airports that are processed
        if airports is not None and id not in airports:
            continue

        if badairports is not None and id in badairports:
            if id not in skipped:
                print("skipping", id)
                skipped.add(id)
            continue
        if badareas is not None and id in badareas:
            if id not in skipped:
                print("skipping", id)
                skipped.add(id)
            continue

        # print parameters for debugging
        if False and airports is not None:
            for i, name in enumerate(names):
                if i < len(f.record):
                    print(id, name, i, f.record[i])

        # get relevant parameters
        lower = util.f2m * abs(float(f.record[lower_desc_index]))
        upper = util.f2m * abs(float(f.record[upper_desc_index]))
        #print("TYPE_CODE", type_code, float(f.record[lower_desc_index]), float(f.record[upper_desc_index]))
        if type_code not in ('CLASS_E2', 'CLASS_E3', 'CLASS_E4', 'CLASS_E5'):
            #if type_code not in ('CLASS_A', 'CLASS_B', 'CLASS_C', 'CLASS_D', 'CLASS_E'):
            #print("bad typecode", id, type_code)
            continue
        if lower == 0 and f.record[lower_uom_index] == 'SFC':
            lower = util.SFC


        # create airspace (if needed)
        if id not in airspaces:
            airspaces[id] = Airspace(id, ident, type_code)
        airspace = airspaces[id]

        # create region
        region = Region(airspace, lower, upper)
        region.set_points(region.make_points(f.shape.points[:-1]))
        airspace.add_region(region)

    return airspaces

def load_airspaces(airports):
    shp = shapefile.Reader(settings.nasr_shape_path)
    names = [field[0] for field in shp.fields]
    #print('names', names)
    id_index = names.index('DeletionFlag')
    ident_index = names.index('IDENT')
    type_code_index = names.index('TYPE_CODE')
    lower_desc_index = names.index('LOWER_DESC')
    upper_desc_index = names.index('UPPER_DESC')
    lower_uom_index = names.index('LOWER_UOM')

    # organize all shapes into airspaces
    skipped = set()
    airspaces = {}
    for f in shp.shapeRecords():
        id = f.record[id_index]
        ident = f.record[ident_index]
        type_code = f.record[type_code_index]
        #if id == '':
        #    type_codes.add(f.record[type_code_index])
        #    continue
        if f.shape.points[0] != f.shape.points[-1]:
            #print("shape not closed")
            continue
        if len(id) == 0:
            id = area_name(ident)
        elif len(id) == 3:
            id = f"K{id}-{type_code[6:]}"

        # limit airports that are processed
        if airports is not None and id not in airports:
            continue

        if badairports is not None and id in badairports:
            if id not in skipped:
                print("skipping", id)
                skipped.add(id)
            continue

        # print parameters for debugging
        if False and airports is not None:
            for i, name in enumerate(names):
                if i < len(f.record):
                    print(id, name, i, f.record[i])

        # get relevant parameters
        lower = util.f2m * abs(float(f.record[lower_desc_index]))
        upper = util.f2m * abs(float(f.record[upper_desc_index]))
        #print("TYPE_CODE", type_code, float(f.record[lower_desc_index]), float(f.record[upper_desc_index]))
        if type_code not in ('CLASS_E2', 'CLASS_E3', 'CLASS_E4', 'CLASS_E5'):
            #if type_code not in ('CLASS_A', 'CLASS_B', 'CLASS_C', 'CLASS_D', 'CLASS_E'):
            #print("bad typecode", id, type_code)
            continue
        if lower == 0 and f.record[lower_uom_index] == 'SFC':
            lower = util.SFC


        # create airspace (if needed)
        if id not in airspaces:
            airspaces[id] = Airspace(id, ident, type_code)
        airspace = airspaces[id]

        # create region
        region = Region(airspace, lower, upper)
        region.set_points(region.make_points(f.shape.points[:-1]))
        airspace.add_region(region)

    return airspaces

def generate_overlapping_airspaces(airspaces):
    print("generate_overlapping_airspaces", airspaces)

    # first basic cleanup
    for airspace in airspaces:
        #airspace.simplify()
        #airspace.dump()
        airspace.cleanup()
        #airspace.dump()

    # insert all points into the quad tree
    # points that are close together will be grouped
    if True and len(airspaces) > 1:
        qtree = QuadTree()
        for airspace in airspaces:
            for region in airspace.regions:
                region.insert_points(qtree, region.make_points(region.points), 50)

        # merge nearby edges
        if True:
            for airspace in airspaces:
                for region in airspace.regions:
                    region.cleanup_edges(qtree)

        # substract higher class airspaces from lower class airspaces
        if airspace_intersect:
            for a1 in airspaces:
                for a2 in airspaces:
                    if a1 is not a2:
                        if a1.type_class > a2.type_class and util.bbox_overlap(a1.bbox, a2.bbox):
                            a1.subtract_airspace(qtree, a2)
                    elif a1.type_class == a2.type_class and util.bbox_overlap(a1.bbox, a2.bbox):
                        print(f"possible overlap {a1, a2}")

        if True:
            t = 0
            n = 0
            g = 0
            for pt in qtree.all():
                t += 1
                if pt.is_grouped():
                    g += 1
                    n += len(pt.group)
            print(f"{t} points, {n} grouped points, {g} groups")

    if dump_airspaces:
        for airspace in airspaces:
            airspace.dump()

    if airspace_check:
        for airspace in airspaces:
            airspace.check()

    # output as a 3D object
    t1 = tiler.Tiler(settings.airports_dir + "-1x", 1)
    t5 = tiler.Tiler(settings.airports_dir + "-5x", 5)
    for airspace in airspaces:
        if False:
            print("airspace", airspace)
            for r in airspace.regions:
                print("region", r)
                for p in r.points:
                    print("point", p)
                r.check()

        g1 = gltf.GLTF()
        airspace.draw(t1, g1)
        g5 = gltf.GLTF()
        airspace.draw(t5, g5)
        extras = {
            'id': airspace.id,
            'class': airspace.type_class,
            'height': settings.defaultHeight[airspace.type_class],
            "flyto": True,
        }
        geometricError = settings.defaultGeometricError[airspace.type_class]

        t1.save_tile(airspace.id, g1, geometricError, extras)
        t5.save_tile(airspace.id, g5, geometricError, extras)
        print("saved", airspace.id)

def load_airspace_boundaries():
    shp = shapefile.Reader(settings.nasr_shape_path)
    names = [field[0] for field in shp.fields]
    id_index = names.index('DeletionFlag')
    ident_index = names.index('IDENT')
    type_code_index = names.index('TYPE_CODE')
    airspaces = {}
    for f in shp.shapeRecords():
        id = f.record[id_index]
        ident = f.record[ident_index]
        type_code = f.record[type_code_index]
        if len(id) == 0:
            id = area_name(ident)
        elif len(id) == 3:
            id = f"K{id}-{type_code[6:]}"
        key = (id, ident, type_code)
        if key in airspaces:
            airspaces[key] = util.bbox_union(airspaces[key], f.shape.bbox)
        else:
            airspaces[key] = f.shape.bbox

        #print(f"{key} = {f.shape.bbox}")

    return airspaces

def load_airspace_clusters():
    boundaries = load_airspace_boundaries()
    remaining = set(boundaries.keys())
    clusters = []
    while len(remaining) > 0:
        key = next(iter(remaining))
        remaining.remove(key)
        cluster = {key}
        cluster_bbox = boundaries[key]
        clusters.append(cluster)
        updated = '_E' not in key[2]
        while updated:
            updated = False
            for key in remaining:
                if '_E' not in key[2] and util.bbox_overlap(cluster_bbox, boundaries[key]):
                    cluster_bbox = util.bbox_union(cluster_bbox, boundaries[key])
                    cluster.add(key)
                    updated = True
            remaining = remaining.difference(cluster)

    return clusters

if __name__ == "__main__":
    tm = time.time()
    if False:
        print("loading areas...")
        all_areas = enumerate_areas()
        print("found {len(all_areas)} areas")
        for name, area in all_areas.items():
            try:
                generate_overlapping_airspaces([area])
            except:
                traceback.print_exc()

                print("FAILED", name)
                badareas.add(name)
        print("badareas", badareas)
        sys.exit(0)

    if airports is None:
        clusters = load_airspace_clusters()
        print(f"found {len(clusters)} clusters")
        #for i, cluster in enumerate(clusters):
        #    print(i, cluster)
        for depth in range(1,6):
            for i, cluster in enumerate(clusters):
                ids = set([id for id, _, _ in cluster])
                if airports is not None:
                    ids = ids.intersection(airports)
                if badairports is not None:
                    ids = ids.difference(badairports)
                if len(ids) > 0 and (depth == 5 or len(ids) == depth):
                    print(f"cluster {i}, {ids}")
                    try:
                        airspaces = load_airspaces(ids)
                        generate_overlapping_airspaces(list(airspaces.values()))
                    except:
                        traceback.print_exc()
                        print("FAILED", ids)
                        badairports.update(ids)
        if True:
            combiner.combine_airports(settings.airports_dir + "-1x")
            combiner.combine_airports(settings.airports_dir + "-5x")
    else:
        for airport in airports:
            print("airport", airport)
            try:
                airspaces = load_airspaces({airport})
                assert len(airspaces) > 0
                for airspace in airspaces.values():
                    generate_overlapping_airspaces([airspace])
            except:
                traceback.print_exc()

                print("FAILED", airport)
                badairports.add(airport)

    print("bad airports", badairports)
    tm = math.floor(time.time() - tm)
    hrs = tm // 3600
    min = (tm // 60) % 60
    sec = (tm % 60)
    print(f"done in {hrs}:{min:02}:{sec:02}")

# (c)2019, Arthur van Hoff

import shapefile, pyproj, affine, math, os, sys, shapely.geometry, panda3d.core
import settings, util, tiler, gltf
from geometry import Point, QuadTree, angle, centroid, bearing

# moffet overlapping palo alto
# out of memory for NY sectional
# package up more easily
# class E

add_floors = True
add_ceilings = False
add_borders = True
add_verticals = True
add_poles = True
dump_airspaces = False
remove_interior_walls = True
combine_points = True
cleanup_airspace_regions = True
airspace_cleanup = True
airspace_intersect = False
airspace_check = True
airspace_class_E = False
airports = {'KSJC', 'KRHV', 'KPAO', 'KSQL', 'KOAK', 'KHWD', 'KSFO', 'KNUQ'}
airports.update({'KAPC', 'KCCR', 'KLVK', 'KMRY', 'KSNS'})
airports.update({'KSMF', 'KSAC', 'KBAB', 'KMHR', 'KMOD', 'KSCK'})
#airports = {'KSFO', 'KHWD'}
#airports = {'KSFO'}

black = (0, 0, 0, 1)
red = (1, 0, 0, 1)
wall_alpha = 0.8
wall_colors = {
    'A': (1.0, 0.5, 0.0, wall_alpha),
    'B': (0.0, 0.5, 1.0, wall_alpha),
    'C': (0.5, 0.0, 1.0, wall_alpha),
    'D': (0.0, 1.0, 0.5, wall_alpha),
    'E': (1.0, 0.5, 0.0, wall_alpha),
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
                for i, pt in enumerate(region.points):
                    region.points[i] = qtree.insert_grouped(pt, dist=60)
            if True:
                for region in self.regions:
                    region.cleanup_edges(qtree)
            # REMIND self intersect

    def add_region(self, region):
        region.check()
        self.regions.append(region)
        self.bbox = util.bbox_union(self.bbox, region.bbox)

    def cleanup_self_intersection(self):
        updated = False
        #self.check()
        #for i, r1 in enumerate(self.regions[:-1]):
        #for j, r2 in enumerate(self.regions[i+1:]):
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
                        #print("self intersection", p1, p2, p3)
                        if util.not_empty(p1):
                            for p in p1:
                                self.add_region(Region(self, r1.lower, r1.upper, self.lonlats.get_poly_points(p, 'I1')))
                        for p in p2:
                            self.add_region(Region(self, min(r1.lower, r2.lower), max(r1.upper, r2.upper), self.lonlats.get_poly_points(p,'I2')))
                        if util.not_empty(p3):
                            for p in p3:
                                self.add_region(Region(self, r2.lower, r2.upper, self.lonlats.get_poly_points(p, 'I3')))

                        #self.regions[-2].combine(self.regions[-1])

                        r2.clear()
                        j = j - 1
                        del self.regions[j]
                        r1.clear()
                        i = i - 1
                        del self.regions[i]
                        updated = True
                        break
        self.check()

        # resolve any new self intersections
        if updated:
            for i in range(len(self.regions)):
                for j in range(i+1, len(self.regions)):
                    self.regions[i].combine(self.regions[j])
                    self.regions[j].combine(self.regions[i])
            for i in range(len(self.regions)):
                self.regions[i].cleanup_stuff()
        self.check()
        return updated

    def subtract_airspace(self, other):
        updated = False
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
                        #print("subtract airspace", i, j, self.id, other.id)
                        if util.not_empty(p1):
                            for p in p1:
                                self.add_region(Region(self, r1.lower, r1.upper, self.lonlats.get_poly_points(p, 'S1')))
                        if r1.lower < r2.lower:
                            for p in p2:
                                self.add_region(Region(self, r1.lower, min(r2.upper, r2.lower), self.lonlats.get_poly_points(p, 'S2a')))
                        if r1.upper > r2.upper:
                            for p in p2:
                                self.add_region(Region(self, max(r1.lower, r2.upper), r2.upper, self.lonlats.get_poly_points(p, 'S2b')))
                        # leave p3 alone
                        r1.clear()
                        i = i - 1
                        del self.regions[i]
                        updated = True
                        break
        # resolve any new self intersections
        if updated:
            for i in range(len(self.regions)):
                for j in range(i+1, len(self.regions)):
                    self.regions[i].combine(self.regions[j])
                    self.regions[j].combine(self.regions[i])
            for i in range(len(self.regions)):
                self.regions[i].cleanup_stuff()

        return updated

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
    def __init__(self, airspace, lower, upper, points):
        super().__init__()
        self.airspace = airspace
        self.lower = lower
        self.upper = upper
        self.points = points
        self.bbox = util.bbox_points(points)
        self.polygon = None
        for point in self.points:
            point[2].add(self)
        for p0, p1, p2 in util.enumerate_triples(self.points):
            p1.angle = angle(p0, p1, p2)

    def simplify(self):
        self.polygon = None
        bb = self.bbox
        self.points = [
            Point(bb[0], bb[1], {self}),
            Point(bb[2], bb[1], {self}),
            Point(bb[2], bb[3], {self}),
            Point(bb[0], bb[3], {self}),
        ]

    #
    # Delete any duplicate points.
    # Delete any points that are too close together.
    # Avoid deleting corners
    #
    def cleanup_points(self, mindist=100, maxcenterdist=20, maxangle=15):
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
                i = (i + 1) % n
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
                        #print(f"{self}: straight line {prev} to {i}, {prevd:.2f}/{pd:.2f}, {prevd - pd:.2f} {(prevd - pd)/pd:.5f}??")
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
    def cleanup_edges(self, qtree, maxdist=75):
        i = 0
        n = len(self.points)
        while i < n:
            p0 = self.points[i]
            p1 = self.points[(i + 1) % n]
            ll = p0.distance(p1)
            c = centroid([p0, p1])
            candidates = []
            for pt in qtree.all_near(c, ll/1.8):
                if self not in pt.regions and self.overlap(pt.regions):
                    ld = pt.distance_line(p0, p1)
                    if ld < min(ll/2, maxdist):
                        d0 = pt.distance(p0)
                        if ld < d0 and ld < pt.distance(p1) and abs(angle(p0, pt, p1)) < 35:
                            candidates.append((d0, pt))

            if len(candidates) > 0:
                pt = sorted(candidates)[0][1]
                pt.regions.add(self)
                self.points.insert(i+1, pt)
                n += 1

            i += 1

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
            if add_verticals and angle(p1, p2, p3) > 35:
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
        for i, p in enumerate(self.points):
            if self not in p[2]:
                print("BAD POINT", self, i, p)
                for j, q in enumerate(self.points):
                    print(j, q)
                raise Exception("bad point")
            if p in self.points[i+1:]:
                print("duplicate", i, len(self.points), self, p, self.points[i+1:].index(p))

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
            print(f"    {i:4}: {p1.distance(p2):6.1f}, {bearing(p1, p2):5.1f}, {angle(p0, p1, p2):5.1f}, {p1}")

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "R[%d,%s,%s-%s,%d]" % (self.index, self.airspace.id, self.ht(self.lower), self.ht(self.upper), len(self.points))

#
# load and pre-process all the listed airspaces
#

area_number = 0

def load_airspaces(airports):
    shp = shapefile.Reader(settings.nasr_shape_path)
    names = [field[0] for field in shp.fields]
    id_index = names.index('DeletionFlag')
    ident_index = names.index('IDENT')
    type_code_index = names.index('TYPE_CODE')
    lower_desc_index = names.index('LOWER_DESC')
    upper_desc_index = names.index('UPPER_DESC')
    lower_uom_index = names.index('LOWER_UOM')

    # organize all shapes into airspaces
    airspaces = {}
    type_codes = set()
    for f in shp.shapeRecords():
        id = f.record[id_index]
        #if id == '':
        #    type_codes.add(f.record[type_code_index])
        #    continue
        if f.shape.points[0] != f.shape.points[-1]:
            #print("shape not closed")
            continue
        if len(id) == 0:
            global area_number
            area_number = area_number + 1
            id = "A%04d" % (area_number)
        elif len(id) == 3:
            id = "K" + id

        # limit airports that are processed
        if airports is not None and id not in airports:
            continue

        # print parameters for debugging
        if False and airports is not None:
            for i, name in enumerate(names):
                if i < len(f.record):
                    print(id, name, i, f.record[i])

        # get relevant parameters
        ident = f.record[ident_index]
        type_code = f.record[type_code_index]
        type_codes.add(type_code)
        lower = util.f2m * abs(float(f.record[lower_desc_index]))
        upper = util.f2m * abs(float(f.record[upper_desc_index]))
        if type_code.startswith('CLASS_E'):
            if not airspace_class_E:
                continue
            id = f"{id}-E"
            type_code = 'CLASS_E'
        if type_code not in ('CLASS_A', 'CLASS_B', 'CLASS_C', 'CLASS_D', 'CLASS_E'):
            print("bad typecode", id, type_code)
            continue
        if lower == 0 and f.record[lower_uom_index] == 'SFC':
            lower = util.SFC


        # create airspace (if needed)
        if id not in airspaces:
            airspaces[id] = Airspace(id, ident, type_code)
        airspace = airspaces[id]

        # create points
        points = [Point(*lonlat) for lonlat in f.shape.points[:-1]]

        # create region
        region = Region(airspace, lower, upper, points)
        airspace.add_region(region)
    return airspaces

geometricErrors = {
    'A': 10000,
    'B': 5000,
    'C': 4000,
    'D': 3000,
    'E': 2000,
    'G': 10000,
}
airspaceHeights = {
    'A': 100000,
    'B': 100000,
    'C': 80000,
    'D': 30000,
    'E': 20000,
    'G': 100000,
}

def generate_overlapping_airspaces(airspaces):
    # first basic cleanup
    for airspace in airspaces:
        airspace.cleanup()

    print("generate_overlapping_airspaces", airspaces)

    # insert all points into the quad tree
    # points that are close together will be grouped
    if True and len(airspaces) > 1:
        qtree = QuadTree()
        for airspace in airspaces:
            for region in airspace.regions:
                for i, pt in enumerate(region.points):
                    region.points[i] = qtree.insert_grouped(Point(pt.lon, pt.lat, {region}), dist=60)

        # merge nearby edges
        if True:
            for airspace in airspaces:
                for region in airspace.regions:
                    region.cleanup_edges(qtree)

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

    # REMIND: cleanup self intersection
    # REMIND: exclude higher class airspaces
    # REMIND: KPAO, KNUQ

    # create directory
    dst_dir = os.path.join(settings.www_dir, "airspaces")
    if not os.path.exists(dst_dir):
        os.mkdir(dst_dir)

    # output as a 3D object
    t = tiler.Tiler()
    for airspace in airspaces:
        if False:
            print("airspace", airspace)
            for r in airspace.regions:
                print("region", r)
                for p in r.points:
                    print("point", p)
                r.check()

        g = gltf.GLTF()
        airspace.draw(t, g)
        extras = {
            'id': airspace.id,
            'class': airspace.type_class,
            'height': airspaceHeights[airspace.type_class],
        }
        geometricError = geometricErrors[airspace.type_class]

        t.save_tile(dst_dir, airspace.id, g, geometricError, extras)
        print("saved", dst_dir, airspace.id)

def generate_airspaces(airports):
    print("generate_airspaces", airports)
    airspaces = load_airspaces(airports)

    if False:
        for airspace in airspaces.values():
            airspace.dump()

    # generate in batches of overlapping airspaces
    remaining = set(airspaces.values())
    while len(remaining) > 0:
        airspace = next(iter(remaining))
        remaining.remove(airspace)
        overlapping = {airspace}
        bbox = airspace.bbox
        updated = True
        while updated:
            updated = False
            for airspace in remaining:
                if util.bbox_overlap(bbox, airspace.bbox):
                    bbox = util.bbox_union(bbox, airspace.bbox)
                    overlapping.add(airspace)
                    updated = True
            remaining = remaining.difference(overlapping)
        generate_overlapping_airspaces(overlapping)

if __name__ == "__main__":
    generate_airspaces(airports)

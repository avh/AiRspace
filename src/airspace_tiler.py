# (c)2019, Arthur van Hoff

import shapefile, pyproj, affine, math, os, sys, shapely.geometry, panda3d.core
import settings, util, tiler, gltf

# moffet overlapping palo alto
# out of memory for NY sectional
# package up more easily
# class E

add_floors = True
add_ceilings = False
add_borders = True
remove_interior_walls = True
combine_points = True
cleanup_airspace_regions = True
airspace_cleanup = True
airspace_intersect = True
airspace_check = True
airports = None
airports = {'KSJC', 'KRHV', 'KPAO', 'KSQL', 'KOAK', 'KHWD', 'KSFO', 'KNUQ'}
#airports = {'KOAK', 'KSFO'}
#airports = {'KPAO', 'KNUQ'}

black = (0, 0, 0, 1)
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
    line_colors[k] = (v[0]/2, v[1]/2, v[2]/2, line_alpha)


#
# LonLatHash:
#
# A hash table to map quantized map coordinates.
#
# Each lonlat is reduced to a quantized coordinate,
# which is then mapped to a tuple (lon, lat, set).
#
# The set is modified to contains all features intersecting
# at that coordinate.
#
# Line intersections are computed in lonlat space, which is
# not correct, but close enough.
#

class LonLatHash:
    def __init__(self):
        self.lonlats = {}

    def get_point(self, lonlat, debug=None):
        if lonlat in self.lonlats:
            p = self.lonlats[lonlat]
        else:
            if debug is None:
                p = (*lonlat, set())
            else:
                p = (*lonlat, set(), debug)
            self.lonlats[lonlat] = p
        return p

    def get_poly_points(self, poly, debug=None):
        coords = poly.exterior.coords
        if len(coords) == 0:
            print("EMPTY POLY", poly)
            return []
        if coords[0] != coords[-1]:
            print("OPEN POLY", poly)
        else:
            coords = coords[:-1]
        return [self.get_point(coords[i-1], debug) for i in range(len(coords), 0, -1)]

    def sfc_elevation(self, lonlat, h):
        return 0 if h == util.SFC else h

    def d2m(self, d):
        return 2 * settings.earth_radius * math.tan(0.5*util.d2r*d)

    def distance(self, p1, p2, maxdist=10):
        d = util.distance_xy(p1, p2)
        return util.FAR if d > maxdist else self.d2m(d)

    def distance_line(self, l1, l2, p, maxdist=10):
        d = util.distance_line_xy(l1, l2, p)
        return util.FAR if d > maxdist else self.d2m(d)

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
    def __init__(self, lonlats, id, ident, type_code):
        super().__init__()
        self.lonlats = lonlats
        self.id = id
        self.ident = ident
        self.type_code = type_code
        self.type_class = type_code[6:]
        self.regions = []
        self.points = {}
        self.bbox = util.bbox_init()

    def add_region(self, region):
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
                    if len(p2) > 0:
                        for p in p1:
                            self.add_region(Region(self, r1.lower, r1.upper, self.lonlats.get_poly_points(p, 'I1')))
                        for p in p2:
                            self.add_region(Region(self, min(r1.lower, r2.lower), max(r1.upper, r2.upper), self.lonlats.get_poly_points(p, 'I2')))
                        for p in p3:
                            self.add_region(Region(self, r2.lower, r2.upper, self.lonlats.get_poly_points(p, 'I3')))


                        r2.clear()
                        j = j - 1
                        del self.regions[j]
                        r1.clear()
                        i = i - 1
                        del self.regions[i]
                        updated = True
                        break
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
                    if len(p2) > 0:
                        for p in p1:
                            self.add_region(Region(self, r1.lower, r1.upper, self.lonlats.get_poly_points(p, 'S1')))
                        for p in p2:
                            self.add_region(Region(self, r1.lower, r2.lower, self.lonlats.get_poly_points(p, 'S2')))
                        r1.clear()
                        i = i - 1
                        del self.regions[i]
                        updated = True
                        break
        return updated

    def cleanup(self):
        for region in self.regions:
            region.cleanup()

    def draw(self, t, gltf):
        for region in self.regions:
            region.draw(t, gltf)

    def check(self):
        for region in self.regions:
            region.check()

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "A[%d,%s,%d]" % (self.index, self.id, len(self.regions))

#
# Region (an area on the map, bounded by a list of points, with a lower and upper elevation)
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

    def replace(self, oldpt, newpt):
        oldpt[2].remove(self)
        newpt[2].add(self)
        for i in range(len(self.points)):
            if self.points[i] == oldpt:
                self.points[i] = newpt
            i += 1

    def cleanup(self):
        i = 0
        while i < len(self.points):
            if self.points[i] == self.points[(i+1) % len(self.points)]:
                del self.points[i]
            else:
                i += 1

    def clear(self):
        for point in self.points:
            point[2].discard(self)
        self.points = []
        self.polygon = None
        self.bbox = util.bbox_init()

    def combine(self, other):
        if self == other:
            raise Exception("combine with self")
        #print("combine", self, other)
        for point in self.points:
            if other not in point[2]:
                other.combine_point(point)

    def combine_point(self, point):
        n = len(self.points)
        besti = -1
        bestd = util.FAR
        for i in range(n):
            if point == self.points[i]:
                return
            d = self.airspace.lonlats.distance(self.points[i], point)
            if d < bestd:
                besti = i
                bestd = d

        if besti >= 0 and bestd < 50:
            #print("MATCH POINT", self, besti, bestd, point, self.points[besti])
            oldpoint = self.points[besti]
            for r in oldpoint[2].copy():
                r.replace(oldpoint, point)
            return

        besti = -1
        bestd = util.FAR
        for i in range(n):
            d = self.airspace.lonlats.distance_line(self.points[i], self.points[(i+1) % n], point)
            if d < bestd:
                besti = i
                bestd = d

        if besti >= 0 and bestd < 35:
            #print("in_between", self.points[besti][:2], self.points[(besti+1) % n][:2], point[:2], bestd)
            point[2].add(self)
            self.points.insert(besti+1, point)
            return True

        return False

    def get_polygon(self):
        if self.polygon is None:
            self.polygon = shapely.geometry.Polygon([p[0:2] for p in self.points])
            if not self.polygon.is_valid:
                raise Exception("invalid poligon")
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
        n = len(self.points)
        for i in range(n):
            self.draw_wall(t, g, i, self.points[i], self.points[(i+1) % n], lines)
        g.add_mesh(g.add_rgba(wall_colors[self.airspace.type_class]))

        if add_borders and len(lines) > 0:
            for p1,p2 in lines:
                g.add_line(p1, p2)
            g.add_mesh(g.add_rgba(line_colors[self.airspace.type_class]))

    def draw_wall(self, t, g, index, p1, p2, lines):
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
            self.draw_wall_panel(t, g, index, p1, p2, *p, lines)

    def draw_wall_panel(self, t, g, index, p1, p2, h1, h2, lines):
        if h1 < h2:
            if p1[0] == p2[0] and p1[1] == p2[1]:
                print("bad panel, zero length", self, p1, p2, h1, h2)
                return
            if h1 >= h2:
                print("bad panel, invalid height", self, p1, p2, h1, h2)
                return
            v1 = t.lla2xyz((p1[0], p1[1], self.airspace.lonlats.sfc_elevation(p1, h1)))
            v2 = t.lla2xyz((p2[0], p2[1], self.airspace.lonlats.sfc_elevation(p2, h1)))
            v3 = t.lla2xyz((p2[0], p2[1], h2))
            v4 = t.lla2xyz((p1[0], p1[1], h2))
            g.add_quad(v1, v2, v3, v4)
            lines.append((v1, v2))
            lines.append((v3, v4))

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
                print("duplicate", i, len(self.points), self, p, self.points[i+1:].index(p), self.points[i+1])

    def ht(self, h):
        return "SFC" if h == util.SFC else "%d" % (int(round(h * util.m2f)))

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "R[%d,%s,%s-%s,%d]" % (self.index, self.airspace.id, self.ht(self.lower), self.ht(self.upper), len(self.points))

#
# load and pre-process all the listed airspaces
#

area_number = 0

def load_airspaces(lonlats):
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
        lower = util.f2m * abs(float(f.record[lower_desc_index]))
        upper = util.f2m * abs(float(f.record[upper_desc_index]))
        if lower == 0 and f.record[lower_uom_index] == 'SFC':
            lower = util.SFC

        type_codes.add(type_code)

        # create airspace (if needed)
        if id not in airspaces:
            airspaces[id] = Airspace(lonlats, id, ident, type_code)
        airspace = airspaces[id]

        # create points
        points = []
        for lonlat in f.shape.points[:-1]:
            points.append(lonlats.get_point(lonlat))

        # create region
        region = Region(airspace, lower, upper, points)
        airspace.add_region(region)

    print("TYPE_CODES", type_codes)

    # select area airspaces and regions
    regions = []
    for airspace in airspaces.values():
        if airspace.type_class < 'E':
            regions.extend(airspace.regions)
    print("found", len(regions), "regions for", len(airspaces), "airspaces")

    # check airspaces
    if airspace_check:
        for a in airspaces.values():
            a.check()

    # combine shared points
    if combine_points:
        print("combining points")
        for i in range(len(regions)-1):
            for j in range(i+1, len(regions)):
                if util.bbox_overlap(regions[i].bbox, regions[j].bbox):
                    regions[i].combine(regions[j])
                    regions[j].combine(regions[i])

    # cleanup airspace regions
    if cleanup_airspace_regions:
        print("cleanup airspace regions")
        for airspace in airspaces.values():
            airspace.cleanup()

    # check airspaces
    if airspace_check:
        for a in airspaces.values():
            a.check()

    # cleanup self intersection
    if airspace_cleanup:
        print("cleanup airspaces")
        for a1 in airspaces.values():
            if a1.type_class < 'E' and a1.cleanup_self_intersection():
                print("airspace", a1, "required cleanup")

    # exclude higher class airspaces
    if airspace_intersect:
        print("cleanup intersecting airspaces")
        for a1 in airspaces.values():
            if a1.type_class < 'E':
                for a2 in airspaces.values():
                    if a1 != a2 and a2.type_class < 'E' and a1.type_code > a2.type_code and util.bbox_overlap(a1.bbox, a2.bbox):
                        print("intersect", a1, a2)
                        if a1.subtract_airspace(a2):
                            print("airspace", a1, "intersected by", a2)
    if 'KPAO' in airspaces and 'KNUQ' in airspaces:
        print("fixing KNUQ and KPAO intersection")
        airspaces['KNUQ'].subtract_airspace(airspaces['KPAO'])

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

def generate_airspaces():
    lonlats = LonLatHash()
    airspaces = load_airspaces(lonlats)
    dst_dir = os.path.join(settings.www_dir, "airspaces")
    if not os.path.exists(dst_dir):
        os.mkdir(dst_dir)

    t = tiler.Tiler()
    for airspace in airspaces.values():
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


if __name__ == "__main__":
    generate_airspaces()

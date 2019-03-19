# (c)2019, Arthur van Hoff

import shapefile, pyproj, affine, math, os, sys, shapely.geometry, panda3d.core
import settings, objfmt, elevation, chart_proj, util

# SFC
# moffet overlapping palo alto
# out of memory for NY sectional
# package up more easily
# class E

add_floors = True
add_ceilings = False
add_pillars = False
map_scale = (0.0001, 0.0001, 0.0001)
remove_interior_walls = True
surface_outside = True
combine_points = True
airspace_cleanup = True
airspace_intersect = True
airports = None
#airports = {'KNUQ', 'KPAO'}
#chart_name = "San Francisco TAC"
#chart_name = "Los Angeles TAC"
#chart_name = "San Francisco SECTIONAL"
#chart_name = "Los Angeles SECTIONAL"
#chart_name = "New York TAC"
#chart_name = "New York SECTIONAL"
chart_names = [
    #"Los Angeles SECTIONAL",
    #"Los Angeles TAC",
    "San Francisco TAC",
]

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
    def __init__(self, chart, id, ident, type_code):
        super().__init__()
        self.chart = chart
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
                        print("found intersection", r1, r2)

                        for p in p1:
                            self.add_region(Region(self, r1.lower, r1.upper, self.chart.get_poly_points(p, 'I1')))
                        for p in p2:
                            self.add_region(Region(self, min(r1.lower, r2.lower), max(r1.upper, r2.upper), self.chart.get_poly_points(p, 'I2')))
                        for p in p3:
                            self.add_region(Region(self, r2.lower, r2.upper, self.chart.get_poly_points(p, 'I3')))

                        self.check()

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
                            self.add_region(Region(self, r1.lower, r1.upper, self.chart.get_poly_points(p, 'S1')))
                        for p in p2:
                            self.add_region(Region(self, r1.lower, r2.lower, self.chart.get_poly_points(p, 'S2')))
                        r1.clear()
                        i = i - 1
                        del self.regions[i]
                        updated = True
                        break
        return updated

    def draw(self, out):
        out.mtllib(os.path.join(settings.charts_dir, "airspace.mtl"))
        out.newline()
        if True:
            out.comment("airspace %s" % (self))
            for region in self.regions:
                out.comment("region %s%s" % (region, "" if len(region.points) > 0 else ", skipped"))
            out.newline()

        for region in self.regions:
            region.draw(out)

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
                if self.points[(i+1) % len(self.points)] == newpt:
                    del self.points[i]
                elif self.points[(i-1) % len(self.points)] == newpt:
                    del self.points[i]
                else:
                    self.points[i] = newpt
                return

    def clear(self):
        #print("clear", self, len(self.points))
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
            d = util.distance_xy(self.points[i], point)
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
            d = util.distance_line_xy(self.points[i], self.points[(i+1) % n], point)
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
        return self.polygon

    def draw(self, out):
        if len(self.points) == 0:
            return

        out.comment("region %s" % (self))
        out.usemtl(self.airspace.type_code.replace(' ', '_'))
        self.draw_walls(out)
        out.newline()

        # floors
        if add_floors and self.airspace.type_class < 'E' and self.lower > chart_proj.SFC:
            out.comment("floor %s" % (self))
            off = out.v_index
            t = panda3d.core.Triangulator()
            for p in self.points:
                t.addVertex(p[0], p[1])
                out.v((p[0], self.lower, p[1]))
            for i in range(len(self.points)):
                t.addPolygonVertex(i)
            t.triangulate()
            for i in range(t.getNumTriangles()):
                if surface_outside:
                    out.f_v(off + t.getTriangleV0(i), off + t.getTriangleV2(i), off + t.getTriangleV1(i))
                else:
                    out.f_v(off + t.getTriangleV0(i), off + t.getTriangleV1(i), off + t.getTriangleV2(i))
            out.newline()

        # ceilings
        if add_ceilings and self.type_class < 'E':
            out.comment("ceiling %s" % (self))
            off = out.v_index
            t = panda3d.core.Triangulator()
            for p in self.points:
                t.addVertex(p[0], p[1])
                out.v((p[0], self.upper, p[1]))
            for i in range(len(self.points)):
                t.addPolygonVertex(i)
            t.triangulate()
            for i in range(t.getNumTriangles()):
                if surface_outside:
                    out.f_v(off + t.getTriangleV0(i), off + t.getTriangleV2(i), off + t.getTriangleV1(i))
                else:
                    out.f_v(off + t.getTriangleV0(i), off + t.getTriangleV1(i), off + t.getTriangleV2(i))
            out.newline()

        # debugging
        if add_pillars:
            out.comment("debug %s" % (self))
            out.pillar(self.points[0], h1=0, h2=85, r=100, color='GREEN')
            out.pillar(self.points[-1], h1=0, h2=75, r=110, color='RED')
            for i, point in enumerate(self.points):
                out.pillar(point, h1=-50, h2=100, r=50, color='YELLOW')
                if len(point[2]) > 1:
                    out.pillar(point, h1=0, h2=100 + len(point[2])*100, r=75, color='BLUE')
            out.newline()

    def draw_walls(self, out):
        n = len(self.points)
        for i in range(n):
            self.draw_wall(out, i, self.points[i], self.points[(i+1) % n])

    def draw_wall(self, out, index, p1, p2):
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
            self.draw_wall_panel(out, index, p1, p2, *p)

    def draw_wall_panel(self, out, index, p1, p2, h1, h2):
        if h1 < h2:
            v = out.v_index
            if True:
                out.comment("distance=%f, index=%d/%d, h1=%f, h2=%f" % (util.distance_xy(p1, p2), index, len(self.points), h1, h2))
                if len(p1) == 4:
                    out.comment("p1 NOTE %s" % (p1[3]))
                for f in p1[2]:
                    out.comment("p1 %s%s" % (f, ", self" if f == self else ""))
                if len(p2) == 4:
                    out.comment("p2 NOTE %s" % (p2[3]))
                for f in p2[2]:
                    out.comment("p2 %s%s" % (f, ", self" if f == self else ""))
            if p1[0] == p2[0] and p1[1] == p2[1]:
                out.comment("bad panel, zero length")
                print("bad panel", self, p1, p2, h1, h2)
                return
            if h1 >= h2:
                out.comment("bad panel (height)")
                print("bad panel", self, p1, p2, h1, h2)
                return
            out.v((p1[0], self.airspace.chart.sfc_elevation(p1, h1), p1[1]))
            out.v((p2[0], self.airspace.chart.sfc_elevation(p2, h1), p2[1]))
            out.v((p2[0], h2, p2[1]))
            out.v((p1[0], h2, p1[1]))
            if surface_outside:
                out.f_v(v, v+3, v+2, v+1)
            else:
                out.f_v(v, v+1, v+2, v+3)

    def hilite(self, out, color='RED'):
        out.comment("hilite %s" % (self))
        out.usemtl(color)
        for i in range(len(self.points)):
            p1 = self.points[i]
            p2 = self.points[(i+1) % len(self.points)]
            self.draw_wall_panel(out, i, p1, p2, self.lower, self.upper)

    def connects(self, p1, p2):
        if self not in p1[2] or self not in p2[2]:
            return False
        i = self.points.index(p1)
        j = self.points.index(p2)
        return ((i+1) % len(self.points)) == j or ((j+1) % len(self.points)) == i

    def check(self):
        for i, p in enumerate(self.points):
            if self not in p[2]:
                print(self, p)
                raise Exception("bad point")
            if p in self.points[i+1:]:
                print("duplicate", self, p)

    def ht(self, h):
        return "SFC" if h == chart_proj.SFC else "%d" % (int(round(h * util.m2f)))

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "R[%d,%s,%s-%s,%d]" % (self.index, self.airspace.id, self.ht(self.lower), self.ht(self.upper), len(self.points))

#
# load and pre-process all the airspaces
# associated with a chart
#

area_number = 0

def load_chart_airspaces(chart):
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
            print("shape not closed")
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
            lower = chart_proj.SFC

        type_codes.add(type_code)

        # create airspace (if needed)
        if id not in airspaces:
            airspaces[id] = Airspace(chart, id, ident, type_code)
        airspace = airspaces[id]

        # create points
        points = []
        for lonlat in f.shape.points[:-1]:
            xy = chart.lonlat2xy(lonlat)
            points.append(chart.get_point((int(xy[0]), int(xy[1]))))

        # create region
        region = Region(airspace, lower, upper, points)
        airspace.add_region(region)

    print("TYPE_CODES", type_codes)

    # select area airspaces and regions
    chart_airspaces = []
    chart_regions = []
    for airspace in airspaces.values():
        if util.bbox_overlap(chart.bbox, airspace.bbox):
            chart_airspaces.append(airspace)
            if airspace.type_class < 'E':
                chart_regions.extend(airspace.regions)
    print("found", len(chart_airspaces), "airspaces out of ", len(airspaces))

    # combine shared points
    if combine_points:
        print("combining points")
        for i in range(len(chart_regions)-1):
            for j in range(i+1, len(chart_regions)):
                if util.bbox_overlap(chart_regions[i].bbox, chart_regions[j].bbox):
                    chart_regions[i].combine(chart_regions[j])
                    chart_regions[j].combine(chart_regions[i])

    # cleanup self intersection
    if airspace_cleanup:
        print("cleanup airspaces")
        for a1 in chart_airspaces:
            if a1.type_class < 'E' and a1.cleanup_self_intersection():
                print("airspace", a1, "required cleanup")

    # exclude higher class airspaces
    if airspace_intersect:
        print("cleanup intersecting airspaces")
        for a1 in chart_airspaces:
            if a1.type_class < 'E':
                for a2 in chart_airspaces:
                    if a1 != a2 and a2.type_class < 'E' and a1.type_code > a2.type_code and util.bbox_overlap(a1.bbox, a2.bbox):
                        if a1.subtract_airspace(a2):
                            print("airspace", a1, "intersected by", a2)
    if airspaces['KPAO'] in chart_airspaces and airspaces['KNUQ'] in chart_airspaces:
        print("fixing KNUQ and KPAO intersection")
        airspaces['KNUQ'].subtract_airspace(airspaces['KPAO'])

    return chart_airspaces

def generate_chart_airspaces(chart_name):
    chart = chart_proj.Chart(chart_name)
    chart_airspaces = load_chart_airspaces(chart)
    dst_dir = os.path.join(settings.data_dir, chart.name.replace(' ', '_'))
    if not os.path.exists(dst_dir):
        os.mkdir(dst_dir)

    # save chart (if necessary)
    chart_path = os.path.join(dst_dir, "chart.obj")
    if not os.path.exists(chart_path):
        with objfmt.create(chart_path) as out:
            out.scale = map_scale
            out.offset = (-chart.width/2, 0, -chart.height/2)
            chart.draw(out)
        print("saved", chart_path)

    # save area airspaces
    for airspace in chart_airspaces:
        airspace_path = os.path.join(dst_dir, airspace.type_class + "_" + airspace.id + ".obj")
        with objfmt.create(airspace_path) as out:
            out.scale = map_scale
            out.offset = (-chart.width/2, 0, -chart.height/2)
            airspace.draw(out)
        print("saved", airspace_path)

if __name__ == "__main__":
    for chart_name in chart_names:
        generate_chart_airspaces(chart_name)

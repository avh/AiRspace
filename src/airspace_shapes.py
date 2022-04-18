# (c)2019-2022, Artfahrt Inc. Arthur van Hoff

import shapefile, tiler, gltf, panda3d, panda3d.core, time, multiprocessing, os, shutil, traceback, shapely
import settings, util, combiner
from geometry import angle, bearing, centroid, Point, QuadTree

area_shapes_table = settings.db.hash_table("area_shapes")
airport_shapes_table = settings.db.hash_table("airport_shapes")
shp = None
x1_dir = settings.airports_dir + "-1x"
x5_dir = settings.airports_dir + "-5x"
t1 = tiler.Tiler(x1_dir, 1)
t5 = tiler.Tiler(x5_dir, 5)

add_floors = True
add_ceilings = False
add_borders = True
add_poles = True
add_verticals = True
remove_interior_walls = True
max_workers = 8
#airports = {'KHWD-D', 'KSFO-B', 'KRHV-D'}
#airports = {'KATL-B'}
airports = None

#
# colors
#

black = (0, 0, 0, 1)
red = (1, 0, 0, 1)
green = (0, 1, 0, 1)

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

def enumerate_segments(points, min_corner_angle=settings.min_corner_angle):
    if abs(points[0].angle) < min_corner_angle:
        yield points + [points[0]]
    else:
        i, n = 0, len(points)
        for j in range(n):
            if abs(points[(j+1) % n].angle) >= min_corner_angle:
                yield points[i:j+1] + [points[(j+1) % n]]
                i = (j+1) % n

class Airspace:
    def __init__(self, table, id):
        self.id = id
        self.data = table.get(id)
        self.type_class = self.data['class']
        self.regions = []
        global shp
        if shp is None:
            shp = shapefile.Reader(settings.nasr_shape_path).shapeRecords()
        for i, region in enumerate(self.data['regions']):
            self.regions.append(Region(self, region['lower'][0], region['upper'][0], shp[region['id']].shape.points[:-1]))


    def cleanup(self):
        for region in self.regions:
            region.normalize_points()
            region.cleanup_points(settings.min_corner_angle, settings.min_line_length, settings.min_line_length/2)
            region.cleanup_straights(settings.min_corner_angle, settings.max_line_distance)

        qtree = QuadTree()
        for region in self.regions:
            region.merge_points(qtree, settings.min_point_distance)
        for region in self.regions:
            region.merge_lines(qtree, settings.max_line_distance)

        self.cleanup_self_intersections(qtree, settings.min_point_distance)
        if False and airports is not None and len(airports) == 1:
            self.dump()

    def cleanup_self_intersections(self, qtree, min_point_distance):
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
                        #print(f"self intersect {r1} {r2}")
                        if util.not_empty(p1):
                            for p in p1:
                                r = Region(self, r1.lower, r1.upper, [(c[0], c[1]) for c in p.exterior.coords])
                                r.cleanup_points(settings.min_corner_angle, settings.min_line_length, settings.min_line_length/2)
                                r.merge_points(qtree, min_point_distance)
                                self.regions.append(r)
                        for p in p2:
                            r = Region(self, min(r1.lower, r2.lower), max(r1.upper, r2.upper), [(c[0], c[1]) for c in p.exterior.coords])
                            r.cleanup_points(settings.min_corner_angle, settings.min_line_length, settings.min_line_length/2)
                            r.merge_points(qtree, min_point_distance)
                            self.regions.append(r)
                        if util.not_empty(p3):
                            for p in p3:
                                r = Region(self, r2.lower, r2.upper, [(c[0], c[1]) for c in p.exterior.coords])
                                r.cleanup_points(settings.min_corner_angle, settings.min_line_length, settings.min_line_length/2)
                                r.merge_points(qtree, min_point_distance)
                                self.regions.append(r)

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
            if True:
                for region in self.regions:
                    region.merge_lines(qtree, min_point_distance)

    def draw(self, t, gltf):
        for region in self.regions:
            region.draw(t, gltf)

    def save(self):
        if len(self.regions) == 0:
            print("warning: no regions for {self}")
            return
        g1 = gltf.GLTF()
        self.draw(t1, g1)
        g5 = gltf.GLTF()
        self.draw(t5, g5)
        extras = {
            'id': self.id,
            'class': self.type_class,
            'height': settings.defaultHeight[self.type_class],
            "flyto": True,
        }
        geometricError = settings.defaultGeometricError[self.type_class]
        t1.save_tile(self.id, g1, geometricError, extras)
        t5.save_tile(self.id, g5, geometricError, extras)

    def dump(self, pts=True):
        print(self)
        for region in self.regions:
            region.dump(pts=pts)

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"A[{self.id},{len(self.regions)}]"

class Region:
    count = 0

    def __init__(self, airspace, lower, upper, points):
        self.id = Region.count
        Region.count += 1

        self.airspace = airspace
        self.lower = lower
        self.upper = upper
        self.polygon = None

        # eliminate duplicates
        self.points = [Point(*pt, {self}) for i, pt in enumerate(points) if pt != points[(i+1) % len(points)]]
        assert len(self.points) > 2, f"{self}: too few points, {len(self.points)}"

        # compute bbox and angle for each point
        bbox = util.bbox_init()
        for p0, p1, p2 in util.enumerate_triples(self.points):
            p1.angle = angle(p0, p1, p2)
            bbox = util.bbox_add(bbox, p1)
        self.bbox = bbox

    #
    # get the polygon for this region
    #
    def get_polygon(self):
        if self.polygon is None:
            self.polygon = shapely.geometry.Polygon([(p.lon, p.lat) for p in self.points])
            if not self.polygon.is_valid:
                self.polygon = self.polygon.buffer(0)
            if not self.polygon.is_valid:
                self.dump()
                assert self.polygon.is_valid
        return self.polygon

    #
    # normalize points
    #
    def normalize_points(self):
        # ensure clockwise winding
        if sum([pt.angle for pt in self.points]) < 0:
            #print("REVERSING", self, sum([pt.angle for pt in self.points]))
            self.points = list(reversed(self.points))
            for p in self.points:
                p.angle = -p.angle

        # pick best corner to start
        candidates = sorted([(pt.angle, i, pt) for i, pt in enumerate(self.points) if abs(pt.angle) > settings.min_corner_angle], reverse=True)
        if len(candidates) == 0:
            candidates = sorted([(pt.lat, pt.lon, i) for i, pt in enumerate(self.points)])
        else:
            candidates = sorted([(pt.lat, pt.lon, i) for _, i, pt in candidates])
        i = candidates[0][2]

        self.points = self.points[i:] + self.points[:i]
        self.polygon = None

    #
    # Delete duplicate points.
    # Delete points that are too close together.
    #
    def cleanup_points(self, min_corner_angle, min_line_length, max_line_distance):
        pcount = 0
        p0 = self.points[-1]
        p1 = self.points[0]
        i = 0
        n = len(self.points)
        eliminated = []
        while i < n:
            p2 = self.points[(i+1) % n]
            if abs(p0.angle) < min_corner_angle and p0.distance(p1) < min_line_length and max(pt.distance_line(p0, p2) for pt in eliminated + [p1]) < max_line_distance:
                del self.points[i]
                eliminated.append(p1)
                p1 = p2
                n -= 1
                pcount += 1
            else:
                eliminated = []
                p0 = p1
                p1 = p2
                i += 1
        if pcount > 0:
            print(f"eliminated {pcount} points from {self}")
            self.polygon = None
            for p0, p1, p2 in util.enumerate_triples(self.points):
                p1.angle = angle(p0, p1, p2)

    #
    # Eliminate any intermediary points for straights
    #
    def cleanup_straights(self, min_corner_angle, max_line_distance):
        min_corner_angle = settings.min_corner_angle_override.get(self.airspace.id, min_corner_angle)
        max_line_distance = settings.max_line_distance_override.get(self.airspace.id, max_line_distance)
        scount, pcount = 0, 0
        points = []
        for segment in enumerate_segments(self.points, min_corner_angle):
            if len(segment) > 2:
                maxd = max(pt.distance_line(segment[0], segment[-1]) for pt in segment[1:-1])
                if maxd < max_line_distance:
                    #print("STRAIGHT", self, maxd, len(segment), segment[0], segment[-1])
                    scount += 1
                    pcount += len(segment)-2
                    points.append(segment[0])
                    continue
                #print("not straight", self, maxd, len(segment), segment[0], segment[-1])
            points.extend(segment[:-1])
        self.points = points
        if scount > 0:
            print(f"eliminated {scount} straights ({pcount} points) from {self}")
            self.polygon = None
            for p0, p1, p2 in util.enumerate_triples(self.points):
                p1.angle = angle(p0, p1, p2)

    #
    # Merge nearby points
    #
    def merge_points(self, qtree, min_point_distance):
        min_point_distance = settings.min_point_distance_override.get(self.airspace.id, min_point_distance)
        #self.points = [qtree.insert_grouped(pt, min_point_distance) for pt in self.points]
        for _, i in sorted([(pt.angle, i) for i, pt in enumerate(self.points)], reverse=True):
            self.points[i] = qtree.insert_grouped(self.points[i], min_point_distance)

    #
    # Merge nearby points into line segments
    #
    def merge_lines(self, qtree, max_line_distance):
        max_line_distance = settings.max_line_distance_override.get(self.airspace.id, max_line_distance)
        count = 0
        i = 0
        n = len(self.points)
        while i < n:
            p1 = self.points[i]
            p2 = self.points[(i+1) % n]
            c = centroid((p1, p2))
            ll = p1.distance(p2)
            candidates = []
            for pt in qtree.all_near(c, ll/1.8):
                if self not in pt.regions and self.vertical_overlap(pt.regions):
                    ld = pt.distance_line(p1, p2)
                    if ld < min(ll/2, max_line_distance):
                        d = pt.distance(p1)
                        if ld < d and ld < pt.distance(p2) and abs(angle(p1, pt, p2)) < 35:
                            candidates.append((d, pt))
            if len(candidates) > 0:
                pt = sorted(candidates)[0][1]
                pt.regions.add(self)
                self.points.insert(i+1, pt)
                n += 1
                count += 1
            i += 1

        if count > 0:
            self.polygon = None
            print(f"inserted {count} points in {self}")

    def vertical_overlap(self, regions):
        for reg in regions:
            if self.upper > reg.lower and self.lower < reg.upper:
                return True
        return False

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
            for p1,p2,grp,_ in poles:
                if grp:
                    g.add_line(p1, p2)
            g.add_mesh(g.add_rgba(red))
            for p1,p2,grp,multi in poles:
                if not grp and multi:
                    g.add_line(p1, p2)
            g.add_mesh(g.add_rgba(green))
            for p1,p2,grp,multi in poles:
                if not grp and not multi:
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
                poles.append((v1, v5, p1.group is not None, len(p1.regions) > 1))

    def connects(self, p1, p2):
        if self not in p1[2] or self not in p2[2]:
            return False
        i = self.points.index(p1)
        j = self.points.index(p2)
        return ((i+1) % len(self.points)) == j or ((j+1) % len(self.points)) == i

    def sfc_elevation(self, lonlat, h):
        return 0 if h == util.SFC else h

    def clear(self):
        for pt in self.points:
            pt.regions.discard(self)
        self.polygon = None

    def dump(self, pts=True):
        print(f"  {self}")
        if pts:
            for i,(p0,p1,p2) in enumerate(util.enumerate_triples(self.points)):
                print(f"{i:8}, {p1.index:5}, {p1.lon:11.7f}, {p1.lat:11.7f}, {p1.distance(p2):9.4f}, {p1.angle:9.4f}, {angle(p0,p1,p2):9.4f}, {bearing(p1,p2):9.4f}, {p1.regions}")

    def ht(self, h):
        return "SFC" if h == util.SFC else "%d" % (int(round(h * util.m2f/100)))

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"R[{self.id},{self.airspace.id},{self.ht(self.lower)}-{self.ht(self.upper)},{len(self.points)}]"


def group_airports():
    #clusters = [(set([a['id']]),a['bbox']) for a in airport_shapes_table.all() if a['id'].endswith('-B')]
    clusters = [(set([a['id']]),a['bbox']) for a in airport_shapes_table.all() if a['id']]

    i = 0
    while i < len(clusters):
        a, b = clusters[i]
        j = 0
        while j < len(clusters):
            if i != j and util.bbox_overlap(b, clusters[j][1]):
                if i > j:
                    i -= 1
                a.update(clusters[j][0])
                b = util.bbox_union(b, clusters[j][1])
                del clusters[j]
            else:
                j += 1
        if clusters[i] == (a, b):
            i += 1
        else:
            clusters[i] = (a, b)
    return [cluster[0] for cluster in clusters]
    #clusters = [sorted(list(c[0])) for c in clusters]
    #return sorted(clusters, key=lambda x: (len(x), x))

def process_cluster(q, table_name):
    table = settings.db.hash_table(table_name)
    while True:
        args = q.get()
        if args[0] == 'done':
            break

        try:
            airports = [Airspace(table, id) for id in args[1]]
            for airport in airports:
                print("processing", airport)
                tm = time.time()
                print("cleanup", airport)
                airport.cleanup()
                print("save", airport)
                airport.save()
                print(f"saved {airport.id} in {util.time_str(tm)}")
        except:
            print(f"exception: cluster failed, {airports}")
            traceback.print_exc()

def process_clusters(table_name, clusters, max_workers=max_workers):
    max_workers = min(len(clusters), max_workers)
    q = ctx.Queue(max_workers*2)
    processes = [ctx.Process(target=process_cluster, args=(q, table_name)) for _ in range(max_workers)]
    for p in processes:
        p.start()
    for cluster in clusters:
        q.put(('cluster', cluster))
    for _ in range(max_workers):
        q.put(('done',))
    for p in processes:
        p.join()

if __name__ == "__main__":
    ctx = multiprocessing.get_context('spawn')
    tm = time.time()

    if airports is None:
        if os.path.exists(x1_dir):
            shutil.rmtree(x1_dir)
        if os.path.exists(x5_dir):
            shutil.rmtree(x5_dir)

    if True:
        clusters = group_airports()
        if airports is not None:
            clusters = [cluster.intersection(airports) for cluster in clusters if not cluster.isdisjoint(airports)]
        print(f"processing {len(clusters)} clusters")
        process_clusters("airport_shapes", clusters)
    else:
        if False:
            ruby = area_shapes_table.get('A-RUBY-E5')
            print(ruby)
            os.exit(1)

        if False:
            for i, airspace in enumerate(area_shapes_table.all()):
                if airspace['class'] == 'E5':
                    print(i, airspace)
            os.exit(1)
        clusters = [{airspace['id']} for airspace in area_shapes_table.all() if airspace['class'] == 'E5']
        #clusters = [{'A-RUBY-E5'}]
        print(f"processing {len(clusters)} clusters")
        process_clusters("area_shapes", clusters)



    print(f"found {len(clusters)} clusters")

    combiner.combine_airports(settings.airports_dir + "-1x")
    combiner.combine_airports(settings.airports_dir + "-5x")
    print(f"done in {util.time_str(tm)}")

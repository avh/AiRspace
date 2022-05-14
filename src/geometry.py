import math
import settings, util

def centroid(points):
    lon, lat, n = 0, 0, 0
    for pt in points:
        lon += pt.lon
        lat += pt.lat
        n += 1
    return Point(lon/n, lat/n)

def weighted_centroid(points):
    lon, lat, n, a = 0, 0, 0, 0
    for pt in points:
        a = max(a, pt.angle)
        w = abs(pt.angle)/90 + 1
        lon += pt.lon * w
        lat += pt.lat * w
        n += w
    return Point(lon/n, lat/n), a

def bearing(p1, p2):
    #x = math.cos(p2.lat) * math.sin(p2.lon - p1.lon)
    #y = math.cos(p1.lat) * math.sin(p2.lat) - math.sin(p1.lat) * math.cos(p2.lat) * math.cos(p2.lon - p1.lon)
    #return math.fmod(math.atan2(x, y) * util.r2d + 360, 360)n
    lat1, lon1 = p1.lat * util.d2r, p1.lon * util.d2r
    lat2, lon2 = p2.lat * util.d2r, p2.lon * util.d2r
    y = math.sin(lon2 - lon1) * math.cos(lat1)
    x = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(lon2 - lon1)
    return math.fmod(math.atan2(x, y) * util.r2d + 360, 360)

def angle(p0, p1, p2):
    a = bearing(p1, p2) - bearing(p0, p1)
    if a < -180:
        a += 360
    if a > 180:
        a -= 360
    return a

    #v0x = p1.lon - p0.lon
    #v0y = p1.lat - p0.lat
    #v1x = p2.lon - p1.lon
    #v1y = p2.lat - p1.lat
    #return math.acos(((v0x*v1x)+(v0y*v1y)) / (math.sqrt(v0x*v0x + v0y*v0y) * math.sqrt(v1x*v1x + v1y*v1y))) * util.r2d

class Point:
    count = 0
    accuracy = 100000

    def __init__(self, lon=0, lat=0, regions=None, angle=0):
        Point.count += 1
        self.index = Point.count
        #self.lon = round(lon * Point.accuracy) / Point.accuracy
        #self.lat = round(lat * Point.accuracy) / Point.accuracy
        self.lon = lon
        self.lat = lat
        self.regions = regions or set()
        self.group = None
        self.angle = angle

    def is_grouped(self):
        return self.group is not None

    def all(self):
        yield self

    def distance(self, other):
        lat1 = self.lat * util.d2r
        lat2 = other.lat * util.d2r
        lat_d = (other.lat - self.lat) * util.d2r
        lon_d = (other.lon - self.lon) * util.d2r
        a = (math.sin(lat_d/2)**2) + math.cos(lat1) * math.cos(lat2) * (math.sin(lon_d/2)**2)
        return settings.earth_radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def distance_line(self, l1, l2):
        dx = l2.lon - l1.lon
        dy = l2.lat - l1.lat
        det = dx*dx + dy*dy
        if det == 0:
            return self.distance(l1)
        a = (dy*(self.lat - l1.lat) + dx*(self.lon - l1.lon))/det
        return self.distance(Point(l1.lon + a*dx, l1.lat + a*dy))

    def recenter(self):
        assert self.group is not None
        c, a = weighted_centroid(self.group)
        self.lon = c.lon
        self.lat = c.lat
        self.angle = a

    def __getitem__(self, i):
        if i == 0:
            return self.lon
        if i == 1:
            return self.lat
        if i == 2:
            return self.regions
        if isinstance(i, slice):
            if i.start == 0 and i.stop == 2:
                return (self.lon, self.lat)
        return None

    def __hash__(self):
        return (self.lon, self.lat).__hash__()

    def __eq__(self, other):
        return self.lon == other.lon and self.lat == other.lat

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f"P({self.index},{self.lon:.8f},{self.lat:.8f},{self.regions}{'' if self.group is None else ',grouped'})"

class QuadTree:
    maxleafs = 8

    def __init__(self):
        self.center = None
        self.children = []

    def insert(self, pt):
        if self.center is not None:
            if pt.lon < self.center.lon:
                if pt.lat < self.center.lat:
                    self.children[0].insert(pt)
                else:
                    self.children[1].insert(pt)
            else:
                if pt.lat < self.center.lat:
                    self.children[2].insert(pt)
                else:
                    self.children[3].insert(pt)
        elif len(self.children) == QuadTree.maxleafs:
            self.divide()
            self.insert(pt)
        else:
            self.children.append(pt)

    def remove(self, pt):
        if self.center is not None:
            if pt.lon < self.center.lon:
                if pt.lat < self.center.lat:
                    self.children[0].remove(pt)
                else:
                    self.children[1].remove(pt)
            else:
                if pt.lat < self.center.lat:
                    self.children[2].remove(pt)
                else:
                    self.children[3].remove(pt)
        elif pt in self.children:
            del self.children[self.children.index(pt)]
        else:
            assert False, f"point not found: {pt}"

    def insert_grouped(self, point, dist=25, allpoints=False):
        assert not point.is_grouped()
        assert len(point.regions) <= 1
        d = 2*math.atan2(dist, settings.earth_radius)*util.r2d
        bestpt = None
        bestdist = util.FAR
        for pt in self.all_bbox(point.lon - d, point.lat + d, point.lon + d, point.lat - d):
            if allpoints or pt.regions.isdisjoint(point.regions):
                dp = pt.distance(point)
                if dp < bestdist:
                    bestpt = pt
                    bestdist = dp

        if point is bestpt:
            return point
        if bestdist <= dist:
            # group these points
            if not bestpt.is_grouped():
                bestpt.group = [bestpt, point]
            else:
                bestpt.group.append(point)
            bestpt.regions.update(point.regions)
            self.remove(bestpt)
            bestpt.recenter()
            self.insert(bestpt)
            return bestpt

        self.insert(point)
        return point

    def get_poly_points(self, poly, reg, dist=5):
        coords = poly.exterior.coords
        assert len(coords) > 0, "empty polygon"
        if len(coords) == 0:
            print("EMPTY POLY", poly)
            return []
        if coords[0] != coords[-1]:
            print("OPEN POLY", poly)
        else:
            coords = coords[:-1]
        return [self.insert_grouped(Point(coords[i-1][0], coords[i-1][1], {reg})) for i in range(len(coords), 0, -1)]

    def divide(self):
        pts = self.children
        self.children = [QuadTree(), QuadTree(), QuadTree(), QuadTree()]
        self.center = centroid(pts)
        for pt in pts:
            self.insert(pt)

    def all(self):
        for child in self.children:
            yield from child.all()

    def all_bbox(self, left, top, right, bottom):
        if self.center is not None:
            if left < self.center.lon:
                if bottom < self.center.lat:
                    yield from self.children[0].all_bbox(left, top, right, bottom)
                if top >= self.center.lat:
                    yield from self.children[1].all_bbox(left, top, right, bottom)
            if right >= self.center.lon:
                if bottom < self.center.lat:
                    yield from self.children[2].all_bbox(left, top, right, bottom)
                if top >= self.center.lat:
                    yield from self.children[3].all_bbox(left, top, right, bottom)
        else:
            for pt in self.children:
                if pt.lon >= left and pt.lon <= right and pt.lat >= bottom and pt.lat <= top:
                    yield pt

    def all_near(self, point, m):
        d = 2*math.atan2(m, settings.earth_radius)*util.r2d
        for pt in self.all_bbox(point.lon - d, point.lat + d, point.lon + d, point.lat - d):
            if pt is not point and pt.distance(point) <= m:
                yield pt

    def all_bad_nodes(self, bbox=util.bbox_all()):
        if self.center is not None:
            yield from self.children[0].all_bad_nodes((bbox[0], bbox[1], self.center[0], self.center[1]))
            yield from self.children[1].all_bad_nodes((bbox[0], self.center[1], self.center[0], bbox[3]))
            yield from self.children[2].all_bad_nodes((self.center[0], bbox[1], bbox[2], self.center[1]))
            yield from self.children[3].all_bad_nodes((self.center[0], self.center[1], bbox[2], bbox[3]))
        else:
            for child in self.children:
                if not util.bbox_contains(bbox, child):
                    yield child, bbox

    def check_tree(self, bbox=util.bbox_init()):
        bad = list(self.all_bad_nodes())
        if len(bad) > 0:
            for pt, bbox in bad:
                print("bad", pt, bbox)
            #assert False

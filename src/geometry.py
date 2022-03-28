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
    x = math.cos(p2.lat) * math.sin(p2.lon - p1.lon)
    y = math.cos(p1.lat) * math.sin(p2.lat) - math.sin(p1.lat) * math.cos(p2.lat) * math.cos(p2.lon - p1.lon)
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

    def __init__(self, lon=0, lat=0, regions=None, angle=0):
        Point.count += 1
        self.index = Point.count
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
        det = det = dx*dx + dy*dy
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

    def __eq__(self, other):
        return self.lon == other.lon and self.lat == other.lat

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f"P({self.index},{self.lon:.8f},{self.lat:.8f},{self.regions}{'' if self.group is None else ',grouped'})"

class QuadTree:
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
        elif len(self.children) == 4:
            self.divide()
            self.insert(pt)
        else:
            self.children.append(pt)

    def insert_grouped(self, point, dist=25):
        assert not point.is_grouped()
        assert len(point.regions) <= 1
        d = 2*math.atan2(dist, settings.earth_radius)*util.r2d
        bestpt = None
        bestdist = util.FAR
        for pt in self.all_bbox(point.lon - d, point.lat + d, point.lon + d, point.lat - d):
            #if pt.regions.isdisjoint(point.regions):
            dp = pt.distance(point)
            if dp < bestdist:
                bestpt = pt
                bestdist = dp

        if point is bestpt:
            print("FOUND TWICE", point)
            return point
        if bestdist <= dist:
            # group these points
            if not bestpt.is_grouped():
                bestpt.group = [bestpt, point]
            else:
                bestpt.group.append(point)
            bestpt.regions.update(point.regions)
            bestpt.recenter()
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
            if pt != point and pt.distance(point) <= m:
                yield pt

#
# Delete any duplicate points.
# Delete any points that are too close together.
# Dont delete corners
#
def cleanup_points(reg, mindist=40, mincenterdist=1, maxangle=15):
    rc = 0
    i = 0
    c = 0
    n = len(reg.points)
    p0 = reg.points[-1]
    p1 = reg.points[0]
    p2 = reg.points[1]
    d01 = p0.distance(p1)
    d12 = p1.distance(p2)
    while c < n:
        if (p0.lon == p1.lon and p0.lat == p2.lat) or (p1.lon == p2.lon and p1.lat == p2.lat) or (d01 < mindist and d12 < mindist and p1.distance(Point((p0.lon + p2.lon)/2, (p0.lat + p2.lat)/2)) < mincenterdist and angle(p0, p1, p2) < maxangle):
            #print(f"delete {i}, {p0}, {p1}, {p2}")
            del reg.points[i]
            n -= 1
            p1 = p2
            p2 = reg.points[(i+1) % n]
            d01 = p0.distance(p1)
            d12 = p1.distance(p2)
            c = 0
            rc += 1
        else:
            i = (i + 1) % n
            p0 = p1
            p1 = p2
            p2 = reg.points[(i+1) % n]
            d01 = d12
            d12 = p1.distance(p2)
            c += 1
    if rc > 0:
        print(f"removed {rc} unnecessary points from {reg}")

def cleanup_straights(reg):
    prev = None
    prevd = 0
    i = 0
    c = 0
    n = len(reg.points)
    p0 = reg.points[-1]
    p1 = reg.points[0]
    p2 = reg.points[1]
    b01 = bearing(p0, p1)
    b12 = bearing(p1, p2)
    while c < 2*n:
        if abs(b12 - b01) > 15:
            if prev is not None and i != (prev + 1) % n:
                pp = reg.points[prev]
                pd = p1.distance(pp)
                if pd > 0 and (prevd - pd)/pd < 0.01:
                    print(f"{reg}: straight line {prev} to {i} {prevd:.2f}/{pd:.2f}, {prevd - pd:.2f} {(prevd - pd)/pd:.5f}??")
                    # knock out points inbetween
                    while (prev + 1) % n != i:
                        del reg.points[(prev + 1) % n]
                        n -= 1
                        if prev < i:
                            i -= 1
                        else:
                            prev = prev % n
            prev = i
            prevd = 0

        i = (i + 1) % n
        c += 1
        prevd += p1.distance(p2)
        p0 = p1
        p1 = p2
        p2 = reg.points[(i + 1) % n]
        b01 = b12
        b12 = bearing(p1, p2)



def cleanup_lines(qtree, reg, maxdist=25):
    i = 0
    n = len(reg.points)
    while i < n:
        p0 = reg.points[i]
        p1 = reg.points[(i+1) % n]
        ll = p0.distance(p1)
        c = centroid([p0, p1])
        for pt in qtree.all_near(c, ll/1.8):
            if reg not in pt.regions and pt.distance_line(p0, p1) < min(ll/2, maxdist):
                pt.regions.add(reg)
                reg.points.insert(i+1, pt)
                n += 1
                break
        i += 1

def corners(points, minangle=20):
    p0 = points[-1]
    p1 = points[0]
    p2 = points[1]
    n = len(points)
    for i in range(n):
        a = angle(p0, p1, p2)
        if a > minangle:
            yield (a, p1)
        p0 = p1
        p1 = p2
        p2 = points((i+2) % n)

if __name__ == "__main__":
    from airspace_tiler import load_airspaces
    airspaces = load_airspaces({'KMRY'})

    if False:
        for airspace in airspaces.values():
            print(airspace)
            for reg in airspace.regions:
                print(reg)
                mindist = 10000
                maxdist = -1
                for i, pt in enumerate(reg.points):
                    d = pt.distance(reg.points[(i + 1) % len(reg.points)])
                    if d < mindist:
                        mindist = d
                    if d > maxdist:
                        maxdist = d
                print(f"mindist={mindist}, maxdist={maxdist}")

    if False:
        for airspace in airspaces.values():
            for reg in airspace.regions:
                cleanup_points(reg)
    if True:
        for airspace in airspaces.values():
            for reg in airspace.regions:
                cleanup_straights(reg)

    qtree = QuadTree()

    # insert all points into the quad tree
    # points that are close together will be grouped
    for airspace in airspaces.values():
        for reg in airspace.regions:
            for i, pt in enumerate(reg.points):
                reg.points[i] = qtree.insert_grouped(pt)

    #
    # insert points into nearby lines
    #
    if False:
        for airspace in airspaces.values():
            for reg in airspace.regions:
                cleanup_lines(qtree, reg)

    n = 0
    for pt in qtree.all():
        n += 1
    print(f"{n} counted points")

    if True:
        khwd = airspaces['KMRY']
        for reg in khwd.regions:
            print(reg)
            for i, p1 in enumerate(reg.points):
                p0 = reg.points[(i-1) % len(reg.points)]
                p2 = reg.points[(i+1) % len(reg.points)]
                d1 = p1.distance(p0)
                d2 = p1.distance(p2)
                d3 = p0.distance(p2)
                c = Point((p0.lon + p2.lon)/2, (p0.lat + p2.lat)/2)
                d4 = p1.distance(c)
                b = bearing(p0, p1)
                a = angle(p0, p1, p2)

                print(f"{i:4}: {p1.lon:.4f},{p1.lat:.4f} {d1:.4f} {d2:.4f} {d3:.4f} {d4:.4f} {b:.4f} {a:.4f} {p1.regions}")
                #if p1.is_grouped():
                #    print(f"GROUP {p1.regions}")
                #    for i, pt in enumerate(p1.group):
                #        print(f"{i}: {pt}")

    t = 0
    n = 0
    g = 0
    for pt in qtree.all():
        t += 1
        if pt.is_grouped():
            g += 1
            n += len(pt.group)
    print(f"{t} points, {n} grouped points, {g} groups")

# (c)2019, Arthur van Hoff

import os, sys, requests, math, shapely, shapely.geometry, shapely.ops, numpy
from scipy import optimize
import settings

d2r = math.pi/180
r2d = 180/math.pi
f2m = 1/3.28084
m2f = 1/f2m
FAR = 1000000
SFC = -999999
TOP = +999999
MININT = -sys.maxsize
MAXINT = sys.maxsize

def distance_xy(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def distance_line_xy(l1, l2, p):
    a = l2[0] - l1[0]
    b = l2[1] - l1[1]

    d = a**2 + b**2
    if d == 0:
        return math.sqrt((l1[0] - p[0])**2 + (l1[1] - p[1])**2)

    #if distance_xy(p, l1) > d or distance_xy(p, l2) > d:
    #    return FAR

    m = ((l1[0] + l2[0])/2, (l1[1] + l2[1])/2)
    if ((p[0]-m[0])**2 + (p[1]-m[1])**2) > d/4:
        return FAR

    return (abs(b*p[0] - a*p[1] + l1[1]*l2[0] - l1[0]*l2[1]) / math.sqrt(d))

def nearest_point(points, target):
    bestp = None
    bestd = MAXINT
    for p in points:
        d = (p[0] - target[0])**2 + (p[1] - target[1])**2
        if d < bestd:
            bestp = p
            bestd = d
    return bestp

def bbox_all():
    return (MININT, MININT, MAXINT, MAXINT)

def bbox_init():
    return (MAXINT, MAXINT, MININT, MININT)

def bbox_add(bbox, p):
    return (min(bbox[0], p[0]), min(bbox[1], p[1]), max(bbox[2], p[0]), max(bbox[3], p[1]))

def bbox_overlap(bbox1, bbox2):
    return bbox1[0] <= bbox2[2] and bbox1[2] >= bbox2[0] and bbox1[1] <= bbox2[3] and bbox1[3] >= bbox2[1]

def bbox_union(bbox1, bbox2):
    return (min(bbox1[0], bbox2[0]), min(bbox1[1], bbox2[1]), max(bbox1[2], bbox2[2]), max(bbox1[3], bbox2[3]))

def bbox_points(pts):
    b = bbox_init()
    for p in pts:
        b = bbox_add(b, p)
    return b

def bbox_contains(bbox, p):
    return p[0] >= bbox[0] and p[1] >= bbox[1] and p[0] <= bbox[2] and p[1] <= bbox[3]

def winding_order(points):
    sum = 0
    p0 = points[-1]
    for p1 in points:
        sum += (p1[0] - p0[0]) * (p1[1] + p0[1])
        p0 = p1
    return sum

def is_empty(poly):
    return not not_empty(poly)

def not_empty(poly):
    if isinstance(poly, list):
        for p in poly:
            if not_empty(p):
                return True
    elif isinstance(poly, shapely.geometry.LineString):
        return False
    elif isinstance(poly, (shapely.geometry.MultiPolygon, shapely.geometry.GeometryCollection)):
        for g in poly.geoms:
            if not_empty(g):
                return True
    elif len(poly.exterior.coords) > 0:
        return True
    return False

def fit_arc(points):
    # see https://scipy-cookbook.readthedocs.io/items/Least_Squares_Circle.html

    def calc_R(xc, yc):
        """ calculate the distance of each 2D points from the center (xc, yc) """
        return numpy.sqrt((x-xc)**2 + (y-yc)**2)

    def f_2(c):
        """ calculate the algebraic distance between the data points and the mean circle centered at c=(xc, yc) """
        Ri = calc_R(*c)
        return Ri - Ri.mean()

    x = numpy.array([pt[0] for pt in points])
    y = numpy.array([pt[1] for pt in points])
    x_m = x.mean()
    y_m = y.mean()

    center, _ = optimize.leastsq(f_2, (x_m, y_m))
    radius = calc_R(*center).mean()
    print(center, radius)
    return (center[0], center[1]), radius

def enumerate_pairs(points):
    n = len(points)
    p1 = points[0]
    for i in range(n):
        p2 = points[(i+1) % n]
        yield p1, p2
        p1 = p2

def enumerate_triples(points):
    n = len(points)
    p0 = points[-1]
    p1 = points[0]
    for i in range(n):
        p2 = points[(i+1) % n]
        yield p0, p1, p2
        p0 = p1
        p1 = p2

#
# Given a complex polygon construct a list of simple
# polygons that describe the same area.
#

def polygon_list(poly):
    if poly.area == 0:
        return []

    if isinstance(poly, shapely.geometry.Polygon):
        if len(poly.interiors) == 0:
            return [poly]
        assert len(poly.interiors) == 1, f"multiple interior polygons {len(poly.interiors)}"

        cy = poly.interiors[0].centroid.y
        xmin, _, xmax, _ = poly.bounds
        line = shapely.geometry.LineString([(xmin, cy), (xmax, cy)])

        newpoly = shapely.ops.split(poly, line)
        return polygon_list(newpoly)

    if isinstance(poly, (shapely.geometry.MultiPolygon, shapely.geometry.GeometryCollection)):
        return [y for x in [polygon_list(pts) for pts in poly.geoms] for y in x]

    if isinstance(poly, shapely.geometry.LineString):
        return [shapely.geometry.Polygon(poly.coords)]

    assert False, f"unexpected polygon type: {type(poly)}"


#
# Intersect two polygons (p1, p1), resulting in
# three sets of polygons ((p1 - p2), (p1 & p2), (p2 - p1))
#

def polygon_intersection(p1, p2):
    #return [p1], [], [p2]
    return polygon_list(p1.difference(p2)), polygon_list(p1.intersection(p2)), polygon_list(p2.difference(p1))
#
# Download a file
#

def download_file(url, dst=None):
    filename = os.path.basename(url)
    if dst is None:
        dst = os.path.join(settings.tmp_dir, os.path.basename(url))
    if os.path.exists(dst):
        return dst

    req = requests.get(url=url, stream=True)
    if req.status_code != 200:
        print("failed to download %s" % (url))
        return None

    clen = int(req.headers['content-length'])
    tmp = dst + ".partial"
    total = 0
    with open(tmp, 'wb') as out:
        for chunk in req.iter_content(chunk_size=100*1024):
            out.write(chunk)
            total += len(chunk)
            sys.stdout.write("\r                                                                \r")
            sys.stdout.write("%s: %2.3f%% of %dMB" % (filename, 100 * total / clen, clen//(1024*1024)))
            sys.stdout.flush()

    sys.stdout.write("\r                                                                \r")
    sys.stdout.flush()
    print("downloaded %s, %dMB" % (filename, clen//(1024*1024)))
    os.rename(tmp, dst)
    return dst

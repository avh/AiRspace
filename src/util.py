# (c)2019, Arthur van Hoff

import os, sys, requests, math, shapely

f2m = 1/3.28084
m2f = 1/f2m
FAR = 1000000
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

#
# Given a complex polygon construct a list of simple
# polygons that describe the same area.
#

def polygon_list(poly, holes=False):
    result = []
    polygon_list_update(poly, result, holes)
    return result

def polygon_list_update(poly, result, holes=False):
    if isinstance(poly, shapely.geometry.Polygon):
        if len(poly.interiors) == 0 or holes:
            result.append(poly)
        else:
            print("break up", len(poly.interiors), "holes")
            # eliminate holes by cutting through the center of the first hole
            b1 = bbox_points(poly.exterior.coords)
            b2 = bbox_points(poly.interiors[0].coords)

            # find existing points near equator of the hole
            mid = (b2[1] + b2[3])/2
            tl = (b1[0] - 100, b1[1] - 100)
            tr = (b1[2] + 100, b1[1] - 100)
            ml = (b1[0] - 100, mid)
            mr = (b1[2] + 100, mid)
            bl = (b1[0] + 100, b1[3] + 100)
            br = (b1[2] - 100, b1[3] + 100)

            l1 = nearest_point(poly.exterior.coords, ml)
            r1 = nearest_point(poly.exterior.coords, mr)
            l2 = nearest_point(poly.interiors[0].coords, l1)
            r2 = nearest_point(poly.interiors[0].coords, r1)

            ml = (ml[0], l1[1])
            mr = (mr[0], r1[1])

            # top half
            top = shapely.geometry.Polygon([tl, tr, mr, r1, r2, l2, l1, ml])
            polygon_list_update(poly.intersection(top), result, holes)

            # bottom half
            bot = shapely.geometry.Polygon([br, bl, ml, l1, l2, r2, r1, mr])
            polygon_list_update(poly.intersection(bot), result, holes)
    elif isinstance(poly, shapely.geometry.MultiPolygon):
        for p in poly:
            polygon_list_update(p, result, holes)
    elif isinstance(poly, shapely.geometry.GeometryCollection):
        for g in poly.geoms:
            polygon_list_update(g, result, holes)

#
# Cleveryly intersect two polygons (p1, p1), resulting in
# three sets of polygons ((p1 - p2), (p1 & p2), (p2 - p1))
#

def polygon_intersection(p1, p2):
    result = ([],[],[])
    polygon_intersection_update(p1, p2, result)
    return result

def polygon_intersection_update(p1, p2, result):
    intersection = polygon_list(p1.intersection(p2), True)

    if len(intersection) == 0:
        result[0].append(p1)
        result[2].append(p2)
    else:
        diff_12 = polygon_list(p1.difference(p2), True)
        diff_21 = polygon_list(p2.difference(p1), True)

        # check for holes
        for poly in diff_12 + intersection + diff_21:
            if len(poly.interiors) > 0:
                print("break up intersection", len(poly.interiors), "holes")
                b1 = bbox_points([*p1.exterior.coords, *p2.exterior.coords])
                b2 = bbox_points(poly.interiors[0].coords)

                # find existing points near equator of the hole
                mid = (b2[1] + b2[3])/2
                tl = (b1[0] - 100, b1[1] - 100)
                tr = (b1[2] + 100, b1[1] - 100)
                ml = (b1[0] - 100, mid)
                mr = (b1[2] + 100, mid)
                bl = (b1[0] + 100, b1[3] + 100)
                br = (b1[2] - 100, b1[3] + 100)

                l1 = nearest_point(poly.exterior.coords, ml)
                r1 = nearest_point(poly.exterior.coords, mr)
                l2 = nearest_point(poly.interiors[0].coords, l1)
                r2 = nearest_point(poly.interiors[0].coords, r1)

                ml = (ml[0], l1[1])
                mr = (mr[0], r1[1])

                # top half
                top = shapely.geometry.Polygon([tl, tr, mr, r1, r2, l2, l1, ml])
                polygon_intersection_update(p1.intersection(top), p2.intersection(top), result)

                # bottom half
                bot = shapely.geometry.Polygon([br, bl, ml, l1, l2, r2, r1, mr])
                polygon_intersection_update(p1.intersection(bot), p2.intersection(bot), result)

                # top half
                #top = shapely.geometry.Polygon([(b1[0], b1[1]), (b1[2], b1[1]), (b1[2], mid), (b1[0], mid), (b1[0], b1[1])])
                #polygon_intersection_update(p1.intersection(top), p2.intersection(top), result)

                # bottom half
                #bot = shapely.geometry.Polygon([(b1[0], mid), (b1[2], mid), (b1[2], b1[3]), (b1[0], b1[3]), (b1[0], mid)])
                #polygon_intersection_update(p1.intersection(bot), p2.intersection(bot), result)
                return

        result[0].extend(diff_12)
        result[1].extend(intersection)
        result[2].extend(diff_21)

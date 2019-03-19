# (c)2019, Arthur van Hoff

import pyproj, affine, os, sys
import settings, elevation, util

SFC = -999999
TOP = +999999

charts_table = settings.db.geo_table("charts")
elevations = elevation.Elevations()

class Chart:
    def __init__(self, name):
        self.name = name
        self.info = charts_table.get(name)
        self.proj = pyproj.Proj(self.info['projection'])
        self.forward_transform = affine.Affine(*self.info['transform'])
        self.reverse_transform = ~self.forward_transform
        self.scale = 1.0
        self.points = {}

        print("INFO", name, self.info)

        # estimate the scale of the map
        y = self.info['size'][1] / 2
        _, _, dist = pyproj.Geod(ellps='WGS84').inv(*self.xy2lonlat((0, y)), *self.xy2lonlat((self.info['size'][0], y)))
        self.scale = dist/self.info['size'][0]

        self.width = self.info['size'][0] * self.scale
        self.height = self.info['size'][1] * self.scale
        self.bbox = (0, 0, self.width, self.height)

    def sfc_elevation(self, xy, h):
        return elevations.get(self.xy2lonlat(xy)) if h == SFC else h

    # map lonlat to xy in meters
    def lonlat2xy(self, lonlat):
        x, y = self.reverse_transform * self.proj(lonlat[0], lonlat[1])
        return (self.scale*x, self.scale*y)

    # map lonlat to xyz in meters
    def lonlat2xyz(self, lonlat, height=0):
        x, y = self.lonlat2xy(lonlat)
        return (x, height, y)

    # map xy in meters to lonlat
    def xy2lonlat(self, xy):
        x, y = self.forward_transform * (xy[0]/self.scale, xy[1]/self.scale)
        return self.proj(x, y, inverse=True)

    def get_point(self, xy, debug=None):
        if xy in self.points:
            point = self.points[xy]
        else:
            if debug is not None:
                print("new point", xy, debug)
                point = (*xy, set(), debug)
            else:
                point = (*xy, set())
            self.points[xy] = point
        return point

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

    def check_points(self):
        for p in self.points.values():
            for f in p[2]:
                if p not in f.points:
                    print("invalid point", f, p)

    def draw(self, out, n=None, flat=False):
        if flat:
            mtlname = out.mtllib(self.info['material'])
            out.image(mtlname,
                      (0, 0, 0),
                      (self.width, 0, 0),
                      (self.width, 0, self.height),
                      (0, 0, self.height))
        else:
            if n is None:
                degrees = self.xy2lonlat((self.width, self.height/2))[0] - self.xy2lonlat((0, self.height/2))[0]
                n = int(settings.elevation_steps * degrees)
                print("N", n)
            mtlname = out.mtllib(self.info['material'])
            out.usemtl(mtlname)
            m = int(n*self.height // self.width)
            vi = out.v_index
            vti = out.vt_index
            for y in range(m+1):
                for x in range(n+1):
                    mxmy = ((x * self.width)/n, (y * self.height)/m)
                    elevation = elevations.get(self.xy2lonlat(mxmy))
                    out.v((mxmy[0], elevation, mxmy[1]))
                    out.vt((x/n, 1 - y/m))
            for y in range(m):
                for x in range(n):
                    out.f_vt((vi, vti), (vi+n+1, vti+n+1), (vi+n+2, vti+n+2), (vi+1, vti+1))
                    vi += 1
                    vti += 1
                vi += 1
                vti += 1
        out.newline()

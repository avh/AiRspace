# (c)2018, Arthur van Hoff
import os, sys, glob, gdal, osr, pyproj, db, PIL.Image, math, numpy, re, affine, cv2, shutil
import settings, objfmt

max_zoom = 12
areas = ["San Francisco", "Seattle", "Los Angeles", "Las Vegas", "Phoenix"]
#areas = None
testing = False

charts_table = settings.db.geo_table("charts")

epsg3857 = pyproj.Proj(init='epsg:3857')
#print(epsg3857)
earth_circumference = epsg3857(180, 0)[0] - epsg3857(-180, 0)[0]
#print(earth_circumference)

class MapLevel:
    def __init__(self, type, zoom, proj=epsg3857):
        self.type = type
        self.zoom = zoom
        self.proj = proj
        self.tile_count = 2**self.zoom
        self.tile_size = 256
        self.map_size = self.tile_count * self.tile_size
        self.zoom_out = None
        self.zoom_in = None

        self.dir = os.path.join(os.path.join(settings.tiles_dir, type), "%d" % self.zoom)

        self.meters_per_pixel = earth_circumference / self.map_size
        self.reverse_transform = affine.Affine.scale(self.map_size/earth_circumference, -self.map_size/earth_circumference)
        self.reverse_transform = affine.Affine.translation(self.map_size/2, self.map_size/2) * self.reverse_transform
        self.forward_transform = ~self.reverse_transform
        self.touched = numpy.zeros((self.tile_count, self.tile_count), dtype='bool')

    # map lonlat to xy in pixels
    def lonlat2xy(self, lonlat):
        return self.reverse_transform * self.proj(lonlat[0], lonlat[1])

    # map pixel coordinate into lonlat
    def xy2lonlat(self, xy):
        x, y = self.forward_transform * (xy[0], xy[1])
        return self.proj(x, y, inverse=True)

    def touch(self, txy):
        self.touched[txy[0], txy[1]] = True
        if self.zoom_out is not None:
            self.zoom_out.touch((txy[0]//2, txy[1]//2))

    def info(self):
        print("zoom=%d, width=%d, tiles=%dx%d, meters_per_pixel=%f" % (self.zoom, self.map_size, self.tile_count, self.tile_count, self.meters_per_pixel))
        self.lonlat2xy((-123, 30))

def make_levels(type, max_zoom):
    levels = [MapLevel(type, zoom) for zoom in range(0, max_zoom+1)]
    for zoom in range(0, len(levels)-1):
        levels[zoom].zoom_in = levels[zoom+1]
        levels[zoom+1].zoom_out = levels[zoom]
    return levels

if testing:
    shutil.rmtree(os.path.join(settings.tiles_dir,'test'))
    sec_levels = make_levels('test', max_zoom)
    tac_levels = sec_levels
else:
    sec_levels = make_levels('sec', max_zoom)
    tac_levels = make_levels('tac', max_zoom)

def get_rgba(ds):
    band = ds.GetRasterBand(1)
    data = band.ReadAsArray(0, 0, ds.RasterXSize, ds.RasterYSize)
    rct = band.GetRasterColorTable()
    clut = []
    for i in range(rct.GetCount()):
        entry = rct.GetColorEntry(i)
        clut.append((entry[2], entry[1], entry[0], entry[3]))
    clut = numpy.array(clut, dtype='uint8')
    rgba = numpy.empty((ds.RasterYSize, ds.RasterXSize, 4), dtype='uint8')
    for i in range(4):
        rgba[...,i] = cv2.LUT(data, clut[:,i])
    return rgba

def fade_edges(img, nsteps=10):
    for i in range(0, nsteps):
        alpha = i / nsteps
        img[:,i,3] = alpha * img[:,i,3]
        img[:,-1-i,3] = alpha * img[:,-1-i,3]
        img[i,:,3] = alpha * img[i,:,3]
        img[-1-i,:,3] = alpha * img[-1-i,:,3]

def extract_tile(img, rect, size=(256,256), borderValue=(0, 0, 0, 0)):
    #print("extract_tile", img.shape, rect)
    w = rect[1][0] - rect[0][0]
    if w > size[0]*2 or w*2 < size[0]:
        print("warining: losing resolution", size[0]/w)

    src_rect = numpy.array(rect, dtype='float32')
    dst_rect = numpy.array([(0,0), (size[0], 0), size, (0, size[1])], dtype='float32')
    mat = cv2.getPerspectiveTransform(src_rect, dst_rect)
    return cv2.warpPerspective(img, mat, size, borderValue=borderValue)

def combine_tiles(tile1, tile2):
    alpha1 = tile1[:,:,3] / 255
    alpha2 = 1.0 - alpha1
    for c in range(0, 3):
        tile1[:,:,c] = tile1[:,:,c] * alpha1 + tile2[:,:,c] * alpha2
    tile1[:,:,3] = numpy.maximum(tile1[:,:,3], tile2[:,:,3])

def get_lonlat(ds):
    str = ds.GetProjection()
    lon = re.search(r'PARAMETER\["central_meridian",([^\]]+)\]', str).group(1),
    lat = re.search(r'PARAMETER\["latitude_of_origin",([^\]]+)\]', str).group(1),
    return float(lon[0]), float(lat[0])

def get_projection(ds):
    inSRS_wkt = ds.GetProjection()  # gives SRS in WKT
    inSRS_converter = osr.SpatialReference()  # makes an empty spatial ref object
    inSRS_converter.ImportFromWkt(inSRS_wkt)  # populates the spatial ref object with our WKT SRS
    return inSRS_converter.ExportToProj4()  # Exports an SRS ref as a Proj4 string usable by PyProj

def get_transform(ds):
    return affine.Affine.from_gdal(*ds.GetGeoTransform())

def xy2lonlat(xy, forward_transform, proj):
    x, y = forward_transform * (xy[0], xy[1])
    return proj(x, y, inverse=True)

def lonlat2xy(lonlat, reverse_transform, proj):
    #print("lonlat2xy", lonlat, "to", reverse_transform * proj(lonlat[0], lonlat[1]))
    return reverse_transform * proj(lonlat[0], lonlat[1])

def lonlat2xyr(lonlat, reverse_transform, proj):
    xy = lonlat2xy(lonlat, reverse_transform, proj)
    return (round(xy[0]), round(xy[1]))

def extract_tiles(levels, zoom, chart, overwrite=False):
    print("chart", chart)
    level = levels[zoom]
    os.makedirs(level.dir, exist_ok=True)

    for chart_file in glob.glob(os.path.join(chart['path'], "*.tif")):
        ds = gdal.Open(chart_file)
        tx = ds.GetGeoTransform()
        if tx[1] == 1.0:
            print("skipping", chart_file)
            continue
        width = ds.RasterXSize
        height = ds.RasterYSize
        print("extract_tiles, zoom=%d, %s, %s, size=%dx%d" % (zoom, chart['name'], chart['type'], width, height))

        fullname = chart['name']
        if chart['type'] == 'tac':
            fullname += " TAC"
        elif chart['type'] == 'sec':
            fullname += " SECTIONAL"

        #lonlat = get_lonlat(ds)
        #print("lonlat", lonlat)
        #print(chart)

        # projection
        proj = pyproj.Proj(get_projection(ds))
        forward_transform = affine.Affine(*get_transform(ds)[:6])
        reverse_transform = ~forward_transform

        lon_min = 360
        lat_min = 180
        lon_max = -360
        lat_max = - 180
        for xy in [(0, 0), (width, 0), (width/2, 0), (0, height), (width/2, height), (width, height)]:
            lon,lat = xy2lonlat(xy, forward_transform, proj)
            lon_min = min(lon, lon_min)
            lon_max = max(lon, lon_max)
            lat_min = min(lat, lat_min)
            lat_max = max(lat, lat_max)

        # load image
        rgba = get_rgba(ds)
        #img = PIL.Image.fromarray(data, "RGBA")
        #print("loaded image")
        print("rgba", rgba.shape, rgba.dtype)
        fade_edges(rgba)
        if fullname in settings.chart_notes:
            for args in settings.chart_notes[fullname]:
                print(args)
                edge = 5
                margin = 10 if chart['type'] == 'sec' else 50
                if args[0] == 'l-lon':
                    lastxy = (-1, -1)
                    lon = float(args[1])
                    for lat in numpy.arange(lat_max+1, lat_min-1, -0.1):
                        xy = lonlat2xyr((lon,lat), reverse_transform, proj)
                        xy = (xy[0] + edge, xy[1])
                        for y in range(max(0, lastxy[1]), min(height-1, xy[1])):
                            x = round(lastxy[0] + (xy[0] - lastxy[0]) * (y - lastxy[1]) / (xy[1] - lastxy[1]))
                            rgba[y, 0:x, 3] = 0
                            for m in range(0, margin):
                                rgba[y, x + m, 3] = rgba[y, x + m, 3] * m / margin
                        lastxy = xy

                elif args[0] == 'b-lat':
                    lastxy = (-1, -1)
                    lat = float(args[1])
                    for lon in numpy.arange(lon_min-1, lon_max+1, 0.1):
                        xy = lonlat2xyr((lon,lat), reverse_transform, proj)
                        xy = (xy[0], xy[1] - edge)
                        for x in range(max(0, lastxy[0]), min(width-1, xy[0])):
                            y = round(lastxy[1] + (xy[1] - lastxy[1]) * (x - lastxy[0]) / (xy[0] - lastxy[0]))
                            rgba[y:height-1, x, 3] = 0
                            for m in range(0, margin):
                                rgba[y + m, x, 3] = rgba[y + m, x, 3] * m / margin
                        lastxy = xy

                elif args[0] == 't-fix':
                    lon = float(args[1])
                    lat = float(args[2])
                    xy = lonlat2xyr((lon, lat), reverse_transform, proj)
                    xy = (xy[0], max(0, xy[1] + edge))
                    rgba[0:xy[1],:,3] = 0
                    for m in range(0, margin):
                        rgba[xy[1]+m,:,3] = rgba[xy[1]+m,:,3] * (m / margin)

                elif args[0] == 'b-fix':
                    lon = float(args[1])
                    lat = float(args[2])
                    xy = lonlat2xyr((lon, lat), reverse_transform, proj)
                    xy = (xy[0], min(xy[1] - edge, height))
                    rgba[xy[1]:height-1,:,3] = 0
                    for m in range(0, margin):
                        rgba[xy[1]-m,:,3] = rgba[xy[1]-m,:,3] * (m / margin)

                elif args[0] == 'l-fix':
                    lon = float(args[1])
                    lat = float(args[2])
                    xy = lonlat2xyr((lon, lat), reverse_transform, proj)
                    xy = (max(0, xy[0] + edge), xy[1])
                    rgba[:,0:xy[0],3] = 0
                    for m in range(0, margin):
                        rgba[:,xy[0]+m,3] = rgba[:,xy[0]+m,3] * (m / margin)

                elif args[0] == 'r-fix':
                    lon = float(args[1])
                    lat = float(args[2])
                    xy = lonlat2xyr((lon, lat), reverse_transform, proj)
                    xy = (min(xy[0] - edge, width), xy[1])
                    rgba[:,xy[0]:width-1,3] = 0
                    for m in range(0, margin):
                        rgba[:,xy[0]-m,3] = rgba[:,xy[0]-m,3] * (m / margin)

                elif args[0] == "bounds":
                    lonlat1 = (float(args[1]), float(args[2]))
                    lonlat2 = (float(args[3]), float(args[4]))
                    xy1 = lonlat2xyr(lonlat1, reverse_transform, proj)
                    xy2 = lonlat2xyr(lonlat2, reverse_transform, proj)
                    xmin = max(0, min(xy1[0], xy2[0]) + edge)
                    xmax = min(width-1, max(xy1[0], xy2[0]) - edge)
                    ymin = max(0, min(xy1[1], xy2[1]) + edge)
                    ymax = min(height-1, max(xy1[1], xy2[1]) - edge)
                    rgba[0:ymin,:,3] = 0
                    rgba[ymax:height,:,3] = 0
                    rgba[:,0:xmin,3] = 0
                    rgba[:,xmax:width] = 0
                    for m in range(0, margin):
                        f = m/margin
                        rgba[ymin+m,xmin+m:xmax-m,3] = f * rgba[ymin+m,xmin+m:xmax-m,3]
                        rgba[ymax-m,xmin+m:xmax-m,3] = f * rgba[ymax-m,xmin+m:xmax-m,3]
                        rgba[ymin+m:ymax-m,xmin+m,3] = f * rgba[ymin+m:ymax-m,xmin+m,3]
                        rgba[ymin+m:ymax-m,xmax-m,3] = f * rgba[ymin+m:ymax-m,xmax-m,3]

                elif args[0] == "box":
                    lonlat1 = (float(args[1]), float(args[2]))
                    lonlat2 = (float(args[3]), float(args[4]))
                    xy1 = lonlat2xyr(lonlat1, reverse_transform, proj)
                    xy2 = lonlat2xyr(lonlat2, reverse_transform, proj)
                    xmin = max(0, min(xy1[0], xy2[0]) - edge)
                    xmax = min(width-1, max(xy1[0], xy2[0]) + edge)
                    ymin = max(0, min(xy1[1], xy2[1]) - edge)
                    ymax = min(height-1, max(xy1[1], xy2[1]) + edge)
                    rgba[ymin:ymax,xmin:xmax,3] = 0
                    #print("BOX", lonlat1, lonlat2, xy1, xy2, xmin, xmax, ymin, ymax)
                    for m in range(0, margin):
                        f = m/margin
                        rgba[max(0,ymin-m),max(xmin-m,0):min(xmax+m,width-1),3] = f * rgba[max(0,ymin-m),max(xmin-m,0):min(xmax+m,width-1),3]
                        rgba[max(0,ymin-m):min(ymax+m,height-1),min(xmax+m,width-1),3] = f * rgba[max(0,ymin-m):min(ymax+m,height-1),min(xmax+m,width-1),3]
                        rgba[min(ymax+m,height-1),max(xmin-m,0):min(xmax+m,width-1),3] = f * rgba[min(ymax+m,height-1),max(xmin-m,0):min(xmax+m,width-1),3]
                else:
                    print("warning: ignoring", args)


        #print("bounds", (lon_min, lat_min), (lon_max, lat_max))
        xy = level.lonlat2xy((lon_min, lat_max))
        #print(xy)
        tile_min = (round(xy[0]) // level.tile_size, round(xy[1]) // level.tile_size)
        xy = level.lonlat2xy((lon_max, lat_min))
        #print(xy)
        tile_max = (round(xy[0]) // level.tile_size, round(xy[1]) // level.tile_size)
        #print("tiles", tile_min, tile_max, (tile_max[0] - tile_min[0], tile_max[1] - tile_min[1]))
        #print("tile_size", width // (tile_max[0] - tile_min[0]))

        count = 0
        for tx in range(tile_min[0]-1, tile_max[0]+1):
            tile_dir = os.path.join(level.dir, "%d" % (tx))
            if not os.path.exists(tile_dir):
                os.mkdir(tile_dir)
            for ty in range(tile_min[1]-1, tile_max[1]+1):
                tile_path = os.path.join(tile_dir, "%d.png" % (ty))

                rect = [
                    lonlat2xy(level.xy2lonlat(((tx + xy[0]) * level.tile_size, (ty + xy[1])*level.tile_size)), reverse_transform, proj) for xy in [(0, 0), (1, 0), (1, 1), (0, 1)]
                ]

                # boundary check
                if max(rect[1][0], rect[2][0]) <= 0 or min(rect[0][0], rect[3][0]) >= rgba.shape[1] or min(rect[2][1], rect[3][1]) <= 0 or max(rect[0][1], rect[1][1]) >= rgba.shape[0]:
                    continue

                #print("tile", (tx, ty), rect)
                count += 1
                tile = extract_tile(rgba, rect, (level.tile_size, level.tile_size))
                #print("saved", tile_path)

                if os.path.exists(tile_path) and not overwrite:
                    combine_tiles(tile, cv2.imread(tile_path, cv2.IMREAD_UNCHANGED))

                cv2.imwrite(tile_path, tile, [int(cv2.IMWRITE_PNG_COMPRESSION), 9])
                level.touch((tx, ty))
        print("added", count, "tiles")


def scale_tiles(levels, zoom):
    print("scale_tiles", zoom)
    os.makedirs(levels[zoom].dir, exist_ok=True)
    s = levels[zoom].tile_size
    tmp = numpy.zeros((s*2, s*2, 4), dtype='uint8')
    count = 0
    for xy in numpy.argwhere(levels[zoom].touched):
        tmp[:,:,:] = 0
        for off in [(0, 0), (1, 0), (1, 1), (0, 1)]:
            tx = xy[0]*2 + off[0]
            ty = xy[1]*2 + off[1]
            tile_path = os.path.join(levels[zoom+1].dir, "%d/%d.png" % (tx, ty))
            if os.path.exists(tile_path):
                tmp[s*off[1]:s*off[1]+s, s*off[0]:s*off[0]+s] = cv2.imread(tile_path, cv2.IMREAD_UNCHANGED)

        tile = cv2.resize(tmp, (s, s), interpolation=cv2.INTER_LANCZOS4)
        #print("tile", tile.shape, tile.dtype)
        tile_dir = os.path.join(levels[zoom].dir, "%d" % (xy[0]))
        if not os.path.exists(tile_dir):
            os.mkdir(tile_dir)
        tile_path = os.path.join(tile_dir, "%d.png" % (xy[1]))
        cv2.imwrite(tile_path, tile, [int(cv2.IMWRITE_PNG_COMPRESSION), 9])
        count += 1
        #print("saved scaled", tile_path)
    print("scaled", count, "tiles")


# sec charts
if False:
    for chart in settings.db.hash_table("sec_list").all():
        if chart['name'] + " SECTIONAL" in settings.chart_notes and (areas is None or chart['name'] in areas):
            extract_tiles(sec_levels, len(sec_levels)-1, chart)
    for zoom in range(len(sec_levels)-2, -1, -1):
        scale_tiles(sec_levels, zoom)

# tac charts
if True:
    for chart in settings.db.hash_table("tac_list").all():
        if chart['name'] + " TAC" in settings.chart_notes and (areas is None or chart['name'] in areas):
            extract_tiles(tac_levels, len(tac_levels)-1, chart, overwrite=True)
    for zoom in range(len(tac_levels)-2, len(tac_levels)-4, -1):
        scale_tiles(tac_levels, zoom)

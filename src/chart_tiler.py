# (c)2018, Arthur van Hoff

# REMIND: Hawaiian Islands SEC (rotated)
# REMIND: Honolulu, Guam, Samoa (on Hawaiian Islands map)
# REMIND: Western Aleutian Islands SEC (across date line)
# REMIND: r-lon

import os, sys, glob, osgeo.gdal, osgeo.osr, pyproj, db, PIL.Image, math, numpy, re, affine
import cv2, shutil, tqdm, multiprocessing, filelock, hashlib, time
import settings, util


max_zoom = 13
tile_size = 256
areas = None
#areas = {"San Francisco", "Seattle", "Los Angeles", "Las Vegas", "Phoenix", "Klamath Falls", "Salt Lake City", "Great Falls"}
#areas = {"Caribbean - 1", "Caribbean - 2"}
#areas = {"Hawaiian Islands"}
if areas is not None:
    print(f"processing: {areas}")

charts_table = settings.db.geo_table("charts")

epsg3857 = pyproj.Proj('epsg:3857')
#print(epsg3857)
earth_circumference = epsg3857(180, 0)[0] - epsg3857(-180, 0)[0]
#print(earth_circumference)

class MapLevel:
    def __init__(self, type, zoom, proj=epsg3857):
        self.type = type
        self.zoom = zoom
        self.proj = proj
        self.tile_count = 2**self.zoom
        self.map_size = self.tile_count * tile_size
        self.zoom_out = None
        self.zoom_in = None

        self.dir = os.path.join(os.path.join(settings.tiles_dir, type), f"{self.zoom}")
        os.makedirs(self.dir, exist_ok=True)

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

    def load(self):
        for x in tqdm.tqdm(os.listdir(self.dir)):
            tx = int(x)
            for y in os.listdir(os.path.join(self.dir, x)):
                if y[0] != '.':
                    ty = int(y[:-4])
                    self.touch((tx, ty))

    def __str__(self):
        used = self.touched.sum()
        total = self.tile_count*self.tile_count
        kb = 50
        return f"zoom={self.zoom}, width={self.map_size}, tiles={self.tile_count}x{self.tile_count}, used={used}/{total}, {100*used/total:.2f}%, {used*kb/(1024*1024):.1f}GB, m/pix={self.meters_per_pixel}"

def make_levels(type, max_zoom):
    levels = [MapLevel(type, zoom) for zoom in range(0, max_zoom+1)]
    for zoom in range(0, len(levels)-1):
        levels[zoom].zoom_in = levels[zoom+1]
        levels[zoom+1].zoom_out = levels[zoom]
    return levels

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

    # REMIND: pick best resolution
    #w = rect[1][0] - rect[0][0]
    #if w > size[0]*2 or w*2 < size[0]:
    #    print("warining: losing resolution", size[0]/w)

    src_rect = numpy.array(rect, dtype='float32')
    dst_rect = numpy.array([(0,0), (size[0], 0), size, (0, size[1])], dtype='float32')
    mat = cv2.getPerspectiveTransform(src_rect, dst_rect)
    return cv2.warpPerspective(img, mat, size, borderValue=borderValue)

def combine_tiles(tile1, tile2):
    if tile2 is not None:
        assert tile1 is not None
        alpha1 = tile1[:,:,3] / 255
        alpha2 = 1.0 - alpha1
        for c in range(0, 3):
            tile1[:,:,c] = tile1[:,:,c] * alpha1 + tile2[:,:,c] * alpha2
        tile1[:,:,3] = numpy.maximum(tile1[:,:,3], tile2[:,:,3])

def write_img(path, tile):
    if tile[:,:,3].any():
        dir_name, file_name = os.path.split(path)
        new_path = os.path.join(dir_name, ".new_" + file_name)
        cv2.imwrite(new_path, tile, [int(cv2.IMWRITE_PNG_COMPRESSION), 9])
        if os.path.exists(path):
            os.remove(path)
        os.rename(new_path, path)
        return True
    return False

def get_lonlat(ds):
    str = ds.GetProjection()
    lon = re.search(r'PARAMETER\["central_meridian",([^\]]+)\]', str).group(1),
    lat = re.search(r'PARAMETER\["latitude_of_origin",([^\]]+)\]', str).group(1),
    return float(lon[0]), float(lat[0])

def get_projection(ds):
    inSRS_wkt = ds.GetProjection()  # gives SRS in WKT
    inSRS_converter = osgeo.osr.SpatialReference()  # makes an empty spatial ref object
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


def check_lon(lbl, lon):
    assert (lon > -180 and lon < -50) or (lon > 165 and lon < 180), f"{lbl}: invalid longitude {lon}"
def check_lat(lbl, lat):
    assert lat > 13 and lat < 72, f"{lbl}: invalid latitude {lat}"
def check_lonlat(lbl, lonlat):
    check_lon(lbl, lonlat[0])
    check_lat(lbl, lonlat[1])
def check_lonlat_box(lbl, lonlat1, lonlat2):
    check_lonlat(lbl, lonlat1)
    check_lonlat(lbl, lonlat2)
    assert lonlat1[0] < lonlat2[0] and lonlat1[1] < lonlat2[1], f"{lbl}: invalid bounds {lonlat1} {lonlat2}"
    assert lonlat2[0] - lonlat1[0] < 10 and lonlat2[1] - lonlat2[1] < 10, f"{lbl}: large bounds {lonlat1} {lonlat2}"

def list_charts_for_tiling(chart_list, chart, kind):
    for chart_file in glob.glob(os.path.join(chart['path'], "*.tif")):
        filename = os.path.splitext(os.path.basename(chart_file))[0]
        if f" {kind} " in filename:
            filename = filename[0:filename.rindex(' ')]
        if f" {kind}" not in filename:
            continue
        if filename not in settings.chart_notes:
            print(f"warning: no settings for {filename}, skipping")
            continue
        if len(settings.chart_notes[filename]) == 0:
            continue
        ds = osgeo.gdal.Open(chart_file)
        tx = ds.GetGeoTransform()
        if tx[1] == 1.0:
            print(f"skipping {chart_file}")
            continue
        width = ds.RasterXSize
        height = ds.RasterYSize

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

        x1 = lonlat2xyr((lon_min,lat_min), reverse_transform, proj)[0]
        x2 = lonlat2xyr((lon_min+1,lat_min), reverse_transform, proj)[0]
        map_level = min(math.ceil(math.log2(360*(x2-x1)/tile_size)), max_zoom)

        chart_list.append((map_level, filename, chart_file))

class ChartFile:
    def __init__(self, path:str):
        self.path = str
        self.ds = osgeo.gdal.Open(path)
        self.tx = self.ds.GetGeoTransform()
        self.width = self.ds.RasterXSize
        self.height = self.ds.RasterYSize
        self.proj = pyproj.Proj(get_projection(self.ds))
        self.forward_transform = affine.Affine(*get_transform(self.ds)[:6])
        self.reverse_transform = ~self.forward_transform
        self.rgba = get_rgba(self.ds)
        self.edge = 5
        self.margin = 50 if ' TAC' in path else 10
        self.lon_min = 360
        self.lat_min = 180
        self.lon_max = -360
        self.lat_max = - 180
        for x in (0, self.width):
            for y in (0, self.height/2, self.height):
                lon, lat = self.xy2lonlat((x,y))
                self.lon_min = min(lon, self.lon_min)
                self.lon_max = max(lon, self.lon_max)
        for x in (0, self.width/2, self.width):
            for y in (0, self.height):
                lon, lat = self.xy2lonlat((x,y))
                self.lat_min = min(lat, self.lat_min)
                self.lat_max = max(lat, self.lat_max)
        if self.lon_min < -90 and self.lon_max > 90:
            self.lon_min, self.lon_max = self.lon_max, self.lon_min

    def xy2lonlat(self, xy):
        x, y = self.forward_transform * (xy[0], xy[1])
        return self.proj(x, y, inverse=True)

    def lonlat2xy(self, lonlat):
        return self.reverse_transform * self.proj(lonlat[0], lonlat[1])

    def lonlat2xyr(self, lonlat):
        xy = self.lonlat2xy(lonlat)
        return (round(xy[0]), round(xy[1]))

    def enum_lonlat(self, start, stop, step=0.1):
        if start[0] > 0 and stop[0] < 0:
            stop = (stop[0] + 360, stop[1])

        v = (stop[0] - start[0]), (stop[1] - start[1])
        d = math.sqrt(v[0]**2 + v[1]**2)
        n = math.ceil(d / step)

        for i in range(0, n+1):
            lon = start[0] + (v[0] * i / n)
            lat = start[1] + (v[1] * i / n)
            yield lon if lon < 180 else lon - 360, lat

    def enum_xy(self, start, stop):
        v = (stop[0] - start[0]), (stop[1] - start[1])
        nsteps = max(1, abs(v[0]), abs(v[1]))
        for s in range(0, nsteps):
            x = start[0] + round(v[0]*s/nsteps)
            y = start[1] + round(v[1]*s/nsteps)
            if x >= 0 and x < self.width and y >= 0 and y < self.height:
                yield x, y

    def between_latlon(self, start, stop, step=0.1):
        lastxy = None
        for lonlat in self.enum_lonlat(start, stop, step):
            xy = self.lonlat2xyr(lonlat)
            if lastxy is not None:
                yield from self.enum_xy(lastxy, xy)
            lastxy = xy
        if lastxy is not None:
            yield from self.enum_xy(lastxy, lastxy)

    def fade_edges(self, nsteps):
        alpha = (numpy.arange(0, nsteps) / nsteps)[None,...]
        self.rgba[:, 0:nsteps, 3] = self.rgba[:, 0:nsteps, 3] * alpha
        self.rgba[:, -nsteps:, 3] = self.rgba[:, -nsteps:, 3] * numpy.flip(alpha, 1)
        alpha = alpha.transpose()
        self.rgba[0:nsteps, :, 3] = self.rgba[0:nsteps, :, 3] * alpha
        self.rgba[-nsteps:, :, 3] = self.rgba[-nsteps:, :, 3] * numpy.flip(alpha, 0)

    def apply(self, args):
        e = self.edge
        m = self.margin

        if args[0] == 'l-lon':
            lon = float(args[1])
            alpha = (numpy.arange(0, m) / m)
            for x, y in self.between_latlon((lon, self.lat_min - 0.1), (lon, self.lat_max + 0.1)):
                self.rgba[y, 0:x+e, 3] = 0
                self.rgba[y, x+e:x+e+m, 3] = self.rgba[y, x+e:x+e+m, 3] * alpha

        elif args[0] == 'r-lon':
            lon = float(args[1])
            alpha = numpy.flip(numpy.arange(0, m) / m)
            for x, y in self.between_latlon((lon, self.lat_min - 0.1), (lon, self.lat_max + 0.1)):
                self.rgba[y, x-e:, 3] = 0
                self.rgba[y, x-e-m:x-e, 3] = self.rgba[y, x-e-m:x-e, 3] * alpha

        elif args[0] == 't-lat':
            lat = float(args[1])
            alpha = (numpy.arange(0, m) / m)
            for x, y in self.between_latlon((self.lon_min - 0.1, lat), (self.lon_max + 0.1, lat)):
                self.rgba[:y+e, x, 3] = 0
                self.rgba[y+e:y+e+m, x, 3] = self.rgba[y+e:y+e+m, x, 3] * alpha

        elif args[0] == 'b-lat':
            lat = float(args[1])
            alpha = numpy.flip(numpy.arange(0, m) / m)
            for x, y in self.between_latlon((self.lon_min - 0.1, lat), (self.lon_max + 0.1, lat)):
                self.rgba[y-e:, x, 3] = 0
                self.rgba[y-e-m:y-e, x, 3] = self.rgba[y-e-m:y-e, x, 3] * alpha

        elif args[0] == 'l-fix':
            x = self.lonlat2xyr((float(args[1]), float(args[2])))[0]
            alpha = (numpy.arange(0, m) / m)[None, ...]
            self.rgba[:, 0:x+e, 3] = 0
            self.rgba[:, x+e:x+e+m, 3] = self.rgba[:, x+e:x+e+m, 3] * alpha

        elif args[0] == 'r-fix':
            x = self.lonlat2xyr((float(args[1]), float(args[2])))[0]
            alpha = numpy.flip(numpy.arange(0, m) / m)[None, ...]
            self.rgba[:, x-e:, 3] = 0
            self.rgba[:, x-e-m:x-e, 3] = self.rgba[:, x-e-m:x-e, 3] * alpha

        elif args[0] == 't-fix':
            y = self.lonlat2xyr((float(args[1]), float(args[2])))[1]
            alpha = (numpy.arange(0, m) / m)[..., None]
            self.rgba[0:y+e, :, 3] = 0
            self.rgba[y+e:y+e+m, :, 3] = self.rgba[y+e:y+e+m, :, 3] * alpha

        elif args[0] == 'b-fix':
            y = self.lonlat2xyr((float(args[1]), float(args[2])))[1]
            alpha = numpy.flip(numpy.arange(0, m) / m)[..., None]
            self.rgba[y-e:, :, 3] = 0
            self.rgba[y-e-m:y-e, :, 3] = self.rgba[y-e-m:y-e, :, 3] * alpha

        elif args[0] == 'l-line':
            alpha = (numpy.arange(0, m) / m)
            for x, y in self.between_latlon((float(args[1]), float(args[2])), (float(args[3]), float(args[4]))):
                self.rgba[y, 0:x+e, 3] = 0
                self.rgba[y, x+e:x+e+m, 3] = self.rgba[y, x+e:x+e+m, 3] * alpha

        elif args[0] == 'r-line':
            alpha = (numpy.arange(0, m) / m)
            for x, y in self.between_latlon((float(args[1]), float(args[2])), (float(args[3]), float(args[4]))):
                self.rgba[y, x-e:, 3] = 0
                self.rgba[y, x-e-m:x-e, 3] = self.rgba[y, x-e-m:x-e, 3] * alpha

        elif args[0] == 'bounds':
            self.apply(('l-lon', args[1]))
            self.apply(('b-lat', args[2]))
            self.apply(('r-lon', args[3]))
            self.apply(('t-lat', args[4]))

        elif args[0] == 'box':
            xy1 = self.lonlat2xyr((float(args[1]), float(args[2])))
            xy2 = self.lonlat2xyr((float(args[3]), float(args[4])))
            xmin = max(0, min(xy1[0], xy2[0]) - e)
            xmax = min(self.width, max(xy1[0], xy2[0]) + e)
            ymin = max(0, min(xy1[1], xy2[1]) - e)
            ymax = min(self.height, max(xy1[1], xy2[1]) + e)
            self.rgba[ymin:ymax, xmin:xmax, 3] = 0
            xmin = max(0, xmin - m)
            xmax = min(self.width, xmax + m)
            ymin = max(0, ymin - m)
            ymax = min(self.height, ymax + m)

            for i in range(0, m):
                alpha = 1.0 - i / m
                self.rgba[ymin+i:ymax-i, xmin+i, 3] = self.rgba[ymin+i:ymax-i, xmin+i, 3] * alpha
                self.rgba[ymin+i:ymax-i, xmax-i-1, 3] = self.rgba[ymin+i:ymax-i, xmax-i-1, 3] * alpha
                self.rgba[ymin+i, xmin+i+1:xmax-i-1, 3] = self.rgba[ymin+i, xmin+i+1:xmax-i-1, 3] * alpha
                self.rgba[ymax-i-1, xmin+i+1:xmax-i-1, 3] = self.rgba[ymax-i-1, xmin+i+1:xmax-i-1, 3] * alpha

    def save(self, filename):
        tm = time.time()
        print(f"writing {filename}.png ...")
        cv2.imwrite(f"{filename}.png", self.rgba, [int(cv2.IMWRITE_PNG_COMPRESSION), 9])
        print(f"saved {filename}.png in {util.time_str(tm)}")


def process_chart(inq, outq, level, overwrite):
    touched = []
    while True:
        chart = inq.get()
        if chart[0] == 'done':
            break
        filename = chart[1]
        chart_file = chart[2]
        cf = ChartFile(chart_file)
        print(chart_file)

        rgba = cf.rgba
        proj = cf.proj
        #forward_transform = cf.forward_transform
        reverse_transform = cf.reverse_transform
        #width = cf.width
        #height = cf.height
        lon_min = cf.lon_min
        lon_max = cf.lon_max
        lat_min = cf.lat_min
        lat_max = cf.lat_max


        # fade edges
        cf.fade_edges(nsteps=20)

        # process notes
        for args in settings.chart_notes[filename]:
            cf.apply(args)

        if True:
            cf.save(filename)


        xy = level.lonlat2xy((lon_min, lat_max))
        tile_min = (round(xy[0]) // tile_size, round(xy[1]) // tile_size)
        xy = level.lonlat2xy((lon_max, lat_min))
        tile_max = (round(xy[0]) // tile_size, round(xy[1]) // tile_size)

        if tile_max[0] < tile_min[0]:
            tile_max = (tile_max[0] + level.tile_count, tile_max[1])

        # extract tiles
        count = 0
        for tx in range(tile_min[0]-1, tile_max[0]+1):
            tx = tx % level.tile_count
            tile_dir = os.path.join(level.dir, f"{tx}")
            if not os.path.exists(tile_dir):
                os.mkdir(tile_dir)
            for ty in range(tile_min[1]-1, tile_max[1]+1):
                tile_path = os.path.join(tile_dir, f"{ty}.png")

                rect = [
                    lonlat2xy(level.xy2lonlat(((tx + xy[0]) * tile_size, (ty + xy[1])*tile_size)), reverse_transform, proj) for xy in [(0, 0), (1, 0), (1, 1), (0, 1)]
                ]

                # boundary check
                if max(rect[1][0], rect[2][0]) <= 0 or min(rect[0][0], rect[3][0]) >= rgba.shape[1] or min(rect[2][1], rect[3][1]) <= 0 or max(rect[0][1], rect[1][1]) >= rgba.shape[0]:
                    continue

                count += 1
                tile = extract_tile(rgba, rect, (tile_size, tile_size))

                tmpfile = f"/tmp/{hashlib.md5(tile_path.encode('utf-8')).hexdigest()}.lock"
                with filelock.FileLock(tmpfile):
                    if os.path.exists(tile_path) and not overwrite:
                        combine_tiles(tile, cv2.imread(tile_path, cv2.IMREAD_UNCHANGED))
                    if write_img(tile_path, tile):
                        touched.append((tx, ty))

    outq.put(touched)

def process_charts(levels, zoom, charts, overwrite=False, maxworkers=8):
    if len(charts) > 0:
        nworkers = min(maxworkers, len(charts))
        inq = ctx.Queue(nworkers*2)
        outq = ctx.Queue(nworkers*2)
        for _ in range(nworkers):
            ctx.Process(target=process_chart, args=(inq, outq, levels[zoom], overwrite)).start()

        for chart in charts:
            inq.put(chart)

        for _ in range(nworkers):
            inq.put(('done',))

        # count results
        ntiles = 0
        for _ in range(nworkers):
            for xy in outq.get():
                levels[zoom].touch(xy)
                ntiles += 1
        print(f"updated {ntiles} tiles using {nworkers} workers")

def scale_worker(inq, outq, src_zoom, dst_zoom, src_dir, dst_dir):
    ntiles = 0
    s = tile_size
    n = 2**(src_zoom - dst_zoom)
    tmp = numpy.zeros((s*n, s*n, 4), dtype='uint8')
    while True:
        xy = inq.get()
        if xy[0] == 'done':
            break

        count = 0
        tmp[:,:,:] = 0
        for offx in range(n):
            for offy in range(n):
                tx = xy[0]*n + offx
                ty = xy[1]*n + offy
                tile_path = os.path.join(src_dir, f"{tx}/{ty}.png")
                if os.path.exists(tile_path):
                    tmp[s*offy:s*offy+s, s*offx:s*offx+s] = cv2.imread(tile_path, cv2.IMREAD_UNCHANGED)
                    count += 1
        if count > 0:
            #tmp = cv2.GaussianBlur(tmp, (5,5), sigmaX=1.0)
            #tile = cv2.resize(tmp, (s, s), interpolation=cv2.INTER_AREA)
            #tile = cv2.resize(tmp, (s, s), interpolation=cv2.INTER_LANCSOZ64)
            tile = numpy.asarray(PIL.Image.fromarray(tmp).resize((s,s), PIL.Image.LANCZOS))
            tile_dir = os.path.join(dst_dir, f"{xy[0]}")
            os.makedirs(tile_dir, exist_ok=True)
            tile_path = os.path.join(tile_dir, f"{xy[1]}.png")
            if write_img(tile_path, tile):
                ntiles += 1

    outq.put(ntiles)

def scale_tiles(levels, src_zoom, dst_zoom, maxworkers=16):
    if dst_zoom < 0:
        return
    src_zoom = min(src_zoom, len(levels)-1)

    ntiles = levels[dst_zoom].touched.sum()
    if ntiles == 0:
        return

    print(f"scale_tiles {ntiles:,}, {src_zoom} => {dst_zoom}")

    # fork workers
    nworkers = max(0, min(maxworkers, ntiles))
    inq = ctx.Queue(nworkers*2)
    outq = ctx.Queue(nworkers*2)
    src_dir = levels[src_zoom].dir
    dst_dir = levels[dst_zoom].dir
    for _ in range(nworkers):
        ctx.Process(target=scale_worker, args=(inq, outq, src_zoom, dst_zoom, src_dir, dst_dir,)).start()

    # process each level
    os.makedirs(dst_dir, exist_ok=True)
    for xy in tqdm.tqdm(numpy.argwhere(levels[dst_zoom].touched)):
        inq.put(xy)
    for _ in range(nworkers):
        inq.put(('done', None))

    # count results
    ntiles = 0
    for _ in range(nworkers):
        ntiles += outq.get()
    print(f"scaled {ntiles} tiles using {nworkers} workers")

if __name__ == '__main__':
    ctx = multiprocessing.get_context('spawn')
    tm = time.time()

    # basic consistency checks
    if True:
        for key, vals in settings.chart_notes.items():
            for v in vals:
                if v[0] in ('bounds', 'box'):
                    check_lonlat_box(key, v[1:3], v[3:])
                elif v[0] in ('l-lon', 'r-lon'):
                    check_lon(key, v[1])
                elif v[0] in ('b-lat', 't-lat'):
                    check_lat(key, v[1])
                elif v[0] in ('t-fix', 'b-fix', 'l-fix', 'r-fix'):
                    check_lonlat(key, v[1:])

    # process sec charts
    if True:
        if True and areas is None:
            sec_dir = os.path.join(settings.tiles_dir, 'sec')
            print(f"removing {sec_dir}")
            if os.path.exists(sec_dir):
                shutil.rmtree(sec_dir)

        chart_list = []
        if True:
            for chart in settings.db.hash_table("sec_list").all():
                if areas is None or chart['name'] in areas:
                    if chart['name'].startswith('Caribbean'):
                        list_charts_for_tiling(chart_list, chart, 'VFR Chart')
                    else:
                        list_charts_for_tiling(chart_list, chart, 'SEC')

        if True:
            print(f"{len(chart_list)} charts")
            for ch in sorted(chart_list):
                print(ch)

        if True:
            levels = make_levels('sec', max_zoom)
            for zoom in range(len(levels)-1, -1, -1):
                if areas is None:
                    levels[zoom].load()
                print(levels[zoom])
                process_charts(levels, zoom, [chart for chart in chart_list if chart[0] == zoom], areas is not None)
                scale_tiles(levels, zoom, zoom-1)


    # process tac charts
    if True:
        toplevel = 9

        if False and areas is None:
            tac_dir = os.path.join(settings.tiles_dir, 'tac')
            print(f"removing {tac_dir}")
            if os.path.exists(tac_dir):
                shutil.rmtree(tac_dir)

        chart_list = []
        if True:
            for chart in settings.db.hash_table("tac_list").all():
                if areas is None or chart['name'] in areas:
                    if areas is None or chart['name'] in areas:
                        if chart['name'] == 'Grand Canyon':
                            list_charts_for_tiling(chart_list, chart, 'General Aviation')
                        else:
                            list_charts_for_tiling(chart_list, chart, 'TAC')

        if True:
            print(f"{len(chart_list)} charts")
            for ch in sorted(chart_list):
                print(ch)

        if True:
            levels = make_levels('tac', max_zoom)
            for zoom in range(len(levels)-1, toplevel-1, -1):
                if areas is None:
                    levels[zoom].load()
                print(levels[zoom])
                process_charts(levels, zoom, [chart for chart in chart_list if chart[0] == zoom][:1], areas is not None)
                scale_tiles(levels, zoom, zoom-1)

    tm = math.floor(time.time() - tm)
    hrs = tm // 3600
    min = (tm // 60) % 60
    sec = (tm % 60)
    print(f"done in {hrs}:{min:02}:{sec:02}")

# (c)2018, Arthur van Hoff

# REMIND: Hawaiian Islands SEC (rotated)
# REMIND: Honolulu, Guam, Samoa (on Hawaiian Islands map)
# REMIND: Western Aleutian Islands SEC (across date line)
# REMIND: Miami SEC (missing)

# REMIND: Base tile resolution on chart resolution
# REMIND: Process multiple charts simultaneously

import os, sys, glob, gdal, osr, pyproj, db, PIL.Image, math, numpy, re, affine, cv2, shutil, tqdm, multiprocessing
import settings


#max_zoom = 10
max_zoom = 12
areas = None
#areas = {nm[:-4] for nm in settings.chart_notes.keys() if nm.endswith(" SEC")}
#areas = {"San Francisco", "Seattle", "Los Angeles", "Las Vegas", "Phoenix", "Klamath Falls", "Salt Lake City", "Great Falls"}
#areas = {"Caribbean - 1", "Caribbean - 2"}
#areas = {"Western Aleutian Islands"}
if areas is not None:
    print(f"processing: {areas}")

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
        return f"zoom={self.zoom}, width={self.map_size}, tiles={self.tile_count}x{self.tile_count}, used={used}/{total}, {100*used/total:.2f}%, {used*kb/(1024*1024):.1f}GB, meters_per_pixel={self.meters_per_pixel}"

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
    alpha1 = tile1[:,:,3] / 255
    alpha2 = 1.0 - alpha1
    for c in range(0, 3):
        tile1[:,:,c] = tile1[:,:,c] * alpha1 + tile2[:,:,c] * alpha2
    tile1[:,:,3] = numpy.maximum(tile1[:,:,3], tile2[:,:,3])

def write_img(path, tile):
    dir_name, file_name = os.path.split(path)
    new_path = os.path.join(dir_name, ".new_" + file_name)
    cv2.imwrite(new_path, tile, [int(cv2.IMWRITE_PNG_COMPRESSION), 9])
    if os.path.exists(path):
        os.remove(path)
    os.rename(new_path, path)

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

def extract_tiles(levels, zoom, chart, kind, overwrite=False):
    level = levels[zoom]
    os.makedirs(level.dir, exist_ok=True)
    chart_count = 0

    for chart_file in glob.glob(os.path.join(chart['path'], "*.tif")):
        filename = os.path.splitext(os.path.basename(chart_file))[0]
        if f" {kind} " in filename:
            filename = filename[0:filename.rindex(' ')]
        if f" {kind}" not in filename:
            continue
        if filename not in settings.chart_notes:
            print(f"warning: no settings for {filename}, skipping")
            continue
        ds = gdal.Open(chart_file)
        tx = ds.GetGeoTransform()
        if tx[1] == 1.0:
            print("skipping", chart_file)
            continue
        chart_count += 1
        width = ds.RasterXSize
        height = ds.RasterYSize
        print(f"extract_tiles, zoom={zoom}, {chart['name']}, {filename}, {chart['type']}, kind={kind}, size={width}x{height}")

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
        fade_edges(rgba)
        for args in settings.chart_notes[filename]:
            #print(args)
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
                check_lonlat(filename, (lon, lat))
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
                check_lonlat(filename, (lon, lat))
                xy = lonlat2xyr((lon, lat), reverse_transform, proj)
                xy = (max(0, xy[0] + edge), xy[1])
                rgba[:,0:xy[0],3] = 0
                for m in range(0, margin):
                    rgba[:,xy[0]+m,3] = rgba[:,xy[0]+m,3] * (m / margin)

            elif args[0] == 'r-fix':
                lon = float(args[1])
                lat = float(args[2])
                check_lonlat(filename, (lon, lat))
                xy = lonlat2xyr((lon, lat), reverse_transform, proj)
                xy = (min(xy[0] - edge, width), xy[1])
                rgba[:,xy[0]:width-1,3] = 0
                for m in range(0, margin):
                    rgba[:,xy[0]-m,3] = rgba[:,xy[0]-m,3] * (m / margin)

            elif args[0] == 'bounds':
                lonlat1 = (float(args[1]), float(args[2]))
                lonlat2 = (float(args[3]), float(args[4]))
                check_lonlat_box(filename, lonlat1, lonlat2)
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

            elif args[0] == 'box':
                lonlat1 = (float(args[1]), float(args[2]))
                lonlat2 = (float(args[3]), float(args[4]))
                check_lonlat_box(filename, lonlat1, lonlat2)
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
            tile_dir = os.path.join(level.dir, f"{tx}")
            if not os.path.exists(tile_dir):
                os.mkdir(tile_dir)
            for ty in range(tile_min[1]-1, tile_max[1]+1):
                tile_path = os.path.join(tile_dir, f"{ty}.png")

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

                write_img(tile_path, tile)
                level.touch((tx, ty))

        assert count > 0, f"no tiles found for {chart['name']}"
        print(f"added {count} tiles for {filename}")
    assert chart_count > 0, f"no charts found for {chart['name']}"

def scale_worker(inq, outq, src_zoom, dst_zoom, src_dir, dst_dir, tile_size):
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
            tile = cv2.resize(tmp, (s, s), interpolation=cv2.INTER_AREA)
            tile_dir = os.path.join(dst_dir, f"{xy[0]}")
            os.makedirs(tile_dir, exist_ok=True)
            tile_path = os.path.join(tile_dir, f"{xy[1]}.png")
            write_img(tile_path, tile)
            ntiles += 1

    outq.put(ntiles)

def scale_tiles(levels, top_level=0, maxworkers=16):
    for dst_zoom in range(len(levels)-2, top_level-1, -1):
        print("scale_tiles", levels[dst_zoom])

        # fork workers
        src_zoom = min(dst_zoom+1, len(levels)-1)
        nworkers = max(1, min(levels[dst_zoom].tile_count, maxworkers))
        inq = ctx.Queue(nworkers*2)
        outq = ctx.Queue(nworkers*2)
        src_dir = levels[src_zoom].dir
        dst_dir = levels[dst_zoom].dir
        tile_size = levels[dst_zoom].tile_size
        for _ in range(nworkers):
            ctx.Process(target=scale_worker, args=(inq, outq, src_zoom, dst_zoom, src_dir, dst_dir, tile_size)).start()

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
        print(f"level {dst_zoom}: scaled {ntiles} tiles using {nworkers} workers")

if __name__ == '__main__':
    ctx = multiprocessing.get_context('spawn')

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

    # scale test
    if True:
        sec_levels = make_levels('sec', max_zoom)
        print(f"loading {sec_levels[-1].dir}")
        sec_levels[-1].load()
        for i, level in enumerate(sec_levels):
            print(i, level)

        scale_tiles(sec_levels)


    # sec charts
    if False:
        if True:
            print("-- sec chart list--")
            for name in sorted([chart['name'] for chart in settings.db.hash_table("sec_list").all()]):
                print(name)
            print("--")
        if True and areas is None:
            print(f"removing {os.path.join(settings.tiles_dir,'sec')}")
            shutil.rmtree(os.path.join(settings.tiles_dir,'sec'))
        if True:
            sec_levels = make_levels('sec', max_zoom)
            sec_levels[-1].load()
        if True:
            for chart in settings.db.hash_table("sec_list").all():
                if areas is None or chart['name'] in areas:
                    if chart['name'].startswith('Caribbean'):
                        extract_tiles(sec_levels, len(sec_levels)-1, chart, 'VFR Chart', overwrite=areas is not None)
                    else:
                        extract_tiles(sec_levels, len(sec_levels)-1, chart, 'SEC', overwrite=areas is not None)
        if True:
            scale_tiles(sec_levels)

    # tac charts
    if False:
        if True:
            print("-- tac chart list--")
            for name in sorted([chart['name'] for chart in settings.db.hash_table("tac_list").all()]):
                print(chart['name'])
            print("--")
        if True and areas is None:
            print(f"removing {os.path.join(settings.tiles_dir,'tac')}")
            shutil.rmtree(os.path.join(settings.tiles_dir,'tac'))
        if True:
            tac_levels = make_levels('tac', max_zoom)
            tac_levels[-1].load()
        if True:
            for chart in settings.db.hash_table("tac_list").all():
                if areas is None or chart['name'] in areas:
                    if chart['name'] == 'Grand Canyon':
                        extract_tiles(tac_levels, len(tac_levels)-1, chart, 'General Aviation', overwrite=areas is not None)
                    else:
                        extract_tiles(tac_levels, len(tac_levels)-1, chart, 'TAC', overwrite=areas is not None)
        if True:
            scale_tiles(tac_levels)

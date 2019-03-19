# (c)2018, Arthur van Hoff

import csv, os, sys, dateutil.parser, zipfile, datetime, re, gdal, numpy, PIL.Image, scipy.ndimage.filters, osr, pyproj, affine
import settings, util, elevation, download

bbox = util.bbox_all()
bbox = (-180, 10, -59, 80)

def elevation_urls(bbox=util.bbox_all()):
    urls = []
    with open(settings.elevation_cvs, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            zip_url = row['downloadURL']
            zip_name = os.path.basename(zip_url)
            expr = re.search(r'([ns])([0-9]+)([ew])([0-9]+)', zip_name)
            lon = (1 if expr.group(3) == 'e' else -1) * int(expr.group(4))
            lat = (1 if expr.group(1) == 'n' else -1) * int(expr.group(2))
            if not util.bbox_contains(bbox, (lon, lat)):
                continue
            created = dateutil.parser.parse(row['dateCreated'])
            urls.append(((lon, lat), created, zip_url))
    return urls

def elevation_download(lonlat, created, zip_url, elevation_path):
    zip_name = os.path.basename(zip_url)
    img_name = os.path.splitext(zip_name)[0] + ".img"
    img_path = os.path.join(settings.charts_source_dir, img_name)
    if not os.path.exists(img_path) or os.path.getctime(img_path) < created.timestamp():
        zip_path = download.download_file(zip_url)
        if zip_path is None:
            return False
        with zipfile.ZipFile(zip_path) as zip:
            for name in zip.namelist():
                if name.endswith(".img"):
                    zip.extract(name, settings.tmp_dir)
                    os.rename(os.path.join(settings.tmp_dir, name), img_path)
                    break
        os.remove(zip_path)
        print("loaded", img_path)

    margin = 6
    width = 3600
    height = 3600
    scale = width // settings.elevation_steps

    ds = gdal.Open(img_path)
    band = ds.GetRasterBand(1)
    data = band.ReadAsArray(margin, margin, width, height)
    data[data < -1000] = 0
    datamin = numpy.amin(data)
    datamax = numpy.amax(data)

    if False:
        tmp = numpy.array((255 * (data - datamin) / (datamax - datamin)), numpy.uint8)
        img = PIL.Image.fromarray(tmp)
        img.save(os.path.join(settings.tmp_dir, img_name + ".large.png"))

    # compute windowed maximum heights
    data = scipy.ndimage.filters.maximum_filter(data, size=(scale, scale))
    # down sample data
    data = data[::scale,::scale]

    if False:
        tmp = numpy.array((255 * (data - datamin + 1) / (datamax - datamin + 1)), numpy.uint8)
        img = PIL.Image.fromarray(tmp)
        img.save(os.path.join(settings.tmp_dir, img_name + ".small.png"))

    # convert to shorts (sufficient for meter accuracy)
    data = data.astype(numpy.int16)

    # save numpy data
    numpy.save(elevation_path, data)
    return True

urls = elevation_urls(bbox)
for i in range(len(urls)):
    lonlat, created, zip_url = urls[i]

    elevation_path = os.path.join(settings.elevations_dir, elevation.tile_name(lonlat) + ".npy")
    if os.path.exists(elevation_path):
        continue
    if zip_url.startswith("ftp:"):
        print("skipping", zip_url)
        continue

    if elevation_download(lonlat, created, zip_url, elevation_path):
        print("downloaded %s, %.2f%% (%d of %d)" % (elevation_path, 100*(i+1)/len(urls), i+1, len(urls)))

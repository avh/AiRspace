# (c)2018, Arthur van Hoff
import os, sys, glob, gdal, osr, pyproj, db, PIL.Image, math, numpy, re, affine
import settings, objfmt

charts_table = settings.db.geo_table("charts")

def get_data(ds):
    band = ds.GetRasterBand(1)
    clut = []
    rct = band.GetRasterColorTable()
    for i in range(rct.GetCount()):
        entry = rct.GetColorEntry(i)
        val = (0xFF << 24) + (entry[2] << 16) + (entry[1] << 8) + (entry[0] << 0)
        #print("%4d: 0x%08x" % (i, val))
        clut.append(val)
    return numpy.take(numpy.array(clut, numpy.uint32), band.ReadAsArray(0, 0, ds.RasterXSize, ds.RasterYSize))

def get_projection(ds):
    inSRS_wkt = ds.GetProjection()  # gives SRS in WKT
    inSRS_converter = osr.SpatialReference()  # makes an empty spatial ref object
    inSRS_converter.ImportFromWkt(inSRS_wkt)  # populates the spatial ref object with our WKT SRS
    return inSRS_converter.ExportToProj4()  # Exports an SRS ref as a Proj4 string usable by PyProj

def get_lonlat(ds):
    str = ds.GetProjection()
    lon = re.search(r'PARAMETER\["central_meridian",([^\]]+)\]', str).group(1),
    lat = re.search(r'PARAMETER\["latitude_of_origin",([^\]]+)\]', str).group(1),
    return float(lon[0]), float(lat[0])

def get_transform(ds):
    return affine.Affine.from_gdal(*ds.GetGeoTransform())

def extract_chart(chart):
    for chart_file in glob.glob(os.path.join(chart['path'], "*.tif")):
        ds = gdal.Open(chart_file)
        tx = ds.GetGeoTransform()
        if tx[1] == 1.0:
            print("skipping", chart_file)
            continue

        print("updating chart for %s" % (chart['name']))

        fullname = chart['name']
        if chart['type'] == 'tac':
            fullname += " TAC"
        elif chart['type'] == 'sec':
            fullname += " SECTIONAL"

        width = ds.RasterXSize
        height = ds.RasterYSize
        scale = math.sqrt(settings.chart_target_size / (width*height))
        img_width = int(scale*width)
        img_height = int(scale*height)

        # save image (if needed)
        img_path = os.path.join(settings.charts_dir, fullname.replace(' ', '_') + ".jpg")
        if not os.path.exists(img_path) or os.path.getmtime(img_path) < os.path.getmtime(chart_file):
            data = get_data(ds)
            img = PIL.Image.fromarray(data, "RGBA").convert("RGB")

            img = img.resize((img_width, img_height), PIL.Image.ANTIALIAS)
            img.save(img_path)
            print("saved", img_path)

        # save material (if needed)
        mtl_path = os.path.splitext(img_path)[0] + ".mtl"
        if not os.path.exists(mtl_path) or os.path.getmtime(mtl_path) < os.path.getmtime(chart_file):
            with objfmt.create(mtl_path) as mtl:
                mtl.newmtl(img_path)
            print("saved", mtl_path)

        info = {
            'name': fullname,
            'type': chart['type'],
            'size': (width, height),
            'img': (img_width, img_height),
            'path': img_path,
            'material': mtl_path,
            'lonlat': get_lonlat(ds),
            'transform': get_transform(ds)[:6],
            'projection': get_projection(ds),
            'source': chart,
        }
        #print(info)
        charts_table.set(info['lonlat'], fullname, info)


for chart in settings.db.hash_table("sec_list").all():
    extract_chart(chart)

for chart in settings.db.hash_table("tac_list").all():
    extract_chart(chart)

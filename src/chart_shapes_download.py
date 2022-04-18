# (c)2018, Arthur van Hoff

import os, requests, lxml.etree, urllib.parse, zipfile, shutil, shapefile
import settings, util, unicodedata, re

def shape_name(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.upper())
    value = re.sub(r'[-\s]+', '-', value).strip('-_')
    return value.replace(' ', '-').replace('-CLASS-','-')

def download_chart_shapes():
    #
    # Scan the NASR page for the current download
    #

    url = settings.faa_nasr_url
    print("requesting", url)
    req = requests.get(url=url)
    html = lxml.etree.HTML(req.text)

    for t in html.xpath(".//h2[text()='Current']/following-sibling::ul"):
        href = t.find(".//a").attrib["href"]
        break

    url = urllib.parse.urljoin(url, href)
    print("requesting", url)
    req = requests.get(url=url)
    html = lxml.etree.HTML(req.text)

    for t in html.xpath(".//li/a[text()='Download']"):
        href = t.attrib["href"]
        break

    url = urllib.parse.urljoin(url, href)

    #
    # download the file
    #

    name = os.path.basename(urllib.parse.urlparse(url).path)
    zip_path = os.path.join(settings.charts_source_dir, name)
    util.download_file(url, zip_path)

    #
    # extract the file
    #

    zip_dir = os.path.splitext(zip_path)[0]

    print("extracting", zip_path, "to", zip_dir)
    with zipfile.ZipFile(zip_path) as zip:
        zip.extractall(zip_dir)

    #
    # create link
    #
    if os.path.lexists(settings.nasr_dir):
        os.remove(settings.nasr_dir)
    os.symlink(os.path.relpath(zip_dir, os.path.dirname(settings.nasr_dir)), settings.nasr_dir)
    print("created", settings.nasr_dir)

def process_chart_shapes():
    # see https://aeronav.faa.gov/Open_Data_Supp/Data_Dictionary.pdf
    shp = shapefile.Reader(settings.nasr_shape_path)
    names = [field[0] for field in shp.fields]

    id_index = names.index('DeletionFlag')
    #name_index = names.index('NAME')
    ident_index = names.index('IDENT')
    #class_index = names.index('CLASS')
    #mil_code_index = names.index('MIL_CODE')
    comm_name_index = names.index('COMM_NAME')
    level_index = names.index('LEVEL')
    sector_index = names.index('SECTOR')
    onshore_index = names.index('ONSHORE')
    exclusion_index = names.index('EXCLUSION')
    type_code_index = names.index('TYPE_CODE')
    local_type_index = names.index('LOCAL_TYPE')
    lower_desc_index = names.index('LOWER_DESC')
    lower_uom_index = names.index('LOWER_UOM')
    lower_val_index = names.index('LOWER_VAL')
    lower_code_index = names.index('LOWER_CODE')
    upper_desc_index = names.index('UPPER_DESC')
    upper_uom_index = names.index('UPPER_UOM')
    upper_val_index = names.index('UPPER_VAL')
    upper_code_index = names.index('UPPER_CODE')
    wkhr_code_index = names.index('WKHR_CODE')
    wkhr_rmk_index = names.index('WKHR_RMK')
    delete_index = names.index('DeletionFlag')

    # organize all shapes into airspaces
    area_shapes = {}
    airport_shapes = {}
    for i, f in enumerate(shp.shapeRecords()):
        id = f.record[id_index]
        ident = f.record[ident_index]
        type_code = f.record[type_code_index]
        type_class = type_code[6:]
        if len(id) == 0:
            id = f"A-{shape_name(ident)}"
        elif len(id) == 3:
            id = f"K{id}-{type_class}"
        elif len(id) == 4:
            id = f"{id}-{type_class}"
        else:
            assert False, f"bad id: {id}"

        if f.shape.points[0] != f.shape.points[-1]:
            print(f"{id}: shape not closed")
            continue

        # create an airport or area (if needed)
        shapes = airport_shapes if type_class in ('B', 'C', 'D', 'E2', 'E3', 'E4') else area_shapes
        if id not in shapes:
            shapes[id] = {
                'id': id,
                'ident': ident,
                #'name': f.record[name_index],
                'comm_name': f.record[comm_name_index],
                'type_code': type_code,
                'class': type_code[6:],
                'sector': f.record[sector_index],
                'local_type': f.record[local_type_index],
                'bbox': util.bbox_init(),
                'delete': f.record[delete_index],
                'exclusion': f.record[exclusion_index],
                'hours': (f.record[wkhr_code_index], f.record[wkhr_rmk_index]),
                'regions': []
            }
        shape = shapes[id]
        assert shape['id'] == id
        assert shape_name(shape['ident']) == shape_name(ident), f"{shape['ident']} != {ident}"
        assert shape['class'] == type_code[6:], "{shape['class']} != {type_code[6:]}, {shape}"
        assert shape['type_code'] == type_code, f"{shape['type_code']} != {type_code}, {shape}"
        assert shape['local_type'] == f.record[local_type_index], f"{shape['local_type']} != {f.record[local_type_index]}"
        assert shape['delete'] == f.record[delete_index]
        assert shape['comm_name'] == f.record[comm_name_index]
        assert shape['sector'] == f.record[sector_index]
        assert shape['exclusion'] == f.record[exclusion_index]
        assert shape['hours'] == (f.record[wkhr_code_index], f.record[wkhr_rmk_index])

        # get relevant parameters region parameters
        lower = util.f2m * abs(float(f.record[lower_desc_index]))
        upper = util.f2m * abs(float(f.record[upper_desc_index]))
        if lower == 0 and f.record[lower_uom_index] == 'SFC':
            lower = util.SFC

        bbox = util.bbox_init()
        for pt in f.shape.points[:-1]:
            bbox = util.bbox_add(bbox, pt)

        region = {
            'id': i,
            'bbox': bbox,
            'lower': (
                lower,
                float(f.record[lower_desc_index]),
                f.record[lower_val_index],
                f.record[lower_uom_index],
                f.record[lower_code_index],
            ),
            'upper': (
                upper,
                float(f.record[upper_desc_index]),
                f.record[upper_val_index],
                f.record[upper_uom_index],
                f.record[upper_code_index],
            ),
            'level': f.record[level_index],
            'onshore': f.record[onshore_index] != '0',
        }
        shape['regions'].append(region)
        shape['bbox'] = util.bbox_union(shape['bbox'], bbox)

    airport_shapes_table = settings.db.hash_table("airport_shapes")
    airport_shapes_table.clear()
    for i, shape in enumerate(airport_shapes.values()):
        airport_shapes_table.set(shape['id'], shape)
    print(f"found {airport_shapes_table.count()} airport shapes")

    area_shapes_table = settings.db.hash_table("area_shapes")
    area_shapes_table.clear()
    for i, shape in enumerate(area_shapes.values()):
        area_shapes_table.set(shape['id'], shape)
    print(f"found {area_shapes_table.count()} area shapes")
    #print(names)


if __name__ == "__main__":
    if False:
        download_chart_shapes()
    if True:
        process_chart_shapes()

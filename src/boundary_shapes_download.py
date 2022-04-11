# (c)2018, Arthur van Hoff

import os, requests, lxml.etree, urllib.parse, zipfile, shutil, shapefile
import settings, util, unicodedata, re

def shape_name(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.upper())
    value = re.sub(r'[-\s]+', '-', value).strip('-_')
    return value.replace(' ', '-').replace('-CLASS-','-')

def download_boundary_shapes():
    url = settings.boundaries_url

    #
    # download the file
    #

    name = "Airspace_Boundary.zip"
    zip_path = os.path.join(settings.charts_source_dir, name)
    util.download_file(url, zip_path)

    #
    # extract the file
    #

    zip_dir = os.path.splitext(zip_path)[0]
    os.makedirs(zip_dir, exist_ok=True)

    print("extracting", zip_path, "to", zip_dir)
    with zipfile.ZipFile(zip_path) as zip:
        zip.extractall(zip_dir)

def process_boundary_shapes():
    # see https://aeronav.faa.gov/Open_Data_Supp/Data_Dictionary.pdf
    path = os.path.join(settings.charts_source_dir, "Airspace_Boundary/Airspace_Boundary.shp")
    shp = shapefile.Reader(path)
    names = [field[0] for field in shp.fields]
    #id_index = names.index('OBJECTID')
    #name_index = names.index('NAME')
    ident_index = names.index('IDENT')
    icao_id_index = names.index('ICAO_ID')
    #class_index = names.index('CLASS')
    #mil_code_index = names.index('MIL_CODE')
    comm_name_index = names.index('COMM_NAME')
    level_index = names.index('LEVEL_')
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
    shapes = {}
    for i, f in enumerate(shp.shapeRecords()):
        #id = str(f.record[id_index])
        ident = f.record[ident_index]
        type_code = f.record[type_code_index]

        # create airspace (if needed)
        if ident not in shapes:
            shapes[ident] = {
                'ident': ident,
                #'name': f.record[name_index],
                'icao_id': f.record[icao_id_index],
                'type_code': type_code,
                'class': type_code[6:],
                'local_type': f.record[local_type_index],
                'bbox': util.bbox_init(),
                'delete': f.record[delete_index],
                'hours': (f.record[wkhr_code_index], f.record[wkhr_rmk_index]),
                'regions': []
            }
        shape = shapes[ident]
        #assert shape['id'] == id, f"{id}, {shape}"
        assert shape_name(shape['ident']) == shape_name(ident), f"{shape['ident']} != {ident}"
        assert shape['class'] == type_code[6:], "{shape['class']} != {type_code[6:]}, {shape}"
        assert shape['type_code'] == type_code, f"{shape['type_code']} != {type_code}, {shape}"
        assert shape['local_type'] == f.record[local_type_index], f"{shape['local_type']} != {f.record[local_type_index]}"
        #assert shape['delete'] == f.record[delete_index], f"{f.record[delete_index]}, {shape}"
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
            'sector': f.record[sector_index],
            'comm_name': f.record[comm_name_index],
            'exclusion': f.record[exclusion_index],
        }
        shape['regions'].append(region)
        shape['bbox'] = util.bbox_union(shape['bbox'], bbox)

        if f.shape.points[0] != f.shape.points[-1]:
            print(f"{id}, {ident}: shape not closed")
            print(shape)

    boundary_shapes_table = settings.db.hash_table("boundary_shapes")
    boundary_shapes_table.clear()
    for i, shape in enumerate(shapes.values()):
        boundary_shapes_table.set(shape['id'], shape)
    print(f"found {boundary_shapes_table.count()} boundary shapes")

    print(names)


if __name__ == "__main__":
    if False:
        download_boundary_shapes()
    if True:
        process_boundary_shapes()

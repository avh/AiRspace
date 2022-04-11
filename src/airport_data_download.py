# (c)2022 Artfahrt Inc, Arthur van Hoff

import os, openpyxl, datetime, math, tqdm
import util, settings

def download_airport_data():
    xlsx_path = os.path.join(settings.charts_source_dir, 'all_airports.xlsx')
    util.download_file(settings.all_airport_data_url, xlsx_path)

def toDegrees(sec):
    sign = 1 if sec[-1] in ('E','N') else -1
    sec = float(sec[:-1])
    h = math.floor(sec / 3600)
    m = math.floor(sec / 60) % 60
    s = sec % 60
    return sign * (h + m/60 + s/3600)

def process_airport_data():
    xlsx_path = os.path.join(settings.charts_source_dir, 'all_airports.xlsx')
    wb = openpyxl.load_workbook(xlsx_path)
    sheet = wb.active
    print(f"found {sheet.max_row} airports ({sheet.max_column} columns)")
    col_names = []
    for column in sheet.iter_cols(1, sheet.max_column):
        col_names.append(column[0].value)

    if False:
        print(col_names)

    loc_id_index = col_names.index('Loc Id')
    icao_id_index = col_names.index('Icao Id')

    airports = settings.db.hash_table('airports')
    airports.clear()
    for r, row in tqdm.tqdm(enumerate(sheet.iter_rows(1, sheet.max_row)), total=sheet.max_row):
        if r > 0:
            airport = {}
            for c in range(1, sheet.max_column):
                v = row[c].value
                if v is not None and v != '':
                    if isinstance(v, datetime.datetime):
                        v = v.strftime("%m/%d/%Y")
                    airport[col_names[c]] = v
            id = row[icao_id_index].value
            if id is None or len(id) != 4:
                id = row[loc_id_index].value

            airport['id'] = id
            airport['Latitude'] = toDegrees(airport['ARP Latitude Sec'])
            airport['Longitude'] = toDegrees(airport['ARP Longitude Sec'])
            del airport['ARP Latitude']
            del airport['ARP Latitude Sec']
            del airport['ARP Longitude']
            del airport['ARP Longitude Sec']
            #print(airport)
            assert airports.get(id) is None
            airports.set(id, airport)

if __name__ == "__main__":
    if True:
        download_airport_data()
    if True:
        process_airport_data()

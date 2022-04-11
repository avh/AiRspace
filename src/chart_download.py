# (c)2018-2020, Artfahrt Inc, Arthur van Hoff

import os, zipfile
import settings, util

def download_chart(chart):
    path = chart['path']
    if os.path.exists(path):
        return

    zip_path = util.download_file(chart['href'])
    if zip_path is None:
        return

    try:
        with zipfile.ZipFile(zip_path) as zip:
            zip.extractall(settings.tmp_dir)
            print("installing", chart['name'])
            os.makedirs(path, exist_ok=True)
            for name in zip.namelist():
                os.rename(os.path.join(settings.tmp_dir, name), os.path.join(path, name))
    except zipfile.BadZipFile:
        print("%s: bad zipfile" % (zip_path))
    finally:
        #os.remove(zip_path)
        pass


#
# Download charts
#

if __name__ == '__main__':
    sec_list = settings.db.hash_table("sec_list")
    for chart in sec_list.all():
        download_chart(chart)

    tac_list = settings.db.hash_table("tac_list")
    for chart in tac_list.all():
        download_chart(chart)

    heli_list = settings.db.hash_table("heli_list")
    for chart in heli_list.all():
        download_chart(chart)

    plan_list = settings.db.hash_table("plan_list")
    for chart in plan_list.all():
        download_chart(chart)

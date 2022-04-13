# (c)2018-2020, Artfahrt Inc, Arthur van Hoff

import os, zipfile, time, multiprocessing
import settings, util

max_download_workers = 8

def download_chart(q):
    while True:
        task = q.get()
        if task[0] == 'done':
            break

        chart = task[1]
        path = chart['path']
        if os.path.exists(path):
            continue

        zip_path = util.download_file(chart['href'])
        if zip_path is None:
            continue

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

def download_charts(list_name, max_workers=max_download_workers):
    chart_list = settings.db.hash_table(list_name)
    max_workers = min(chart_list.count(), max_workers)

    q = ctx.Queue(max_workers*2)
    workers = [ctx.Process(target=download_chart, args=(q,)) for _ in range(max_workers)]
    for w in workers:
        w.start()
    for chart in chart_list.all():
        q.put(('chart', chart))
    for _ in range(max_workers):
        q.put(('done', ))
    for w in workers:
        w.join()


#
# Download charts
#

if __name__ == '__main__':
    ctx = multiprocessing.get_context('spawn')
    tm = time.time()
    download_charts("sec_list")
    download_charts("tac_list")
    download_charts("heli_list")
    download_charts("plan_list")
    download_charts("ifr_low_list")
    download_charts("ifr_high_list")
    download_charts("ifr_area_list")
    print(f"done in {util.time_str(tm)}")

# (c)2018, Arthur van Hoff

import requests, os, datetime, dateutil.parser, locale, zipfile, sys, glob, lxml.etree
import settings, util, download

#
# download all the chart files
#

chart_urls = []

for url in chart_urls:
    filename = os.path.basename(url)
    name = os.path.splitext(filename)[0]
    dst = os.path.join(settings.charts_source_dir, filename)
    headers = {}
    if os.path.exists(dst):
        mtime = datetime.datetime.utcfromtimestamp(os.path.getctime(dst))
        headers['if-modified-since'] = mtime.strftime(locale.nl_langinfo(locale.D_T_FMT))

    req = requests.get(url=url, headers=headers, stream=True)
    if req.status_code == 304:
        print("%s: skipping" % (filename))
        continue
    if req.status_code == 404:
        print("%s: not found" % (url))
        continue
    if req.status_code != 200:
        print("%s: failed, code=%d" % (url, req.status_code))
        break

    clen = int(req.headers['content-length'])
    tmp = os.path.join(settings.tmp_dir, filename)
    if not os.path.exists(tmp) or os.path.getsize(tmp) != clen:
        total = 0
        with open(tmp, 'wb') as out:
            for chunk in req.iter_content(chunk_size=100*1024):
                out.write(chunk)
                total += len(chunk)
                sys.stdout.write("\r                                                                \r")
                sys.stdout.write("%s: %2.3f%% of %dMB" % (filename, 100 * total / clen, clen//(1024*1024)))
                sys.stdout.flush()

    sys.stdout.write("\r                                                                \r")
    sys.stdout.flush()
    print("downloaded %s" % (tmp))
    try:
        dst_dir = os.path.join(dst, os.path.splitext(filename)[0])
        if not os.path.exists(dst_dir):
            os.mkdir(dst_dir)
        with zipfile.ZipFile(tmp) as zip:
            zip.extractall(settings.tmp_dir)
            for path in glob.glob(os.path.join(dst_dir, "*.*")):
                os.remove(path)
            for name in zip.namelist():
                os.rename(os.path.join(settings.tmp_dir, name), os.path.join(settings.charts_source_dir, name.replace(' ', '_')))
        os.rename(tmp, os.path.join(settings.charts_source_dir, filename))
    except zipfile.BadZipFile:
        print("%s: bad zipfile" % (tmp))
        #os.remove(tmp)

def download_chart(chart):
    path = chart['path']
    if os.path.exists(path):
        return

    zip_path = download.download_file(chart['href'])
    if zip_path is None:
        return

    try:
        with zipfile.ZipFile(zip_path) as zip:
            zip.extractall(settings.tmp_dir)
            print("installing", chart['name'])
            os.mkdir(path)
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

sec_list = settings.db.hash_table("sec_list")
for sec in sec_list.all():
    download_chart(sec)

tac_list = settings.db.hash_table("tac_list")
for tac in tac_list.all():
    download_chart(tac)

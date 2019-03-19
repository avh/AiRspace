# (c)2019, Arthur van Hoff
import os, sys, requests
import settings

def download_file(url, dst=None):
    filename = os.path.basename(url)
    if dst is None:
        dst = os.path.join(settings.tmp_dir, os.path.basename(url))
    if os.path.exists(dst):
        return dst

    req = requests.get(url=url, stream=True)
    if req.status_code != 200:
        print("failed to download %s" % (url))
        return None

    clen = int(req.headers['content-length'])
    tmp = dst + ".partial"
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
    print("downloaded %s, %dMB" % (filename, clen//(1024*1024)))
    os.rename(tmp, dst)
    return dst

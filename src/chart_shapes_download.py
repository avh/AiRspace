# (c)2018, Arthur van Hoff

import os, requests, lxml.etree, urllib.parse, zipfile, shutil
import settings, util

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

for t in html.xpath(".//a[text()='Download']"):
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

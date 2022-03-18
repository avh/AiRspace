# (c)2018, Arthur van Hoff

import os, requests, lxml.etree
import settings

#
# Scan the FAA digital products page for the current list of SEC and TAC charts.
#

req = requests.get(url=settings.faa_chart_url)

html = lxml.etree.HTML(req.text)
sec_list = settings.db.hash_table("sec_list")
sec_list.clear()
col = 1

for tr in html.xpath(".//div[@id='sectional']/table/tbody/tr"):
    name = ''.join(tr[0].text)
    date = ''.join(tr[col].text)
    href = tr[col].find(".//a").attrib["href"]
    sec = {
        'name': name,
        'type': 'sec',
        'current': col == 1,
        'date': date,
        'href': href,
        'path': "data/charts/source/" + os.path.splitext(os.path.basename(href))[0]
    }
    #print(sec)
    sec_list.set(name, sec)

for tr in html.xpath(".//div[@id='caribbean']/table/tbody/tr"):
    name = ''.join(tr[0].text)
    date = ''.join(tr[col].text)
    href = tr[col].find(".//a").attrib["href"]
    sec = {
        'name': name,
        'type': 'sec',
        'current': col == 1,
        'date': date,
        'href': href,
        'path': "data/charts/source/" + os.path.splitext(os.path.basename(href))[0]
    }
    #print(sec)
    sec_list.set(name, sec)

tac_list = settings.db.hash_table("tac_list")
tac_list.clear()
for tr in html.xpath(".//div[@id='terminalArea']/table/tbody/tr"):
    name = ''.join(tr[0].text)
    date = ''.join(tr[col].text)
    href = tr[col].find(".//a").attrib["href"]
    tac = {
        'name': name,
        'type': 'tac',
        'current': col == 1,
        'date': date,
        'href': href,
        'path': "data/charts/source/" + os.path.splitext(os.path.basename(href))[0]
    }
    #print(tac)
    tac_list.set(name, tac)

for tr in html.xpath(".//div[@id='grandCanyon']/table/tbody/tr"):
    name = ''.join(tr[0].text)
    date = ''.join(tr[col].text)
    href = tr[col].find(".//a").attrib["href"]
    tac = {
        'name': name,
        'type': 'tac',
        'current': col == 1,
        'date': date,
        'href': href,
        'path': "data/charts/source/" + os.path.splitext(os.path.basename(href))[0]
    }
    #print(tac)
    tac_list.set(name, tac)

print("%d sectional charts" % (sec_list.count()))
print("%d terminal area charts" % (sec_list.count()))

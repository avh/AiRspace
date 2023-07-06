# (c)2023, Arthur van Hoff, Artfahrt Inc. 

import os, requests, lxml.html, lxml.etree
from dateutil import parser
from common.datastore import DataStore
import settings

#
# Scan the FAA digital products page for the current list of SEC and TAC charts.
#
def update_chart_list(table, html, tag, kind):
    count = 0
    for tr in html.xpath(f".//div[@id='{tag}']/table/tbody/tr"):
        name = ''.join(tr[0].text).strip()
        date = parser.parse(tr[1].text).strftime('%y-%m-%d')
        next = parser.parse(tr[2].text if tr[2].text else tr[2][0].text).strftime('%y-%m-%d') 
        href = tr[1].find(".//a").attrib["href"]
        old = table[name]
        if old is None or old['date'] != date:
            table[name] = {
                'name': name,
                'type': kind,
                'date': date,
                'next': next,
                'href': href,
                'path': f"data/charts/{date}/{kind}/{os.path.splitext(os.path.basename(href))[0]}"
            }
            count += 1
    return count

def lambda_handler(event, context):
    db = DataStore()
    table = db['chart_list']
    #table.clear()
    count = 0

    if True:
        req = requests.get(url=settings.faa_vfr_chart_url)
        html = lxml.etree.HTML(req.text)

        count += update_chart_list(table, html, 'sectional', 'sec')
        count += update_chart_list(table, html, 'caribbean', 'sec')

        count += update_chart_list(table, html, 'terminalArea', 'tac')
        count += update_chart_list(table, html, 'grandCanyon', 'tac')

        count += update_chart_list(table, html, 'helicopter', 'hel')
        count += update_chart_list(table, html, 'Planning', 'pln')

    if True:
        req = requests.get(url=settings.faa_ifr_chart_url)
        html = lxml.etree.HTML(req.text)

        count += update_chart_list(table, html, 'lowsHighsAreas', 'ifr')
        count += update_chart_list(table, html, 'caribbean', 'ifr')
        count += update_chart_list(table, html, 'gulf', 'ifr')

    return {'rows':len(table), 'updates':count}

if __name__ == '__main__':
    print(lambda_handler(None, None))
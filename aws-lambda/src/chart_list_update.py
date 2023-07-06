# (c)2023, Arthur van Hoff, Artfahrt Inc. 

import os, requests, lxml.html, lxml.etree
from dateutil import parser

faa_vfr_chart_url = "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/vfr/"
faa_ifr_chart_url = "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/ifr/"

#
# Scan the FAA digital products page for the current list of SEC and TAC charts.
#
def update_chart_list(html, tag, kind, table):
    for tr in html.xpath(f".//div[@id='{tag}']/table/tbody/tr"):
        name = ''.join(tr[0].text).strip()
        date = parser.parse(''.join(tr[1].text)).strftime('%y-%m-%d')
        next = parser.parse(''.join(tr[2].text)).strftime('%y-%m-%d')
        href = tr[1].find(".//a").attrib["href"]
        sec = {
            'name': name,
            'type': kind,
            'date': date,
            'next': next,
            'href': href,
            'path': "data/charts/" + date + '/' + os.path.splitext(os.path.basename(href))[0]
        }
        table[name] = sec

def lambda_handler(event, context):
    result = {}

    if True:
        req = requests.get(url=faa_vfr_chart_url)
        html = lxml.etree.HTML(req.text)

        sec_list = {}
        update_chart_list(html, 'sectional', 'sec', sec_list)
        update_chart_list(html, 'caribbean', 'sec', sec_list)

        tac_list = {}
        update_chart_list(html, 'terminalArea', 'tac', tac_list)
        update_chart_list(html, 'grandCanyon', 'tac', tac_list)

        hel_list = {}
        update_chart_list(html, 'helicopter', 'hel', hel_list)

        pln_list = {}
        update_chart_list(html, 'Planning', 'pln', pln_list)

        result['VFR sectional charts'] = sec_list
        result['VFR terminal area charts'] = tac_list
        result['VFR helicopter charts'] = hel_list
        result['VFR planning charts'] = pln_list

    if True:
        req = requests.get(url=faa_ifr_chart_url)
        html = lxml.etree.HTML(req.text)

        ifr_list = {}

        update_chart_list(html, 'lowsHighsAreas', 'ifr', ifr_list)
        update_chart_list(html, 'caribbean', 'ifr', ifr_list)
        update_chart_list(html, 'gulf', 'ifr', ifr_list)

        result['IFR charts'] = ifr_list

    return result



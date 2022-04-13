# (c)2018-2022, Artfhart Inc, Arthur van Hoff

import os, requests, lxml.html, lxml.etree, dateutil, time
import settings, util

#
# Scan the FAA digital products page for the current list of SEC and TAC charts.
#
def update_chart_list(html, tag, kind, table, col=1):
    for tr in html.xpath(f".//div[@id='{tag}']/table/tbody/tr"):
        name = ''.join(tr[0].text).strip()
        date = dateutil.parser.parse(''.join(tr[col].text)).strftime('%y-%m-%d')
        href = tr[col].find(".//a").attrib["href"]
        sec = {
            'name': name,
            'type': kind,
            'date': date,
            'href': href,
            'path': "data/charts/" + date + '/' + os.path.splitext(os.path.basename(href))[0]
        }
        table.set(name, sec)

if __name__ == '__main__':
    tm = time.time()

    if True:
        req = requests.get(url=settings.faa_vfr_chart_url)
        html = lxml.etree.HTML(req.text)

        sec_list = settings.db.hash_table("sec_list")
        sec_list.clear()
        update_chart_list(html, 'sectional', 'sec', sec_list)
        update_chart_list(html, 'caribbean', 'sec', sec_list)

        tac_list = settings.db.hash_table("tac_list")
        tac_list.clear()
        update_chart_list(html, 'terminalArea', 'tac', tac_list)
        update_chart_list(html, 'grandCanyon', 'tac', tac_list)

        hel_list = settings.db.hash_table("hel_list")
        hel_list.clear()
        update_chart_list(html, 'helicopter', 'hel', hel_list)

        pln_list = settings.db.hash_table("pln_list")
        update_chart_list(html, 'Planning', 'pln', pln_list)


        print(f"{sec_list.count():4} VFR sectional charts")
        print(f"{tac_list.count():4} VFR terminal area charts")
        print(f"{hel_list.count():4} VFR helicopter charts")
        print(f"{pln_list.count():4} VFR planning charts")

    if True:
        req = requests.get(url=settings.faa_ifr_chart_url)
        html = lxml.etree.HTML(req.text)

        ifr_list = settings.db.hash_table("ifr_list")
        ifr_list.clear()
        update_chart_list(html, 'lowsHighsAreas', 'ifr', ifr_list)
        ifr_low_list = settings.db.hash_table("ifr_low_list")
        ifr_high_list = settings.db.hash_table("ifr_high_list")
        ifr_area_list = settings.db.hash_table("ifr_area_list")
        for s in ifr_list.all():
            name = s['name']
            if name.startswith("EL"):
                ifr_low_list.set(name, s)
            elif name.startswith("EH"):
                ifr_high_list.set(name, s)
            elif name.startswith("EPHI"):
                ifr_high_list.set(name, s)
            elif name.startswith("Area"):
                ifr_area_list.set(name, s)

        print(f"{ifr_low_list.count():4} IFR low charts")
        print(f"{ifr_high_list.count():4} IFR high charts")
        print(f"{ifr_area_list.count():4} IFR area charts")

    print(f"done in {util.time_str(tm)}")

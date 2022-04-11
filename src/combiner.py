
import json, glob,os
import settings, util

def bounds_init():
    return (util.MAXINT, util.MAXINT, util.MININT, util.MININT, util.MAXINT, util.MININT)

def bounds_union(b1, b2):
    return (
        min(b1[0], b2[0]), min(b1[1], b2[1]),
        max(b1[2], b2[2]), max(b1[3], b2[3]),
        min(b1[4], b2[4]), max(b1[5], b2[5]),
    )

def save_area(dir, id, flyto, airports):
    print(f"{dir}/{id}, {len(airports)}")

    clazz = 'E5'
    for airport in airports:
        if airport['extras']['class'] < clazz:
            clazz = airport['extras']['class']

    geometricError = settings.defaultGeometricError[clazz]
    bounds = bounds_init()
    for a in airports:
        bounds = bounds_union(bounds, a['root']['boundingVolume']['region'])

    tile = {
        "asset": {
            "version": "1.0",
            "tilesetVersion": "1.2.3",
        },
        "extras": {
            "class": clazz,
            "height": settings.defaultHeight[clazz],
            "id": id,
            "flyto": flyto,
        },
        "geometricError": geometricError,
        "root": {
            "geometricError": geometricError,
            "refine": "ADD",
            "boundingVolume": {"region": bounds},
            "children": [
                {
                    'boundingVolume': a['root']['boundingVolume'],
                    'geometricError': geometricError,
                    'content': {
                        'uri':a['root']['content']['uri'],
                    }
                } for a in airports
            ],
            "transform": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        },
    }
    with open(os.path.join(dir, f"{id}.json"), 'wb') as out:
        out.write(json.dumps(tile, sort_keys=True, indent=4).encode('utf-8'))


def combine_airports(dir):
    airport_classes = {
        'B': {},
        'C': {},
        'D': {},
        'E': {},
        'E1': {},
        'E2': {},
        'E3': {},
        'E4': {},
        'E5': {},
    }
    areas = {}
    for airport_file in glob.glob(os.path.join(dir, "*-*.json")):
        with open(airport_file) as f:
            data = json.load(f)
        if 'content' not in data['root']:
            continue
        airport_classes[data['extras']['class']][data['extras']['id']] = data
        id = data['extras']['id']
        id = id[:id.rindex('-')]
        if id not in areas:
            areas[id] = []
        areas[id].append(data)

    for clazz, airports in airport_classes.items():
        save_area(dir, f"CLASS_{clazz}", False, airports.values())
    for id, airports in areas.items():
        save_area(dir, id, True, airports)


if __name__ == '__main__':
    combine_airports(settings.airports_dir + "-1x")
    combine_airports(settings.airports_dir + "-5x")

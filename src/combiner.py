
import json, glob,os
import settings, util

defaultGeometricError = {
    'A': 20000,
    'B': 18000,
    'C': 16000,
    'D': 14000,
    'E': 12000,
    'G': 10000,
}
defaultHeight = {
    'A': 50000,
    'B': 40000,
    'C': 40000,
    'D': 40000,
    'E': 40000,
    'G': 40000,
}

def bounds_init():
    return (util.MAXINT, util.MAXINT, util.MININT, util.MININT, util.MAXINT, util.MININT)

def bounds_union(b1, b2):
    return (
        min(b1[0], b2[0]), min(b1[1], b2[1]),
        max(b1[2], b2[2]), max(b1[3], b2[3]),
        min(b1[4], b2[4]), max(b1[5], b2[5]),
    )

def save_airports(dir, clazz, airports):
    print(f"{dir}/CLASS_{clazz}, {len(airports)}")

    geometricError = defaultGeometricError[clazz]
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
            "height": defaultHeight[clazz],
            "id": f"CLASS_{clazz}",
            "flyto": False,
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
    with open(os.path.join(dir, f"CLASS_{clazz}.json"), 'wb') as out:
        out.write(json.dumps(tile, sort_keys=True, indent=4).encode('utf-8'))


def combine_airports(dir):
    airport_classes = {
        'B': {},
        'C': {},
        'D': {},
        'E': {},
    }
    for airport_file in glob.glob(os.path.join(dir, "K*.json")):
        with open(airport_file) as f:
            data = json.load(f)
        airport_classes[data['extras']['class']][data['extras']['id']] = data

    for clazz, airports in airport_classes.items():
        save_airports(dir, clazz, airports.values())


if __name__ == '__main__':
    combine_airports(settings.airports_dir)

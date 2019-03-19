# (c)2018, Arthur van Hoff

import math, os, numpy
import settings

def tile_name(lonlat):
    return "%s%d%s%d" % ('s' if lonlat[1] < 0 else 'n', abs(lonlat[1]), 'w' if lonlat[0] < 0 else 'e', abs(lonlat[0]))

class Elevations:
    def __init__(self):
        self.tiles = {}

    def get(self, lonlat):
        lon_i = int(math.floor(lonlat[0]))
        lat_i = int(math.floor(lonlat[1]))
        name = tile_name((lon_i, lat_i + 1))
        if name in self.tiles:
            data = self.tiles[name]
        else:
            tile_path = os.path.join(settings.elevations_dir, name + ".npy")
            try:
                data = numpy.load(tile_path)
                #print("found", tile_path)
            except IOError:
                print("tile not found", name)
                data = None
            self.tiles[name] = data
        if data is None:
            return -50

        x = int((lonlat[0] - lon_i) * data.shape[1])
        y = (data.shape[0]-1) - int((lonlat[1] - lat_i) * data.shape[0])
        return data[y][x]

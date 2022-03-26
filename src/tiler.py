# (c)2019, Artfahrt Inc by Arthur van Hoff

import os, pyproj, json
import util

class Tiler:
    TerrainExaggeration = 5

    def __init__(self):
        self.ecef_proj = pyproj.Proj(proj='geocent', ellps='WGS84', datum='WGS84')
        self.lla_proj = pyproj.Proj(proj='latlong', ellps='WGS84', datum='WGS84')
        self.region = None

    # convert lon,lat,alt to x,y,z
    def lla2xyz(self, lla):
        if self.region is None:
            self.region = [lla[0], lla[1], lla[0], lla[1], lla[2], lla[2]]
        else:
            self.region[0] = min(self.region[0], lla[0])
            self.region[1] = min(self.region[1], lla[1])
            self.region[2] = max(self.region[2], lla[0])
            self.region[3] = max(self.region[3], lla[1])
            self.region[4] = min(self.region[4], lla[2])
            self.region[5] = max(self.region[5], lla[2])

        if lla[2] < -1000:
            raise Exception("bad altitude: " + lla)
        return pyproj.transform(self.lla_proj, self.ecef_proj, lla[0], lla[1], lla[2]*Tiler.TerrainExaggeration, radians=False)

    # convert x,y,z to lon,lat,alt
    def xyz2lla(self, xyz):
        lla = pyproj.transform(self.ecef_proj, self.lla_proj, *xyz, radians=False)
        return (lla[0], lla[1], lla[2]/Tiler.TerrainExaggeration)

    # expand a region given a lla
    def expand_region(self, reg, lla):
        reg[0] = min(reg[0], lla[0])
        reg[1] = min(reg[1], lla[1])
        reg[2] = max(reg[2], lla[0])
        reg[3] = max(reg[3], lla[1])
        reg[4] = min(reg[4], lla[2])
        reg[5] = max(reg[5], lla[2])

    # compute the region occupied by a gltf
    def gltf_region(self, gltf):
        lon, lat, alt = self.xyz2lla(gltf.vmin)
        if alt < -1000:
            raise Exception("bad altitude: " + (lon, lat, alt))
        reg = [lon, lat, lon, lat, alt, alt]
        self.expand_region(reg, self.xyz2lla((gltf.vmax[0], gltf.vmin[1], gltf.vmin[2])))
        self.expand_region(reg, self.xyz2lla((gltf.vmin[0], gltf.vmax[1], gltf.vmin[2])))
        self.expand_region(reg, self.xyz2lla((gltf.vmin[0], gltf.vmin[1], gltf.vmax[2])))
        self.expand_region(reg, self.xyz2lla((gltf.vmin[0], gltf.vmax[1], gltf.vmax[2])))
        self.expand_region(reg, self.xyz2lla((gltf.vmax[0], gltf.vmin[1], gltf.vmax[2])))
        self.expand_region(reg, self.xyz2lla((gltf.vmax[0], gltf.vmax[1], gltf.vmin[2])))
        self.expand_region(reg, self.xyz2lla((gltf.vmax[0], gltf.vmax[1], gltf.vmax[2])))
        return reg

    # convert a region in degrees to radians
    def region_rad(self, reg):
        return [reg[0]*util.d2r, reg[1]*util.d2r, reg[2]*util.d2r, reg[3]*util.d2r, reg[4], reg[5]]

    # generate a tile for a single gltf object
    def save_tile(self, dir, name, gltf, geometricError=5000, extras=None):
        if self.region is None:
            return

        path = os.path.join(dir, name)
        gltf.save(path + ".b3dm")
        #gltf.save(path + ".gltf")
        #gltf.save(path + ".glb")

        tile = {
            "asset": {
                "version": "1.0",
                "tilesetVersion": "1.2.3",
            },
            "geometricError": geometricError,
            "root": {
                "boundingVolume": {
                    "region": self.region_rad(self.region),
                },
                "geometricError": 0,
                "refine": "ADD",
                "content": {
                    "boundingVolume": {
                        "region": self.region_rad(self.region),
                    },
                    "uri": name + ".b3dm"
                },
                "transform": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
                "children": [],
            },
        }
        if extras is not None:
            tile["extras"] = extras

        with open(path + ".json", 'wb') as out:
            out.write(json.dumps(tile, sort_keys=True, indent=4).encode('utf-8'))

        self.region = None

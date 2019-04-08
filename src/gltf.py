# (c)2019, Artfahrt Inc by Arthur van Hoff
# Wrapper class for generating GLTF

import os, io, json, struct, math

LINES = 1
TRIANGLES = 4

VERTICES = 34962
NORMALS = 34962
INDICES = 34963

USHORT = 5123
UINT = 5125
FLOAT = 5126

class GLTF:
    def __init__(self):
        self.scenes = [{
            "nodes": []
        }]
        self.nodes = []
        self.meshes = []
        self.bufferViews = []
        self.accessors = []
        self.materials = []
        self.buffer = None
        self.v_hash = {}
        self.v_list = []
        self.n_list = []
        self.i_list = []
        self.vmin = None
        self.vmax = None
        self.rgbas = {}

    def add_rgba(self, rgba):
        if rgba in self.rgbas:
            return self.rgbas[rgba]

        self.materials.append({
            'pbrMetallicRoughness': {
                'baseColorFactor': rgba,
                'metallicFactor': 0.5,
                'roughnessFactor': 0.5,
            },
            'alphaMode': "OPAQUE" if len(rgba) == 3 or rgba[3] == 1 else "BLEND",
            'doubleSided': True,
        })
        self.rgbas[rgba] = len(self.materials)-1
        return len(self.materials)-1

    def add_vertex(self, v):
        if v in self.v_hash:
            return self.v_hash[v]
        self.v_hash[v] = len(self.v_list)
        self.v_list.append(v)
        self.n_list.append([0, 0, 0])
        return len(self.v_list)-1

    def add_triangle(self, v1, v2, v3):
        if v1 != v2 and v2 != v3 and v1 != v3:
            i1 = self.add_vertex(v1)
            i2 = self.add_vertex(v2)
            i3 = self.add_vertex(v3)
            self.i_list.append((i1, i2, i3))
            # compute triangle normal
            u = (v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2])
            v = (v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2])
            n = (u[1]*v[2] - u[2]*v[1], u[2]*v[0] - u[0]*v[2], u[0]*v[1] - u[1]*v[0])
            # add to vertex normals
            for i in [i1, i2, i3]:
                for j in range(0, 3):
                    self.n_list[i][j] += n[j]

    def add_quad(self, v1, v2, v3, v4):
        self.add_triangle(v1, v2, v3)
        self.add_triangle(v1, v3, v4)

    def add_line(self, v1, v2):
        if v1 != v2:
            self.i_list.append((self.add_vertex(v1), self.add_vertex(v2)))

    def add_cylinder(self, v, h1, h2, r, n=20):
        rads = [2*math.pi*i/n for i in range(n)]
        l1 = [(v[0] + r*math.sin(a), v[1] + h1, v[2] + r*math.cos(a)) for a in rads]
        l2 = [(v[0] + r*math.sin(a), v[1] + h2, v[2] + r*math.cos(a)) for a in rads]
        for i in range(n):
            self.add_quad(l1[i], l1[(i+1) % n], l2[(i+1) % n], l2[i])

    def add_mesh(self, material=None, normals=False):
        if len(self.i_list) == 0:
            return

        if len(self.i_list[0]) == 2:
            mode = LINES
        elif len(self.i_list[0]) == 3:
            mode = TRIANGLES
        else:
            raise Exception("invalid indices")

        primitive = {
            "mode": mode,
            "indices": self.add_indices(),
            "attributes": {
                "POSITION": self.add_vertices(),
            },
        }
        if normals:
            primitive["attributes"]["NORMAL"] = self.add_normals()
        if material is not None:
            primitive["material"] = material

        self.scenes[-1]["nodes"].append(len(self.nodes))
        self.nodes.append({"mesh":len(self.meshes)})
        self.meshes.append({"primitives": [primitive]})

        self.v_hash = {}
        self.v_list = []
        self.i_list = []
        return len(self.meshes)-1

    def add_vertices(self):
        vsize = struct.calcsize("<fff")
        vdata = bytearray(vsize * len(self.v_list) + 4 - (vsize * len(self.v_list)) % 4)
        for i, v in enumerate(self.v_list):
            struct.pack_into("<fff", vdata, i*vsize, *v)
        #print(len(self.v_list), "vertices", len(vdata), "bytes")

        vmin = self.v_list[0]
        vmax = vmin
        for v in self.v_list:
            vmin = [min(vmin[i], v[i]) for i in range(0, 3)]
            vmax = [max(vmax[i], v[i]) for i in range(0, 3)]
        self.vmin = vmin if self.vmin is None else [min(vmin[i], self.vmin[i]) for i in range(0, 3)]
        self.vmax = vmax if self.vmax is None else [max(vmax[i], self.vmax[i]) for i in range(0, 3)]

        self.bufferViews.append({
            "buffer": 0,
            "byteOffset": len(self.buffer),
            "byteLength": len(vdata),
            "target": VERTICES,
        })

        self.accessors.append({
            "bufferView": len(self.bufferViews)-1,
            "byteOffset": 0,
            "componentType": FLOAT,
            "type": "VEC3",
            "count": len(self.v_list),
            "min": vmin,
            "max": vmax,
        })

        self.buffer = self.buffer + vdata
        return len(self.accessors)-1

    def add_normals(self):
        # normalize normals
        normals = []
        for n in self.n_list:
            nlen = math.sqrt(n[0]**2 + n[1]**2 + n[2]**2)
            normals.append((n[0]/nlen, n[1]/nlen, n[2]/nlen) if nlen > 0 else (0, 0, 0))

        nsize = struct.calcsize("<fff")
        ndata = bytearray(nsize * len(normals) + 4 - (nsize * len(normals)) % 4)
        for i, n in enumerate(normals):
            struct.pack_into("<fff", ndata, i*nsize, *n)
        #print(len(normals), "normals", len(ndata), "bytes")

        nmin = normals[0]
        nmax = nmin
        for n in normals:
            nmin = [min(nmin[i], n[i]) for i in range(0, 3)]
            nmax = [max(nmax[i], n[i]) for i in range(0, 3)]

        self.bufferViews.append({
            "buffer": 0,
            "byteOffset": len(self.buffer),
            "byteLength": len(ndata),
            "target": NORMALS,
        })

        self.accessors.append({
            "bufferView": len(self.bufferViews)-1,
            "byteOffset": 0,
            "componentType": FLOAT,
            "type": "VEC3",
            "count": len(self.v_list),
            "min": nmin,
            "max": nmax
        })

        self.buffer = self.buffer + ndata
        return len(self.accessors)-1

    def add_indices(self):
        n = len(self.i_list[0])
        fmt = "<" + "H" * n if n*len(self.i_list) <= 2**16 else "<" + "I" * n
        isize = struct.calcsize(fmt)
        #print("FMT", n, fmt, isize)
        idata = bytearray(isize * len(self.i_list))
        for i, t in enumerate(self.i_list):
            struct.pack_into(fmt, idata, i*isize, *t)
        if len(idata) % 4 != 0:
            idata = idata + bytearray(4 - len(idata) % 4)
        #print(len(self.i_list), "elements", len(idata), "bytes")

        if self.buffer is None:
            self.buffer = bytearray(0)

        self.bufferViews.append({
            "buffer": 0,
            "byteOffset": len(self.buffer),
            "byteLength": len(idata),
            "target": INDICES,
        })

        self.accessors.append({
            "bufferView": len(self.bufferViews)-1,
            "byteOffset": 0,
            "componentType": USHORT if fmt[-1] == "H" else UINT,
            "type": "SCALAR",
            "count": n*len(self.i_list),
            "min": [0],
            "max": [len(self.v_list)-1],
        })

        self.buffer = self.buffer + idata
        return len(self.accessors)-1


    def to_json(self, uri=None):
        obj = {
            "asset": {
                "version": "2.0",
                "generator": "ArtFahrt",
            },
        }
        if len(self.scenes) > 0:
            obj["scenes"] = self.scenes
        if len(self.nodes) > 0:
            obj["nodes"] = self.nodes
        if len(self.meshes) > 0:
            obj["meshes"] = self.meshes
        if len(self.bufferViews) > 0:
            obj["bufferViews"] = self.bufferViews
        if len(self.accessors) > 0:
            obj["accessors"] = self.accessors
        if len(self.materials) > 0:
            obj["materials"] = self.materials

        if self.buffer is not None:
            obj['buffers'] = [{
                'byteLength': len(self.buffer)
            }]
            if uri is not None:
                obj['buffers'][0]['uri'] = uri

        return json.dumps(obj, sort_keys=True, indent=4).encode('utf-8')

    def write_glb(self, out):
        # json
        json = self.to_json()
        if len(json) % 4 != 0:
            json = json + b' ' * (4 - len(json) % 4)
        size = 12 + 8 + len(json)

        # data
        if self.buffer is not None:
            data = self.buffer
            size = size + 8 + len(data)

        # header
        out.write(b'glTF')
        out.write(struct.pack('<I', 2))
        out.write(struct.pack('<I', size))

        # json
        out.write(struct.pack('<I', len(json)))
        out.write(b'JSON')
        out.write(json)

        # data
        if data is not None:
            out.write(struct.pack('<I', len(data)))
            out.write(b'BIN\x00')
            out.write(data)

    def write_b3dm(self, out):
        gltf_data = self.to_array()

        feature_table = {
            'BATCH_LENGTH': 0,
        }
        feature_data = json.dumps(feature_table).encode('utf-8')
        if len(feature_table) % 4 != 0:
            feature_data = feature_data + b' ' * (4 - len(feature_data) % 4)

        size = 28 + len(feature_data) + len(gltf_data)

        out.write(b'b3dm')
        out.write(struct.pack('<I', 1))
        out.write(struct.pack('<I', size))
        out.write(struct.pack('<I', len(feature_data)))
        out.write(struct.pack('<I', 0))
        out.write(struct.pack('<I', 0))
        out.write(struct.pack('<I', 0))
        out.write(feature_data)
        out.write(gltf_data)


    def to_array(self):
        with io.BytesIO() as out:
            self.write_glb(out)
            return out.getvalue()

    def save(self, fname):
        if fname.endswith('.glb'):
            with open(fname, 'wb') as out:
                self.write_glb(out)
        elif fname.endswith('.gltf'):
            dname = fname[:-5] + ".bin" if self.buffer is not None else None
            with open(fname, 'wb') as out:
                out.write(self.to_json(dname))
            if dname is not None:
                with open(dname, 'wb') as out:
                    out.write(self.buffer)
        elif fname.endswith('.b3dm'):
            with open(fname, 'wb') as out:
                self.write_b3dm(out)
        else:
            raise IOError("invalid gltf file name: " + fname)

def gltf_from_b3dm(fname):
    if not fname.endswith(".b3dm"):
        raise Exception("invalid b3dm file: " + fname)
    with open(fname, 'rb') as f:
        data = f.read()
    if struct.unpack("4s", data[0:4])[0] != b'b3dm':
        raise Exception("invalid magic")
    if struct.unpack("i", data[4:8])[0] != 1:
        raise Exception("invalid version")
    if struct.unpack("i", data[8:12])[0] != len(data):
        raise Exception("invalid length")

    feature_json_len = struct.unpack("i", data[12:16])[0]
    feature_bin_len = struct.unpack("i", data[16:20])[0]
    batch_json_len = struct.unpack("i", data[20:24])[0]
    batch_bin_len = struct.unpack("i", data[24:28])[0]
    off = 28

    if feature_json_len > 0:
        glb_feature_json = json.loads(data[off:off+feature_json_len].decode('utf-8'))
        glb_feature_name = fname[0:-5] + ".glb.feature.json"
        with open(glb_feature_name, 'wb') as f:
            f.write(json.dumps(glb_feature_json, indent=4).encode('utf-8'))
        print("saved", glb_feature_name)
        off += feature_json_len
    if feature_bin_len > 0:
        print("ignoring", feature_bin_len, "bytes of binary feature data")
        off += feature_bin_len
    if batch_json_len > 0:
        glb_batch_json = json.loads(data[off:off+batch_json_len].decode('utf-8'))
        glb_batch_name = fname[0:-5] + ".glb.batch.json"
        with open(glb_batch_name, 'wb') as f:
            f.write(json.dumps(glb_batch_json, indent=4).encode('utf-8'))
        print("saved", glb_batch_name)
        off += batch_json_len
    if batch_bin_len > 0:
        print("ignoring", batch_bin_len, "bytes of binary batch data")
        off += batch_bin_len


    glb_name = fname[0:-5] + ".glb"
    glb_data = data[off:]
    if struct.unpack("4s", glb_data[0:4])[0] != b'glTF':
        raise Exception("invalid embedded gltf")
    if struct.unpack("i", glb_data[4:8])[0] != 2:
        raise Exception("invalid embedded gltf version")
    if struct.unpack("i", glb_data[8:12])[0] != len(glb_data):
        raise Exception("invalid embedded gltf length")

    with open(glb_name, 'wb') as f:
        f.write(glb_data)
    print("saved", glb_name)

    gltf_name = fname[0:-5] + ".gltf"
    off = 12
    gltf_len = struct.unpack("i", glb_data[off:off+4])[0]
    off += 4
    if gltf_len <= 0:
        raise Exception("invalid embedded gltf json length")
    if struct.unpack("4s", glb_data[off:off+4])[0] != b'JSON':
        raise Exception("invalid embedded gltf JSON")
    off += 4
    gltf_json = json.loads(glb_data[off:off+gltf_len].decode('utf-8'))
    off += gltf_len

    if off+4 <= len(glb_data):
        bin_name = os.path.split(fname)[1][0:-5] + ".bin"
        gltf_json["buffers"][0]["uri"] = bin_name
        bin_len = struct.unpack("i", glb_data[off:off+4])[0]
        off += 4
        if struct.unpack("4s", glb_data[off:off+4])[0] != b'BIN\x00':
            raise Exception("invalid embedded gltf JSON")
        off += 4
        bin_data = glb_data[off:off+bin_len]
        off += bin_len

        with open(bin_name, 'wb') as f:
            f.write(bin_data)
        print("saved", bin_name)

    with open(gltf_name, 'wb') as f:
        f.write(json.dumps(gltf_json, indent=4).encode('utf-8'))
    print("saved", gltf_name)

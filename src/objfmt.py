# (c)2018, Arthur van Hoff
# OBJ 3D data format writer

import os, datetime, math

class _OBJWriter:
    def __init__(self, path):
        self.path = path
        self.base = os.path.dirname(path)
        self.v_index = 1
        self.vt_index = 1
        self.f_index = 1
        self.offset = (0.0, 0.0, 0.0)
        self.scale = (1.0, 1.0, 1.0)
        self.materials = {}

    def __enter__(self):
        self.out = open(self.path, 'w')
        self.comment("%s, %s" % (datetime.datetime.now(), os.path.basename(self.path)))
        return self

    def comment(self, txt):
        self.out.write("# %s\n" % (txt))

    def mtllib(self, mtl_path):
        mtl_file = os.path.basename(mtl_path)
        mtl_dir = os.path.dirname(mtl_path)
        dst_path = os.path.join(self.base, mtl_file)
        if not os.path.exists(dst_path):
            os.link(mtl_path, dst_path)
        mtl_name = None
        for line in [line.rstrip('\n') for line in open(mtl_path)]:
            if line.startswith("newmtl "):
                mtl_name = line[7:].strip()
                self.materials[mtl_name] = mtl_path
            elif line.startswith("map_Kd "):
                texture_name = line[7:].strip()
                dst_texture_path = os.path.join(self.base, texture_name)
                if os.path.exists(dst_texture_path):
                    os.remove(dst_texture_path)
                os.link(os.path.join(mtl_dir, texture_name), dst_texture_path)

        self.out.write("mtllib %s\n" % (mtl_file))
        return mtl_name

    def usemtl(self, name):
        if name not in self.materials:
            raise Exception("no such material loaded: " + name)
        self.out.write("usemtl %s\n" % name)

    def newmtl(self, path, name=None):
        if name is None:
            name = os.path.splitext(self.path)[0].replace(os.sep, '_')
        self.out.write("newmtl %s\n" % name)
        self.out.write("Ka 1.000000 1.000000 1.000000\n")
        self.out.write("Kd 1.000000 1.000000 1.000000\n")
        self.out.write("Ks 0.000000 0.000000 0.000000\n")
        self.out.write("Tr 1.000000\n")
        self.out.write("illium 1\n")
        self.out.write("Ns 0.000000\n")
        self.out.write("map_Kd %s\n" % os.path.basename(path))
        return name

    def image(self, name, *vs):
        vi = self.v_index
        vti = self.vt_index
        self.v(*vs)
        self.vt((0, 0), (1,0), (1,1), (0,1))
        self.usemtl(name)
        self.f_vt(*[(vi + i, vti + i) for i in range(4)])

    def v(self, *vs):
        for v in vs:
            self.out.write("v %f %f %f\n" % (self.scale[0] * (v[0] + self.offset[0]), self.scale[1] * (v[1] + self.offset[1]), self.scale[2] * (v[2] + self.offset[2])))
        self.v_index += len(vs)

    def vt(self, *vts):
        for vt in vts:
            self.out.write("vt %f %f\n" % vt)
        self.vt_index += len(vts)

    def f_v(self, *vs):
        self.out.write("f")
        for v in vs:
            self.out.write(" %d" % v)
        self.out.write("\n")
        self.f_index += 1

    def f_vt(self, *vts):
        self.out.write("f")
        for vt in vts:
            self.out.write(" %d/%d" % vt)
        self.out.write("\n")
        self.f_index += 1

    def newline(self):
        self.out.write("\n")

    def pillar(self, xy, h1=0, h2=1000, r=50, n=20, color='RED'):
        self.comment("pillar %f,%f, h1=%f, h2=%f, r=%f" % (xy[0], xy[1], h1, h2, r))
        self.usemtl(color)
        off = self.v_index
        for i in range(n):
            a = 2*math.pi*i/n
            self.v((xy[0] + r*math.sin(a), h1, xy[1] + r*math.cos(a)))
            self.v((xy[0] + r*math.sin(a), h2, xy[1] + r*math.cos(a)))
        for i in range(n):
            self.f_v(off + i*2, off+((i*2+2) % (2*n)), off + ((i*2+3) % (2*n)), off + i*2+1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.out.close()
        self.out = None

def create(path):
    return _OBJWriter(path)

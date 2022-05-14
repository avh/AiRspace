# (c)Artfahrt 2022, Arthur van Hoff

import sys, random, math, numpy, pyproj, affine, traceback
from PySide6 import QtCore, QtWidgets, QtGui
from geometry import Point

import settings, util, airspace_shapes
from airspace_shapes import Airspace, Region
from geometry import angle, bearing
airport_shapes_table = settings.db.hash_table("airport_shapes")

epsg3857 = pyproj.Proj('epsg:3857')
earth_circumference = epsg3857(180, 0)[0] - epsg3857(-180, 0)[0]
print("earth", earth_circumference)
black = QtGui.QColor(0, 0, 0)
white = QtGui.QColor(255, 255, 255)
red = QtGui.QColor(255, 0, 0)
orange = QtGui.QColor(200, 100, 100)
darkGray = QtGui.QColor(50, 50, 50)
gray = QtGui.QColor(150, 150, 150)
lightGray = QtGui.QColor(200, 200, 200)
font = QtGui.QFont('Helvetica', 10)

class ZoomingCanvas(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.transform = QtGui.QTransform()
        self.pos = None
        self.moved = False

    def wheelEvent(self, event):
        #print("wheel", event.position(), event.pixelDelta())
        self.pos = event.position().x(), event.position().y()
        dist = event.pixelDelta().y()
        if dist != 0:
            self.zoom(self.pos, 1.005**dist)

    def mousePressEvent(self, event):
        self.pos = event.position().x(), event.position().y()
        self.moved = False

    def mouseMoveEvent(self, event):
        delta = event.position().x() - self.pos[0], event.position().y() - self.pos[1]
        self.pos = event.position().x(), event.position().y()
        if delta[0] != 0 or delta[1] != 0:
            self.moved = True
            self.scroll(delta)

    def mouseReleaseEvent(self, event):
        self.pos = event.position().x(), event.position().y()
        if not self.moved:
            self.mouseClick(self.pos)

    def mouseClick(self, xy):
        ...

    def focus(self, bbox, margin=20):
        #print(bbox)
        self.scale = min((self.width() - 2*margin) / (bbox[2] - bbox[0]), (self.height() - 2*margin) / (bbox[3] - bbox[1]))
        self.transform = QtGui.QTransform()
        self.transform.scale(self.scale, self.scale)
        self.transform.translate(margin/self.scale - bbox[0], margin/self.scale - bbox[1])
        self.update()

    def zoom(self, xy, scale):
        #print("zoom", xy, scale)
        txy = self.transform.inverted()[0].map(*xy)
        self.scale = self.scale * scale
        self.transform = QtGui.QTransform()
        self.transform.scale(self.scale, self.scale)
        self.transform.translate(xy[0]/self.scale - txy[0], xy[1]/self.scale - txy[1])
        self.update()

    def scroll(self, xy):
        #print("scroll", xy)
        txy = self.transform.inverted()[0].map(0, 0)
        self.transform = QtGui.QTransform()
        self.transform.scale(self.scale, self.scale)
        self.transform.translate(xy[0]/self.scale - txy[0], xy[1]/self.scale - txy[1])
        self.update()

    def paintEvent(self, event):
        qp = QtGui.QPainter()
        qp.begin(self)
        try:
            self.paint(qp)
        except:
            traceback.print_exc()
        finally:
            qp.end()

    def paint(self, qp):
        ...


class AirspaceCanvas(ZoomingCanvas):
    def __init__(self):
        super().__init__()
        #self.setGeometry(300, 300, 280, 170)
        self.airspace = None
        self.transform = QtGui.QTransform()
        self.map_size = 1024
        self.reverse_transform = affine.Affine.scale(self.map_size/earth_circumference, -self.map_size/earth_circumference)
        self.reverse_transform = affine.Affine.translation(self.map_size/2, self.map_size/2) * self.reverse_transform
        self.show()

    def lonlat2xy(self, lonlat):
        return self.reverse_transform * epsg3857(*lonlat)

    def xy2lonlat(self, xy):
        xy = ~self.reverse_transform * xy
        return epsg3857(*xy, inverse=True)

    def proj(self, lonlat):
        return self.transform.map(*self.lonlat2xy(lonlat))

    def cleanup(self):
        self.selected = None
        self.airspace.cleanup()
        self.update()

    def set_airspace(self, airspace):
        self.airspace = airspace
        self.selected = None
        self.reset()

    def reset(self):
        self.focus([*self.lonlat2xy((self.airspace.bbox[0], self.airspace.bbox[3])), *self.lonlat2xy((self.airspace.bbox[2], self.airspace.bbox[1]))])

    def dump(self):
        if self.selected is not None:
            self.selected.dump()
        elif self.airspace is not None:
            self.airspace.dump()

    def mouseClick(self, xy):
        self.selected = None
        candidates = []
        pt = QtCore.QPointF(*xy)
        for region in self.airspace.regions:
            poly = QtGui.QPolygonF([QtCore.QPointF(*self.proj((p.lon, p.lat))) for p in region.points])
            if poly.containsPoint(pt, QtCore.Qt.WindingFill):
                candidates.append(region)
                break
        if self.selected is not None and self.selected in candidates:
            self.selected = candidates[(candidates.index(self.selected) + 1) % len(candidates)]
        elif len(candidates) > 0:
            self.selected = candidates[0]
        else:
            self.selected = None
        self.update()

        if self.selected is not None:
            points = self.selected.points
            besti = None
            bestd = None
            for i, pt in enumerate(points):
                d = util.distance_xy(xy, self.proj((pt.lon, pt.lat)))
                if besti is None or bestd > d:
                    besti = i
                    bestd = d
            print(besti, bestd)
            if bestd < 10:
                p0 = points[(besti + len(points) - 1) % len(points)]
                p1 = points[besti]
                p2 = points[(besti + 1) % len(points)]
                print(f"p0: {i-1:4}, {p0}")
                print(f"    distance {round(p0.distance(p1))}m")
                print(f"    bearing {bearing(p0, p1):.1f}")
                print(f"p1: {i:4}, {p1}")
                print(f"    angle {p1.angle}, {angle(p0, p1, p2)}, {self.proj((p0.lon, p0.lat))}, {self.proj((p1.lon, p1.lat))}, {self.proj((p2.lon, p2.lat))}")
                print(f"    distance {round(p1.distance(p2))}m")
                print(f"    bearing {bearing(p1, p2):.1f}")
                print(f"p2: {i+1:4}, {p2}")

        self.update()

    def paint(self, qp):
        if self.airspace is None:
            qp.setPen(gray)
            qp.setFont(font)
            qp.drawText(self.width()/2, self.height()/2, "this space is intentionally left blank")
            return

        self.drawGrid(qp)
        self.drawScale(qp)
        self.drawLabels(qp)
        qp.setPen(gray)
        points = []
        for region in self.airspace.regions:
            if region != self.selected:
                for p1, p2 in util.enumerate_pairs(region.points):
                    p1 = self.proj((p1.lon, p1.lat))
                    p2 = self.proj((p2.lon, p2.lat))
                    points.append(p1)
                    qp.drawLine(*p1, *p2)
        qp.setPen(QtCore.Qt.NoPen)
        qp.setBrush(darkGray)
        for p in points:
            qp.drawEllipse(QtCore.QPointF(*p), 1, 1)
        qp.setBrush(QtCore.Qt.NoBrush)
        if self.selected is not None:
            points = []
            qp.setPen(orange)
            for p1, p2 in util.enumerate_pairs(self.selected.points):
                p1 = self.proj((p1.lon, p1.lat))
                p2 = self.proj((p2.lon, p2.lat))
                points.append(p1)
                qp.drawLine(*p1, *p2)
            qp.setPen(red)
            for p in points:
                qp.drawEllipse(QtCore.QPointF(*p), 3, 3)

    def drawGrid(self, qp):
        p1 = Point(*self.xy2lonlat(self.transform.inverted()[0].map(0, 0)))
        p2 = Point(*self.xy2lonlat(self.transform.inverted()[0].map(self.width(), self.height())))

        qp.setFont(font)
        qp.setPen(white)
        for lat in range(math.floor(p2.lat), math.ceil(p1.lat)+1):
            x, y = self.proj((p1.lon, lat))
            qp.drawText(x, y-5, f"{lat}")
            qp.drawLine(x, y, *self.proj((p2.lon, lat)))
        for lon in range(math.floor(p1.lon), math.ceil(p2.lon)+1):
            x, y = self.proj((lon, p1.lat))
            qp.drawText(x+5, y+8, f"{lon}")
            qp.drawLine(x, y, *self.proj((lon, p2.lat)))

    def drawScale(self, qp, margin=10):
        start = margin, self.height() - margin
        pt = Point(*self.xy2lonlat(self.transform.inverted()[0].map(*start)))
        points = [(start, 0)]
        for i in range(0, 8):
            m = 10**i
            lonlat = pt.lon + (360*m/earth_circumference)/math.cos(pt.lat*util.d2r), pt.lat
            d = self.proj(lonlat)[0] - start[0]
            if d < 5:
                continue
            if d > self.width() - 2*margin:
                break
            points.append(((margin + d, start[1]), m))
        qp.setPen(lightGray)
        qp.drawLine(*points[0][0], *points[-1][0])
        qp.setBrush(lightGray)
        for pt, _ in points:
            qp.drawEllipse(QtCore.QPointF(*pt), 3, 3)
        qp.setBrush(QtCore.Qt.NoBrush)
        qp.setPen(gray)
        qp.setFont(font)
        for pt, dist in points[1:]:
            if dist < 1000:
                qp.drawText(pt[0]-10, pt[1]-8, f"{dist}m")
            else:
                qp.drawText(pt[0]-10, pt[1]-8, f"{dist//1000}km")

    def drawLabels(self, qp):
        qp.setFont(font)
        for region in self.airspace.regions:
            p1, p2 = self.proj((region.bbox[0], region.bbox[1])), self.proj((region.bbox[2], region.bbox[3]))
            rect = QtCore.QRectF(p1[0], p1[1], p2[0] - p1[0], p2[1] - p1[1])
            qp.setPen(red if region is self.selected else darkGray)
            qp.drawText(rect, QtCore.Qt.AlignCenter, f"{region.ht(region.lower)}-{region.ht(region.upper)}")


class EditWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QtCore.QSettings('Artfahrt', 'AirspaceEditor')
        self.setWindowTitle("Airspace Editor")
        self.frame = QtWidgets.QFrame(self)
        self.frame.setFixedWidth(200)
        self.frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_layout = QtWidgets.QVBoxLayout(self.frame)
        self.frame_layout.setAlignment(QtCore.Qt.AlignTop)

        self.canvas = AirspaceCanvas()

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.frame)
        layout.addWidget(self.canvas)
        self.setLayout(layout)


        self.airspace = QtWidgets.QLineEdit(self.settings.value('airspace', ''))
        self.airspace.editingFinished.connect(self.load_airspace)
        self.frame_layout.addWidget(self.airspace)

        cleanup = QtWidgets.QPushButton("cleanup")
        cleanup.clicked.connect(lambda x: self.canvas.cleanup())
        self.frame_layout.addWidget(cleanup)

        reset = QtWidgets.QPushButton("reset")
        reset.clicked.connect(lambda x: self.canvas.reset())
        self.frame_layout.addWidget(reset)

        dump = QtWidgets.QPushButton("dump")
        dump.clicked.connect(lambda x: self.canvas.dump())
        self.frame_layout.addWidget(dump)

        floors = QtWidgets.QCheckBox("floors")
        floors.setChecked(airspace_shapes.add_floors)
        floors.toggled.connect(self.toggle_floors)
        self.frame_layout.addWidget(floors)

        ceilings = QtWidgets.QCheckBox("ceilings")
        ceilings.setChecked(airspace_shapes.add_ceilings)
        ceilings.toggled.connect(self.toggle_ceilings)
        self.frame_layout.addWidget(ceilings)

        poles = QtWidgets.QCheckBox("poles")
        poles.setChecked(airspace_shapes.add_poles)
        poles.toggled.connect(self.toggle_poles)
        self.frame_layout.addWidget(poles)

        save = QtWidgets.QPushButton("save")
        save.clicked.connect(lambda x: self.canvas.airspace.save())
        self.frame_layout.addWidget(save)

        self.restoreGeometry(self.settings.value('geometry', None))

    def toggle_floors(self, checked):
        airspace_shapes.add_floors = checked

    def toggle_ceilings(self, checked):
        airspace_shapes.add_ceilings = checked

    def toggle_poles(self, checked):
        airspace_shapes.add_poles = checked

    def load_airspace(self):
        id = self.airspace.text()
        try:
            print("load airport", id)
            airspace = Airspace(airport_shapes_table, id)
            self.canvas.set_airspace(airspace)
            self.save()
        except:
            print(f"not loaded {id}")
            raise

    def closeEvent(self, event):
        self.save()
        super(EditWindow, self).closeEvent(event)

    def save(self):
        self.settings.setValue('airspace', self.airspace.text())
        self.settings.setValue('geometry', self.saveGeometry())


if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    win = EditWindow()
    win.show()

    sys.exit(app.exec())

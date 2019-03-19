# (c)2018, Arthur van Hoff

import os
import db

#
# Directories
#

tmp_dir = "tmp"
if not os.path.exists(tmp_dir):
    os.mkdir(tmp_dir)

data_dir = "data"
if not os.path.exists(data_dir):
    os.mkdir(data_dir)

charts_dir = os.path.join(data_dir, "charts")
if not os.path.exists(charts_dir):
    os.mkdir(charts_dir)

charts_source_dir = os.path.join(charts_dir, "source")
if not os.path.exists(charts_source_dir):
    os.mkdir(charts_source_dir)

elevations_dir = os.path.join(charts_dir, "elevations")
if not os.path.exists(elevations_dir):
    os.mkdir(elevations_dir)

nasr_dir = os.path.join(charts_source_dir, "NASR")
cloudahoy_dir = os.path.join(data_dir, "cloudahoy")
tiles_dir = os.path.join(data_dir, "tiles")
sec_tiles_dir = os.path.join(tiles_dir, "sec")
tac_tiles_dir = os.path.join(tiles_dir, "tac")

faa_chart_url = "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/vfr/"
faa_nasr_url = "https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/NASR_Subscription/"
elevation_cvs = os.path.join(charts_source_dir, "ned3694_20181220_205600.csv")
nasr_shape_path = os.path.join(nasr_dir, "Additional Data/Shape_Files/Class_Airspace")
#
# Database
#

db = db.Database("charts")

#
# Chart sizes
#

chart_target_size = 4096*4096
elevation_steps = 100

#
# Sectional Chart Notes
#

chart_notes = {
    "San Francisco SECTIONAL": [
        ('l-lon', -125),
        ('b-lat', 36),
        ('t-fix', -125, 40.21),
    ],
    "San Francisco TAC": [
        ('bounds', -123.15,37.008, -121.382,38.19),
    ],
    "Los Angeles SECTIONAL": [
        ('b-lat', 32),
        ('l-lon', -122),
        ('t-fix', -121.5,36.11),
        ('box', -120.11,33.575, -122,31),
        ('box', -121.55,34.245, -125,37),
    ],
    "Los Angeles TAC": [
        ('bounds', -119,33.41, -116.792,34.516),
    ],
    "Klamath Falls SECTIONAL": [
        ('b-lat', 40.),
        ('l-lon', -125),
    ],
    "Seattle SECTIONAL": [
        ('l-lon', -125),
        ('b-fix', -125, 44.4),
    ],
    "Seattle TAC": [
        ('bounds', -123.183,46.75, -121.53,48.061),
    ],
    "Las Vegas SECTIONAL": [
        ('l-lon', -118),
        ('b-fix', -118, 35.58),
    ],
    "Las Vegas TAC": [
        ('bounds', -115.616,35.7, -113.866,36.733),
    ],
    "Phoenix SECTIONAL": [
        ('l-lon', -116),
        ('t-fix', -116,35.7),
    ],
    "Phoenix TAC": [
        ('bounds', -112.858,32.783, -111.165,34.085),
    ],
    "Salt Lake City SECTIONAL": [
        ('l-lon', -117),
        ('b-lat', 40),
    ],
    "Salt Lake City TAC": [
        ('bounds', -112.85,40.125, -111.028,41.416),
    ],
    "Great Falls SECTIONAL": [
        ('l-lon', -117),
        ('b-fix', -117,44.416),
    ],
}

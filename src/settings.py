# (c)2018, Arthur van Hoff

import os, math
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

www_dir = "www"
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
tiles_dir = os.path.join(www_dir, "tiles")
sec_tiles_dir = os.path.join(tiles_dir, "sec")
tac_tiles_dir = os.path.join(tiles_dir, "tac")

faa_chart_url = "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/vfr/"
faa_nasr_url = "https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/NASR_Subscription/"
elevation_cvs = os.path.join(charts_source_dir, "ned3694_20181220_205600.csv")
nasr_shape_path = os.path.join(nasr_dir, "Additional_Data/Shape_Files/Class_Airspace")

earth_circumference = 40075017
earth_radius = earth_circumference/(2*math.pi)

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
    # annotations:
    # l-lon = left longitude
    # b-lat = bottom latitude
    # t-fix = top fixed at lon, lat
    # b-fix = bottom fixed at lon, lat
    # box = (left-lon,bottom-lat,right-lon,top-lat) inset that needs to be erased
    # bounds = (left-lon,bottom-lat,right-lon,top-lat) outline of the chart

    # ----------- Sectional Charts ------------

    "Albuguerque SEC": [
        ('l-lon', -109),
        ('b-lat', 32),
        ('t-fix', -109, 36.216),
    ],
    "San Francisco SEC": [
        ('l-lon', -125),
        ('b-lat', 36),
        ('t-fix', -125, 40.21),
    ],
    "Los Angeles SEC": [
        ('b-lat', 32),
        ('l-lon', -122),
        ('t-fix', -121.5,36.11),
        ('box', -120.11, 33.575, -122, 31),
        ('box', -121.55, 34.245, -125, 37),
    ],
    "Klamath Falls SEC": [
        ('b-lat', 40.),
        ('l-lon', -125),
    ],
    "Seattle SEC": [
        ('l-lon', -125),
        ('b-fix', -125, 44.4),
    ],
    "Las Vegas SEC": [
        ('l-lon', -118),
        ('b-fix', -118, 35.58),
    ],
    "Phoenix SEC": [
        ('l-lon', -116),
        ('t-fix', -116,35.7),
    ],
    "Salt Lake City SEC": [
        ('l-lon', -117),
        ('b-lat', 40),
    ],
    "Great Falls SEC": [
        ('l-lon', -117),
        ('b-fix', -117, 44.416),
    ],

    # ----------- Carribean (part of sec charts) ------------

    "Carribean 1 VFR": [
        ('l-lon', -85),
        ('b-lat', 16),
    ],
    "Carribean 2 VFR": [
        ('l-lon', -73),
        ('b-lat', 14),
    ],

    # ----------- Terminal Area Charts ------------

    "Anchorage TAC": [
        ('bounds', -151.813, 60.563, -148.313, 61.655)
    ],
    "Fairbanks TAC": [
        ('bounds', -149.3, 64.166, -145.783, 65.25)
    ],
    "Atlanta TAC": [
        ('bounds', -85.29, 32.975, -83.6, 34.308),
    ],
    "Baltimore-Washington TAC": [
        ('bounds', -78.315, 38.166, -75.928, 39.8)
    ],
    "Boston TAC": [
        ('bounds', -71.855, 41.25, -69.566, 42.866)
    ],
    "Charlotte TAC": [
        ('bounds', -81.815, 34.665, -80.085, 35.896)
    ],
    "Chicago TAC": [
        ('bounds', -88.766, 41.45, -87.25, 42.482)
    ],
    "Cincinnati TAC": [
        ('bounds', -85.533, 38.478, -83.7, 40.07)
    ],
    "Cleveland TAC": [
        ('bounds', -82.59, 40.866, -81.095, 41.9)
    ],
    "Dallas-Ft Worth TAC": [
        ('bounds', -98.2, 32.005, -95.883, 33.666)
    ],
    "Denver TAC": [
        ('bounds', -105.57, 39.25, -103.725, 40.566)
    ],
    "Colorado Springs TAC": [
        ('bounds', -105.506, 37.8, -103.483, 39.266)
    ],
    "Detroit TAC": [
        ('bounds', -84.278, 41.716, -82.383, 42.855)
    ],
    "Houston TAC": [
        ('bounds', -96.133, 29.09, -94.513, 30.510)
    ],
    "Kansas City TAC": [
        ('bounds', -95.886, 38.733, -94.071, 39.908)
    ],
    "Las Vegas TAC": [
        ('bounds', -115.616, 35.7, -113.866, 36.733),
    ],
    "Los Angeles TAC": [
        ('bounds', -119, 33.41, -116.792, 34.516),
    ],
    "Memphis TAC": [
        ('bounds', -90.85, 34.4, -89.125, 35.705)
    ],
    "Miami TAC": [
        ('bounds', -81.165, 25.2, -79.315, 26.765)
    ],
    "Minneapolis-St Paul TAC": [
        ('bounds', -94.016, 44.36, -92.458, 45.375)
    ],
    "New Orleans TAC": [
        ('bounds', -91.265, 29.558, -89.663, 30.583)
    ],
    "New York TAC": [
        ('bounds', -74.89, 40.216, -72.66, 41.266)
    ],
    "Philadelphia TAC": [
        ('bounds', -75.893, 39.48, -74.51, 40.5)
    ],
    "Phoenix TAC": [
        ('bounds', -112.858, 32.783, -111.165, 34.085),
    ],
    "Pittsburgh TAC": [
        ('bounds', -80.95, 39.96, -79.73, 41.0)
    ],
    "Puerto Rico-VI TAC": [
        ('bounds', -67.5, 17.645, -64.24, 18.7833)
    ],
    "St Louis TAC": [
        ('bounds', -91.066, 38.183, -89.63, 39.218)
    ],
    "Salt Lake City TAC": [
        ('bounds', -112.85, 40.125, -111.028, 41.416),
    ],
    "San Diego TAC": [
        ('bounds', -117.966, 32.5, -116.291, 33.616),
    ],
    "San Francisco TAC": [
        ('bounds', -123.15,37.008, -121.382,38.19),
    ],
    "Seattle TAC": [
        ('bounds', -123.183, 46.75, -121.53, 48.061),
    ],
    "Portland TAC": [
        ('bounds', -123.183, 45.2, -122.066, 46.0166),
    ],
    "Tampa TAC": [
        ('bounds', -83.09, 27.296, -81.833, 28.59)
    ],
    "Orlando TAC": [
        ('bounds', -82.016, 27.83, -80.146, 29.184)
    ],

    # ----------- Grand Canyon (part of tac charts) ------------

    "Grand Canyon General Aviation": [
        ('bounds', -114.108, 35.7, -111.308, 36.641)
    ],
}

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
airports_dir = os.path.join(tiles_dir, "airports")

faa_vfr_chart_url = "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/vfr/"
faa_ifr_chart_url = "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/ifr/"
faa_nasr_url = "https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/NASR_Subscription/"
elevation_cvs = os.path.join(charts_source_dir, "ned3694_20181220_205600.csv")
nasr_shape_path = os.path.join(nasr_dir, "Additional_Data/Shape_Files/Class_Airspace")
all_airport_data_url = "https://adip.faa.gov/publishedAirports/all-airport-data.xlsx"
boundaries_url = "https://opendata.arcgis.com/api/v3/datasets/67885972e4e940b2aa6d74024901c561_0/downloads/data?format=shp&spatialRefId=4326"

earth_circumference = 40075017
earth_radius = earth_circumference/(2*math.pi)

#
# default 3D settings
#

defaultGeometricError = {
    'A': 20000,
    'B': 18000,
    'C': 16000,
    'D': 14000,
    'E': 12000,
    'E1': 12000,
    'E2': 12000,
    'E3': 12000,
    'E4': 12000,
    'E5': 12000,
    'G': 10000,
}

defaultHeight = {
    'A': 50000,
    'B': 40000,
    'C': 40000,
    'D': 40000,
    'E': 40000,
    'E1': 40000,
    'E2': 40000,
    'E3': 40000,
    'E4': 40000,
    'E5': 40000,
    'G': 40000,
}

#
# Database (requires local redis-server)
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

    "Albuquerque SEC": [
        ('l-lon', -109),
        ('b-lat', 32),
        ('t-fix', -109, 36.216),
        ('r-fix', -101.98, 32),
    ],
    "Anchorage SEC": [
        ('l-lon', -151.5),
        ('b-lat', 60),
        ('r-fix', -140.333, 60),
        ('t-fix', -151.5, 64.166),
    ],
    "Atlanta SEC": [
        ('l-lon', -88),
        ('b-lat', 32),
        ('t-fix', -88, 36.216),
    ],
    "Bethel SEC": [
        ('l-lon', -173),
        ('b-fix', -173, 59.583),
    ],
    "Billings SEC": [
        ('l-lon', -109),
        ('b-fix', -109, 44.416),
    ],
    "Brownsville SEC": [
        ('l-lon', -103),
        ('b-lat', 24),
        ('r-fix', -96.833, 24),
    ],
    "Cape Lisburne SEC": [
        ('l-lon', -171.5),
        ('b-lat', 68),
    ],
    "Charlotte SEC": [
        ('l-lon', -82),
        ('b-lat', 32),
    ],
    "Cheyenne SEC": [
        ('l-lon', -109),
        ('b-lat', 40),
    ],
    "Chicago SEC": [
        ('l-lon', -93),
        ('b-lat', 40),
        ('t-fix', -93, 44.203),
    ],
    "Cincinnati SEC": [
        ('l-lon', -85),
        ('b-lat', 36),
    ],
    "Cold Bay SEC": [
        ('l-lon', -164),
        ('b-fix', -164, 53.863),
    ],
    "Dallas-Ft Worth SEC": [
        ('l-lon', -102),
        ('b-lat', 32),
        ('r-fix', -94.983, 32),
    ],
    "Dawson SEC": [
        ('l-lon', -145),
        ('b-lat', 64),
    ],
    "Denver SEC": [
        ('l-lon', -111),
        ('b-fix', -111, 35.585),
    ],
    "Detroit SEC": [
        ('l-lon', -85),
        ('b-lat', 40),
    ],
    "Dutch Harbor SEC": [
        ('l-lon', -173),
        ('b-lat', 52),
        ('box', -173, 54.583, -169.266, 57),
        ('box', -170, 54.9, -165.000, 57),
    ],
    "El Paso SEC": [
        ('l-lon', -109),
        ('b-lat', 28),
    ],
    "Fairbanks SEC": [
        ('l-lon', -158),
        ('b-lat', 64),
        ('t-fix', -158, 68.166),
        ('r-fix', -144.916, 64),
    ],
    "Great Falls SEC": [
        ('l-lon', -117),
        ('b-fix', -117, 44.416),
    ],
    "Green Bay SEC": [
        ('l-lon', -93),
        ('b-lat', 44),
    ],
    "Halifax SEC": [
        ('l-lon', -69),
        ('b-lat', 44),
        # REMIND: Halifax bump in CYQI
    ],
    "Hawaiian Islands SEC": [
        ("t-fix", -159.700, 23.633),
        ("l-line", -160.916, 21.866, -159.700, 23.633),
        ("l-line", -160.916, 21.866, -158.000, 20.1),
        ("l-line", -158.000, 20.1, -155.383, 18.383),
        ("r-line", -159.750, 23.633, -154.133, 20.083),
        ("r-line", -154.133, 20.083, -155.383, 18.383),
        ("b-fix", -155.383, 18.383),
    ],
    "Honolulu Inset SEC": [
        ('bounds', -158.466, 20.766, -157.366, 21.600),
        ('r-line', -157.600, 20.766, -157.366, 20.966),
    ],
    "Mariana Islands Inset SEC": [
        #('l-line', -144.916, 15.416, -144.916, 14.133),
        #('l-line', -145.416, 13.583, -144.916, 14.133),
        #('b-fix', -145.000, 13.333),
    ],
    "Samoan Islands Inset SEC": [
        #('l-lon', -172.85),
        #('b-lat', 13.333),
        #('r-line', -170.133, 13.833, -170.133, 14.783),
    ],
    "Houston SEC": [
        ('l-lon', -97),
        ('b-lat', 28),
    ],
    "Jacksonville SEC": [
        ('l-lon', -85),
        ('b-lat', 28),
        ('box', -79.9, 30.916, -78, 33),
        ('box', -86, 27, -83.716, 29.3),
        # REMIND: inset
    ],
    "Juneau SEC": [
        ('l-lon', -141),
        ('b-lat', 56),
        ('r-fix', -130.383, 56),
        ('t-fix', -141, 60.15),
        ('box', -141, 55.5, -137.333, 57.85),
        ('box', -141, 55.5, -138.866, 59.216),
    ],
    "Kansas City SEC": [
        ('l-lon', -97),
        ('b-lat', 36),
        ('t-fix', -90, 40.225),
    ],
    "Ketchikan SEC": [
        ('l-lon', -139),
        ('b-lat', 52),
        ('box', -139, 54.480, -135.583, 57),
    ],
    "Klamath Falls SEC": [
        ('b-lat', 40.),
        ('l-lon', -125),
    ],
    "Kodiak SEC": [
        ('l-lon', -162),
        ('b-lat', 56),
        ('box', -153.3, 56, -151, 56.916),
    ],
    "Lake Huron SEC": [
        ('l-lon', -85),
        ('b-lat', 44),
        ('t-fix', -85, 48.216),
    ],
    "Las Vegas SEC": [
        ('l-lon', -118),
        ('b-fix', -118, 35.583),
    ],
    "Los Angeles SEC": [
        ('b-lat', 32),
        ('l-fix', -121.583, 35),
        ('t-fix', -121.5,36.11),
        ('r-fix', -114.766, 32),
        ('box', -122, 31, -120.11, 33.575),
        ('box', -122, 34.245, -121.503, 37),
    ],
    "McGrath SEC": [
        ('l-lon', -162),
        ('b-lat', 60),
    ],
    "Memphis SEC": [
        ('l-lon', -95),
        ('b-lat', 32),
        ('r-fix', -87.966, 32),
        ('t-fix', -88, 36.216),
    ],
    "Miami SEC": [
        ('l-lon', -83),
        ('b-lat', 24),
        ('t-fix', -78, 28.116),
    ],
    "Montreal SEC": [
        ('l-lon', -77),
        ('b-lat', 44),
        ('t-fix', -69, 48.225),
        ('r-fix', -68.683, 44),
    ],
    "New Orleans SEC": [
        ('l-lon', -91),
        ('r-lon', -84.5),
        ('b-lat', 28),
        ('box', -87.083, 27.5, -85.9, 29.65),
        ('box', -86, 27.5, -84.5, 29.3),
    ],
    "New York SEC": [
        ('l-lon', -77),
        ('b-lat', 40),
    ],
    "Nome SEC": [
        ('l-lon', -171),
        ('b-lat', 64),
        ('box', -171, 67, -169, 69),
    ],
    "Omaha SEC": [
        ('l-lon', -101),
        ('b-lat', 40),
    ],
    "Phoenix SEC": [
        ('l-lon', -116),
        ('b-fix', -116, 31.283),
        ('t-fix', -116, 35.7),
        ('r-fix', -108.95, 31.5),
    ],
    "Point Barrow SEC": [
        ('l-lon', -157),
        ('b-lat', 68),
    ],
    "St Louis SEC": [
        ('l-lon', -91),
        ('b-lat', 36),
    ],
    "Salt Lake City SEC": [
        ('l-lon', -117),
        ('b-lat', 40),
    ],
    "San Antonio SEC": [
        ('l-lon', -103),
        ('b-lat', 28),
        ('r-lon', -96.5),
    ],
    "San Francisco SEC": [
        ('l-lon', -125),
        ('b-lat', 36),
        ('t-fix', -125, 40.21),
    ],
    "Seattle SEC": [
        ('l-lon', -125),
        ('b-fix', -125, 44.416),
    ],
    "Seward SEC": [
        ('l-lon', -152),
        ('b-fix', -152, 59.333),
    ],
    "Twin Cities SEC": [
        ('l-lon', -101),
        ('b-fix', -101, 44.425),
    ],
    "Washington SEC": [
        ('l-lon', -79),
        ('b-lat', 36),
        ('box', -73.133, 35.8, -71.8, 37.733),
        # REMIND: inset
    ],
    "Western Aleutian Islands West SEC": [
        ('l-fix', 169.365, 51),
        ('t-fix', 170, 53.15),
        ('b-lat', 51),
    ],
    "Western Aleutian Islands East SEC": [
        ('t-fix', 178, 53.116),
        ('l-lon', 178),
        ('b-lat', 51),
    ],
    "Wichita SEC": [
        ('t-fix', -103, 40.25),
        ('l-lon', -104),
        ('b-lat', 36),
        ('r-fix', -96.666, 40),
    ],

    # ----------- Carribean (part of sec charts) ------------

    "Caribbean 1 VFR Chart": [
        ('l-fix', -85, 16),
        ('b-lat', 16),
    ],
    "Caribbean 2 VFR Chart": [
        ('l-fix', -73, 16),
        ('b-lat', 14),
    ],

    # ----------- Terminal Area Charts ------------

    "Anchorage TAC": [
        ('bounds', -151.813, 60.563, -148.399, 61.655)
    ],
    "Fairbanks TAC": [
        ('bounds', -149.3, 64.188, -145.783, 65.25)
    ],
    "Atlanta TAC": [
        ('bounds', -85.29, 32.975, -83.6, 34.308),
    ],
    "Baltimore-Washington TAC": [
        ('bounds', -78.315, 38.266, -75.928, 39.8)
    ],
    "Boston TAC": [
        ('bounds', -71.855, 41.25, -69.588, 42.866)
    ],
    "Charlotte TAC": [
        ('bounds', -81.815, 34.665, -80.100, 35.896)
    ],
    "Chicago TAC": [
        ('bounds', -88.766, 41.48, -87.29, 42.482)
    ],
    "Cincinnati TAC": [
        ('bounds', -85.533, 38.478, -83.76, 40.07)
    ],
    "Cleveland TAC": [
        ('bounds', -82.59, 40.866, -81.095, 41.9)
    ],
    "Dallas-Ft Worth TAC": [
        ('bounds', -98.2, 32.050, -95.899, 33.666)
    ],
    "Denver TAC": [
        ('bounds', -105.57, 39.25, -103.799, 40.566)
    ],
    "Colorado Springs TAC": [
        ('bounds', -105.506, 37.8, -103.483, 39.266)
    ],
    "Detroit TAC": [
        ('bounds', -84.278, 41.716, -82.399, 42.855)
    ],
    "Houston TAC": [
        ('bounds', -96.133, 29.09, -94.563, 30.500)
    ],
    "Kansas City TAC": [
        ('bounds', -95.886, 38.733, -94.091, 39.908)
    ],
    "Las Vegas TAC": [
        ('bounds', -115.616, 35.7, -113.895, 36.733),
    ],
    "Los Angeles TAC": [
        ('bounds', -119, 33.41, -116.810, 34.516),
    ],
    "Memphis TAC": [
        ('bounds', -90.85, 34.4, -89.155, 35.705),
    ],
    "Miami TAC": [
        ('bounds', -81.165, 25.283, -79.399, 26.765),
        ('box', -80.183, 25, -79, 25.483),
        # REMIND: inset
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
        ('bounds', -112.858, 32.783, -111.199, 34.085),
    ],
    "Pittsburgh TAC": [
        ('bounds', -80.95, 40, -79.73, 41.0)
    ],
    "Puerto Rico-VI TAC": [
        ('bounds', -67.5, 17.645, -64.24, 18.7833)
    ],
    "St Louis TAC": [
        ('bounds', -91.066, 38.183, -89.63, 39.218)
    ],
    "Salt Lake City TAC": [
        ('bounds', -112.85, 40.125, -111.100, 41.416),
    ],
    "San Diego TAC": [
        ('bounds', -117.966, 32.5, -116.300, 33.610),
    ],
    "San Francisco TAC": [
        ('bounds', -123.15,37.008, -121.382,38.19),
    ],
    "Seattle TAC": [
        ('bounds', -123.183, 46.75, -121.59, 48.061),
    ],
    "Portland TAC": [
        ('bounds', -123.183, 45.2, -122.076, 46.0166),
    ],
    "Tampa TAC": [
        ('bounds', -83.09, 27.296, -81.833, 28.59)
    ],
    "Orlando TAC": [
        ('bounds', -82.016, 27.83, -80.146, 29.194)
    ],

    # ----------- Grand Canyon (part of tac charts) ------------

    "Grand Canyon General Aviation": [
        ('bounds', -114.108, 35.633, -111.319, 36.641),
        ('box', -111.65, 36.341, -111, 37),
    ],

    # ----------- Flyway Planning Charts ------------

    "Anchorage FLY": [
        ('bounds', -151.813, 60.563, -148.399, 61.655)
    ],
    "Fairbanks FLY": [
        ('bounds', -149.3, 64.188, -145.783, 65.25)
    ],
    "Atlanta FLY": [
        ('bounds', -85.29, 32.975, -83.6, 34.308),
    ],
    "Baltimore-Washington FLY": [
        ('bounds', -78.315, 38.266, -75.928, 39.8)
    ],
    "Boston FLY": [
        ('bounds', -71.855, 41.25, -69.588, 42.866)
    ],
    "Charlotte FLY": [
        ('bounds', -81.815, 34.665, -80.100, 35.896)
    ],
    "Chicago FLY": [
        ('bounds', -88.766, 41.48, -87.29, 42.482)
    ],
    "Cincinnati FLY": [
        ('bounds', -85.533, 38.478, -83.76, 40.07)
    ],
    "Cleveland FLY": [
        ('bounds', -82.59, 40.866, -81.095, 41.9)
    ],
    "Dallas-Ft Worth FLY": [
        ('bounds', -98.2, 32.050, -95.899, 33.666)
    ],
    "Denver FLY": [
        ('bounds', -105.57, 39.25, -103.799, 40.566)
    ],
    "Colorado Springs FLY": [
        ('bounds', -105.506, 37.8, -103.483, 39.266)
    ],
    "Detroit FLY": [
        ('bounds', -84.278, 41.716, -82.399, 42.855)
    ],
    "Houston FLY": [
        ('bounds', -96.133, 29.09, -94.563, 30.500)
    ],
    "Kansas City FLY": [
        ('bounds', -95.886, 38.733, -94.091, 39.908)
    ],
    "Las Vegas FLY": [
        ('bounds', -115.616, 35.7, -113.895, 36.733),
    ],
    "Los Angeles FLY": [
        ('bounds', -119, 33.41, -116.810, 34.516),
    ],
    "Memphis FLY": [
        ('bounds', -90.85, 34.4, -89.155, 35.705),
    ],
    "Miami FLY": [
        ('bounds', -81.165, 25.283, -79.399, 26.765),
        ('box', -80.183, 25, -79, 25.483),
        # REMIND: inset
    ],
    "Minneapolis-St Paul FLY": [
        ('bounds', -94.016, 44.36, -92.458, 45.375)
    ],
    "New Orleans FLY": [
        ('bounds', -91.265, 29.558, -89.663, 30.583)
    ],
    "New York FLY": [
        ('bounds', -74.89, 40.216, -72.66, 41.266)
    ],
    "New York TAC VFR Planning Charts": [
        # REMIND
    ],
    "Philadelphia FLY": [
        ('bounds', -75.893, 39.48, -74.51, 40.5)
    ],
    "Phoenix FLY": [
        ('bounds', -112.858, 32.783, -111.199, 34.085),
    ],
    "Pittsburgh FLY": [
        ('bounds', -80.95, 40, -79.73, 41.0)
    ],
    "Puerto Rico-VI FLY": [
        ('bounds', -67.5, 17.645, -64.24, 18.7833)
    ],
    "St Louis FLY": [
        ('bounds', -91.066, 38.183, -89.63, 39.218)
    ],
    "Salt Lake City FLY": [
        ('bounds', -112.85, 40.125, -111.100, 41.416),
    ],
    "San Diego FLY": [
        ('bounds', -117.966, 32.5, -116.300, 33.610),
    ],
    "San Francisco FLY": [
        ('bounds', -123.15,37.008, -121.382,38.19),
    ],
    "Seattle FLY": [
        ('bounds', -123.183, 46.75, -121.59, 48.061),
    ],
    "Portland FLY": [
        ('bounds', -123.183, 45.2, -122.076, 46.0166),
    ],
    "Tampa FLY": [
        ('bounds', -83.09, 27.296, -81.833, 28.59)
    ],
    "Orlando FLY": [
        ('bounds', -82.016, 27.83, -80.146, 29.194)
    ],

    # ----------- Grand Canyon (part of FLY charts) ------------

    "Grand Canyon Air Tour Operators": [
        ('bounds', -114.108, 35.633, -111.319, 36.641),
        ('box', -111.65, 36.341, -111, 37),
    ],
}

# charts Makefile
TOP=.
include $(TOP)/Makefile.mk

airspace: flake8
	python3 src/airspace.py

cloudahoy: flake8
	python3 src/cloudahoy.py

elevation_download: flake8
	python3 src/elevation_download.py

chart_extract: flake8
	python3 src/chart_extract.py

tile_extract: flake8
	python3 src/tile_extract.py

chart_list_update: flake8
	python3 src/chart_list_update.py

chart_download: flake8
	python3 src/chart_download.py

chart_shapes_download: flake8
	python3 src/chart_shapes_download.py

update-all: chart_list_update chart_download chart_extract chart_shapes_download


flake8:
	flake8 --config $(TOP)/flake8.config src/*.py

test: flake8
	python3 test.py


install_packages:
	pip3 install pyproj
	pip3 install panda3d
	pip3 install pyshp
	pip3 install affine
	pip3 install shapely
	pip3 install lxml
	pip3 install pillow
	pip3 install redis
	pip3 install numpy
	pip3 install requests
	pip3 install python-dateutil
	pip3 install gdal
	pip3 install cv2

# GoogleMaps API Key AIzaSyBh1uArKkL2r9IxPVRA2Xj3wviuii-zdLE

-include Makefile.$(USER)

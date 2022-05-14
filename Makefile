# charts Makefile
TOP=.
PIP3=pip3
FLAKE8=flake8
PYTHON=/usr/local/bin/python3

all: update chart_tiler airspace_tiler

update: chart_list_update chart_data_download airport_data_download chart_shapes_download

chart_list_update: flake8
	$(PYTHON) src/chart_list_update.py

chart_data_download: flake8
	$(PYTHON) src/chart_data_download.py

chart_shapes_download: flake8
	$(PYTHON) src/chart_shapes_download.py

boundary_shapes_download: flake8
	$(PYTHON) src/boundary_shapes_download.py

airport_data_download: flake8
	$(PYTHON) src/airport_data_download.py

chart_tiler: flake8
	$(PYTHON) src/chart_tiler.py

airspace_tiler: flake8
	$(PYTHON) src/airspace_tiler.py

airspace_shapes: flake8
	$(PYTHON) src/airspace_shapes.py

airspace_combiner: flake8
	$(PYTHON) src/combiner.py

airspace_edit: flake8
	$(PYTHON) src/airspace_edit.py

flake8:
	$(FLAKE8) --config $(TOP)/flake8.config src/*.py

install_packages:
	$(PIP3) install -r requirements.txt

kill:
	killall -9 Python

.FORCE:

-include Makefile.$(USER)

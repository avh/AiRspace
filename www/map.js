// (c)2022 Artfahrt Inc.

d2r = 3.1415972 / 180
Cesium.Camera.DEFAULT_VIEW_RECTANGLE = Cesium.Rectangle.fromDegrees(-120, 20, -80, 50);
Cesium.Camera.DEFAULT_VIEW_FACTOR = 0;
Cesium.Ion.defaultAccessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiIwMDU1NzUwNi0yNjdjLTRjYTktOTJhZS02ZTMxMWI5YmNhMGEiLCJpZCI6ODg0MSwiaWF0IjoxNjI1MDIwMTk3fQ.PKYn_UKdoBoXROZTihLa_WmmpmRLEWg38uEXxFniHeI';
var activeLayers = new Set();
var activeAirports = new Set();


let params = new URLSearchParams(window.location.search);

var viewer = new Cesium.Viewer('cesiumContainer', {
    baseLayerPicker : false,
    terrainProvider : new Cesium.EllipsoidTerrainProvider({}),
    timeline: false,
    shadows: true,
});
viewer.camera.changed.addEventListener(function() {
    if (viewer.camera._suspendTerrainAdjustment && viewer.scene.mode === Cesium.SceneMode.SCENE3D) {
        viewer.camera._suspendTerrainAdjustment = false;
        viewer.camera._adjustHeightForTerrain();
    }
});

if (params.get('debug') != null) {
    viewer.extend(Cesium.viewerCesium3DTilesInspectorMixin);
    var inspectorViewModel = viewer.cesium3DTilesInspector.viewModel;
}

sec_layer = new Cesium.UrlTemplateImageryProvider({
    url : 'tiles/sec/{z}/{x}/{y}.png',
    credit : 'Artfahrt Inc',
    hasAlphaChannel: true,
    maximumLevel: 12,
});
viewer.scene.imageryLayers.addImageryProvider(sec_layer);

tac_layer = new Cesium.UrlTemplateImageryProvider({
    url : 'tiles/tac/{z}/{x}/{y}.png',
    credit : 'Artfahrt Inc',
    hasAlphaChannel: true,
    //minimumLevel: 8,
    maximumLevel: 12,
});
viewer.scene.imageryLayers.addImageryProvider(tac_layer);

viewer.scene.imageryLayers.get(0).show = false;
viewer.scene.imageryLayers.get(1).show = false;
viewer.scene.imageryLayers.get(2).show = false;
viewer.scene.globe.depthTestAgainstTerrain = true;
viewer.scene.globe.terrainExaggeration = 5.0;

airports = new Map()

function showAirport(airport, on)
{
    if (!airports.has(airport)) {
        airports.set(airport, new Cesium.Cesium3DTileset({
            url: 'tiles/airports/' + airport + ".json"
        }));
    }
    airspace = airports.get(airport);
    if (on) {
        if (!viewer.scene.primitives.contains(airspace)) {
            viewer.scene.primitives.add(airspace).readyPromise.then(function(tileset) {
                if (airspace.extras.flyto) {
                    viewer.flyTo(airspace, {
                        offset: new Cesium.HeadingPitchRange(0*d2r, -50*d2r, airspace.extras.height)
                    });
                }
            });
        }
    } else {
        viewer.scene.primitives.remove(airspace);
        airports.delete(airport);
    }
}

function showLayer(name, on)
{
    if (name == 'EARTH') {
        viewer.scene.imageryLayers.get(0).show = on;
    } else if (name == 'SEC') {
        viewer.scene.imageryLayers.get(1).show = on;
    } else if (name == 'TAC') {
        viewer.scene.imageryLayers.get(2).show = on;
    } else if (name == 'TERRAIN') {
        if (on) {
	    viewer.terrainProvider = Cesium.createWorldTerrain({
                requestWaterMask : false,
                requestVertexNormals : true,
            });
        } else {
            viewer.terrainProvider = new Cesium.EllipsoidTerrainProvider({});
        }
    } else if (name == 'CLASS_B') {
        showAirport('CLASS_B', on);
    } else if (name == 'CLASS_C') {
        showAirport('CLASS_C', on);
    } else if (name == 'CLASS_D') {
        showAirport('CLASS_D', on);
    }
}

function saveState()
{
    var state = [];
    $('.layer').each(function() {
        if (this.checked) {
            state.push($(this).attr('id'));
        }
    });
    state = state.join(',');
    $.cookie('map.layers', state)
}

$(document).ready(function() {
    layers = $.cookie('map.layers');
    if (layers == undefined) {
        layers = "EARTH,SEC,TAC,CLASS_B,CLASS_C,CLASS_D";
    }
    for (layer of layers.split(',')) {
        showLayer(layer, true)
        $('#' + layer).prop('checked', true)
    }
    $('.layer').change(function () {
        showLayer($(this).attr('id'), this.checked);
        saveState();
    });
    $('#airports').keyup(function (e) {
        if (e.keyCode == 13) {
            for (airport of this.value.split(',')) {
                airport = airport.toUpperCase();
                showAirport(airport, !airports.has(airport));
            }
        }
    });

    // remember camera position
    function toStringCatesian3(p) {
        return p.x + "," + p.y + "," + p.z;
    }
    function getCartesian3(str) {
        strs = str.split(',');
        return new Cesium.Cartesian3(parseFloat(strs[0]), parseFloat(strs[1]), parseFloat(strs[2]));
    }
    viewer.camera.moveEnd.addEventListener(function() {
        $.cookie("map.camera.position", toStringCatesian3(viewer.camera.position));
        $.cookie("map.camera.direction", toStringCatesian3(viewer.camera.direction));
        $.cookie("map.camera.up", toStringCatesian3(viewer.camera.up));
    });
    if ($.cookie('map.camera.position') != undefined) {
        viewer.camera.position = getCartesian3($.cookie('map.camera.position'))
    }
    if ($.cookie('map.camera.direction') != undefined) {
        viewer.camera.direction = getCartesian3($.cookie('map.camera.direction'))
    }
    if ($.cookie('map.camera.up') != undefined) {
        viewer.camera.up = getCartesian3($.cookie('map.camera.up'))
    }
});

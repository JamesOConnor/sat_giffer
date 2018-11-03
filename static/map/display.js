var mymap = L.map('mapid').setView([51.505, -0.09], 13);
var Esri_WorldImagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
});
Esri_WorldImagery.addTo(mymap);

var drawnItems = new L.FeatureGroup();
mymap.addLayer(drawnItems);
var drawControl = new L.Control.Draw({
    draw: {
        polygon: false,
        marker: false,
        polyline:false,
        circlemarker:false,
        circle:false
    },
    edit: {
        featureGroup: drawnItems,
        edit: false
    }
});

mymap.addControl(drawControl);
mymap.on(L.Draw.Event.CREATED, function (e) {
   layer = e.layer;
   console.log(layer);
   mymap.addLayer(layer);
});
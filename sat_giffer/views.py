import base64
import json
import logging
import os
from io import BytesIO

import sentinelhub
from django.http import HttpResponse
from django.shortcuts import render
from rasterio.warp import transform_bounds
from sentinelhub import common
from shapely.geometry import box

from src.giffer import *

logging.basicConfig(format='%(asctime)s %(message)s', filename='sat-giffer.log',level=logging.INFO)

def leaflet_map(request):
    """
    Show the slippy map as a view
    :param request:
    :return:
    """
    return render(request, 'leaflet_map.html')


def get_gif(request):
    """
    Generate a gif for the bounds included in the request body
    :param request:
    :return: A message with an s3 URL where the file is hosted
    """
    body = request.GET.get('bounds', 'default')
    toa = request.GET.get('toa', False)
    s, w, n, e = body.split(',')
    bbox_crs = 'epsg:4326'
    boundingbox = box(float(w), float(s), float(e), float(n))
    bbox = common.BBox(boundingbox.bounds, crs=bbox_crs)
    search_results = sentinelhub.opensearch.get_area_info(bbox, ('2015-06-01', datetime.now().strftime('%Y-%m-%d')), maxcc=0.1)
    if len(search_results) == 0:
        return HttpResponse("Couldn't find any images for that search!")

    # Select a single tile (redupe)
    first_tile = '/'.join(search_results[0]['properties']['s3URI'].split('/')[4:7])

    out_crs = 'epsg:%s' % get_utm_srid(search_results[0]['properties']['centroid']['coordinates'][1],
                                       search_results[0]['properties']['centroid']['coordinates'][0])

    bounds = transform_bounds(bbox_crs, out_crs, *boundingbox.bounds, densify_pts=21)
    bounds2 = transform_bounds(bbox_crs, 'epsg:3410', *boundingbox.bounds, densify_pts=21)

    equal_area_boundingbox = box(float(bounds2[0]), float(bounds2[1]), float(bounds2[2]), float(bounds2[3]))
    if equal_area_boundingbox.area / 10000 > 1000:
        return HttpResponse('Selected area too large, please select an area under 1000 ha')

    vrt_params = dict(add_alpha=True, crs=out_crs)
    nodata = 0
    if nodata is not None:
        vrt_params.update(
            dict(
                nodata=nodata,
                add_alpha=False,
                src_nodata=nodata,
                init_dest_nodata=False,
            )
        )

    os.environ["AWS_REQUEST_PAYER"] = "requester"

    keys = get_s3_urls(first_tile, search_results, toa)

    if len(keys) > 10:
        keys = keys[:10]
    keys = keys[:1]
    logging.info(keys)
    data = get_data_for_keys(bounds, keys, out_crs, vrt_params)
    logging.info('Data retrieved')
    sio = BytesIO()
    im = Image.fromarray((data[0].clip(0,1)*255).astype(np.uint8))
    im.save(sio, 'png')
    sio.seek(0)
    im.save('gifs/%s.png'%body)
    url = "https://s3.eu-central-1.amazonaws.com/sat-giffer/gifs/%s.png"%body
    upload_file_to_s3('gifs/%s.png'%body)
    im = base64.b64encode(sio.read()).decode()
    stream_response = "data:image/png;base64," + im
    date = '-'.join(keys[0].split('/')[-6:-3])
    resp = json.dumps({'data':'<img src = "%s"/> <br> <p> Date: %s, Mean NDVI: %0.2f </p>'%(stream_response, date, data[0].mean()), 'url':url,
                       'bounds':[body.split(',')[:2], body.split(',')[2:]]})
    return HttpResponse(resp)

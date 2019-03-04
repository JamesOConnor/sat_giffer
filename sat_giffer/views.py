import datetime
import logging
import os

import imageio
import sentinelhub
from django.http import HttpResponse
from django.shortcuts import render
from rasterio.warp import transform_bounds
from sentinelhub import common
from shapely.geometry import box

from src.giffer import *

logging.basicConfig(format='%(asctime)s %(message)s', filename='sat-giffer.log', level=logging.INFO)

def leaflet_map(request):
    """
    Show the slippy map as a view
    :param request:
    :return:
    """
    return render(request, 'leaflet_map.html')

def date_formatter(date):
    if not date:
        return datetime.datetime.now().date().strftime('%Y-%m-%d')
    day = date.split('/')[1]
    month = date.split('/')[0]
    year = date.split('/')[2]
    return '%s-%s-%s'%(year, month, day)


def get_gif(request):
    """
    Generate a gif for the bounds included in the request body
    :param request:
    :return: A message with an s3 URL where the file is hosted
    """
    body = request.GET.get('bounds', 'default')
    toa = request.GET.get('toa', True)
    start_date = request.GET.get('start_date')
    if not start_date:
        start_date = '01/10/2018'
    end_date = request.GET.get('end_date', None)
    start_date = date_formatter(start_date)
    end_date = date_formatter(end_date)

    s, w, n, e = body.split(',')
    bbox_crs = 'epsg:4326'
    boundingbox = box(float(w), float(s), float(e), float(n))
    bbox = common.BBox(boundingbox.bounds, crs=bbox_crs)
    search_results = sentinelhub.opensearch.get_area_info(bbox, (start_date, end_date), maxcc=0.1)
    if len(search_results) == 0:
        return HttpResponse("Couldn't find any images for that search!")

    # Select a single tile (redupe)
    first_tile = '/'.join(search_results[0]['properties']['s3Path'].split('/')[1:4])
    out_crs = 'epsg:%s' % get_utm_srid(search_results[-1]['properties']['centroid']['coordinates'][1],
                                       search_results[-1]['properties']['centroid']['coordinates'][0])

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
    logging.info(keys)
    data = get_data_for_keys(bounds, keys, out_crs, vrt_params)
    logging.info('Data retrieved')
    drawn = make_gif(keys, data, toa)
    logging.info('Dates added to image files')
    if len(drawn) == 0:
        return HttpResponse("Couldn't find any cloud free images for that search!")
    imageio.mimwrite('gifs/%s.gif' % body, drawn[::-1], fps=1)
    upload_file_to_s3(body)
    out_body = 'Your file is ready <a href="https://s3.eu-central-1.amazonaws.com/sat-giffer/gifs/%s.gif">here</a><br>' % body
    return HttpResponse(out_body)

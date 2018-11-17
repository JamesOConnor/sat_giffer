import os

import boto3
import imageio
import sentinelhub
from django.http import HttpResponse
from django.shortcuts import render
from rasterio.warp import transform_bounds
from sentinelhub import common
from shapely.geometry import box

from src.giffer import *

MAX_WORKERS = 4

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
    toa = request.GET.get('toa', True)
    s, w, n, e = body.split(',')
    bbox_crs = 'epsg:4326'
    boundingbox = box(float(w), float(s), float(e), float(n))
    bbox = common.BBox(boundingbox.bounds, crs='epsg:4326')
    search_results = sentinelhub.opensearch.get_area_info(bbox, ('2015-06-01', '2018-11-01'), maxcc=0.1)
    if len(search_results) == 0:
        return HttpResponse("Couldn't find any images for that search!")

    # Select a single tile (redupe)
    first_tile = '/'.join(search_results[0]['properties']['s3URI'].split('/')[4:7])

    out_crs = 'epsg:%s' % get_utm_srid(search_results[0]['properties']['centroid']['coordinates'][1],
                                       search_results[0]['properties']['centroid']['coordinates'][0])

    bounds = transform_bounds(bbox_crs, out_crs, *boundingbox.bounds, densify_pts=21)
    bounds2 = transform_bounds(bbox_crs, 'epsg:3410', *boundingbox.bounds, densify_pts=21)

    equal_area_boundingbox = box(float(bounds2[0]), float(bounds2[1]), float(bounds2[2]), float(bounds2[3]))
    if equal_area_boundingbox.area / 10000 < 100:
        return HttpResponse('Selected area too small, please select an area over 100 ha')
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

    if toa:
        keys = [i['properties']['s3URI'] for i in search_results if
                first_tile in i['properties']['s3URI']]
    else:
        keys = [i['properties']['s3URI'].replace('l1c', 'l2a') + 'R10m/' for i in search_results if
                first_tile in i['properties']['s3URI']]

    with futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        _worker = partial(rgb_for_key, bounds=bounds, vrt_params=vrt_params, out_crs=out_crs)
        data = list(executor.map(_worker, keys))
        gc.collect()

    drawn = make_gif(keys, data)
    if len(drawn) == 0:
        return HttpResponse("Couldn't find any cloud free images for that search!")
    imageio.mimwrite('gifs/%s.gif' % body, drawn[::-1], fps=1)
    s3_client = boto3.Session(settings.AWS_KEY, settings.AWS_SECRET).client('s3', region_name='eu-central-1')
    s3_client.upload_file(Filename='gifs/%s.gif' % body, Bucket='sat-giffer', Key='gifs/%s.gif' % body,
                          ExtraArgs={'ACL': 'public-read'})
    out_body = 'Your file is ready <a href="https://s3.eu-central-1.amazonaws.com/sat-giffer/gifs/%s.gif">here</a><br>' % body
    return HttpResponse(out_body)


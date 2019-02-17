import base64
import datetime
import json
import logging
import os
from io import BytesIO

import requests
import sentinelhub
import wget
from django.http import HttpResponse
from django.shortcuts import render
from rasterio.warp import transform_bounds
from sentinelhub import common
from shapely.geometry import box
import pandas as pd

from src.giffer import *

logging.basicConfig(format='%(asctime)s %(message)s', filename='sat-giffer.log', level=logging.INFO)

query_dict = {'34TEK': '(40.112712, 21.580847)', '34TFK': '(40.116753, 22.734850)', '34SFJ': '(39.312515, 22.898818)',
              '34SEJ': '(39.182069, 21.772864)'}

SEARCH_URL = 'https://scihub.copernicus.eu/dhus/search?q=footprint:"Intersects%s" ' \
             'AND ingestiondate:[2018-01-14T20:28:45.963Z TO 2019-01-14T20:28:45.963Z] ' \
             'AND producttype:S2MSI2A ' \
             'AND cloudcoverpercentage:[0 TO 0.1]' \
             '&rows=100&start=0&format=json'


def get_file(url, fname):
    r = requests.get(url, stream=True, auth=('ucfajoc', 'ibi7Fepi'))
    with open(fname, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()
    return fname

#
# for key in query_dict.keys():
#     s = SEARCH_URL % query_dict[key]
#     r = requests.get(s, auth=('ucfajoc', 'ibi7Fepi')).json()
#     try:
#         first = r['feed']['entry'][0]
#     except:
#         try:
#             first = r['feed']['entry']
#         except:
#             continue
#     url = first['link'][0]['href']
#     date = first['date'][0]['content'].split('T')[0]
#     print('downloading to %s'%'%s_%s.zip'%(key, date))
#     fn = '/media/khcbgdev005/khcbgdev0051/george2/%s_%s.zip'%(key, date)
#     if os.path.exists(fn):
#         continue
#     get_file(url, fn)


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
    start_date = request.GET.get('start_date', '01/01/2019')
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
    first_tile = '/'.join([search_result['properties']['s3Path'] for search_result in search_results if
                           '/1/' not in search_result['properties']['s3Path']][0].split('/')[1:4])

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
    #keys = keys[:1]
    logging.info(keys)
    print(datetime.datetime.now())
    data = get_data_for_keys(bounds, keys, out_crs, vrt_params)
    print(datetime.datetime.now())
    logging.info('Data retrieved')
    im = Image.fromarray((data[0].clip(0, 1) * 255).astype(np.uint8))
    im.save('gifs/%s.png' % body)
    upload_file_to_s3('gifs/%s.png' % body)

    url = "https://s3.eu-central-1.amazonaws.com/sat-giffer/gifs/%s.png" % body
    data_raw = [['-'.join(keys[n].split('/')[-5:-2]), data[n].mean(), data[n].min(), data[n].max(), data[n].std()] for n in range(len(data))]
    data = pd.DataFrame(data_raw, columns=['Date', 'Mean', 'Min', 'Max', 'Std'])
    data['Date'] = pd.to_datetime(data['Date'])
    data['Date'] = datetime_to_moment(data['Date'])
    resp = json.dumps({'data': data.to_json(orient='records'), 'url': url, 'bounds': [body.split(',')[:2], body.split(',')[2:]]})
    return HttpResponse(resp)

def datetime_to_moment(series):
    """
    Returns a moment (for use in javascript) given a datetime pandas series
    :param series: pandas series of datetime objects
    :return: pandas series of moments
    """
    return json.loads(series.to_json(orient='values'))

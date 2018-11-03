from django.http import HttpResponse
from django.shortcuts import render
from rasterio.session import AWSSession

from sat_giffer import settings
from rasterio.warp import calculate_default_transform, transform_bounds, Resampling
from rasterio import transform
from concurrent import futures
import math
from functools import partial
import numpy as np
from shapely.geometry import box
import rasterio
from rasterio.vrt import WarpedVRT
from sentinelhub import common
import sentinelhub
import os
import imageio
import gc
from PIL import Image, ImageDraw

session = rasterio.Env(AWSSession(aws_access_key_id=settings.AWS_KEY, aws_secret_access_key=settings.AWS_SECRET))

def get_data(band, key, bounds, vrt_params):
    f=key+'B0%s.jp2'%band
    with session:
        with rasterio.open(f) as src:
            vrt_transform, vrt_width, vrt_height = get_vrt_transform(src, bounds)

            vrt_width = round(vrt_width)
            vrt_height = round(vrt_height)
            vrt_params.update(
                dict(transform=vrt_transform, width=vrt_width, height=vrt_height)
            )

            with WarpedVRT(src, **vrt_params) as vrt:
                data = vrt.read(
                    out_shape=(1, vrt_height, vrt_width),
                    resampling=Resampling.bilinear,
                    indexes=[1],
                )
        gc.collect()
        return data

def rgb_for_key(key, bounds=None, vrt_params=None):
    print(key)
    bands = ['2', '3', '4']
    _worker = partial(get_data, key=key, bounds=bounds, vrt_params=vrt_params)
    with futures.ProcessPoolExecutor(max_workers=3) as executor:
        try:
            data = np.concatenate(list(executor.map(_worker, bands)))
        except:
            return
        gc.collect()
    data2 = np.zeros((data.shape[1], data.shape[2], data.shape[0]))
    for i in range(3):
        data2[:,:,abs(i-2)] = data[i,:,:]
    return data2

def get_vrt_transform(src, bounds, bounds_crs='epsg:3857'):
    """Calculate VRT transform.
    Attributes
    ----------
    src : rasterio.io.DatasetReader
        Rasterio io.DatasetReader object
    bounds : list
        Bounds (left, bottom, right, top)
    bounds_crs : str
        Coordinate reference system string (default "epsg:3857")
    Returns
    -------
    vrt_transform: Affine
        Output affine transformation matrix
    vrt_width, vrt_height: int
        Output dimensions
    """
    dst_transform, _, _ = calculate_default_transform(src.crs,
                                                      bounds_crs,
                                                      src.width,
                                                      src.height,
                                                      *src.bounds)
    w, s, e, n = bounds
    vrt_width = math.ceil((e - w) / dst_transform.a)
    vrt_height = math.ceil((s - n) / dst_transform.e)

    vrt_transform = transform.from_bounds(w, s, e, n, vrt_width, vrt_height)

    return vrt_transform, vrt_width, vrt_height


def leaflet_map(request):
    return render(request, 'leaflet_map.html')


def get_gif(request):
    body = request.GET.get('bounds', 'default')
    toa = request.GET.get('toa', True)
    s, w, n, e = body.split(',')
    bbox_crs = 'epsg:4326'
    pg = box(float(w), float(s), float(e), float(n))
    bbox = common.BBox(pg.bounds, crs='epsg:4326')
    search_results = sentinelhub.opensearch.get_area_info(bbox, ('2018-06-01', '2018-09-01'), maxcc=0.1)
    first_tile = '/'.join(search_results[0]['properties']['s3URI'].split('/')[4:7])
    out_crs = 'epsg:3857'
    bounds = transform_bounds(bbox_crs, out_crs, *pg.bounds, densify_pts=21)

    vrt_params = dict(add_alpha=True, crs=out_crs, resampling=Resampling.bilinear)

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

    with futures.ProcessPoolExecutor(max_workers=2) as executor:
        _worker = partial(rgb_for_key, bounds=bounds, vrt_params=vrt_params)
        data = list(executor.map(_worker, keys))
        gc.collect()

    drawn = make_gif(keys, data)
    imageio.mimwrite('%s.gif'%body, drawn[::-1], fps=1)
    return HttpResponse(body)

def make_gif(keys, data):
    drawn = []
    for fn, i in zip(keys, data):
        if i is None:
            continue
        if len(np.where(i[:, :, 2] == 0)[0]) > i[:, :, 2].size * 0.3:
            continue
        if len(np.where(i[:, :, 2] > 2000)[0]) < i[:, :, 2].size * 0.2:
            i = np.hstack((np.zeros((i.shape[0], 100, 3)), i))
            im = Image.fromarray(np.clip((i * 255 / 2000), 0, 255).astype(np.uint8))
            draw = ImageDraw.Draw(im)
            draw.text((20, 50), '%s' % '-'.join(fn.split('/')[-5:-2]), fill=(255, 255, 255, 255))
            drawn.append(np.array(im))
    return drawn
import gc
import math
import sys
from concurrent import futures
from functools import partial

import boto3
import numpy as np
import rasterio
from PIL import Image, ImageDraw
from sat_giffer import settings
from rasterio import transform
from rasterio.session import AWSSession
from rasterio.vrt import WarpedVRT
from rasterio.warp import calculate_default_transform, Resampling

session = rasterio.Env(
    AWSSession(aws_access_key_id=settings.AWS_KEY, aws_secret_access_key=settings.AWS_SECRET)) if 'test' not in \
                                                                                                  sys.argv[0] else None
MAX_WORKERS = 5


def get_cropped_data_from_bucket(band, key, bounds, vrt_params, out_crs):
    """
    Recovered the data for a given band for a given scene
    :param band: Number of the band of interest
    :param key: Tile location on AWS
    :param bounds: bounding box of the area of interest
    :param vrt_params: meta dictionary for resulting fle
    :param out_crs: output coordinate system
    :return: the cropped data from the band for the bounds
    """
    f = key + 'B0%s.jp2' % band
    with session:
        with rasterio.open(f) as src:
            vrt_transform, vrt_width, vrt_height = get_vrt_transform(src, bounds, bounds_crs=out_crs)
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
        return data / 10000


def ndvi_for_key(key, bounds=None, vrt_params=None, out_crs=None):
    """
    Loops over nir and red bands to generate an ndvi image
    :param key:
    :param bounds:
    :param vrt_params:
    :param out_crs:
    :return:
    """
    print('222')
    bands = ['4', '8']
    _worker = partial(get_cropped_data_from_bucket, key=key, bounds=bounds, vrt_params=vrt_params, out_crs=out_crs)
    with futures.ProcessPoolExecutor(max_workers=3) as executor:
        try:
            data = np.concatenate(list(executor.map(_worker, bands)))
        except:
            return
        gc.collect()
    ndvi = (data[1] - data[0])/(data[1] + data[0])
    return ndvi


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
    print('yes')
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


def get_utm_srid(lat, lon):
    """
    Calculate which utm zone the AOI should fall into
    :param lat: Latitude in WGS84
    :param lon: Longitude in WGS84
    :return: Integer EPSG code
    """
    return int(32700 - round((45 + lat) / 90, 0) * 100 + round((183 + lon) / 6, 0))


def make_gif(keys, data, toa):
    """
    Combine the data into a single array
    :param keys: Location of the tiles on AWS
    :param data: The image arrays
    :param toa: toa True/False
    :return: Data with dates embedded on the gif
    """
    drawn = []
    for fn, i in zip(keys, data):
        if i is None:
            continue
        if len(np.where(i[:, :, 2] == 0)[0]) > i[:, :, 2].size * 0.8:
            continue
        if len(np.where(i[:, :, 2] > 2000)[0]) < i[:, :, 2].size * 0.2:
            i = np.hstack((np.zeros((i.shape[0], 100, 3)), i))
            im = Image.fromarray(np.clip((i * 255 / 2000), 0, 255).astype(np.uint8))
            draw = ImageDraw.Draw(im)
            if toa:
                draw.text((20, 50), '%s' % '-'.join(fn.split('/')[-5:-2]), fill=(255, 255, 255, 255))
            else:
                draw.text((20, 50), '%s' % '-'.join(fn.split('/')[-6:-3]), fill=(255, 255, 255, 255))
            drawn.append(np.array(im))
    return drawn


def upload_file_to_s3(body):
    """
    Uploads a given file to s3
    :param body: filename
    :return: None
    """
    s3_client = boto3.Session(settings.AWS_KEY, settings.AWS_SECRET).client('s3', region_name='eu-central-1')
    s3_client.upload_file(Filename='%s' % body, Bucket='sat-giffer', Key='%s' % body,
                          ExtraArgs={'ACL': 'public-read'})


def get_s3_urls(first_tile, search_results, toa):
    """
    Get a filtered list of S3 URIs given a tile id and search results
    :param first_tile: first tile to appear in the search
    :param search_results: full results of the search
    :param toa: whether to attempt to retrieve toa/boa data
    :return: list of s3 URIs
    """
    if toa:
        keys = [i['properties']['s3URI'] for i in search_results if
                first_tile in i['properties']['s3URI']]
    else:
        keys = [i['properties']['s3URI'].replace('l1c', 'l2a') + 'R10m/' for i in search_results if
                first_tile in i['properties']['s3URI']]
    return keys


def get_data_for_keys(bounds, keys, out_crs, vrt_params):
    """
    Get RGB data from AWS given a list of keys
    :param bounds: bounding box of AOI
    :param keys: List of S3 URIS
    :param out_crs: output crs
    :param vrt_params: params for transformation
    :return: the data array
    """
    with futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        _worker = partial(ndvi_for_key, bounds=bounds, vrt_params=vrt_params, out_crs=out_crs)
        data = list(executor.map(_worker, keys))
        gc.collect()
    return data

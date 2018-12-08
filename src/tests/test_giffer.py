import unittest

import numpy as np

from src.giffer import make_gif, get_s3_urls
from sat_giffer import settings


class gifferTests(unittest.TestCase):
    def setUp(self):
        self.keys = np.load(settings.ROOT_DIR + '/src/tests/fixtures/keys.npy')
        self.keys2 = np.load(settings.ROOT_DIR + '/src/tests/fixtures/keys2.npy')
        self.keys_toa = np.load(settings.ROOT_DIR + '/src/tests/fixtures/keys_toa.npy')
        self.data = np.load(settings.ROOT_DIR + '/src/tests/fixtures/data.npy')
        self.expected = np.load(settings.ROOT_DIR + '/src/tests/fixtures/gif.npy')
        self.search_results = np.load(settings.ROOT_DIR + '/src/tests/fixtures/search_results.npy')
        self.first_tile = '29/U/PV'

    def test_make_gif(self):
        """
        Test gifs are being produced correctly
        """
        actual = make_gif(self.keys, self.data, toa=True)
        np.testing.assert_array_equal(actual, self.expected)

    def test_get_s3_urls_toa(self):
        """
        Images being filtered to toa URIs correctly
        """
        actual = get_s3_urls(self.first_tile, self.search_results, toa=False)
        np.testing.assert_array_equal(actual, self.keys2)

    def test_get_s3_urls_boa(self):
        """
        Images being filtered to boa URIs correctly
        """
        actual = get_s3_urls(self.first_tile, self.search_results, toa=True)
        np.testing.assert_array_equal(actual, self.keys_toa)
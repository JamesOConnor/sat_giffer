import unittest

import numpy as np

from src.giffer import make_gif
from sat_giffer import settings

class gifferTests(unittest.TestCase):
    def setUp(self):
        self.keys = np.load(settings.ROOT_DIR + '/src/tests/fixtures/keys.npy')
        self.data = np.load(settings.ROOT_DIR + '/src/tests/fixtures/data.npy')
        self.expected = np.load(settings.ROOT_DIR + '/src/tests/fixtures/gif.npy')

    def test_make_gif(self):
        """
        Test gifs are being produced correctly
        """
        actual = make_gif(self.keys, self.data)
        np.testing.assert_array_equal(actual, self.expected)
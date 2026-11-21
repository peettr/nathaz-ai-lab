import unittest
import numpy as np
from apcp_identical_v2 import select_identical_apcp

class Msg:
    def __init__(self, blob, values, mask=None):
        self.blob = blob
        self.values = np.ma.array(values, mask=mask)
    def tostring(self):
        return self.blob

class TestAPCP(unittest.TestCase):
    def test_identical_bytes(self):
        m = Msg(b'a', [1., 2.])
        selected, info = select_identical_apcp([m, Msg(b'a', [1., 2.])])
        self.assertIs(selected, m)
        self.assertEqual(info['dedup_identical'], 1)
        self.assertEqual(info['duplicates'][0]['equivalence'], 'same_grib_sha256')
    def test_equal_values(self):
        _, info = select_identical_apcp([Msg(b'a', [1., 2.]), Msg(b'b', [1., 2.])])
        self.assertEqual(info['duplicates'][0]['equivalence'], 'same_values_and_mask')
    def test_different_values_stop(self):
        with self.assertRaisesRegex(ValueError, 'nonidentical'):
            select_identical_apcp([Msg(b'a', [1., 2.]), Msg(b'b', [1., 3.])])
    def test_different_mask_stop(self):
        with self.assertRaisesRegex(ValueError, 'nonidentical'):
            select_identical_apcp([Msg(b'a', [1., 2.], [False, True]), Msg(b'b', [1., 2.], [False, False])])
    def test_missing_stop(self):
        with self.assertRaisesRegex(ValueError, 'messages=0'):
            select_identical_apcp([])

if __name__ == '__main__': unittest.main()

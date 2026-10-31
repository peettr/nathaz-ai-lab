"""Synthetic fixtures only: these are NOT CRC job measurements."""
import unittest
from crc_gpu_bind import resolve, bus_key

CONFIG = 'complex_values gpu_card=4(gpu0[cuda_id=0,device=/dev/nvidia0] \\\n gpu1[cuda_id=1,device=/dev/nvidia1] gpu2[cuda_id=2,device=/dev/nvidia2])'
INVENTORY = '0, 00000000:17:00.0, GPU-aaaa-0000, NVIDIA A10\n1, 00000000:65:00.0, GPU-bbbb-1111, NVIDIA A10\n'
MINORS = {bus_key('0000:17:00.0'):0, bus_key('0000:65:00.0'):1}

def check(env, config=CONFIG, inventory=INVENTORY, minors=MINORS):
    return resolve(env, config, inventory, minors)

class BindingTests(unittest.TestCase):
    def test_grant_not_resource_count(self):
        self.assertEqual(check({'SGE_HGR_gpu_card':'gpu1'})[3], 'GPU-bbbb-1111')
    def test_minor_not_nvml_index(self):
        self.assertEqual(check({'SGE_HGR_gpu_card':'gpu1'}, inventory='0, 00000000:65:00.0, GPU-bbbb-1111, NVIDIA A10')[3], 'GPU-bbbb-1111')
    def test_proc_minor_not_nvml_index(self):
        self.assertEqual(check({'SGE_HGR_gpu_card':'gpu1'}, inventory='0, 00000000:65:00.0, GPU-bbbb-1111, NVIDIA A10')[1], '/dev/nvidia1')
    def test_missing_bus_fails_closed(self):
        with self.assertRaises(ValueError): check({'SGE_HGR_gpu_card':'gpu1'}, minors={bus_key('0000:17:00.0'):0})
    def test_no_grant_even_with_cvd(self):
        with self.assertRaises(ValueError): check({'CUDA_VISIBLE_DEVICES':'0'})
    def test_multiple_grants(self):
        with self.assertRaises(ValueError): check({'SGE_HGR_gpu_card':'gpu0 gpu1'})
    def test_task_conflict(self):
        with self.assertRaises(ValueError): check({'SGE_HGR_gpu_card':'gpu1','SGE_HGR_TASK_gpu_card':'gpu0'})
    def test_unknown_grant(self):
        with self.assertRaises(ValueError): check({'SGE_HGR_gpu_card':'gpu3'})
    def test_device_missing(self):
        with self.assertRaises(ValueError): check({'SGE_HGR_gpu_card':'gpu2'})
    def test_wrong_model(self):
        with self.assertRaises(ValueError): check({'SGE_HGR_gpu_card':'gpu1'}, inventory=INVENTORY.replace('A10','A100'))
    def test_uuid_conflict(self):
        with self.assertRaises(ValueError): check({'SGE_HGR_gpu_card':'gpu1'}, config=CONFIG.replace('cuda_id=1','uuid=GPU-cccc-2222,cuda_id=1'))

if __name__ == '__main__': unittest.main(verbosity=2)

from pathlib import Path
import unittest
SRC = Path(__file__).parent / 'FluidX3D/src'
class Contract(unittest.TestCase):
    def test_filtered_second_layer_has_separate_previous_and_next_buffers(self):
        s=(SRC/'lbm.hpp').read_text()
        self.assertIn('ground_q_previous',s)
        self.assertIn('ground_q_next',s)
    def test_sampling_is_separate_pre_collide_kernel(self):
        s=(SRC/'lbm.cpp').read_text()
        self.assertIn('enqueue_ground_filter()',s)
        self.assertLess(s.index('enqueue_ground_filter()'),s.index('enqueue_stream_collide(); // run LBM'))
    def test_persistent_force_measurement(self):
        s=(SRC/'kernel.cpp').read_text()
        self.assertIn('ground_tau_sum',s)
        self.assertIn('ground_tau_count',s)
    def test_off_switch_has_no_extra_kernel(self):
        s=(SRC/'lbm.cpp').read_text()
        self.assertIn('#ifdef GROUND_WALL_FILTER',s)
if __name__=='__main__': unittest.main()

import unittest
from analytic_links import NATIVE_D3Q19, cylinder_q, plane_q, generate

class GeometryTests(unittest.TestCase):
    def test_direction_pairs(self):
        self.assertEqual(len(NATIVE_D3Q19),19)
        for i in range(1,19,2):
            self.assertEqual(tuple(-x for x in NATIVE_D3Q19[i]),NATIVE_D3Q19[i+1])
    def test_plane(self):
        self.assertAlmostEqual(plane_q((1,3,0),(0,1,0),1,3.25),.25,places=12)
        self.assertAlmostEqual(plane_q((1,3,0),(0,1,0),1,3.75),.75,places=12)
        self.assertIsNone(plane_q((1,3,0),(1,0,0),1,3.25))
    def test_cylinder(self):
        self.assertAlmostEqual(cylinder_q((0,0,0),(1,0,0),2,0,1.75),.25)
        self.assertAlmostEqual(cylinder_q((0,0,0),(1,0,0),2,0,1.25),.75)
    def test_sparse_native(self):
        links,stats=generate((20,12,3),'plane',plane_at=4.25)
        self.assertGreater(len(links),0)
        self.assertTrue(all(links['direction']<19))
        self.assertTrue(all((links['q']>0)&(links['q']<1)))
        self.assertEqual(stats['intersection_unresolved'],0)
        self.assertEqual(len({(int(a),int(b)) for a,b in zip(links['cell'],links['direction'])}),len(links))

# Direct transcription of kernel.cpp:1338-1350 for odd i and its even opposite.
# For a solid neighbour, stream_collide returns at 1490, leaving both slots
# untouched except for outgoing distribution writes from its fluid neighbour.
def read_incoming_even(solid_slots, t):
    return solid_slots[2 if t%2 else 1]
def write_outgoing_odd(solid_slots, t, packet):
    solid_slots[2 if t%2 else 1]=packet

class EsotericBoundaryTests(unittest.TestCase):
    def test_even_direction_delay(self):
        # Even outgoing i+1 at fluid n is written to its own channel
        # (t odd -> i, t even -> i+1). Odd incoming from solid on its
        # other side at t+1 reads the opposite channel.
        slots={1:'old_even',2:'old_odd'}
        slots[2]='new_t0'  # t=0, store_f(n, f_even)
        self.assertEqual(slots[1],'old_even')  # t=1, load_f(n, f_odd)
        slots[1]='new_t1'  # t=1 store_f(n, f_even)
        self.assertEqual(slots[2],'new_t0')  # t=2, load_f(n, f_odd)
    def test_native_solid_delay_vs_bfl_halfway(self):
        slots={1:'old_even',2:'old_odd'}
        write_outgoing_odd(slots,0,'new_t0')
        self.assertEqual(read_incoming_even(slots,1),'old_odd')
        write_outgoing_odd(slots,1,'new_t1')
        self.assertEqual(read_incoming_even(slots,2),'new_t0')
        # Bouzidi (2001) eq 6a/b at q=1/2: f_opposite(r,t+1)=f_i^c(r,t).
        # The native TYPE_S branch instead reads the packet from t-1.
        self.assertNotEqual(read_incoming_even(slots,2),'new_t1')

if __name__=='__main__':unittest.main()

"""Small analytic geometry tests; run with unittest discovery from this directory."""
import unittest
import numpy as np
from link_q import intersect_segments, tiny_unit_tests, DT, DIRS

class LinkTests(unittest.TestCase):
    def test_plane(self):
        tri=np.array([[.25,-2,-2],[.25,2,-2],[.25,0,2.]])
        ids,q=intersect_segments([[0,0,0],[0,3,0]],(1,0,0),tri)
        self.assertEqual(ids.tolist(),[0]);self.assertLess(abs(q[0]-.25),1e-6)

    def test_cube(self):
        # Axis-aligned cube occupies x in [.4,1.4], y,z in [-1,1].
        face=[np.array([[.4,-1,-1],[.4,1,-1],[.4,1,1]]),
              np.array([[.4,-1,-1],[.4,1,1],[.4,-1,1]])]
        hits=[intersect_segments([[0,.2,.1]],(1,0,0),t)[1] for t in face]
        self.assertEqual(sum(map(len,hits)),1)
        self.assertLess(abs(np.concatenate(hits)[0]-.4),1e-6)

    def test_sphere_axis_vertex(self):
        # Octahedral inscribed sphere r=1, axis ray intersects the -x vertex
        # at the *analytic* sphere q=.5 exactly. Other rays have mesh error.
        a=np.array([-1.,0.,0.]); ring=np.array([[0,1,0],[0,0,1],[0,-1,0],[0,0,-1]])
        hits=[]
        for i in range(4):
            tri=np.array([a,ring[i],ring[(i+1)%4]])
            hits.extend(intersect_segments([[-1.5,0,0]],(1,0,0),tri)[1])
        self.assertTrue(hits)
        self.assertTrue(all(abs(q-.5)<1e-6 for q in hits))
        # The multiple hits are one vertex, not multiple distinct surfaces.

    def test_lattice_contract(self):
        self.assertEqual(len(DIRS),18)
        self.assertEqual(DT.itemsize,14)
        self.assertEqual(len(set(DIRS)),18)
        self.assertEqual(DIRS[0],(0,-1,-1))
        self.assertIn('sphere_discretization_caveat',tiny_unit_tests())

if __name__=='__main__':unittest.main()

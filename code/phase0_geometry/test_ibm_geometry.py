import unittest
import numpy as np
import ibm_geometry as g

class GeometryTests(unittest.TestCase):
    def test_split_area_edge_and_normal(self):
        tri=np.array([[[0.,0.,0.],[2.,0.,0.],[0.,2.,0.]]])
        xyz,n,a=g.markers_from_triangles(tri, h=0.5)
        self.assertAlmostEqual(a.sum(),2.,places=12)
        self.assertTrue(np.allclose(n,[0,0,1]))
        self.assertTrue(np.all(np.linalg.norm(xyz[:,None,:]-xyz[None,:,:],axis=-1)>=0))
        self.assertGreater(len(xyz),1)
    def test_clean_duplicate_degenerate_and_open(self):
        tri=np.array([[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]],[[1.,0.,0.],[0.,0.,0.],[0.,1.,0.]],[[0.,0.,0.],[0.,0.,0.],[0.,1.,0.]]])
        clean,info=g.clean_mesh(tri)
        self.assertEqual(len(clean),1)
        self.assertEqual(info['duplicates'],1)
        self.assertEqual(info['degenerate'],1)
        self.assertEqual(info['open_edges'],3)
    def test_voxel_proxy_cube_and_support_boundary(self):
        # Closed cube x,y=[1,4], z=[0,3], two triangles per face.
        v=np.array([[1.,1.,0.],[4.,1.,0.],[4.,4.,0.],[1.,4.,0.],
                    [1.,1.,3.],[4.,1.,3.],[4.,4.,3.],[1.,4.,3.]])
        faces=[]
        for a,b,c,d in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
            faces.extend([v[[a,b,c]],v[[a,c,d]]])
        solid,odd=g.voxel_proxy(np.array(faces),8,8,5)
        self.assertEqual(odd,0)
        self.assertTrue(solid[1,3,3])
        self.assertFalse(solid[4,3,3])
        self.assertFalse(solid[1,0,0])
    def test_delta_partition_linear_and_force(self):
        x=np.array([4.2,3.7,6.1]); indices,w=g.support(x)
        self.assertEqual(len(indices),27)
        self.assertAlmostEqual(w.sum(),1.,places=12)
        field=1.2+2*indices[:,0]-indices[:,1]+.7*indices[:,2]
        self.assertAlmostEqual(np.dot(w,field),1.2+2*x[0]-x[1]+.7*x[2],places=12)
        area,delta_s,df=2.3,.8,np.array([1.,-2.,3.]);self.assertTrue(np.allclose((w[:,None]*area*delta_s*df).sum(axis=0),area*delta_s*df))

if __name__=='__main__':unittest.main()

"""Zero-CU Esoteric-Pull boundary preflight; not a solver validation."""
import unittest

# From FluidX3D kernel.cpp neighbors(), D3Q19 lines 959-968.
C = [(0,0,0),(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1),
     (1,1,0),(-1,-1,0),(1,0,1),(-1,0,-1),(0,1,1),(0,-1,-1),
     (1,-1,0),(-1,1,0),(1,0,-1),(-1,0,1),(0,1,-1),(0,-1,1)]


def specular_index(i):
    x,y,z = C[i]
    return C.index((x,y,-z))


def pull_location(n, i, t):
    """Exact index_f site and direction from load_f(), kernel.cpp 1338-1343."""
    if not i:
        return (n,0)
    odd = i if i%2 else i-1
    if i%2:
        return (n, odd if t%2 else odd+1)
    x,y,z = C[odd]
    return ((n[0]+x,n[1]+y,n[2]+z), odd+1 if t%2 else odd)


def push_location(n, i, t):
    """Exact index_f site and direction from store_f(), kernel.cpp 1345-1350."""
    if not i:
        return (n,0)
    odd = i if i%2 else i-1
    if i%2:
        x,y,z = C[odd]
        return ((n[0]+x,n[1]+y,n[2]+z),odd+1 if t%2 else odd)
    return (n,odd if t%2 else odd+1)


class Gate0(unittest.TestCase):
    def test_specular_direction_involution(self):
        self.assertEqual([specular_index(i) for i in range(19)],
                         [0,1,2,3,4,6,5,7,8,15,16,17,18,13,14,9,10,11,12])
        for i in range(19):
            self.assertEqual(specular_index(specular_index(i)),i)

    def test_vertical_mirror_has_no_horizontal_displacement(self):
        self.assertEqual(C[specular_index(6)],(0,0,1))
        self.assertEqual(C[specular_index(5)],(0,0,-1))

    def test_naive_local_diagonal_swap_is_not_specular_streaming(self):
        # Attempt 1: changing fhn[9] in place after load cannot represent the
        # outgoing +x,-z population from the upwind lateral fluid site.
        target=(5,5,1)
        source=(4,5,1)
        for t in (0,1):
            # Source 15 lands in solid below target, not target's local 9 slot.
            self.assertNotEqual(push_location(source,15,t),pull_location(target,9,t+1))

    def test_naive_specular_redirect_is_not_generic_destination(self):
        # Attempt 2: merely swapping destination direction at current fluid
        # node overwrites another population, while target may read a solid slot.
        source=(5,5,1)
        target=(6,5,1)
        for t in (0,1):
            self.assertNotEqual(push_location(source,15,t),pull_location(target,9,t+1))
            self.assertNotEqual(push_location(source,10,t),pull_location((4,5,1),16,t+1))


if __name__=='__main__':
    unittest.main(verbosity=2)

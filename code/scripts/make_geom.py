# L26.5 test geometry: square prism (20x20x60 mm) on the floor of a fluid box; export the FLUID body (box minus prism) as STEP.
import sys, gmsh
out = sys.argv[1]
gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 1)
gmsh.model.add("l265")
occ = gmsh.model.occ
box = occ.addBox(-60, -50, 0, 180, 100, 80)
prism = occ.addBox(-10, -10, 0, 20, 20, 60)
fluid, _ = occ.cut([(3, box)], [(3, prism)])
occ.synchronize()
print("volumes:", gmsh.model.getEntities(3), "surfaces:", len(gmsh.model.getEntities(2)))
gmsh.option.setString("Geometry.OCCTargetUnit", "MM")
gmsh.write(out)
gmsh.finalize()

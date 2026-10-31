from pathlib import Path
import shutil,tarfile
b=Path(__file__).resolve().parent
src=b/'stage';dest=b/'stage_mixing';assert not dest.exists();shutil.copytree(src,dest)
f=dest/'FluidX3D/src/kernel.cpp';s=f.read_text();needle='\t\tfloat sgs_length_factor=1.0f;\n';assert s.count(needle)==1
s=s.replace(needle,needle+''' )+"#ifdef GROUND_WALL_MODEL"+R(
        // Hypothesis test only: wall-model unchanged; augment SGS mixing length near ground.
        // z_wall is measured above numerical mirror at physical z=0.5 m.
        const int layer=(int)coordinates(n).z+def_Oz-def_ground_first_fluid_z;
        if(layer>=0 && layer<=9 && flagsn_bo!=TYPE_E) {
            const float z_wall=(float)layer+0.5f;
            const float cs_len=sqrt(0.76421222f/(18.0f*1.41421356237f));
            const float taper=z_wall<=5.5f ? 1.0f : (z_wall>=9.5f ? 0.0f : (9.5f-z_wall)/4.0f);
            const float len=cs_len+taper*fmax(0.0f,def_ground_kappa*z_wall-cs_len);
            sgs_length_factor=sq(len/cs_len);
        }
)+"#endif"+R(
''');f.write_text(s)
with tarfile.open(b/'mixing_inputs.tar.gz','w:gz') as t:
 t.add(dest/'FluidX3D',arcname='FluidX3D');t.add(dest/'case',arcname='case')
print('mixing stage created')

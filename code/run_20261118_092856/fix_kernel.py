from pathlib import Path
p=Path(__file__).resolve().parent/'kernel_t13.cpp'
b=Path(__file__).resolve().parents[2]/'R21.4a_T5_caseE_WM_retry1/stage/FluidX3D_off/src/kernel.cpp'
s=b.read_text()
a='return R( // ##########################';assert s.count(a)==1
s=s.replace(a,'string code=R( // ##########################',1)
a=');} // ############################################################### end of OpenCL C code #####################################################################'
assert s.count(a)==1
s=s.replace(a,''');
#ifdef SMAG_CS_010
    const string old_coefficient="0.76421222f*sgs_length_factor*sqrt(Q)/rhon";
    const string new_coefficient="0.2553f*sgs_length_factor*sqrt(Q)/rhon";
    const size_t at=code.find(old_coefficient);
    if(at==string::npos || code.find(old_coefficient,at+1u)!=string::npos) throw std::runtime_error("Smagorinsky coefficient anchor mismatch");
    code.replace(at,old_coefficient.size(),new_coefficient);
#endif
    return code;
} // ############################################################### end of OpenCL C code #####################################################################''',1)
p.write_text('#include "defines.hpp"\n'+s)
print(p)

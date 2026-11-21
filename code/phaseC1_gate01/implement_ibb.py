from pathlib import Path
p=Path(__file__).parent/'impl_stage/FluidX3D/src'
def edit(file, old, new):
 f=p/file; s=f.read_text(); assert s.count(old)==1,(file,old[:80],s.count(old)); f.write_text(s.replace(old,new))
edit('defines.hpp','//#define WALL_GATE0', '//#define LINK_IBB // sparse FP32 interpolated links, single GPU only\n//#define WALL_GATE0')
edit('lbm.hpp','\tMemory<fpxx> fi; // LBM density distribution functions', '''#ifdef LINK_IBB
	Memory<uint> ibb_start; // CSR cell offsets (N+1)
	Memory<uchar> ibb_direction;
	Memory<float> ibb_q, ibb_previous;
	uint ibb_count=0u;
#endif
	Memory<fpxx> fi; // LBM density distribution functions''')
edit('lbm.cpp','#include "lbm.hpp"','#include "lbm.hpp"\n#include <fstream>\n#include <cstdlib>')
edit('lbm.cpp','\tkernel_update_fields = Kernel(device, N, "update_fields", fi, rho, u, flags, t, fx, fy, fz, omega_x, omega_y, omega_z);', '''\tkernel_update_fields = Kernel(device, N, "update_fields", fi, rho, u, flags, t, fx, fy, fz, omega_x, omega_y, omega_z);
#ifdef LINK_IBB
	if(get_D()!=1u) print_error("LINK_IBB single domain only");
	// A converted, little-endian CSR file; see prepare_ibb.py. Never trust a stale table.
	const char* filename=std::getenv("LUW_IBB_CSR");
	std::vector<uint> offsets((size_t)N+1u,0u);
	std::vector<uchar> directions;
	std::vector<float> distances;
	if(filename && *filename) {
		std::ifstream in(filename,std::ios::binary);
		uint64_t cells=0, links=0;
		if(!in.read((char*)&cells,8)||!in.read((char*)&links,8)||cells!=N||links>18ull*N||links>0xffffffffull) print_error("invalid LINK_IBB CSR header");
		ibb_count=(uint)links;
		directions.resize(ibb_count); distances.resize(ibb_count);
		if(!in.read((char*)offsets.data(),4*((size_t)N+1u)) ||
		   !in.read((char*)directions.data(),ibb_count) ||
		   !in.read((char*)distances.data(),4ull*ibb_count)) print_error("truncated LINK_IBB CSR");
		if(offsets[0]!=0u||offsets[N]!=ibb_count) print_error("LINK_IBB CSR offsets");
		for(ulong n=0;n<N;n++) if(offsets[n]>offsets[n+1]||offsets[n+1]-offsets[n]>18) print_error("LINK_IBB CSR cell order");
		for(uint k=0;k<ibb_count;k++) if(directions[k]<1u||directions[k]>=19u||!(distances[k]>0.0f&&distances[k]<1.0f)) print_error("LINK_IBB direction or q invalid");
	}
	ibb_start=Memory<uint>(device,N+1u);
	ibb_direction=Memory<uchar>(device,std::max((ulong)ibb_count,1ull));
	ibb_q=Memory<float>(device,std::max((ulong)ibb_count,1ull));
	ibb_previous=Memory<float>(device,std::max((ulong)ibb_count,1ull));
	for(ulong n=0;n<=N;n++) ibb_start[n]=offsets[n];
	for(uint k=0;k<ibb_count;k++) { ibb_direction[k]=directions[k]; ibb_q[k]=distances[k]; ibb_previous[k]=0.0f; }
	ibb_start.write_to_device(); ibb_direction.write_to_device(); ibb_q.write_to_device(); ibb_previous.write_to_device();
	kernel_stream_collide.add_parameters(ibb_start,ibb_direction,ibb_q,ibb_previous);
#endif''')
# kernel parameters must follow all extension parameters, NOT immediate after base
edit('lbm.cpp','\tif(get_D()>1u) allocate_transfer(device);', '''\tif(get_D()>1u) allocate_transfer(device);''')
# move add_parameters until after temperature block
s=(p/'lbm.cpp').read_text(); s=s.replace('\tkernel_stream_collide.add_parameters(ibb_start,ibb_direction,ibb_q,ibb_previous);\n#endif','\t// Registered after all other extension arguments, below.\n#endif',1); key='#endif // TEMPERATURE\n\n#ifdef PARTICLES\n\tparticles ='; assert key in s; s=s.replace(key,'#endif // TEMPERATURE\n#ifdef LINK_IBB\n\tkernel_stream_collide.add_parameters(ibb_start,ibb_direction,ibb_q,ibb_previous);\n#endif\n\n#ifdef PARTICLES\n\tparticles =',1); (p/'lbm.cpp').write_text(s)
edit('kernel.cpp',')+\") {\"+R( // stream_collide()',''' )+"#ifdef LINK_IBB"+R(
	, const global uint* ibb_start, const global uchar* ibb_direction, const global float* ibb_q, global float* ibb_previous
)+"#endif"+R(
)+") {"+R( // stream_collide()''')
edit('kernel.cpp','\tload_f(n, fhn, fi, j, t); // perform streaming (part 2)\n\n)+"#ifdef GROUND_WALL_MODEL"', '''\tload_f(n, fhn, fi, j, t); // perform streaming (part 2)
)+"#ifdef LINK_IBB"+R(
	// Reconstruct the incoming packet opposite the fluid->solid direction. The
	// previous post-collision packet is saved in a per-link slot by its owner.
	for(uint k=ibb_start[n]; k<ibb_start[n+1u]; k++) {
		const uint d=ibb_direction[k], opposite=(d&1u)?d+1u:d-1u;
		if((flags[j[d]]&TYPE_BO)!=TYPE_S) continue;
		const float q=ibb_q[k], outgoing=ibb_previous[k];
		float reflected=outgoing;
		if(t>0ul && q<0.5f) {
			// First upstream fluid cell at n-c[d]; reverse j[opposite].
			const uxx back=j[opposite];
			if((flags[back]&(TYPE_S|TYPE_E))==0u && !is_halo(back)) {
				// BFL branch for q<1/2: interpolate current outgoing of upstream
				// with the previous local outgoing; read the CURRENT fi parity.
				uxx jb[def_velocity_set]; float fb[def_velocity_set];
				neighbors(back,jb); load_f(back,fb,fi,jb,t);
				reflected=2.0f*q*outgoing+(1.0f-2.0f*q)*fb[d];
			}
		} else if(t>0ul && q>0.5f) {
			// BFL branch for q>=1/2 uses the local incoming distribution.
			reflected=(outgoing+(2.0f*q-1.0f)*fhn[opposite])/(2.0f*q);
		}
		fhn[opposite]=reflected;
	}
)+"#endif"+R(

)+"#ifdef GROUND_WALL_MODEL"''')
edit('kernel.cpp','\tstore_f(n, fhn, fi, j, t); // perform streaming (part 1)\n} // stream_collide()', ''' )+"#ifdef LINK_IBB"+R(
	// Single writer per link, after collision, before fi is repacked by Esoteric-Pull.
	for(uint k=ibb_start[n]; k<ibb_start[n+1u]; k++) ibb_previous[k]=fhn[ibb_direction[k]];
)+"#endif"+R(
	store_f(n, fhn, fi, j, t); // perform streaming (part 1)
} // stream_collide()''')
print('patched')

"""Rebuild LINK_IBB post-collision cache over sparse (cell,direction) samples."""
from pathlib import Path
p=Path(__file__).resolve().parent/'step3_compact_stage/src'
def replace(file,old,new):
 f=p/file;t=f.read_text();assert t.count(old)==1,(file,t.count(old));f.write_text(t.replace(old,new))
replace('lbm.hpp','Memory<float> ibb_post; // two time layers of post-collision D3Q19 (gate validation)', '''Memory<float> ibb_post; // two time layers over sparse unique (cell,direction) requests
\tMemory<uint> ibb_sample_start, ibb_sample_ref0, ibb_sample_ref1, ibb_sample_ref2;
\tMemory<uchar> ibb_sample_direction;
\tuint ibb_sample_count=0u;''')
replace('lbm.cpp','''\tibb_post=Memory<float>(device,2u*N*19u);''','''\t// Each distinct post-collision (cell,direction) packet needed by one or more
\t// links gets one sample slot. Back-neighbour packets do not in general belong
\t// to another solid link, so one slot per physical link is insufficient.
\tstruct Sample { uint cell; uchar d; bool operator<(const Sample& o) const {
\t\treturn cell<o.cell || (cell==o.cell && d<o.d); } };
\tstd::vector<Sample> samples;
\tstd::vector<Sample> requests((size_t)ibb_count*3u);
\tfor(ulong n=0;n<N;n++) for(uint k=offsets[n];k<offsets[n+1];k++) {
\t\tconst uint d=directions[k], op=(d&1u)?d+1u:d-1u;
\t\tconst int3 v=velocity_set[d];
\t\tconst uint x=(uint)(n%Nx), y=(uint)((n/Nx)%Ny), z=(uint)(n/((ulong)Nx*Ny));
\t\tauto shift=[&](int m)->uint { return (uint)(((x+Nx-m*v.x%((int)Nx))%Nx)+Nx*((y+Ny-m*v.y%((int)Ny))%Ny)+Nx*Ny*((z+Nz-m*v.z%((int)Nz))%Nz)); };
\t\trequests[3u*k]=Sample{(uint)n,(uchar)d};
\t\trequests[3u*k+1u]=Sample{shift(1),(uchar)(distances[k]<0.5f?d:op)};
\t\trequests[3u*k+2u]=Sample{distances[k]<0.5f?shift(2):(uint)n,(uchar)(distances[k]<0.5f?d:op)};
\t\tsamples.push_back(requests[3u*k]); samples.push_back(requests[3u*k+1u]);samples.push_back(requests[3u*k+2u]);
\t}
\tstd::sort(samples.begin(),samples.end());
\tsamples.erase(std::unique(samples.begin(),samples.end(),[](const Sample&a,const Sample&b){return a.cell==b.cell&&a.d==b.d;}),samples.end());
\tibb_sample_count=(uint)samples.size();
\tstd::vector<uint> sample_offsets((size_t)N+1u,0u),refs((size_t)ibb_count*3u);
\tfor(const auto& s:samples) sample_offsets[(size_t)s.cell+1u]++;
\tfor(ulong n=1;n<=N;n++) sample_offsets[n]+=sample_offsets[n-1u];
\tfor(size_t k=0;k<refs.size();k++) refs[k]=(uint)(std::lower_bound(samples.begin(),samples.end(),requests[k])-samples.begin());
\tibb_sample_start=Memory<uint>(device,N+1u);
\tibb_sample_direction=Memory<uchar>(device,std::max<ulong>(ibb_sample_count,1ul));
\tibb_sample_ref0=Memory<uint>(device,std::max<ulong>(ibb_count,1ul));
\tibb_sample_ref1=Memory<uint>(device,std::max<ulong>(ibb_count,1ul));
\tibb_sample_ref2=Memory<uint>(device,std::max<ulong>(ibb_count,1ul));
\tibb_post=Memory<float>(device,2u*std::max<ulong>(ibb_sample_count,1ul));
\tfor(ulong n=0;n<=N;n++) ibb_sample_start[n]=sample_offsets[n];
\tfor(uint k=0;k<ibb_sample_count;k++) ibb_sample_direction[k]=samples[k].d;
\tfor(uint k=0;k<ibb_count;k++) {ibb_sample_ref0[k]=refs[3u*k];ibb_sample_ref1[k]=refs[3u*k+1u];ibb_sample_ref2[k]=refs[3u*k+2u];}
\tprintln("LINK_IBB sparse samples "+to_string(ibb_sample_count)+" for "+to_string(ibb_count)+" links; two-layer bytes "+to_string(8ull*ibb_sample_count));''')
replace('lbm.cpp','''\tfor(ulong k=0;k<2u*N*19u;k++) ibb_post[k]=0.0f;
\tibb_start.write_to_device(); ibb_direction.write_to_device(); ibb_owner.write_to_device(); ibb_fallback.write_to_device(); ibb_q.write_to_device(); ibb_previous.write_to_device(); ibb_post.write_to_device(); ibb_link_force.write_to_device();''','''\tfor(ulong k=0;k<2u*std::max<ulong>(ibb_sample_count,1ul);k++) ibb_post[k]=0.0f;
\tibb_start.write_to_device(); ibb_direction.write_to_device(); ibb_owner.write_to_device(); ibb_fallback.write_to_device(); ibb_q.write_to_device(); ibb_previous.write_to_device(); ibb_post.write_to_device(); ibb_link_force.write_to_device();
\tibb_sample_start.write_to_device();ibb_sample_direction.write_to_device();ibb_sample_ref0.write_to_device();ibb_sample_ref1.write_to_device();ibb_sample_ref2.write_to_device();''')
replace('lbm.cpp','''kernel_stream_collide.add_parameters(ibb_start,ibb_direction,ibb_q,ibb_previous,ibb_owner,ibb_fallback,ibb_post,ibb_link_force);''','''kernel_stream_collide.add_parameters(ibb_start,ibb_direction,ibb_q,ibb_previous,ibb_owner,ibb_fallback,ibb_post,ibb_link_force,ibb_sample_start,ibb_sample_direction,ibb_sample_ref0,ibb_sample_ref1,ibb_sample_ref2);''')
replace('kernel.cpp','''global float* ibb_post, global float* ibb_link_force''','''global float* ibb_post, global float* ibb_link_force, const global uint* ibb_sample_start, const global uchar* ibb_sample_direction, const global uint* ibb_sample_ref0, const global uint* ibb_sample_ref1, const global uint* ibb_sample_ref2''')
replace('kernel.cpp','''const ulong off=((t+1ul)&1ul)*(ulong)def_N*19ul;
\t\t\t\treflected=q*(2.0f*q+1.0f)*outgoing+(1.0f+2.0f*q)*(1.0f-2.0f*q)*ibb_post[off+(ulong)back*19ul+d]-q*(1.0f-2.0f*q)*ibb_post[off+(ulong)back2*19ul+d];''','''const ulong off=((t+1ul)&1ul)*(ulong)ibb_sample_start[def_N];
\t\t\t\treflected=q*(2.0f*q+1.0f)*outgoing+(1.0f+2.0f*q)*(1.0f-2.0f*q)*ibb_post[off+ibb_sample_ref1[k]]-q*(1.0f-2.0f*q)*ibb_post[off+ibb_sample_ref2[k]];''')
replace('kernel.cpp','''const ulong off=((t+1ul)&1ul)*(ulong)def_N*19ul;
\t\t\t\treflected=outgoing/(q*(2.0f*q+1.0f))+(2.0f*q-1.0f)/q*ibb_post[off+(ulong)n*19ul+opposite]+(1.0f-2.0f*q)/(1.0f+2.0f*q)*ibb_post[off+(ulong)back*19ul+opposite];''','''const ulong off=((t+1ul)&1ul)*(ulong)ibb_sample_start[def_N];
\t\t\t\treflected=outgoing/(q*(2.0f*q+1.0f))+(2.0f*q-1.0f)/q*ibb_post[off+ibb_sample_ref2[k]]+(1.0f-2.0f*q)/(1.0f+2.0f*q)*ibb_post[off+ibb_sample_ref1[k]];''')
replace('kernel.cpp','''for(uint d=0u; d<19u; d++) ibb_post[(t&1ul)*(ulong)def_N*19ul+(ulong)n*19ul+d]=fhn[d];''','''for(uint k=ibb_sample_start[n];k<ibb_sample_start[n+1u];k++) ibb_post[(t&1ul)*(ulong)ibb_sample_start[def_N]+k]=fhn[ibb_sample_direction[k]];''')
print('compact transformed')
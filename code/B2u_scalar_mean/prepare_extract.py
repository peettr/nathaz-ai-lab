from pathlib import Path
B=Path('./24_Urban_Wind_LBM/06_Logs/wp1b_ibm/inflow_ti/extract_ti.py')
R=Path(__file__).resolve().parent
s=B.read_text().replace("Path('/content/luw-aij-r10')","Path('/content/b2u_case')")
s=s.replace('assert tke_offset+points_count*4==len(m),(tke_offset,len(m))','speed_offset=field_offset(m,tke_offset+points_count*4,\'speed_mean\',1)\n speed2_offset=field_offset(m,speed_offset+points_count*4,\'speed2_mean\',1)\n assert speed2_offset+points_count*4==len(m),(speed2_offset,len(m))')
s=s.replace('fluid=0;tke=0.','fluid=0;tke=0.;speed_mean=0.;speed2_mean=0.')
s=s.replace('tke+=weight*scalar(tke_offset,i,j,k)','tke+=weight*scalar(tke_offset,i,j,k)\n   speed_mean+=weight*scalar(speed_offset,i,j,k)\n   speed2_mean+=weight*scalar(speed2_offset,i,j,k)')
s=s.replace('return math.sqrt(sum(q*q for q in out)),max(tke,0.),fluid, out','return math.sqrt(sum(q*q for q in out)),max(tke,0.),fluid, out, speed_mean, speed2_mean')
s=s.replace('speed,tke,nfluid,uv=interp(', 'speed,tke,nfluid,uv,su,su2=interp(')
s=s.replace("'mean_velocity_mps':uv}","'mean_velocity_mps':uv,'Su_ratio':su/points['uref'],'Srms_ratio':math.sqrt(max(su2,0.))/points['uref'],'speed_mean_mps':su,'speed2_mean_m2s2':su2}")
s=s.replace('values=[interp(x,float(y),z)[0]', 'values=[interp(x,float(y),z)[0]')
s=s.replace('s,k,f,v=interp(', 's,k,f,v,_,_=interp(')
(R/'extract_B2u.py').write_text(s)
print('written',len(s))

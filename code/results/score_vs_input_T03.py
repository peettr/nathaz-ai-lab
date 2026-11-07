"""L22.6 T03 事后补定的并列读法（Lead 11-05 12:2x，看到数据后补，不计分、不替代协议 §5）。
对比基准从 B0 实测改成题面输入的 R：diag_in = max_i |R_ii,cand/R_ii,input − 1|；rho_in = max_ij |ρ_ij,cand − ρ_ij,input|，ρ_ij=R_ij/√(R_ii R_jj)。
同时算 B0 自己相对输入的这两个量作对照。5 个高度取最大。数字全部由 grade JSON 与 B0_target_deviation_full.csv 程序化生成。"""
import csv,json,glob,math,sys,os
inp={}
for r in csv.DictReader(open('T03_harness/template/B0_target_deviation_full.csv')):
    inp[r['z_m']]={k:float(r['input_R'+k]) for k in ('xx','xy','xz','yy','yz','zz')}
def m(R,I):
    d=max(abs(R[c]/I[c]-1) for c in ('xx','yy','zz'))
    rho=lambda T,a,b:T[a+b]/math.sqrt(T[a+a]*T[b+b])
    p=max(abs(rho(R,a,b)-rho(I,a,b)) for a,b in (('x','y'),('x','z'),('y','z')))
    return d,p
b=json.load(open('T03_harness/metrics_v12.json'))['B0']['heights']
print('B0  diag_in=%.3f rho_in=%.3f'%tuple(max(m(b[z]['R_local'],inp[z])[i] for z in inp) for i in (0,1)))
for f in sorted(glob.glob('sessions/*/T03_*/grade_R*.json')):
    g=json.load(open(f))
    if g.get('status')!='scored': continue
    H=g['metrics']['candidate']['heights']
    print(f.split('/')[1],f.split('/')[2],os.path.basename(f)[6:8],g['level'],'diag_in=%.3f rho_in=%.3f'%tuple(max(m(H[z]['R_local'],inp[z])[i] for z in inp) for i in (0,1)))

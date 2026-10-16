import csv,statistics as st,json
order=[16,24,25,26,27,28,29,30,37,38,41,56,57,58,59,60,61,62,63,64,70,71,72,73,39,40,50,51,52,53,54,55,75,76,2,3,4,5,14,15,23,36,42,43,44,1,6,7,8,9,10,11,12,13,17,18,19,20,21,22,31,32,33,34,35,45,46,47,48,49,65,66,67,68,69,74,77,78,79,80]
paper=[0.67,0.74,0.86,0.65,0.72,0.50,0.43,0.62,0.87,0.53,0.50,0.38,0.53,0.41,0.48,0.30,0.10,0.36,0.52,0.46,0.29,0.51,0.51,0.46,0.49,0.48,0.06,0.47,0.39,0.32,0.33,0.42,0.44,0.45,0.70,0.67,0.61,0.55,0.54,0.74,0.18,0.36,0.40,0.39,0.46,0.24,0.57,0.62,0.51,0.32,0.46,0.37,0.48,0.41,0.80,0.75,0.65,0.64,0.49,0.22,0.18,0.37,0.39,0.58,0.34,0.48,0.22,0.05,0.29,0.43,0.47,0.34,0.42,0.47,0.48,0.01,0.41,0.49,0.49,0.46]
assert len(order)==80==len(set(order))==len(paper)
P=dict(zip(order,paper))
r={int(float(x['id'])):x for x in csv.DictReader(open('CaseE_W_points_full_r7.csv'))}
ids=sorted(P); obs=[float(r[i]['after']) for i in ids]; pap=[P[i] for i in ids]
a=[float(r[i]['s_cfd_shift']) for i in ids]; b=[float(r[i]['s_exp_shift']) for i in ids]
mae=lambda s,o: sum(abs(x-y) for x,y in zip(s,o))/len(o)
def corr(x,y):
    mx,my=st.mean(x),st.mean(y); return sum((p-mx)*(q-my) for p,q in zip(x,y))/(sum((p-mx)**2 for p in x)*sum((q-my)**2 for q in y))**.5
out={}
for name,s in [('paper_LUW_digitized',pap),('ours_vector',a),('ours_scalar',b)]:
    out[name]=dict(mae=round(mae(s,obs),3),r=round(corr(s,obs),3),mean_ratio=round(st.mean(s)/st.mean(obs),3),n_below_0p10=sum(x<0.10 for x in s))
out['ours_vector_vs_paper']=dict(mae=round(mae(a,pap),3),r=round(corr(a,pap),3))
out['ours_scalar_vs_paper']=dict(mae=round(mae(b,pap),3),r=round(corr(b,pap),3))
low=[i for i in ids if float(r[i]['s_cfd_shift'])<0.10]
out['our_low_points']=[(i,round(float(r[i]['after']),2),P[i],round(float(r[i]['s_exp_shift']),2)) for i in low]
print(json.dumps(out,indent=1,ensure_ascii=False))

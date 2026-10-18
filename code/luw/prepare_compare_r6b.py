from pathlib import Path
p=Path(__file__).parent
for old,new in [('compare_r6.py','compare_r6b.py'),('plot_compare_r6.py','plot_compare_r6b.py')]:
 s=(p/old).read_text()
 for a,b in [('offset_samples_r6.json','offset_samples_r6b.json'),('CaseE_W_points_r6.csv','CaseE_W_points_r6b.csv'),('CaseE_W_metrics_r6.json','CaseE_W_metrics_r6b.json'),('CaseE_W_scatter_r6.png','CaseE_W_scatter_r6b.png'),('CaseE_W_scatter_compare_r5_r6.png','CaseE_W_scatter_compare_r5_r6b.png'),('r6 / 509m','r6b / 509m')]:s=s.replace(a,b)
 dest=p/new;assert not dest.exists();dest.write_text(s);compile(s,str(dest),'exec')

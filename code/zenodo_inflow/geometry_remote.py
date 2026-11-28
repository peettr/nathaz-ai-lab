import zipfile,numpy as np,json,scipy.spatial
r='/content/zenodo19041698/attempt3';z=zipfile.ZipFile(r+'/boundaryData.zip');b=z.read('boundaryData/points');a=np.fromstring(b[b.find(b'\n(\n')+1:].decode().replace('(',' ').replace(')',' '),sep=' ').reshape(-1,3)
tree=scipy.spatial.cKDTree(a[:,1:]);dd=tree.query(a[:,1:],k=2)[0][:,1]
metrics={'n':len(a),'nearest_neighbor_model_m_quantile':np.quantile(dd,[0,.1,.5,.9,.99,1]).tolist(),'y_model_m_minmax':[float(a[:,1].min()),float(a[:,1].max())],'z_model_m_minmax':[float(a[:,2].min()),float(a[:,2].max())],'x_unique':np.unique(a[:,0]).tolist()}
print(metrics)
open(r+'/geometry.json','w').write(json.dumps(metrics,indent=2))

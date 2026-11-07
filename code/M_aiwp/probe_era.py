import zarr,gcsfs,time,numpy as np
p='gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
t=time.time();g=zarr.open(gcsfs.GCSFileSystem(token='anon').get_mapper(p),mode='r')
print('META',list(g.array_keys())[:15],g['temperature'].shape,g['temperature'].chunks,'time',time.time()-t,flush=True)
i=int((np.datetime64('2023-04-19T12')-np.datetime64('1900-01-01T00'))/np.timedelta64(1,'h'))
t=time.time();print('SAMPLE',g['temperature'][i,:,192:195,1060:1063], 'seconds',time.time()-t,flush=True)

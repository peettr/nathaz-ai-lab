import pathlib,json
p=pathlib.Path('/content/l264diag04');r=p/'AERO_ODE/data'; f=p/'fast_data';f.mkdir(exist_ok=True)
(f/'data').symlink_to(r, target_is_directory=True)
items=[{'path':f'data/era5_test/2024/04/{day:02d}/202404{day:02d}.nc'} for day in range(1,5)]
items.append({'path':'data/hrrr_test/04/01.h5'})
(f/'fast_increment.json').write_text(json.dumps(items));print('FAST_DATA_LINK',f/'data',len(items))

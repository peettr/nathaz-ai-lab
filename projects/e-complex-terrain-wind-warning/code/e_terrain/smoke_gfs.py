import sys,runpy
sys.argv=['run_forecasts.py','--stations','/content/e_terrain/stations_input.csv','--start','2023-10-01','--end','2023-10-02','--sources','GFS','--window','170','179','23','44','--out','/content/e_terrain/pilot_gfs','--limit-inits','1']
runpy.run_path('/content/e_terrain/run_forecasts.py',run_name='__main__')

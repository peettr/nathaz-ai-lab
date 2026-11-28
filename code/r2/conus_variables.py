print('CONUS_VARIABLES',list(m.variables),flush=True)
print('GPU',__import__('torch').cuda.get_device_properties(0).total_memory,flush=True)

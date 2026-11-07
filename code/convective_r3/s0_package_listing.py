from huggingface_hub import list_repo_files
for repo,rev in [('nvidia/stormcast-v1-era5-hrrr','6c89a0877a0d6b231033d3b0d8b9828a6f833ed8'),('nvidia/stormcast-conus','bc8dd783f96fe0fa75fcff5bb67f66b549a5299f')]:
 try: print(repo,list_repo_files(repo,revision=rev),flush=True)
 except Exception as e:print(repo,repr(e),flush=True)

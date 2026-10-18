import subprocess as s
def r(c):
    print("$",c,flush=True); p=s.run(c,shell=True,capture_output=True,text=True); print((p.stdout+p.stderr)[-3000:],flush=True)
r("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv")
r("ls /etc/OpenCL/vendors/ 2>&1; cat /etc/OpenCL/vendors/*.icd 2>&1")
r("ldconfig -p | grep -i -E 'libOpenCL|nvidia-opencl' ")
r("which clinfo g++ make cmake python3; g++ --version | head -1")
r("apt-get -qq install -y clinfo ocl-icd-libopencl1 ocl-icd-opencl-dev >/dev/null 2>&1; mkdir -p /etc/OpenCL/vendors; [ -s /etc/OpenCL/vendors/nvidia.icd ] || echo libnvidia-opencl.so.1 > /etc/OpenCL/vendors/nvidia.icd; clinfo -l 2>&1 | head")

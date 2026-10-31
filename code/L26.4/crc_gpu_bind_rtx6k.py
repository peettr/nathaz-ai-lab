#!/usr/bin/env python3
"""CRC single-host, single-GPU fail-closed launcher. No scheduler submission.
Usage inside an allocated job, after module setup:
  python3 /absolute/path/crc_gpu_bind.py /absolute/run/root command [args...]
Do not export SGE_HGR_* from the submit host (-V or -v).
"""
import glob
import os
import re
import socket
import subprocess
import sys


def bus_key(text):
    match = re.fullmatch(r'([0-9a-fA-F]{4,8}):([0-9a-fA-F]{2}):([0-9a-fA-F]{2})\.([0-7])', text.strip())
    if not match:
        raise ValueError('invalid PCI bus ID: ' + text)
    return tuple(int(match[i], 16) for i in range(1, 5))


def read_proc_minors():
    result = {}
    paths = glob.glob('/proc/driver/nvidia/gpus/*/information')
    if not paths:
        raise ValueError('no NVIDIA proc GPU information')
    for path in paths:
        key = bus_key(os.path.basename(os.path.dirname(path)))
        with open(path, encoding='utf-8') as handle:
            content = handle.read()
        match = re.search(r'^Device Minor:\s*([0-9]+)\s*$', content, re.MULTILINE)
        if not match or key in result:
            raise ValueError('missing or duplicate physical minor in NVIDIA proc data')
        result[key] = int(match[1])
    return result


def resolve(env, config, inventory, minor_by_bus):
    raw = env.get('SGE_HGR_gpu_card', '').strip()
    if not re.fullmatch(r'[A-Za-z0-9_]+', raw):
        raise ValueError('missing or non-single SGE_HGR_gpu_card; no fallback')
    task = env.get('SGE_HGR_TASK_gpu_card', '').strip()
    if task and task != raw:
        raise ValueError('task and host GPU grants disagree')
    config = config.replace('\\\n', ' ')
    grants = re.findall(r'(?<![A-Za-z0-9_])' + re.escape(raw) + r'\[([^\]]+)\]', config)
    if len(grants) != 1:
        raise ValueError('assigned RSMAP ID absent or ambiguous in execution-host configuration')
    attrs = dict(re.findall(r'([a-z_]+)\s*=\s*([^,\s]+)', grants[0]))
    device = attrs.get('device', '')
    match = re.fullmatch(r'/dev/nvidia([0-9]+)', device)
    if not match:
        raise ValueError('expected one physical /dev/nvidiaN mapping')
    minor = int(match.group(1))
    rows = []
    for line in inventory.splitlines():
        fields = [x.strip() for x in line.split(',')]
        if len(fields) != 4:
            raise ValueError('invalid nvidia-smi inventory')
        index, bus, uuid, name = fields
        if not index.isdigit():
            raise ValueError('invalid GPU index')
        key = bus_key(bus)
        if key not in minor_by_bus:
            raise ValueError('NVML PCI bus absent from NVIDIA proc data')
        if minor_by_bus[key] == minor:
            rows.append((index, uuid, name, bus))
    if len(rows) != 1:
        raise ValueError('assigned physical device not uniquely visible to NVML')
    index, uuid, name, bus = rows[0]
    if not re.fullmatch(r'GPU-[0-9a-fA-F-]+', uuid):
        raise ValueError('invalid physical GPU UUID')
    if 'RTX' not in name.upper():
        raise ValueError('assigned GPU is not an RTX')
    if attrs.get('uuid') and attrs['uuid'] != uuid:
        raise ValueError('scheduler UUID and physical device disagree')
    return raw, device, index, uuid, name, bus


def main():
    if len(sys.argv) < 3 or not os.path.isabs(sys.argv[1]):
        raise ValueError('usage: crc_gpu_bind.py /absolute/run/root command [args...]')
    if not re.fullmatch(r'[0-9]+', os.environ.get('JOB_ID', '')):
        raise ValueError('not an SGE job')
    os.chdir(sys.argv[1])
    host = socket.getfqdn()
    config = subprocess.check_output(['qconf', '-se', host], text=True, timeout=20)
    inventory = subprocess.check_output([
        'nvidia-smi', '--query-gpu=index,pci.bus_id,uuid,name',
        '--format=csv,noheader,nounits'], text=True, timeout=20)
    raw, device, index, uuid, name, bus = resolve(os.environ, config, inventory, read_proc_minors())
    previous = os.environ.get('CUDA_VISIBLE_DEVICES', '<unset>')
    os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
    os.environ['CUDA_VISIBLE_DEVICES'] = uuid
    print('GPU_BIND job={} host={} grant={} device={} nvml_index={} bus={} uuid={} name={} previous_CVD={} CUDA_VISIBLE_DEVICES={}'.format(
        os.environ['JOB_ID'], host, raw, device, index, bus, uuid, name, previous, uuid), flush=True)
    os.execvp(sys.argv[2], sys.argv[2:])


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print('GPU_BIND_FATAL: ' + str(exc), file=sys.stderr, flush=True)
        sys.exit(78)

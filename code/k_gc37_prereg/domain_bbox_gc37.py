#!/usr/bin/env python3
"""Per-event WRF d01 (Lambert, 748x600, dx=4 km) corners/edge-midpoints and driver crop box (prereg v2 item 7).
Projection: E1 Akron keeps original K d01 (CEN 38N/-100, TRUELAT1=TRUELAT2=38, STAND_LON=-100).
Other events: CEN_LAT=TRUELAT1=TRUELAT2=round(station lat), CEN_LON=STAND_LON=round(station lon).
Crop box = [floor(min lat)-3, ceil(max lat)+3] x [floor(min lon)-3, ceil(max lon)+3] over 4 corners + 4 edge midpoints (sphere R=6370 km).
Usage: python3 -I domain_bbox_gc37.py events_selected_gc37.json out.json"""
import json, math, sys
def pts(clat, clon):
    R = 6370.0; p1 = math.radians(clat); n = math.sin(p1)
    F = math.cos(p1) * math.tan(math.pi / 4 + p1 / 2) ** n / n
    r0 = R * F / math.tan(math.pi / 4 + p1 / 2) ** n
    def inv(x, y):
        rho = math.copysign(math.hypot(x, r0 - y), n); th = math.atan2(x, r0 - y)
        return math.degrees(2 * math.atan((R * F / rho) ** (1 / n)) - math.pi / 2), clon + math.degrees(th / n)
    hx, hy = 747 * 4 / 2, 599 * 4 / 2
    return [inv(x, y) for x in (-hx, 0, hx) for y in (-hy, 0, hy) if (x, y) != (0, 0)]
ev = json.load(open(sys.argv[1])); out = {}
for k in ['E1', 'E2', 'E3', 'R1', 'R2']:
    e = ev[k]
    clat, clon = (38, -100) if k == 'E1' else (round(float(e['lat'])), round(float(e['lon'])))
    P = pts(clat, clon); la = [p[0] for p in P]; lo = [p[1] for p in P]
    box = [math.floor(min(la)) - 3, math.ceil(max(la)) + 3, math.floor(min(lo)) - 3, math.ceil(max(lo)) + 3]
    out[k] = {'cen_lat': clat, 'cen_lon': clon, 'd01_lat': [min(la), max(la)], 'd01_lon': [min(lo), max(lo)],
              'crop_lat': box[:2], 'crop_lon_west_neg': box[2:]}
    print(k, e['station'], (clat, clon), 'd01 lat %.2f-%.2f lon %.2f-%.2f' % (min(la), max(la), min(lo), max(lo)), 'crop', box)
json.dump(out, open(sys.argv[2], 'w'), indent=1)

"""Report frozen or irregular frames in a captured sequence (use on scroll-driven heroes).

usage: .venv/bin/python tools/check_stutter.py <frames_dir> [start] [end]
A couple of frozen frames at the very start (scroll slower than the site's sequence) or exactly
where a pinned hero ends are normal; runs of them mid-scroll are not.
"""
import glob, sys
import cv2
import numpy as np

files = sorted(glob.glob(f'{sys.argv[1]}/f*.jpg'))
a = int(sys.argv[2]) if len(sys.argv) > 2 else 0
b = int(sys.argv[3]) if len(sys.argv) > 3 else len(files)
load = lambda i: cv2.imread(files[i], cv2.IMREAD_REDUCED_GRAYSCALE_4).astype(np.float32)
prev, d = load(a), []
for i in range(a + 1, b):
    cur = load(i); d.append(float(np.abs(cur - prev).mean())); prev = cur
d = np.array(d)
frozen = (np.where(d < 0.3)[0] + a + 1).tolist()
runs, cur = [], 0
for x in d < 0.3:
    cur = cur + 1 if x else 0; runs.append(cur)
longest = max(runs, default=0)
print(f'frames {a}-{b - 1}: mean change {d.mean():.2f}')
print(f'frozen (no change vs previous): {len(frozen)} {frozen[:40]}')
print(f'longest frozen run: {longest} frames' + ('  <- visible stall, investigate' if longest >= 3 else ''))

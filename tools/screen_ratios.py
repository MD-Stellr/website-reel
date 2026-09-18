"""Measure each green screen's shape in a background and suggest capture viewports.

usage: .venv/bin/python tools/screen_ratios.py <background image>
Run it on the most straight-on angle: perspective makes oblique angles unreliable.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
import numpy as np
from composite import detect_screens, fit_canvas

bg = fit_canvas(cv2.imread(sys.argv[1], cv2.IMREAD_COLOR))
screens, _ = detect_screens(bg)
for s, label, width in zip(screens, ['monitor', 'laptop'], [1440, 1280]):
    tl, tr, br, bl = s['quad']
    w = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    h = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    r = w / h
    vh = int(round(width / r / 2) * 2)
    le, re_ = np.linalg.norm(bl - tl), np.linalg.norm(br - tr)
    skew = abs(le - re_) / max(le, re_)
    note = 'straight-on, reliable' if skew < 0.05 else f'OBLIQUE ({skew:.0%} edge difference): ratio unreliable, measure a straight-on angle'
    print(f'{label:8s} ratio {r:.3f}  suggested viewport {width}x{vh}  [{note}]')

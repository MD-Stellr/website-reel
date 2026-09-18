"""Composite recorded website frames into the chroma-green screens of a background image.

usage:
  .venv/bin/python composite.py --bg bg.png --monitor frames/monitor --laptop frames/laptop --out output/reel.mp4
  multi-angle: --edit configs/edit.json instead of --bg (see configs/edit.json).
  --detect-only writes debug/detect-<angle>.jpg; --still I [I ...] writes debug/still<I>.png; --frames N previews.
"""
import argparse, glob, json, os, subprocess, sys
import cv2
import numpy as np

W, H = 2160, 3840          # working canvas (2x the 1080x1920 deliverable, headroom for the push-in)
OUT_W, OUT_H = 1080, 1920


def fit_canvas(img):
    """Center-crop to 9:16 and resize to the working canvas."""
    h, w = img.shape[:2]
    target = W / H
    if w / h > target:
        nw = int(round(h * target)); x0 = (w - nw) // 2; img = img[:, x0:x0 + nw]
    elif w / h < target:
        nh = int(round(w / target)); y0 = (h - nh) // 2; img = img[y0:y0 + nh]
    interp = cv2.INTER_AREA if img.shape[1] > W else cv2.INTER_LANCZOS4
    return cv2.resize(img, (W, H), interpolation=interp)


def greenness(img):
    f = img.astype(np.float32)
    return f[..., 1] - np.maximum(f[..., 0], f[..., 2])


def order_corners(pts):
    pts = np.asarray(pts, np.float64).reshape(4, 2)
    s, d = pts.sum(1), pts[:, 1] - pts[:, 0]
    return np.array([pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]])  # TL TR BR BL


def line_intersect(l1, l2):
    (vx1, vy1, x1, y1), (vx2, vy2, x2, y2) = l1, l2
    A = np.array([[vx1, -vx2], [vy1, -vy2]]); b = np.array([x2 - x1, y2 - y1])
    t = np.linalg.solve(A, b)[0]
    return np.array([x1 + vx1 * t, y1 + vy1 * t])


def fit_side(pts, a, b):
    """Refine the line through segment a-b using contour points that lie on it (ignoring rounded ends)."""
    ab = b - a; L = np.linalg.norm(ab); u = ab / L; n = np.array([-u[1], u[0]])
    rel = pts - a
    t = rel @ u / L; dist = np.abs(rel @ n)
    sel = pts[(t > 0.06) & (t < 0.94) & (dist < max(4.0, L * 0.008))]
    if len(sel) < 10:
        return (u[0], u[1], a[0], a[1])
    return tuple(cv2.fitLine(sel.astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel())


def screen_sides(contour):
    """Find the 4 true sides of a screen whose green area may be partly covered by something in front.

    Approximates the outline as a polygon, drops edges touching a concave (reflex) vertex (those belong
    to the occluder, e.g. a laptop lid in front of the monitor), keeps the 4 longest remaining edges in
    outline order. Intersecting consecutive sides then recovers hidden corners by extrapolation.
    """
    peri = cv2.arcLength(contour, True)
    for eps in np.linspace(0.002, 0.04, 80):
        poly = cv2.approxPolyDP(contour, eps * peri, True).reshape(-1, 2).astype(np.float64)
        if len(poly) <= 8: break
    # merge nearly-collinear neighbours so one bowed side can't count as two
    changed = True
    while changed and len(poly) > 4:
        changed = False
        for i in range(len(poly)):
            a, b, c = poly[i - 1], poly[i], poly[(i + 1) % len(poly)]
            u, v = b - a, c - b
            ang = np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1)))
            if ang < 8:
                poly = np.delete(poly, i, 0); changed = True; break
    k = len(poly)
    area2 = sum(poly[i, 0] * poly[(i + 1) % k, 1] - poly[(i + 1) % k, 0] * poly[i, 1] for i in range(k))
    orient = np.sign(area2)
    reflex = []
    for i in range(k):
        p0, p1, p2 = poly[i - 1], poly[i], poly[(i + 1) % k]
        cross = (p1[0] - p0[0]) * (p2[1] - p1[1]) - (p1[1] - p0[1]) * (p2[0] - p1[0])
        reflex.append(np.sign(cross) == -orient)
    edges = [(i, (i + 1) % k) for i in range(k) if not reflex[i] and not reflex[(i + 1) % k]]
    if len(edges) < 4:
        edges = [(i, (i + 1) % k) for i in range(k)]
    edges = sorted(sorted(edges, key=lambda e: -np.linalg.norm(poly[e[1]] - poly[e[0]]))[:4])
    return poly, edges


def quad_from_contour(contour):
    poly, edges = screen_sides(contour)
    pts = contour.reshape(-1, 2).astype(np.float64)
    lines = [fit_side(pts, poly[a], poly[b]) for a, b in edges]
    return order_corners([line_intersect(lines[i - 1], lines[i]) for i in range(4)])


def detect_screens(bg):
    g = greenness(bg)
    mask = (g > 60).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))  # small: keep a thin bezel between screens
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contours = sorted([c for c in contours if cv2.contourArea(c) > 0.004 * W * H], key=cv2.contourArea, reverse=True)[:2]
    if len(contours) < 2:
        sys.exit(f'Found {len(contours)} green screen region(s); need 2. Check the background image.')
    screens = []
    for c in contours:
        quad = quad_from_contour(c)
        region = np.zeros((H, W), np.uint8); cv2.drawContours(region, [c], -1, 255, -1)
        region = cv2.dilate(region, np.ones((7, 7), np.uint8))  # this screen's own green area (+ fringe)
        screens.append({'quad': quad, 'area': cv2.contourArea(c), 'cy': quad[:, 1].mean(), 'region': region})
    screens.sort(key=lambda s: s['cy'])  # upper = monitor, lower = laptop
    return screens, g


def expand(quad, px):
    c = quad.mean(0); v = quad - c
    return c + v * (1 + px / np.linalg.norm(v, axis=1, keepdims=True))


def sheen(h, w):
    """Faint diagonal glass reflection, strongest top-left."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = (xx / w * 0.6 + yy / h * 0.4)
    band = np.exp(-((d - 0.28) / 0.16) ** 2) * 0.045 + (1 - d) * 0.015
    return band[..., None]


def prep_screen(frame, s):
    """Screen look: lifted blacks (LCD in a dark room) plus glass sheen, in source space."""
    f = frame.astype(np.float32) / 255.0
    f = f * (1 - s['lift']) + s['lift']
    f = f + (1 - f) * s['sheen']
    return f


def smoothstep(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)


LABELS = ['monitor', 'laptop']


def detect_angle(name, path, swap):
    """Load one background (camera angle), find its screens, write a detection overlay to debug/."""
    bg = fit_canvas(cv2.imread(path, cv2.IMREAD_COLOR))
    screens, g = detect_screens(bg)
    if swap: screens.reverse()
    dbg = bg.copy()
    for s, label in zip(screens, LABELS):
        q = s['quad']
        cv2.polylines(dbg, [q.astype(np.int32)], True, (255, 0, 255), 3, cv2.LINE_AA)
        for p in q: cv2.circle(dbg, tuple(int(v) for v in p), 10, (0, 0, 255), -1, cv2.LINE_AA)
        cv2.putText(dbg, label, tuple(int(v) for v in q[0] + [10, 60]), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 0, 255), 4, cv2.LINE_AA)
        print(f'[{name}] {label}: corners {np.round(q, 1).tolist()}')
    os.makedirs('debug', exist_ok=True)
    cv2.imwrite(f'debug/detect-{name}.jpg', cv2.resize(dbg, (W // 2, H // 2), interpolation=cv2.INTER_AREA))
    return bg, screens, g


def build_angle(bg, screens, g, frame_lists, lift):
    """Precompute everything per-frame compositing needs for one angle."""
    # Key alpha: where the background is still green (lets real occluders stay on top), dilated to eat the fringe.
    key = np.clip((g - 25) / 50, 0, 1)
    key = cv2.dilate(key, np.ones((5, 5), np.uint8))
    # Despill band around each screen: clamp green to max(r, b) so no green halo survives on bezels.
    band = np.zeros((H, W), np.uint8)
    for s in screens: cv2.fillConvexPoly(band, expand(s['quad'], 14).astype(np.int32), 255)
    bgf = bg.astype(np.float32) / 255.0
    rb = np.maximum(bgf[..., 0], bgf[..., 2])
    despilled = bgf.copy(); despilled[..., 1] = np.minimum(bgf[..., 1], rb)
    bgf = np.where(band[..., None] > 0, despilled, bgf)

    inside = np.zeros((H, W), np.float32)
    for s, fl in zip(screens, frame_lists):
        sh, sw = cv2.imread(fl[0]).shape[:2]
        src = np.array([[0, 0], [sw, 0], [sw, sh], [0, sh]], np.float32)
        M = cv2.getPerspectiveTransform(src, expand(s['quad'], 1.0).astype(np.float32))
        x, y, w, h = cv2.boundingRect(expand(s['quad'], 4).astype(np.float32))
        x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
        s['roi'] = (x0, y0, x1, y1)
        s['Mr'] = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], np.float64) @ M
        poly_a = cv2.warpPerspective(np.ones((sh, sw), np.float32), s['Mr'], (x1 - x0, y1 - y0), flags=cv2.INTER_AREA)
        own = s['region'][y0:y1, x0:x1].astype(np.float32) / 255
        s['alpha'] = (poly_a * key[y0:y1, x0:x1] * own)[..., None]
        s['sheen'] = sheen(sh, sw); s['lift'] = lift
        inside[y0:y1, x0:x1] = np.maximum(inside[y0:y1, x0:x1], s['alpha'][..., 0])
    centers = {label: s['quad'].mean(0) for s, label in zip(screens, LABELS)}
    centers['both'] = (centers['monitor'] + centers['laptop']) / 2
    return {'bgf': bgf, 'screens': screens, 'inside': inside, 'centers': centers}


def camera(canvas, z, center):
    """Frame the canvas at zoom z around center (clamped to the image), output 1080x1920."""
    vw, vh = W / z, H / z
    x0 = min(max(center[0] - vw / 2, 0), W - vw); y0 = min(max(center[1] - vh / 2, 0), H - vh)
    # sub-pixel affine to a 2x intermediate (magnification >= 1, no aliasing), then exact 2x area downscale
    A = np.array([[z, 0, -x0 * z], [0, z, -y0 * z]], np.float64)
    mid = cv2.warpAffine(canvas, A, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    return cv2.resize(mid, (OUT_W, OUT_H), interpolation=cv2.INTER_AREA)


def render_frame(angle, frame_lists, i, glow_amt):
    canvas = angle['bgf'].copy()
    light = np.zeros((H // 8, W // 8, 3), np.float32)
    for s, fl in zip(angle['screens'], frame_lists):
        x0, y0, x1, y1 = s['roi']
        content = prep_screen(cv2.imread(fl[i]), s)
        warped = cv2.warpPerspective(content, s['Mr'], (x1 - x0, y1 - y0), flags=cv2.INTER_AREA)
        a = s['alpha']
        canvas[y0:y1, x0:x1] = canvas[y0:y1, x0:x1] * (1 - a) + warped * a
        # accumulate emitted light at 1/8 res for the room glow
        ws = cv2.resize(warped * a, ((x1 - x0) // 8, (y1 - y0) // 8), interpolation=cv2.INTER_AREA)
        light[y0 // 8:y0 // 8 + ws.shape[0], x0 // 8:x0 // 8 + ws.shape[1]] += ws
    if glow_amt > 0:
        glow = cv2.resize(cv2.GaussianBlur(light, (0, 0), 18), (W, H), interpolation=cv2.INTER_LINEAR)
        glow *= glow_amt * (1 - angle['inside'])[..., None]
        canvas = 1 - (1 - canvas) * (1 - glow)  # screen blend
    return np.clip(canvas * 255 + 0.5, 0, 255).astype(np.uint8)


def main():
    global W, H, OUT_W, OUT_H
    ap = argparse.ArgumentParser()
    ap.add_argument('--bg', help='single background (one continuous shot)')
    ap.add_argument('--edit', help='edit JSON: {"angles": {name: image}, "shots": [{"angle", "until", "zoom", "focus"}]}')
    ap.add_argument('--monitor', required=True)
    ap.add_argument('--laptop', required=True)
    ap.add_argument('--out', default='output/reel.mp4')
    ap.add_argument('--fps', type=int, default=60, help='frame rate of the captured frames')
    ap.add_argument('--frames', type=int, default=0, help='limit frame count (preview)')
    ap.add_argument('--zoom', type=float, nargs=2, default=[1.0, 1.08], help='push-in start/end scale (--bg mode)')
    ap.add_argument('--glow', type=float, default=0.22, help='screen light spill onto the room')
    ap.add_argument('--lift', type=float, default=0.025, help='black level lift on screens')
    ap.add_argument('--crf', type=int, default=10, help='x264 quality (lower = higher bitrate)')
    ap.add_argument('--ig30', action='store_true', help='also write a motion-blurred 30fps cut')
    ap.add_argument('--swap', action='store_true', help='swap which screen gets which recording')
    ap.add_argument('--native', action='store_true',
                    help="keep the background's own size and aspect (banners, landscape stills) instead of the 9:16 reel canvas")
    ap.add_argument('--detect-only', action='store_true')
    ap.add_argument('--still', type=int, nargs='*', help='write composited frame PNGs at these indices instead of a video')
    args = ap.parse_args()

    if args.edit:
        edit = json.load(open(args.edit))
        angle_paths, shots = edit['angles'], edit['shots']
    elif args.bg:
        angle_paths = {'A': args.bg}
        shots = [{'angle': 'A', 'zoom': args.zoom, 'ease': 'smooth'}]
    else:
        sys.exit('need --bg or --edit')

    if args.native:  # canvas = the (first) background's own pixels, output at the same size
        h, w = cv2.imread(next(iter(angle_paths.values()))).shape[:2]
        W, H = w - w % 2, h - h % 2
        OUT_W, OUT_H = W, H

    used = sorted({s['angle'] for s in shots})
    detected = {name: detect_angle(name, angle_paths[name], args.swap) for name in used}
    if args.detect_only: return

    frame_lists = [sorted(glob.glob(os.path.join(d, 'f*.jpg')) + glob.glob(os.path.join(d, 'f*.png')))
                   for d in (args.monitor, args.laptop)]
    n = min(len(fl) for fl in frame_lists)
    if args.frames: n = min(n, args.frames)
    angles = {name: build_angle(*detected[name], frame_lists, args.lift) for name in used}

    # Shot table in frames. Every angle reads the SAME frame index, so a cut never changes the scroll position.
    bounds, start = [], 0
    for k, s in enumerate(shots):
        end = n if k == len(shots) - 1 or s.get('until') is None else min(n, round(s['until'] * args.fps))
        bounds.append((start, end, s)); start = end
    for a, b, s in bounds:
        print(f"shot {a / args.fps:5.2f}-{b / args.fps:5.2f}s  angle {s['angle']}  zoom {s.get('zoom', [1, 1])}  focus {s.get('focus', 'both')}")

    def frame(i):
        a, b, s = next(x for x in bounds if x[0] <= i < x[1])
        p = (i - a) / max(b - a - 1, 1)
        p = smoothstep(p) if s.get('ease') == 'smooth' else p
        z0, z1 = s.get('zoom', [1.0, 1.0])
        ang = angles[s['angle']]
        c = ang['centers'][s.get('focus', 'both')]
        return camera(render_frame(ang, frame_lists, i, args.glow), z0 + (z1 - z0) * p, c)

    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    if args.still:
        for i in args.still:
            p = os.path.join('debug', f'still{i}.png'); cv2.imwrite(p, frame(i)); print('still ->', p)
        return

    # High-bitrate H.264 inside the level-4.2 ceiling (1080p60, <=50 Mb/s); aq-mode 3 protects dark gradients.
    x264 = ['-c:v', 'libx264', '-preset', 'slower', '-crf', str(args.crf), '-maxrate', '50M', '-bufsize', '100M',
            '-x264-params', 'aq-mode=3:aq-strength=0.9', '-g', str(args.fps * 2), '-profile:v', 'high',
            '-level', '4.2', '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709',
            '-colorspace', 'bt709', '-movflags', '+faststart']
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{OUT_W}x{OUT_H}',
           '-r', str(args.fps), '-i', '-']
    if args.ig30 and args.fps == 60:
        # optional 30fps cut: blend frame pairs (180-degree shutter motion blur)
        alt = os.path.splitext(args.out)[0] + '-30fps.mp4'
        cmd += ['-filter_complex', '[0]split=2[a][b];[b]tmix=frames=2,fps=30[c]',
                '-map', '[a]', *x264, args.out, '-map', '[c]', *x264, alt]
        print(f'writing {args.out} ({args.fps}fps) + {alt}')
    else:
        cmd += [*x264, args.out]
        print(f'writing {args.out} ({args.fps}fps)')
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        enc.stdin.write(frame(i).tobytes())
        if i % 60 == 0: print(f'frame {i}/{n}', flush=True)
    enc.stdin.close(); enc.wait(); print('done ->', args.out)


if __name__ == '__main__':
    main()

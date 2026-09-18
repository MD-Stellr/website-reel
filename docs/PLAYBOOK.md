# Website Reel — Playbook

Turn any website into a 9:16 Instagram Reel: the site is recorded frame by frame in a headless browser, then composited into the chroma-green screens of an AI-generated room (a monitor + a MacBook), with slow camera push-ins and cuts between camera angles. Output is 1080×1920, 60 fps, ~25 Mb/s H.264.

The pipeline lives in the repo root (cloned to `~/reel-maker`). This playbook is the full reference: how to run it, how it works, the house style, and the reels already made. The Claude Code skill `skills/website-reel/SKILL.md` is the step-by-step procedure that points back here; it triggers on requests like "make a reel for <url>".

---

## 0. TL;DR — make a reel for a new site

```bash
cd ~/reel-maker

# 1. Inspect the site (sections, pinned/scroll-driven parts, videos, text placement)
node inspect4.mjs https://SITE/ 1440 920
node inspect2.mjs https://SITE/ inspect/site-home 1440 920        # screenshots down the page
ffmpeg -y -loglevel error -pattern_type glob -i 'inspect/site-home-[0-9]*.png' \
  -vf "scale=480:-1,tile=5x5:padding=4" -frames:v 1 inspect/site-home-sheet.png   # contact sheet

# 2. Write capture configs (copy configs/rae-monitor.json + configs/rae-laptop.json, change url/out/keyframes)
# 3. Record both screens in parallel (~1 min each)
node capture.mjs configs/site-monitor.json > frames/site-monitor.log 2>&1 &
node capture.mjs configs/site-laptop.json  > frames/site-laptop.log  2>&1 &
wait

# 4. Write the edit (copy configs/rae-edit.json), check stills at the cuts, then render (~4 min)
.venv/bin/python composite.py --edit configs/site-edit.json --monitor frames/site-monitor --laptop frames/site-laptop \
  --out output/site-reel.mp4 --still 300 683 684          # -> debug/still*.png, look at them
.venv/bin/python composite.py --edit configs/site-edit.json --monitor frames/site-monitor --laptop frames/site-laptop \
  --out output/site-reel.mp4

open output/site-reel.mp4
```

The room/backgrounds are reusable: a new site only needs steps 1–4. A new room needs step "Environment image" (§3) first.

---

## 1. Folder layout

| Path | What it is |
|---|---|
| `capture.mjs` | Deterministic website recorder (Playwright). One JSON config per screen. |
| `composite.py` | Green-screen detection + compositing + camera moves + H.264 encode. |
| `inspect.mjs` | Quick site probe: libraries (Lenis, GSAP, Three), fixed/sticky elements, links, canvases/videos. Writes `inspect-top.png`. |
| `inspect2.mjs` | `node inspect2.mjs <url> <outPrefix> <w> <h>` — scrolls the page (to trigger reveals) and saves one screenshot per viewport-height → build a contact sheet with ffmpeg `tile`. Also prints section/heading offsets. |
| `inspect3.mjs` | Hero image-sequence probe (canvas size, pinned-hero wrapper height, how many sequence frames load at start vs on scroll). Rae & Thorburn–specific selector for the hero wrapper; adapt for other sites. |
| `inspect4.mjs` | `node inspect4.mjs <url> <w> <h>` — page height, max scroll, every `<section>` offset/height, `[pinned]` flag for sticky sections, `<video>` list. **Use this at the exact capture viewport.** |
| `tools/sheet.sh` | `tools/sheet.sh <frames_dir> <out.jpg> <frame…>` — contact sheet of chosen captured frames (4 per row). |
| `tools/check_stutter.py` | `.venv/bin/python tools/check_stutter.py <frames_dir> [start] [end]` — frozen-frame report for scroll-driven heroes (a run of 3+ = visible stall). |
| `tools/screen_ratios.py` | `.venv/bin/python tools/screen_ratios.py <background>` — each screen's width/height + suggested capture viewport; flags oblique angles as unreliable. |
| `configs/` | Capture configs (`*-monitor.json`, `*-laptop.json`) and edit plans (`*-edit.json`). |
| `backgrounds/` | Environment images. `env1.webp` = angle A (low 3/4), `env1-angleB.webp` = angle B (straight-on), `*-flip.png` = mirrored versions (laptop on the right). |
| `frames/<name>/f00000.jpg…` | Captured frames (2× DPR JPEG q95). **Big** (≈80–130 MB per second of footage per screen). Delete after rendering if space matters. |
| `output/` | Finished reels (+ optional raw screen recordings). |
| `debug/` | `detect-<angle>.jpg` corner-detection overlays, `still<N>.png` preview frames. |
| `inspect/`, `test/` | Scratch from site inspection and pipeline tests. Safe to delete. |
| `.venv/` | Python venv with `opencv-python-headless` + `numpy`. |

---

## 2. Setup (only if rebuilding from scratch)

Installed and working as of 2026-09-17: Node + Playwright 1.63.0 (Chromium), ffmpeg 8.1 (Homebrew), Python venv with OpenCV 5.0.0 / NumPy 2.5.

```bash
mkdir -p ~/reel-maker && cd ~/reel-maker
npm init -y && npm i playwright@latest && npx playwright install chromium
python3 -m venv .venv && .venv/bin/pip install opencv-python-headless numpy
brew install ffmpeg   # if missing
```

Always run Python through `.venv/bin/python` (system Python has no OpenCV).

---

## 3. Environment image (the room)

### Rules that make an image usable
- **9:16 vertical, highest resolution.** Set the aspect ratio in the tool UI — models ignore "9:16" in text (the first try came out square). GPT Image 2 max at 9:16 is **2160×3840**; current backgrounds are 1920×3413 (fine).
- **Both screens flat chroma green**, edge to edge, no UI/notch/reflections/glare/gradient, crisp straight edges. Any green works (`#00FF00`, `#32D435` both detected fine).
- **A dark bezel must separate the two green areas** where the laptop overlaps the monitor (the script needs two separate green regions).
- Overlap is fine: the laptop may cover a corner of the monitor — the hidden corner is reconstructed automatically.
- **No desk props** (cups, whiskey glass, plants, lamps) — they read as "AI".
- **No green spill** on the desk/keyboard (ask for a *neutral white* screen glow). The script despills bezels anyway.
- Both screens fully in frame, not cropped by the image edge.

### House aesthetic
Dark stealth-luxury ("Batman") high-rise penthouse at night: black stone wall panels, black ceiling with one thin warm LED cove line and pinhole downlights, matte black-oak desk, floor-to-ceiling window with a defocused night skyline and a tower with red aviation beacons. Very low-key light; the screens and city are the brightest things. Real-camera imperfections (shadow noise, slight bloom, vignette), no CGI sheen. Space-black MacBook Pro 16" + thin-bezel monitor on a black arm.

### Which model
- **New room from scratch:** GPT Image 2 (quality **high**, 9:16, max size).
- **Another angle of the same room:** angle B came out of GPT Image 2 using the Appendix A prompt (written to be run with the existing background attached as the reference). A first attempt with Nano Banana and a long "keep identical" prompt returned almost the same angle. Nano Banana **Pro** (not Nano Banana 2) is still the other good option for same-scene re-angles.
- **Edit-prompt lesson:** a long "keep identical" list makes the model copy the camera angle too. Lead with the camera change, describe the *result geometry* ("top and bottom edges horizontal and parallel, left and right edges the same height"), keep "stay the same" to one line. Start a fresh chat so it doesn't anchor to earlier outputs. If it still won't move the camera, attach a real photo with the target angle as "Image B — camera angle only".

The exact prompts used are in **Appendix A**.

### Checking a new background
```bash
cp ~/Downloads/NEW.webp backgrounds/env2.webp
.venv/bin/python composite.py --bg backgrounds/env2.webp --monitor frames/rae-monitor --laptop frames/rae-laptop --detect-only
open debug/detect-A.jpg       # magenta quads + red corners must sit exactly on both screens
```
(`--detect-only` with `--bg` always names the overlay `detect-A.jpg`.)

### Mirroring
If the laptop covers a monitor corner where the site puts text (Rae & Thorburn's hero titles are bottom-left), mirror the backgrounds so the laptop sits on the other side. Only the room is flipped; the site is not.
```bash
.venv/bin/python -c "import cv2; cv2.imwrite('backgrounds/env1-flip.png', cv2.flip(cv2.imread('backgrounds/env1.webp'), 1))"
```
Save flips as PNG (lossless).

---

## 4. Inspecting a site

Run `inspect4.mjs` **at the viewport you'll capture at** (section offsets change with viewport height), and `inspect2.mjs` + a contact sheet to see what each scroll position looks like.

Look for:
1. **Preloader / intro** — capture waits `settleMs` (default 5000, use 6000) before recording.
2. **Custom cursor** — fixed `pointer-events-none` elements; hide via `hideSelectors`. Both sites so far: `".pointer-events-none.fixed.z-\\[100\\]"`.
3. **Pinned (sticky) sections** — scroll range = section height − viewport height. Horizontal carousels and scroll-scrubbed heroes live here.
4. **Scroll-driven video/image-sequence heroes** — never pause inside them (the footage freezes). Check the sequence frames load up front (`inspect3.mjs`: Rae & Thorburn preloads 841 frames at load; good).
5. **Where text sits** relative to the corner the laptop covers → mirror backgrounds if needed (§3).
6. **Dark vs light sections** — dark pages suit the dark room; light pages glow brighter (fine, just be aware).
7. **Laptop page** — pick a second page that complements the homepage (Vauclair: a product page; Rae & Thorburn: the house featured in the hero tour, `/houses/dingle-burn`).

---

## 5. Recording the site — `capture.mjs`

### Viewport = screen shape
Record at the aspect ratio of the **straight-on** background's screens (perspective there is negligible, so the measured ratio is reliable), otherwise the site looks stretched.

```bash
.venv/bin/python tools/screen_ratios.py backgrounds/env1-angleB.webp
# monitor  ratio 1.536  suggested viewport 1440x938  [straight-on, reliable]
# laptop   ratio 1.458  suggested viewport 1280x878  [straight-on, reliable]
```
Current room (env1 / angle B): monitor ≈ 1.54, laptop ≈ 1.46. Rae & Thorburn used **1440×920** / **1280×864** (a hair wider than B's exact 938/878 suggestion, splitting the difference toward angle A); either is fine. (Oblique angle A estimates ~1.72 / ~1.51 assuming a 35 mm lens — unreliable for AI images; the straight-on angle wins.) Always `dpr: 2`: the 2880-wide frames are 2–3× oversampled relative to their size in the reel, which is what keeps text crisp.

### Config keys
```jsonc
{
  "url": "https://rae-thorburn.vercel.app/",
  "out": "frames/rae-monitor",          // frame folder
  "width": 1440, "height": 920,         // CSS viewport
  "dpr": 2,                             // device pixel ratio (frames = 2880x1840)
  "fps": 60,                            // ALWAYS 60 (script default is 30)
  "duration": 18,                       // seconds; both screens must match
  "settleMs": 6000,                     // let preloader/intro finish before recording
  "interp": "smooth",                   // "smooth" = never stops at keyframes; omit = eases to a stop at each
  "hideSelectors": [".pointer-events-none.fixed.z-\\[100\\]"],
  "css": "",                            // optional extra CSS injected before recording
  "keyframes": [[0, 0], [0.8, 250], [9.4, 3680], ...]   // [seconds, scrollY]
  // also: "format": "jpeg"|"png", "quality": 95, "startFrame", "endFrame"
}
```

### Choreography rules (approved in review)
- **Keep scrolling.** Use `"interp": "smooth"` (monotone cubic through keyframes: speed changes, never a full stop, never reverses). A flat pair of keyframes (`[3,900],[3.6,900]`) is a deliberate hold — avoid inside scroll-driven heroes.
- **Speeds:** ~400 px/s through a scroll-driven hero at a 920 px viewport (approved as "a bit slower" than 540); ~450–550 px/s for normal sections; slow to ~150–230 px/s where there's a line worth reading (manifesto), then speed back up.
- Start with a short ease-in (`[0,0],[0.8,250]`).
- Laptop: slower continuous drift (~180–330 px/s) through a secondary page, ending on something strong (footer wordmark / "next" panel).
- 14–18 s total. Both configs must have the same `duration`.

### Run + verify
```bash
node capture.mjs configs/site-monitor.json > frames/site-monitor.log 2>&1 &
node capture.mjs configs/site-laptop.json  > frames/site-laptop.log  2>&1 &
wait; tail -1 frames/site-monitor.log frames/site-laptop.log     # "done: 1080 frames in ~60s"
```
Contact sheet of chosen frames, then look at it:
```bash
tools/sheet.sh frames/site-monitor debug/site-monitor-sheet.jpg 30 180 360 540 720 900 1070
```
Stutter check for a scroll-driven hero (frames with ~0 change while scrolling = freeze):
```bash
.venv/bin/python tools/check_stutter.py frames/site-monitor 0 560
```
A couple of isolated frozen frames at the very start (slow scroll < 1 sequence frame per video frame) or exactly where the hero ends are normal; a run of 3+ is a visible stall.

Raw screen recordings as MP4 (optional, for reviewing the scroll on its own):
```bash
ffmpeg -y -loglevel error -framerate 60 -i frames/site-monitor/f%05d.jpg -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -movflags +faststart output/site-monitor-raw.mp4
```

---

## 6. The edit + render — `composite.py`

### Edit JSON
```json
{
  "angles": { "A": "backgrounds/env1-flip.png", "B": "backgrounds/env1-angleB-flip.png" },
  "shots": [
    {"angle": "B", "until": 11.4, "zoom": [1.00, 1.08], "focus": "both"},
    {"angle": "A", "until": 15.0, "zoom": [1.02, 1.07], "focus": "both"},
    {"angle": "B",                "zoom": [1.06, 1.12], "focus": "both"}
  ]
}
```
- `until` = cut time in seconds (omit on the last shot → runs to the end).
- `zoom` = [start, end] scale for that shot, linear (add `"ease": "smooth"` for smoothstep). 1.0 = full frame.
- `focus` = `"both"` (midpoint of the two screens), `"monitor"`, or `"laptop"` — the push-in target; the frame is clamped to stay inside the image.
- **Sync is automatic:** every angle reads the same frame index from the same recordings, so a cut never changes the scroll position.

### Pacing rules (learned from review — follow these)
- **~3 long shots**, not 6–7 quick ones. No punch-in close-ups.
- **Gentle zooms** (≈0.05–0.08 change per shot).
- **Never cut inside a scroll-driven hero** — hold one angle until the hero has fully left the screen (Rae & Thorburn: first cut at 11.4 s when the manifesto fills the screen).
- Open on the straight-on angle (biggest, cleanest screens).
- Zoom ≤ 2.0 keeps screen content at full sharpness (canvas is 2160×3840 → output 1080×1920).

### Commands
```bash
# detection overlays for every angle in the edit -> debug/detect-A.jpg, debug/detect-B.jpg
.venv/bin/python composite.py --edit configs/site-edit.json --monitor frames/site-monitor --laptop frames/site-laptop --detect-only
# preview frames (index = seconds × 60): check frames right before/after each cut
.venv/bin/python composite.py --edit configs/site-edit.json --monitor frames/site-monitor --laptop frames/site-laptop --out output/x.mp4 --still 300 683 684 1000
# full render (~4 min for 18 s)
.venv/bin/python composite.py --edit configs/site-edit.json --monitor frames/site-monitor --laptop frames/site-laptop --out output/site-reel.mp4
# verify
ffprobe -v error -show_entries stream=width,height,r_frame_rate,nb_frames -show_entries format=duration,size,bit_rate -of default=nw=1 output/site-reel.mp4
ffmpeg -y -loglevel error -i output/site-reel.mp4 -vf "select='eq(n\,10)+eq(n\,400)+eq(n\,700)+eq(n\,1000)',scale=400:712,tile=4x1:padding=4" -frames:v 1 debug/final-sheet.jpg
```
Single-background mode (one continuous shot, smoothstep push-in 1.00→1.08): `--bg backgrounds/env1.webp` instead of `--edit`, optional `--zoom 1.0 1.08`.

### All flags
| Flag | Default | Meaning |
|---|---|---|
| `--edit FILE` / `--bg IMG` | — | Multi-angle edit, or one background as one shot |
| `--monitor DIR`, `--laptop DIR` | required | Frame folders. Upper green region = monitor. |
| `--out FILE` | `output/reel.mp4` | Output path |
| `--fps` | 60 | Frame rate of the captured frames (and output) |
| `--frames N` | all | Render only the first N frames (quick preview) |
| `--zoom A B` | 1.0 1.08 | Push-in for `--bg` mode |
| `--glow` | 0.22 | Screen light spilling onto the room (0 = off) |
| `--lift` | 0.025 | Black-level lift on screens (LCD blacks glow in a dark room) |
| `--crf` | 10 | x264 quality; lower = higher bitrate |
| `--ig30` | off | Also write `*-30fps.mp4` (frame-pair blend = natural motion blur) |
| `--swap` | off | Swap which screen gets which recording |
| `--detect-only` | off | Only write detection overlays |
| `--still N [N…]` | — | Write `debug/still<N>.png` instead of a video |

### Output spec
**1080×1920, 60 fps minimum, high bitrate.** Encoder: libx264 `-preset slower -crf 10 -maxrate 50M -bufsize 100M -x264-params aq-mode=3:aq-strength=0.9 -g 120`, High profile level 4.2, yuv420p, BT.709 tags, `+faststart`. Typical result 21–28 Mb/s. No audio track (music is added in the Instagram app for licensing).

---

## 7. How it works (technical)

### capture.mjs — deterministic recording
Normal screen recording is soft and drops frames. Instead every output frame is a full 2× screenshot, and the browser's clocks are driven so all motion plays at true speed regardless of how long a screenshot takes:
1. `page.clock.install()` before navigation fakes `Date`, `performance.now`, timers and `requestAnimationFrame` (Three.js/R3F shaders, Lenis, Motion all follow it). After the preloader settles, `clock.pauseAt()` freezes it; each frame calls `clock.runFor(1000/fps)`.
2. CSS transitions / CSS animations / WAAPI (incl. Motion's hardware-accelerated animations) are frozen with CDP `Animation.setPlaybackRate(0)`; each frame, `document.getAnimations()` are stepped to the virtual time (new animations start at 0 when first seen). Scroll-timeline animations are left alone.
3. Autoplaying `<video>` elements are paused and seeked to virtual time each frame (waits for `seeked`).
4. Scrolling: `window.scrollTo(y)` + a synthetic `scroll` event so Lenis/Motion listeners update in the same frame. Lenis re-syncs to native scroll, so the script's curve replaces Lenis smoothing.
5. Lazy images are switched to eager and awaited up front (without scrolling, so reveal animations still play during the recording). Fonts awaited. Custom cursor hidden.

### composite.py — compositing
1. Background is center-cropped to 9:16 and scaled to a **2160×3840 working canvas**.
2. **Screen detection:** greenness = G − max(R, B); mask > 60; open 5×5 / close 7×7 (small, so the thin bezel between screens survives); two largest regions. Each outline → polygon; edges touching a concave vertex belong to the occluder (laptop lid) and are dropped; the 4 longest remaining edges are the screen sides; each side is re-fit with `fitLine` on its contour points (ignoring rounded ends); consecutive sides intersect → corners, including **hidden corners** (tested to ±2 px).
3. Upper region (by centroid) = monitor.
4. Per screen: perspective warp of the frame into its quad (INTER_AREA), alpha = warped quad × green key (dilated 5 px) × that screen's own green region (so monitor footage can't paint into the laptop).
5. Despill: green clamped to max(R, B) in a 14 px band around each screen.
6. Screen look: slight black lift + faint diagonal glass sheen; room glow = the screens' emitted light blurred at 1/8 res and screen-blended onto the room outside the screens.
7. Camera: sub-pixel `warpAffine` to a 2× intermediate (magnification ≥ 1, no aliasing), then exact 2× area downscale → 1080×1920. No integer-crop jitter during slow zooms.
8. Frames piped as raw BGR into ffmpeg.

---

## 8. House style & decisions (keep these)
- Output: **60 fps minimum**, high bitrate/quality, 1080×1920 (Instagram's max; >1080 is downscaled by IG, >60 fps not supported).
- Look: dark "Batman" penthouse, low-key light, no props, realistic not "AI".
- Scroll: continuous, no stalls; slower through scroll-driven heroes; slow for key copy.
- Edit: few long shots, gentle zooms, no cut inside the hero, open straight-on.
- Laptop must not cover site text → mirror the room when needed.
- Instagram notes: add music in-app; turn on *Settings → Media quality → Upload at highest quality*; IG may play Reels at 30 fps (`--ig30` makes a motion-blurred 30 fps cut if 60 fps ever looks steppy after upload).

---

## 9. Reels made so far (reproducible)

### Vauclair — vauclair-alpha.vercel.app (fictional perfume house), single angle
- Monitor: homepage (liquid-amber Three.js hero → manifesto → pinned horizontal collection → "Matières"). Laptop: `/collection/vesperale`.
- Configs: `configs/monitor.json` (1440×810), `configs/laptop.json` (1280×800), 60 fps, 14.5 s, eased keyframes (short holds).
- Background: `backgrounds/env1.webp` (angle A, unflipped).
- Render: `.venv/bin/python composite.py --bg backgrounds/env1.webp --monitor frames/monitor --laptop frames/laptop --out output/vauclair-reel.mp4`
- Output: `output/vauclair-reel.mp4` (+ `vauclair-*-raw.mp4` screen recordings).
- Note: captured at 16:9 / 16:10 before the aspect-matching rule; fine for angle A.

### Rae & Thorburn — rae-thorburn.vercel.app (custom homes, Central Otago), two angles, mirrored
- Monitor: homepage — 4600 px pinned drone-tour hero (841-frame canvas image sequence, 7 chapters) → manifesto (4600) → The Houses carousel (5323–6447) → into The Process. Laptop: `/houses/dingle-burn` (the house in the tour).
- Configs: `configs/rae-monitor.json` (1440×920), `configs/rae-laptop.json` (1280×864), 60 fps, 18 s, `"interp": "smooth"`; `configs/rae-edit.json` (B 0–11.4 s → A 11.4–15 s → B 15–18 s).
- Backgrounds: `env1-angleB-flip.png` (B), `env1-flip.png` (A).
- Output: `output/rae-thorburn-reel.mp4` (1080 frames, ~24.7 Mb/s, 56 MB).
- History: v1 had 7 shots with punch-ins and cut inside the hero, and the laptop hid the hero's bottom-left chapter text → review called for fewer/slower cuts, a slower hero, no cut in the hero, and mirrored backgrounds → v2 (current).

---

## 10. Known limitations / gotchas
- **Scroll-scrubbed `<video>` heroes:** capture.mjs pauses and time-seeks *every* `<video>`, which would fight a site that sets `video.currentTime` from scroll. Rae & Thorburn uses a canvas image sequence, so it wasn't hit. Fix when needed: only manage videos that are playing/autoplay when first seen, and just wait for `seeked` on the others.
- **Shader sites** render through Chromium with `--use-angle=metal`; if a WebGL canvas comes out black, check GPU flags.
- **Two green regions required.** If detection reports 1 region, the bezel between the screens is too thin or they touch — regenerate or edit the image.
- **Aspect ratio:** one recording feeds all angles, so match the straight-on angle; oblique angles hide small mismatches.
- **Disk:** each 18 s screen recording is ~1.2 GB of JPEGs. Clean with `rm -rf frames/<name>` after the reel is approved (keep the configs — re-capturing is ~1 min).
- `configs/test.json` + `test/` are pipeline tests (stand-in backgrounds), not real reels.
- Render time: ~0.2–0.25 s per frame (≈4 min for 18 s @ 60 fps); capture ≈55–65 s per screen for 1080 frames, both screens in parallel.

---

## Appendix A — prompts that produced the current room

### Angle A (`env1.webp`) — generated from scratch
```
Photoreal night interior photograph, vertical 9:16, of a stealth all-black high-rise penthouse workstation: dark, monochrome, architectural, brooding, quietly expensive. It must read as a real camera photo, never a 3D render. The creative heart of the image: "the lair desk," a large monitor and an open laptop shot from a low three-quarter angle so they overlap like a real desk setup, both screens flat chroma green, glowing in an otherwise near-black room.

Canvas: vertical 9:16 portrait, full-bleed, the room falling off into near-black (#0A0A0B) at every edge.

Foreground (bottom ~20%): matte black-oak desk (#141210) running diagonally away to the right, softly out of focus near the lens, faint grain and a few dust specks. The desk holds ONLY the laptop and monitor: no cups, no glasses, no plants, no lamps, no books, no decor.
Hero: an open 16-inch MacBook Pro in space black (#232325) at lower-left, turned ~30° toward camera-right, keyboard visible at the bottom edge.
Behind it and higher: a 32-inch Pro Display XDR-style monitor, ultra-thin black bezels, dark graphite frame, on a black arm. It fills ~90% of frame width in the upper-middle, turned ~30° so its right side recedes. The laptop lid sits in front of the monitor's lower-left corner; the laptop's black bezel and lid edge form a clear dark border between the two screens.
Both screens: edge-to-edge flat, uniform, pure chroma green (#00FF00). No UI, no reflections, no glare, no gradient, crisp straight edges. The displays are ON and throw a soft neutral cool-white glow (#DDE3EC, NOT green) onto the keyboard, desk and lid edges.
Midground: black-framed floor-to-ceiling glass, one thin black mullion.
Background: night skyline ~50 floors up, heavily defocused into bokeh: sparse warm window lights, two red aviation beacons, near-black navy sky (#0B1020), no sunset colors.
Room: black textured stone wall panels; black ceiling with one thin warm LED cove line (2700K, #E8B77A) and two small recessed pinhole downlights near the top of the frame.

Lighting: very low-key, ~2 stops darker than a normal interior. The screens and the city are the brightest elements; deep blacks with shadow detail barely held; the cove line is the only warm light; the city faintly rim-lights the monitor's right edge.

Composition: camera low at desk height, ~40 cm from the laptop, left of center, tilted up ~10° and aimed right, three-quarter view, deliberately asymmetrical. Monitor top edge sits ~12% from the top of the frame; the laptop fills the lower-left third; together the screens fill ~60% of the frame, and both green areas stay fully in frame.

Palette: near-black (#0A0A0B), charcoal (#1C1C1E), black oak (#141210), space black (#232325), graphite (#3A3B3E), night navy (#0B1020), cove amber (#E8B77A), city gold (#FFC77A). Monochrome dark with small warm accents; green appears ONLY inside the two screens.

Camera: Sony FX3, 35mm at f/2.8, ISO 3200; laptop and monitor sharp, skyline fully melted into bokeh.

Finish: real-camera imperfections: fine sensor noise in the shadows, slight bloom on the downlights, faint chromatic aberration at the frame edges, gentle vignette, one light fingerprint smudge on the aluminum. No CGI sheen, no symmetry, no plastic textures, no people, no emblems, logos, symbols or text anywhere.

References: Christopher Nolan film-still realism, Wally Pfister low-key night cinematography × Tadao Ando dark minimalism × Wallpaper* magazine. Indistinguishable from a real photograph, 4k.
```
(Suggested use: attach an angle reference — the "We build websites" reel screenshot — and the black-bedroom mood reference, with the line *"Use Image A for camera angle and screen arrangement only. Use Image B for the room's materials and lighting mood only. Ignore their screen content, furniture and colors."* The exact model and references used for `env1.webp` weren't recorded.)

### Angle B (`env1-angleB.webp`) — GPT Image 2, written to be run with `env1.webp` attached
```
Using Image A (attached) as the reference for the room, desk, devices, materials and lighting, create a NEW camera angle: a straight-on, closer shot of the same workstation. Do not reuse Image A's camera angle. Photoreal night interior, vertical 9:16, stealth all-black high-rise penthouse; dark, monochrome, brooding, quietly expensive. The creative heart of the image: "the front row," both screens seen almost dead-on and large in frame, like a premium product shot inside a real room.

Canvas: vertical 9:16 portrait, full-bleed, edges falling off into near-black (#0A0A0B).

Camera: directly in front of the monitor, centered on it, at seated eye level, lens pointing straight at the screen. 50mm lens at f/2.8, ISO 3200. The monitor is perfectly frontal: its top and bottom edges are horizontal and parallel, its left and right edges are the same height, with no receding side.

Monitor: the same thin-bezel monitor on its black arm, filling ~90% of frame width, its top edge ~22% from the top of the frame.
Laptop: the same open space-black 16-inch MacBook Pro (#232325), in front of the monitor and slightly left of center, lid facing the camera squarely, screen upright and fully readable, keyboard deck visible below it. Its top edge overlaps the monitor's lower-left corner by a few centimeters, with the laptop's black bezel forming a clear dark border between the two screens.
Together the two screens fill ~55% of the frame height.

Screens: both displays filled edge-to-edge with the same flat, uniform chroma green as Image A (#32D435). No UI, no notch, no reflections, no glare, no gradient; crisp straight edges meeting thin black bezels. A faint neutral white glow falls on the keyboard and desk, never green.

Room (same as Image A): matte black-oak desk (#141210) in the bottom of the frame; behind and right of the monitor, the black-framed window with the night skyline and the tall tower with two red aviation beacons, deeply defocused; at the left, black textured stone panels with the thin warm LED cove line (#E8B77A) near the top. No cups, glasses, plants, lamps or decor.

Lighting: identical to Image A. Very low-key; the screens and city lights are the brightest elements; deep blacks with barely held shadow detail.

Finish: real-camera imperfections: fine shadow noise, slight bloom on the lights, gentle vignette. No CGI sheen, no people, no logos, emblems or text anywhere.

References: Christopher Nolan film-still realism, Wally Pfister low-key night cinematography, Apple-keynote product framing. Indistinguishable from a real photograph, 4k.
```
Settings: 9:16, 2160×3840 if custom sizes are allowed, quality high.

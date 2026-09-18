---
name: website-reel
description: Make Instagram Reels (vertical 9:16, 60fps) that showcase a website inside an AI-generated room — records the live site frame by frame and composites it into the chroma-green screens of a monitor + MacBook background, with slow push-ins and cuts between camera angles, using the ~/reel-maker pipeline. Use this whenever the user gives a site URL and wants a reel, video, showcase, portfolio clip, or "my site on the laptop/monitor"; wants a new room, background or camera angle for these reels (the green-screen image prompt); or wants to change an existing reel's scroll speed, pauses, cuts, zoom, pages or quality — even if they never say "reel-maker" or "skill".
---

# Website Reel

Produces a 1080×1920, 60 fps, high-bitrate MP4: a real website scrolling on a monitor and a laptop inside a photoreal dark penthouse, cut between two camera angles. The pipeline is this repo, cloned to `~/reel-maker` (the skill folder is symlinked into `~/.claude/skills/`); `docs/PLAYBOOK.md` is the full reference (commands, config schemas, prompts, how it works, gotchas). This skill is the procedure and the judgment calls; open the playbook section named at each step when you need the detail. If `~/reel-maker` doesn't exist, point the user to the repo README's setup section before anything else.

Two reels already exist and are good templates: Vauclair (single angle) and Rae & Thorburn (two angles, mirrored) — playbook §9.

## Scope first

Do only the step that was asked for. "Give me the prompt for the next background" means write the prompt, not wire it into a render; "for the next site" means don't touch the current reel. Running ahead (re-rendering, re-wiring) wastes minutes of render time and overwrites work the user hasn't reviewed.

## House style (tuned through real review rounds — don't relitigate)

- **Output:** 1080×1920, **60 fps**, high bitrate (the pipeline's CRF 10 → ~20–28 Mb/s). Instagram tops out at 1080p and 60 fps, so more resolution/fps buys nothing; say so if asked.
- **Look:** dark stealth-luxury ("Batman") penthouse at night, low-key light, no desk props, real-camera feel, not "AI".
- **Scroll:** always moving (`"interp": "smooth"`); slower through scroll-driven/video heroes (~400 px/s at a 920 px viewport) because a stopped scroll-video looks broken; slow down where there's copy worth reading, then pick up again.
- **Edit:** about 3 long shots with gentle push-ins; open on the straight-on angle; never cut while a scroll-driven hero is on screen. Seven quick cuts with punch-ins was rejected as "too fast, too many angles".
- **Text must stay visible:** the laptop overlaps a monitor corner. If the site puts text there (e.g. bottom-left hero titles), mirror the backgrounds so the laptop sits on the other side.

## Workflow

Work from `~/reel-maker`. Use `.venv/bin/python` for Python (system Python has no OpenCV).

### 1. Room (backgrounds)

Existing: `backgrounds/env1.webp` (angle A, low 3/4), `env1-angleB.webp` (angle B, straight-on), and mirrored `*-flip.png` versions (laptop on the right). Reuse them unless the user wants a new room.

For a new room or angle, write the image prompt with the **image-prompt-crafter** skill, starting from playbook §3 rules and the prompts in Appendix A. Key constraints to carry into any prompt: 9:16 set in the tool UI (text alone gets ignored), both screens flat chroma green edge to edge, a dark bezel separating the two green areas, no props, no green spill. For a re-angle of the same room, lead the prompt with the camera change and describe the resulting geometry; a long "keep identical" list makes the model copy the old angle.

When the user sends a new image: copy it into `backgrounds/`, then
```bash
.venv/bin/python composite.py --bg backgrounds/NEW.webp --monitor frames/rae-monitor --laptop frames/rae-laptop --detect-only
```
and look at `debug/detect-A.jpg` yourself — the magenta quads must sit exactly on both screens (hidden corners behind the laptop are extrapolated; that's expected).

### 2. Inspect the site (playbook §4)

```bash
node inspect4.mjs <url> 1440 920      # sections, [pinned] sticky parts, <video> elements, max scroll
node inspect.mjs <url>                # libraries (Lenis, Three…), fixed elements (cursor/preloader), internal links
node inspect2.mjs <url> inspect/NAME 1440 920   # one screenshot per viewport height
ffmpeg -y -loglevel error -pattern_type glob -i 'inspect/NAME-[0-9]*.png' -vf "scale=480:-1,tile=5x5:padding=4" -frames:v 1 inspect/NAME-sheet.png
```
Look at the contact sheet. Decide: which page goes on the monitor (usually the homepage), which on the laptop (a page that complements it — e.g. the product/house featured in the hero), where the pinned sections and scroll-driven heroes are, where text sits relative to the laptop-covered corner, and which selector hides a custom cursor (both sites so far: `.pointer-events-none.fixed.z-\\[100\\]` in JSON). If the page has a scroll-scrubbed `<video>` (not a canvas sequence), read playbook §10 first — the recorder needs a small fix for that case.

### 3. Viewports and scroll plan (playbook §5)

```bash
.venv/bin/python tools/screen_ratios.py backgrounds/env1-angleB.webp
```
Record at the straight-on angle's screen shape so the site isn't stretched (current room: monitor 1440×920, laptop 1280×864). Re-run `inspect4.mjs` at those exact viewports — offsets change with viewport height.

Write `configs/NAME-monitor.json` and `configs/NAME-laptop.json` by copying `configs/rae-monitor.json` / `rae-laptop.json`. Always `fps: 60`, `dpr: 2`, `interp: "smooth"`, `settleMs: 6000`, and the **same `duration`** for both (14–18 s). Keyframes are `[seconds, scrollY]`; plan speeds per playbook §5 and state the plan to the user in plain words before capturing if the site is new.

### 4. Capture and verify

```bash
node capture.mjs configs/NAME-monitor.json > frames/NAME-monitor.log 2>&1 &
node capture.mjs configs/NAME-laptop.json  > frames/NAME-laptop.log  2>&1 &
wait; tail -1 frames/NAME-monitor.log frames/NAME-laptop.log     # ~1 min each for 1080 frames
tools/sheet.sh frames/NAME-monitor debug/NAME-monitor-sheet.jpg 30 180 360 540 720 900 1070
tools/sheet.sh frames/NAME-laptop  debug/NAME-laptop-sheet.jpg  30 180 360 540 720 900 1070
.venv/bin/python tools/check_stutter.py frames/NAME-monitor 0 <last hero frame>
```
Look at both sheets: reveals playing, nothing blank, cursor hidden, the right sections at the right times. For a scroll-driven hero, a frozen run of 3+ frames is a visible stall — fix before rendering.

### 5. Edit, check, render (playbook §6)

Write `configs/NAME-edit.json` (copy `configs/rae-edit.json`): `angles` → background paths; `shots` → `{angle, until, zoom:[start,end], focus: both|monitor|laptop}`. Every angle reads the same frame index, so cuts never change the scroll position. Place the first cut after the hero has fully left the screen.

```bash
# stills right before/after each cut (frame = seconds × 60) -> debug/still<N>.png; look at them
.venv/bin/python composite.py --edit configs/NAME-edit.json --monitor frames/NAME-monitor --laptop frames/NAME-laptop --out output/NAME-reel.mp4 --still 300 683 684
# full render, ~4 min for 18 s
.venv/bin/python composite.py --edit configs/NAME-edit.json --monitor frames/NAME-monitor --laptop frames/NAME-laptop --out output/NAME-reel.mp4
ffprobe -v error -show_entries stream=width,height,r_frame_rate,nb_frames -show_entries format=duration,size,bit_rate -of default=nw=1 output/NAME-reel.mp4
ffmpeg -y -loglevel error -i output/NAME-reel.mp4 -vf "select='eq(n\,10)+eq(n\,400)+eq(n\,700)+eq(n\,1000)',scale=400:712,tile=4x1:padding=4" -frames:v 1 debug/NAME-final-sheet.jpg
```
Check the frames from the finished file, not just the stills, before reporting.

### 6. Report

Give the path and `! open output/NAME-reel.mp4`, a small spec table (resolution, fps, frames, bitrate, length, size), the shot list with what's on screen in each shot, and anything the user should eyeball. Remind them to add music in the Instagram app.

## Turning feedback into changes

| Feedback | Change | Re-capture? |
|---|---|---|
| Cuts too fast / too many angles | Fewer, longer shots; smaller zoom deltas | No — edit JSON + render |
| Cut happens during the hero | Move the first `until` past the moment the hero leaves the screen | No |
| Scroll too fast / pauses too long | Retime keyframes (stretch or remove holds), keep both durations equal | Yes |
| Laptop hides the site's text | Mirror backgrounds (`cv2.flip(img, 1)` → PNG), point the edit at the flips | No |
| Site looks stretched | Viewport doesn't match the screen shape — re-measure with `screen_ratios.py` | Yes |
| Wants more quality / fps | Already at Instagram's ceiling (1080p, 60 fps, CRF 10); explain | — |

When feedback reveals a new standing preference, add it to playbook §8 so the next session knows.

## Housekeeping

Frames are large (~1.2 GB per 18 s screen); after the user approves a reel, offer to delete `frames/NAME-*` (configs make re-capture a one-minute job). Update playbook §9 with any new reel (configs, backgrounds, what changed across versions) — the playbook is the memory of this project.

# SimMorph design checklist (satisfying 3D physics Shorts)

Source and limits: derived from public titles, descriptions, creator tutorials and "satisfying loop" guides for the
niche (ShortForm3D, 3D 4FUN, Rolling Qub, Kinetic Garden and similar). Video content itself could not be watched from the
build environment, so the checklist records structural patterns only. Nothing from those channels (scenes, assets,
wording, branding) is reused. Every item below is applied in the templates and was checked on rendered frames.

## Story shape
1. ONE question per Short, readable without narration ("CAN 60 BALLS ESCAPE A TINY HOLE?").
2. Setup that is understood in the first second: one clear subject, nothing else in frame.
3. Escalation of 3-6 stages, each visibly bigger or harder than the last (more objects, smaller opening, more rings).
4. The last stage is the extreme case and gets extra simulation time (`simulation.payoff_duration`) so the result is seen.
5. Length comes from the experiment: ~18-24 s when the physics needs it, shorter when it does not. No padding stage.
6. A fifth (or sixth) stage is added only when it brings something new (larger quantity, smaller hole, harder case).

## Frame
7. Subject large: fills the 9:16 frame width; the camera is fitted to the real extents (`camera_rig.fit_camera`).
8. Clean seamless studio backdrop: shadow-catcher floor, no horizon line, mid-tone background so pale objects keep contrast.
9. Saturated, simple materials (glossy colour balls, solid cloth); transparent containers only when they explain the scene.
10. Smooth, rare camera movement. The simulation is the content: no UI, no tutorial look.
11. Text: one short question at the start, one short stage label (`60 BALLS`, `SNUG RING`) - never covering the action.

## Sound and loop
12. Event-driven sound (impacts, landings); music is optional and quiet. A silent stage is fine.
13. Loop: the opening hook replays the final (extreme) result and the last stage ends on it, so the Short reads as
    answer -> proof. A literal geometric loop is only worth it when the end state can naturally return to the start
    (not forced for these experiments).

## Per-experiment escalation
| experiment | question | escalation (stages) |
|---|---|---|
| multiple_balls | WHAT HAPPENS WHEN 100 BALLS DROP AT ONCE? | 5 -> 15 -> 30 -> 60 -> 100 balls into one tall glass box |
| ball_funnel | CAN 60 BALLS ESCAPE A TINY HOLE? | hole 5x -> 1.5x ball width while balls grow 7 -> 60 |
| ring_toss | HOW SMALL CAN THE RING HOLE GET? | hole 2.6x -> 0.9x pole width while rings grow 1 -> 5 |
| cloth_drape | WHAT HAPPENS WHEN WE ADD 256x MORE FACES? | 64 -> 1K -> 4K -> 16K faces, optional close-up stage |
| cloth_objects | HOW MANY OBJECTS CAN ONE CLOTH COVER? | 1 -> 2 -> 3 -> 4 (-> 5) objects under one sheet |

## Review gate before a batch
Render real frames of every experiment at low resolution and look at: subject size, framing, text, motion, collisions,
materials, lighting, escalation and final payoff. Fix first, then batch. (Done for this revision; see the report.)

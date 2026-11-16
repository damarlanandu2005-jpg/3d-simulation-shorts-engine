# SimMorph Creative Research and Concept Blueprint

Date: 2026-11-16 · Branch `v1.1` · Status: research document, no engine changes, no videos generated.

## 0. Read this first: limits of the research

This document is honest about what could and could not be done.

- **I did not watch any competitor video.** Claude in Chrome was not connected, and YouTube blocked every automated route available to me (RSS feeds and Shorts tabs returned `robots_disallowed`; the ShortForm3D channel page failed; fetched video pages carried no view or duration data).
- **None of the five named channels' individual videos could be retrieved.** Web searches for Rolling Qub, 3D 4FUN, Blop Blop, ShortForm3D and Kinetic Garden returned no pages about those channels or their videos. Search results were dominated by unrelated pages.
- **The "at least 20 videos" target is not met.** Section 2 lists only the items that the searches actually surfaced (about a dozen), each labelled as title/snippet-only. I have not padded it with invented entries.
- **No view counts or durations are verified for any named channel.** The only figures that appear are ones found in search snippets, quoted with their source and flagged as unverified aggregator data.
- Everything in the creative-pattern sections (3, 4) is therefore a **hypothesis built from titles, snippets and general knowledge of the genre**, not an observation of specific videos. Observed facts and hypotheses are marked separately.
- Sections 5 onward (SimMorph comparison, concepts, feasibility) rest on our own repository and videos and are first-hand, except where marked.

**To close the gap:** give me 20 to 30 specific video URLs (or short screen recordings) and, ideally, a connected browser. Sections 2 to 4 can then be redone from real observation without changing the rest of this document.

## 1. Scope and method

Searches run: one per named channel plus genre queries. Scoring weights for concepts: curiosity 0.20, visual impact 0.20, satisfying payoff 0.15, originality 0.15, feasibility with Blender 0.15, reusability 0.10, production cost 0.05 (5 = cheap). Scores are my judgment, not measurements.

## 2. Video-by-video inventory (title/snippet only, no playback)

Columns the brief asked for (duration, hook, camera, lighting, sound, loop technique and so on) are **unobserved** for every row. They are left out rather than guessed.

| # | Channel / source | Title (as surfaced) | Evidence | What the snippet supports | Hypothesis (not observed) |
|---|---|---|---|---|---|
| 1 | Unattributed compilation channel (via aggregator pages) | The Most Satisfying Physics Simulations of 2025 | 3D Showcase | Aggregator page lists '312,987 views' (unverified) | Compilation format; 'showcase' framing; Blender-style physics | Many short clips back to back; relies on variety rather than one question |
| 2 | Same family of titles | The Most Satisfying Blender 3D Physics Simulation | 8 Minutes of Non-Stop Satisfaction | Title only; repeated across aggregator sites | 8-minute long-form compilation; descriptions say the clips are 4K 60fps and made by the channel owner | Ambient viewing, not a story |
| 3 | Same family | Peak Satisfying Blender 3D Physics Simulation | 8 Minutes of Non-Stop Satisfaction [What if 19] | Title only | Numbered series ('What if 19') | Series branding through numbering |
| 4 | Same family | Next-Level 3D Blender Physics Showcase | 9 Minutes of Pure Satisfaction | Title only | Long-form compilation | Same as above |
| 5 | Same family | The Most Satisfying Blender Physics Showcase | Cloth Simulation, Hair Particles & Slo-Mo! | Title only | Cloth, hair particles and slow motion are advertised ingredients | Slow motion is a selling point |
| 6 | Same family | Satisfying 3D Physics Showcase | Blender Hair Dynamics Simulation | Hair, Grass, Wind Example | Title only | Hair/grass with wind | Wind-driven soft motion as a genre staple |
| 7 | Same family | Pokemon Energy Physics Simulation in Blender | Title only | Franchise reference in title | Borrowed IP; SimMorph must not do this |
| 8 | Mateusz Zajac, 'Blender is Fun' (80.lv, Creative Bloq) | Soft golden cube getting crushed / jelly cube being prodded | Two news articles quote the channel; no video data | Soft-body cube; articles mention ASMR-style sound effects and mixed reactions to the sound; corners return to their shape | Sound design carries much of the appeal |
| 9 | Blender Bazaar listing | SUPER SATISFYING Physics Loop Made in Blender! | Tutorial listing, no stats | The word 'loop' and 'reactive material' are in the description | Loops plus glossy materials are a known recipe |
| 10 | Reddit r/Simulated posts | Blender 3D Brooklyn Bridge: Earthquake Destruction Simulation | A Reddit post says a dedicated earthquake-simulation channel reached 100,000 subscribers | A single-topic destruction channel at 100k subscribers (per the poster) | Earthquake/destruction is a repeatable series topic |
| 11 | Reddit r/Simulated posts | 3D Mexico City: Earthquake Destruction Comparison | Reddit title only | 'Comparison' framing | Comparisons are a common structure |
| 12 | Reddit r/Simulated posts | Quadruple pendulum ('less chaotic than you would expect') | Reddit title only | Counter-intuitive science hook | Supports the pendulum concept family |
| 13 | DoodleChaos (Patreon) | Impossible Piano Physics Simulation – In the Hall of the Mountain King | Patreon post title, 2022-04-28 | Physics sim set to a known track | Music-synced physics is a distinct format; copyrighted music is a risk for us |
| 14 | Two Minute Papers (via rosetta.to) | This Isn't AI - It's Even Wilder: Squishy Physics That Learn to Move! | Aggregator shows 5m 4s, 60K views | Research-explainer, not a Shorts-style clip | Not a direct competitor |

None of these rows is from Rolling Qub, 3D 4FUN, Blop Blop, ShortForm3D or Kinetic Garden.

## 3. Creative formats (hypotheses from titles and genre knowledge)

Formats I can name and what supports each. **Evidence strength is low throughout** because no videos were observed.

| Format | Supported by | Repeats in the material I saw? | Performance evidence |
|---|---|---|---|
| Compilation / showcase | Many titles above | Yes, very often | Only an unverified 312,987-view aggregator figure |
| Destruction / earthquake | Reddit 100k-subscriber note | Yes | Weak (one forum claim) |
| Soft-body / ASMR sound | Jelly-cube and gold-cube articles | Yes | News coverage, no counts |
| Loop-friendly physics | 'Physics Loop' listing | Occasional | None |
| Counter-intuitive science (pendulums) | Reddit pendulum title | Occasional | None |
| Music-synced physics | DoodleChaos | Occasional | None |
| Extreme comparison, perfect fit, breaking point, weight/pressure, filling/overflow, sorting, marble runs, cloth/fluid, impossible setups, infinite loops | Genre knowledge and the brief's own list, not observed videos | Unknown | None |

I cannot say which formats have the strongest public performance. View counts do not establish what works, and I have almost none.

## 4. Patterns worth acting on (hypothesis, not observation)

1. **A question beats a label.** Titles that promise an answer are common in the genre. SimMorph already moved to question hooks.
2. **One hero, many props.** Compilations dilute attention; a single clear subject per video is the opposite of what the compilation titles do, which is a possible differentiator.
3. **Sound is part of the product.** The jelly-cube coverage is about sound as much as motion. SimMorph's audio is event-driven but plain.
4. **Loops and slow motion are advertised ingredients.** Cheap to add, hard to fake.
5. **Series naming.** Numbered or templated titles ('What if 19') build a recognisable brand.

Things to avoid: borrowed franchises, copyrighted music, reproducing another channel's setup.

## 5. SimMorph today versus the genre (first-hand)

This compares our own curated Kaggle batch (run 43820827640, 6/6 QC) with the **hypothesised** genre, not with watched competitor videos. Ratings are my own, 1 to 5.

| Dimension | SimMorph now | Note |
|---|---|---|
| Concept originality | 2 | Ball-and-hole variations; most videos share one idea |
| Visual clarity | 4 | Studio look, shadow-catcher floor, tight framing after the frame review |
| Strong first frame | 3 | Hook text exists; the first frame is often a still arena |
| Immediate physical action | 3 | Action starts after the hook |
| Object scale | 3 | Fixed after the review but still small versus the frame in some stages |
| Composition | 3 | Centered, safe, undistinctive |
| Materials and lighting | 3 | Clean pastel, little material contrast |
| Motion and interactions | 3 | Rigid and cloth only |
| Escalation | 4 | 3 to 6 stages with real extras |
| Surprise | 2 | Outcomes mostly predictable |
| Payoff | 3 | Longer final stage; the payoff is a repeat of earlier stages at larger scale |
| Replayability | 2 | Loops are approximate |

The weak points are originality, surprise and replayability. Those are concept problems, not rendering problems, which is why this phase is about concepts.

## 6. Thirty original concepts

Each entry: viewer question, setup, what happens physically, visual attraction, escalation, payoff, physics required, reuse, difficulty, why watch, and the engine class. Scores are in section 7.

### 1. The Great Roll-Off  (`shape_race`)

- **Viewer question:** Which shape reaches the bottom first?
- **Initial setup:** Six lanes on one tilted ramp, a different solid at the top of each: sphere, solid cylinder, hollow ring, cube, cone, torus. All same mass and release.
- **What physically happens:** Bullet rigid bodies roll, slide and tumble; the order is decided by shape (rotational inertia, contact), not by the artist.
- **Main visual attraction:** Six objects racing side by side, the lead changing, one tumbling off the track.
- **Escalation / challenge:** Round 2 makes the ramp steeper, round 3 adds a bumpy section; the favourite from round 1 is not always the winner.
- **Final payoff:** Slow-motion photo finish; the loser of round 1 wins the bumpy round (only if the physics says so).
- **Objects and physics required:** Rigid bodies, ramp mesh with lanes, six primitives (the engine already has _primitive/make_rigid).
- **Reusability as multiple videos:** Any set of shapes, any ramp; 'Heaviest vs lightest', 'smooth vs rough'.
- **Technical difficulty:** Low-medium
- **Why it deserves to be watched:** Everyone has a guess before the start, and the answer is a real physics fact (rolling inertia).
- **Engine class:** Supported with small extensions

### 2. What's Under the Sheet?  (`sheet_reveal`)

- **Viewer question:** Can you guess the hidden shape from its sheet?
- **Initial setup:** A large cloth hangs above an empty-looking floor. Hidden under it: a stack of objects forming a silhouette (a face-less 'ghost', a pyramid, a spiral staircase).
- **What physically happens:** Blender cloth drops and drapes over static colliders, with real folds and bridging between objects.
- **Main visual attraction:** A bare sheet becomes a statue: the reveal is the whole video.
- **Escalation / challenge:** Three sheets in a row: easy shape, harder shape, an impossible one that fools the viewer.
- **Final payoff:** Cloth settles and the silhouette is recognisable (or not); the hidden objects fade into view beside it.
- **Objects and physics required:** cloth_objects builder (exists) with arbitrary collider layouts and a ghost-shaded copy for the reveal.
- **Reusability as multiple videos:** Infinite hidden-shape riddles; a guessing-game series.
- **Technical difficulty:** Low
- **Why it deserves to be watched:** A guessing game with a satisfying drape; the cloth engine we already trust gets a story instead of a benchmark.
- **Engine class:** Supported with small extensions

### 3. Is the Jar Full?  (`jar_rocks`)

- **Viewer question:** Is the jar full when it looks full?
- **Initial setup:** A tall glass jar. Big rocks are dropped in until the first rock touches the rim.
- **What physically happens:** Rigid spheres/rocks of three sizes pour in sequence and settle into the gaps of the previous size.
- **Main visual attraction:** The jar that 'looks full' swallows a second and a third pour.
- **Escalation / challenge:** Pour 1 big, pour 2 medium, pour 3 tiny: each time the viewer thinks it is full.
- **Final payoff:** Final pour of tiny beads sinks into the last gaps; the level only rises a sliver.
- **Objects and physics required:** Rigid bodies of three radii, container walls (exists: create_floor_and_wall), settle detection.
- **Reusability as multiple videos:** Different jar shapes, different size ratios (packing density changes).
- **Technical difficulty:** Low-medium
- **Why it deserves to be watched:** A fully real result (packing), a visible wrong guess, and a calm payoff.
- **Engine class:** Supported with small extensions

### 4. Each One 1.5x Bigger  (`domino_giants`)

- **Viewer question:** How big can the last domino be?
- **Initial setup:** A row of dominoes starting thumb-sized, each next one 1.5x larger in every dimension.
- **What physically happens:** Bullet rigid bodies topple in a chain; the energy argument (each domino can topple one 1.5x bigger) is real physics.
- **Main visual attraction:** The chain grows in scale until the camera must climb to follow it.
- **Escalation / challenge:** Ratio and count are the escalation: ×1.5 per step to 12 steps, camera dollies back as the scale grows.
- **Final payoff:** The last domino is the size of a building and falls with a heavy slow-motion thud.
- **Objects and physics required:** Boxes with friction, a tiny initial push, camera follow along a path (camera_rig exists).
- **Reusability as multiple videos:** Different ratios (×1.2, ×2 fails!), curved paths, a spiral.
- **Technical difficulty:** Low-medium
- **Why it deserves to be watched:** A real, famous scaling fact that is visually shocking; a failing ×2 run is a built-in sequel.
- **Engine class:** Supported with small extensions

### 5. The Giant Always Rises  (`brazil_nut`)

- **Viewer question:** Why does the biggest ball rise to the top?
- **Initial setup:** A glass tank with 1,500 small balls and one large red ball buried at the bottom.
- **What physically happens:** The tank is shaken (a kinematic, animated container) and granular convection pushes the big ball up: the Brazil-nut effect.
- **Main visual attraction:** The red ball climbs through the mass like a periscope.
- **Escalation / challenge:** Shake amplitude steps up; a second run with a heavier giant that does not rise.
- **Final payoff:** The red ball breaks the surface and rests on top.
- **Objects and physics required:** Kinematic (animated) collider baked as rigid-body keyframes, ~1,500 spheres, long bake.
- **Reusability as multiple videos:** Size ratios, multiple giants, different container shapes.
- **Technical difficulty:** Medium-high
- **Why it deserves to be watched:** Counter-intuitive real physics and a clear hero object.
- **Engine class:** Requires a new physics template

### 6. Fifteen Pendulums, One Pattern  (`pendulum_wave`)

- **Viewer question:** Do 15 different pendulums ever line up again?
- **Initial setup:** A row of 15 pendulums whose lengths are tuned so each completes one more swing per minute than the last.
- **What physically happens:** Pendulum equation integrated numerically (honest ODE, not a fake animation) and written as keyframes, or hinge constraints.
- **Main visual attraction:** Waves, spirals and chaos appear from simple periodic motion, then realign.
- **Escalation / challenge:** Release together, watch the phase pattern evolve through wave, splits, chaos.
- **Final payoff:** At the full cycle they realign exactly: a built-in loop.
- **Objects and physics required:** A new integrator-based template (not Bullet) with a loop-exact duration.
- **Reusability as multiple videos:** Different numbers of pendulums, damping on/off, vertical vs horizontal view.
- **Technical difficulty:** Low
- **Why it deserves to be watched:** Hypnotic, mathematically exact, and loops perfectly.
- **Engine class:** Requires a new physics template

### 7. Which Tower Survives?  (`earthquake`)

- **Viewer question:** Which tower design survives the earthquake?
- **Initial setup:** Four towers of equal block count: a column, a pyramid, an arch bridge, a zig-zag. They stand on one shaking platform.
- **What physically happens:** The platform is a kinematic (animated) collider with a ramped shaking amplitude; blocks are Bullet rigid bodies.
- **Main visual attraction:** Four structures failing in different ways at different times.
- **Escalation / challenge:** Amplitude ramps over three levels; the survivor of each level is highlighted.
- **Final payoff:** One tower remains after the third level.
- **Objects and physics required:** Kinematic shaking platform + block stacks; careful stability tuning (stacks are sensitive).
- **Reusability as multiple videos:** Any set of structures; real-world designs (pyramid vs column).
- **Technical difficulty:** Medium-high
- **Why it deserves to be watched:** A real engineering question with a visible winner.
- **Engine class:** Requires a new physics template

### 8. Through the Eye of the Needle  (`cloth_ring`)

- **Viewer question:** Can a whole sheet pass through a tiny ring?
- **Initial setup:** A large square sheet hangs above a fixed ring (static torus) that is smaller than the sheet.
- **What physically happens:** Cloth gravity and collision: the sheet gathers and bunches through the hole.
- **Main visual attraction:** A sheet turns into a flowing funnel and a rope of fabric.
- **Escalation / challenge:** Three rings: wide, medium, tiny; with the tiny one the cloth jams in folds.
- **Final payoff:** The last of the cloth slips through the ring and drops.
- **Objects and physics required:** Cloth (exists), static torus collider (exists: ring builder), self-collision tuned.
- **Reusability as multiple videos:** Different cloth sizes, different hole shapes (star, slot).
- **Technical difficulty:** Medium
- **Why it deserves to be watched:** Cloth doing something cloth rarely does in this niche (flow rather than drape).
- **Engine class:** Supported with small extensions

### 9. Why Every Pile Looks the Same  (`pachinko_bell`)

- **Viewer question:** Why does every pile end up the same bell shape?
- **Initial setup:** A grid of pegs above a row of bins, a funnel feeds balls one by one.
- **What physically happens:** Bullet rigid bodies bounce randomly off pegs (Galton board); the counts per bin form a binomial distribution.
- **Main visual attraction:** A flood of colored balls and a growing curve.
- **Escalation / challenge:** 50, 500, 5,000 balls: the bell becomes clearer each time.
- **Final payoff:** The final pile traces a clean bell, with a ghost curve lined up for comparison.
- **Objects and physics required:** Static pegs, thousands of rigid balls (long bake), bin counting via end positions.
- **Reusability as multiple videos:** Different peg layouts, biased boards (tilted), different bin counts.
- **Technical difficulty:** Medium
- **Why it deserves to be watched:** Chaos becomes order; the payoff is a measurable curve.
- **Engine class:** Supported with small extensions

### 10. How Hard Can the Wind Blow?  (`wind_flag`)

- **Viewer question:** How strong a wind can this flag take?
- **Initial setup:** A flag pinned along one edge to a pole on an empty plain.
- **What physically happens:** A wind force field is ramped; the pinned cloth responds (Blender cloth + force field).
- **Main visual attraction:** Folds ripple like a real flag, with a pole as scale.
- **Escalation / challenge:** Breeze, gale, storm, hurricane; the speed ramps continuously.
- **Final payoff:** At the top end it stands straight out, snapping.
- **Objects and physics required:** Cloth with pin group + wind field (new knobs on the existing cloth builder).
- **Reusability as multiple videos:** Banners, sails, a laundry line, different cloth stiffness.
- **Technical difficulty:** Low-medium
- **Why it deserves to be watched:** Beautiful, instantly understood, and cheap to render.
- **Engine class:** Supported with small extensions

### 11. Do Dice Obey the Odds?  (`dice_hist`)

- **Viewer question:** Do real physics dice follow the probability curve?
- **Initial setup:** A shallow tray under a rain of 1,000 pairs of dice.
- **What physically happens:** Each pair is rolled by Bullet; each die's top face is read from its final orientation, and the sums are tallied.
- **Main visual attraction:** A hail of dice, then bars rise per total.
- **Escalation / challenge:** 100, 1,000, 10,000 rolls: the bars approach the theoretical triangle.
- **Final payoff:** A ghost curve of the expected probabilities is overlaid at the end.
- **Objects and physics required:** Dice mesh with pips, orientation-to-face readout, tray, bars generated from real counts (no fake data).
- **Reusability as multiple videos:** Coins, three dice, loaded dice (one weighted die, real center of mass).
- **Technical difficulty:** Medium-high
- **Why it deserves to be watched:** Probability as a physical act, and 'loaded dice' is a strong sequel.
- **Engine class:** Requires a new physics template

### 12. Marbles Paint a Picture  (`mosaic`)

- **Viewer question:** Can marbles build a picture by themselves?
- **Initial setup:** A tall transparent grid of 20 columns; coloured marbles are fed by colour-coded chutes.
- **What physically happens:** Falling and stacking is simulated; the colour sequence per column is chosen by the artist (stated as such).
- **Main visual attraction:** A clear tank filling into pixel art.
- **Escalation / challenge:** Three pictures of growing complexity.
- **Final payoff:** The finished image appears; the camera pulls back to reveal it.
- **Objects and physics required:** Rigid balls, column walls, colour sequences.
- **Reusability as multiple videos:** Any pixel art, logos (own designs), seasonal images.
- **Technical difficulty:** Medium
- **Why it deserves to be watched:** Pure visual payoff; honest that the picture is scripted, the settling is physics.
- **Engine class:** Supported with small extensions

### 13. One Giant or a Thousand Little  (`seesaw_mass`)

- **Viewer question:** Who wins: one giant ball or a thousand small ones of the same total mass?
- **Initial setup:** A seesaw balanced on a hinge; one big ball on the left, a bin of 1,000 small ones on the right, equal mass.
- **What physically happens:** Hinge constraint + rigid bodies; the seesaw tips by torque only.
- **Main visual attraction:** A giant ball against an avalanche of small ones.
- **Escalation / challenge:** Equal mass but different positions: moving the bin outward changes the winner.
- **Final payoff:** The seesaw settles level or tips depending on distance (the real lesson).
- **Objects and physics required:** Rigid-body hinge constraint (Blender supports it), bin with 1,000 balls.
- **Reusability as multiple videos:** Cats vs elephants (just masses), levers of different lengths.
- **Technical difficulty:** Medium-high
- **Why it deserves to be watched:** A counter-intuitive balance puzzle.
- **Engine class:** Requires a new physics template

### 14. How Big a Ball Breaks the Wall?  (`break_wall`)

- **Viewer question:** How big a ball does it take to break this wall?
- **Initial setup:** A wall of glued bricks (fixed constraints with breaking thresholds) and a row of balls of growing size.
- **What physically happens:** Bullet constraints break when the load exceeds the threshold.
- **Main visual attraction:** A wall bursting into bricks.
- **Escalation / challenge:** Balls of 1x, 2x, 4x, 8x radius at the same speed.
- **Final payoff:** The last ball goes right through.
- **Objects and physics required:** Fixed constraints with breaking threshold between bricks; pre-split wall.
- **Reusability as multiple videos:** Walls of different materials (more or less glue), shapes (arches).
- **Technical difficulty:** Medium-high
- **Why it deserves to be watched:** Destruction with a clear cause and effect.
- **Engine class:** Requires a new physics template

### 15. Bounce Ladder  (`bounce_lanes`)

- **Viewer question:** Which bounciness goes the farthest down the stairs?
- **Initial setup:** Five lanes of identical stairs, balls with restitution 0.2, 0.4, 0.6, 0.8, 0.95.
- **What physically happens:** Bullet restitution differences; stairs are static.
- **Main visual attraction:** Five balls bouncing in different rhythms.
- **Escalation / challenge:** Same drop, five restitution values side by side.
- **Final payoff:** The most bouncy leaves the stairs and flies off the end.
- **Objects and physics required:** Rigid balls, stair meshes, a long thin camera pan.
- **Reusability as multiple videos:** Different slopes, friction ladders, spin.
- **Technical difficulty:** Low
- **Why it deserves to be watched:** Cheap, quickly readable, and loopable.
- **Engine class:** Already supported

### 16. The Endless Flip  (`tumble_loop`)

- **Viewer question:** What happens when the box flips forever?
- **Initial setup:** A glass box half full of coloured balls rotates 180 degrees on a pivot, again and again.
- **What physically happens:** A kinematic rotation of the box; balls fall to the new bottom each time.
- **Main visual attraction:** A river of balls falling the length of the box each cycle.
- **Escalation / challenge:** Rotation speed increases; layers mix.
- **Final payoff:** The state after 180 degrees equals the start (mirrored), so the video loops seamlessly.
- **Objects and physics required:** Kinematic rotation of container (animated collider), 400 balls.
- **Reusability as multiple videos:** Different ball sizes (gives Brazil nut again), baffles inside.
- **Technical difficulty:** Medium
- **Why it deserves to be watched:** A perfect loop made from real physics.
- **Engine class:** Requires a new physics template

### 17. Sorted By Size  (`sieve_sort`)

- **Viewer question:** Can holes sort a mess into three sizes?
- **Initial setup:** A tray of mixed spheres (small, medium, large) over three grates with decreasing holes.
- **What physically happens:** Bullet rigid bodies fall through the hole that fits them, otherwise roll on.
- **Main visual attraction:** A mess becomes three clean piles.
- **Escalation / challenge:** Two grates then three then four sizes.
- **Final payoff:** Neat piles in labelled bins.
- **Objects and physics required:** Static grate meshes, rigid spheres.
- **Reusability as multiple videos:** Different shapes (cubes through slots), mixtures.
- **Technical difficulty:** Low-medium
- **Why it deserves to be watched:** Sorting is calming, and the mechanism is clear.
- **Engine class:** Supported with small extensions

### 18. Why Some Piles Are Steeper  (`repose_piles`)

- **Viewer question:** Why does a pile of cubes stand steeper than a pile of balls?
- **Initial setup:** A funnel pours 800 objects onto a plate: spheres, then cubes, then rods.
- **What physically happens:** Bullet friction and shape decide the angle of repose.
- **Main visual attraction:** Three cones side by side with different slopes.
- **Escalation / challenge:** Same pour, different shapes.
- **Final payoff:** Slopes compared with a ghost reference line.
- **Objects and physics required:** Funnel, plate, three primitives.
- **Reusability as multiple videos:** Add roughness, sticky, wet (more friction).
- **Technical difficulty:** Low-medium
- **Why it deserves to be watched:** A real, visible geometry fact.
- **Engine class:** Supported with small extensions

### 19. Gumball Drum  (`gumball_drum`)

- **Viewer question:** What does a rotating drum do to a thousand balls?
- **Initial setup:** A transparent horizontal drum of balls rotates slowly.
- **What physically happens:** Kinematic rotation and Bullet balls.
- **Main visual attraction:** Waves of balls cascade down the drum wall.
- **Escalation / challenge:** Speed rises: tumbling, cascading, centrifuging.
- **Final payoff:** At high speed the balls stick to the wall.
- **Objects and physics required:** Kinematic drum, ~800 balls.
- **Reusability as multiple videos:** Different fill levels.
- **Technical difficulty:** Medium
- **Why it deserves to be watched:** Meditative and shows regimes of motion.
- **Engine class:** Requires a new physics template

### 20. Cradle Counts  (`newton_cradle`)

- **Viewer question:** Why do exactly as many balls leave as arrive?
- **Initial setup:** A Newton's cradle of five balls on strings.
- **What physically happens:** Constraints; Bullet loses energy so the exact behaviour is difficult.
- **Main visual attraction:** Clicking swing.
- **Escalation / challenge:** 1, 2, 3 balls lifted.
- **Final payoff:** Matching count leaves.
- **Objects and physics required:** Point constraints + near-elastic collisions; risky.
- **Reusability as multiple videos:** Different ball masses.
- **Technical difficulty:** High
- **Why it deserves to be watched:** Iconic, but the solver does not reproduce it reliably; do not fake it.
- **Engine class:** Technically difficult or unsuitable

### 21. The Attractor  (`magnet_swarm`)

- **Viewer question:** What happens when a magnet sweeps over a field of spheres?
- **Initial setup:** A floor of 600 small spheres and a moving attractor above.
- **What physically happens:** Rigid bodies feel a Blender force field (attraction; labelled as a force field, not real magnetism).
- **Main visual attraction:** The spheres rise in chains and clump.
- **Escalation / challenge:** Field strength rises in steps.
- **Final payoff:** Drop the attractor off: the whole mass collapses.
- **Objects and physics required:** Force field animated, baked with rigid bodies.
- **Reusability as multiple videos:** Different spheres sizes, two attractors.
- **Technical difficulty:** Medium
- **Why it deserves to be watched:** Looks like nothing else in the niche.
- **Engine class:** Requires a new physics template

### 22. Cube Tornado  (`tornado`)

- **Viewer question:** How many cubes can a tornado lift?
- **Initial setup:** 500 cubes on a floor, a vortex force field above.
- **What physically happens:** Vortex + wind forces on rigid cubes.
- **Main visual attraction:** A rising spiral of cubes.
- **Escalation / challenge:** Vortex strength grows; cube size grows.
- **Final payoff:** The field switches off and the cubes rain down.
- **Objects and physics required:** Vortex and wind force fields with rigid bodies.
- **Reusability as multiple videos:** Cubes → boards → cars (scale).
- **Technical difficulty:** Medium
- **Why it deserves to be watched:** Dramatic motion that stays physical.
- **Engine class:** Requires a new physics template

### 23. The Bridge Test  (`rope_bridge`)

- **Viewer question:** How much weight can this rope bridge hold?
- **Initial setup:** Planks linked by hinge constraints between two cliffs; a ball rolls across.
- **What physically happens:** Hinge constraints; loads grow.
- **Main visual attraction:** A sagging bridge.
- **Escalation / challenge:** 1, 2, 4, 8 weights.
- **Final payoff:** The bridge fails (or holds) at the last load.
- **Objects and physics required:** Many constraints; moderate.
- **Reusability as multiple videos:** Material variants.
- **Technical difficulty:** Medium-high
- **Why it deserves to be watched:** Weight and failure, classic.
- **Engine class:** Requires a new physics template

### 24. The Machine  (`chain_machine`)

- **Viewer question:** Can a ball set off ten steps in a row?
- **Initial setup:** A ball, a ramp, dominoes, a seesaw, a cup, a second ball...
- **What physically happens:** A sequence of rigid bodies and constraints.
- **Main visual attraction:** Everything happens in one take.
- **Escalation / challenge:** Each step triggers the next.
- **Final payoff:** The last step lands.
- **Objects and physics required:** Many components; precise tuning.
- **Reusability as multiple videos:** Different machines.
- **Technical difficulty:** High
- **Why it deserves to be watched:** Beloved format, but costly to tune.
- **Engine class:** Technically difficult or unsuitable

### 25. The Ball Elevator  (`archimedes`)

- **Viewer question:** Can a spinning screw lift 200 balls?
- **Initial setup:** A transparent tube with a helical screw rotating at its centre.
- **What physically happens:** Kinematic rotating helix, Bullet balls climb.
- **Main visual attraction:** Balls rising in a spiral.
- **Escalation / challenge:** Screw speed doubles each round.
- **Final payoff:** A continuous loop of rising balls.
- **Objects and physics required:** Kinematic helix mesh collision: high solver cost.
- **Reusability as multiple videos:** Different pitches.
- **Technical difficulty:** High
- **Why it deserves to be watched:** Unusual real mechanism.
- **Engine class:** Technically difficult or unsuitable

### 26. Shape Sorter  (`shape_sorter`)

- **Viewer question:** Which shapes fit through which holes?
- **Initial setup:** A plate with a circle, square and triangle hole; shapes fall from above.
- **What physically happens:** Rigid bodies and mesh collision.
- **Main visual attraction:** Shapes tumbling to fit.
- **Escalation / challenge:** More shapes.
- **Final payoff:** Counts per hole.
- **Objects and physics required:** Concave mesh collision plate.
- **Reusability as multiple videos:** Different holes.
- **Technical difficulty:** Medium
- **Why it deserves to be watched:** Familiar toy.
- **Engine class:** Supported with small extensions

### 27. The Squish  (`soft_squeeze`)

- **Viewer question:** Can a soft cube squeeze through a gap smaller than itself?
- **Initial setup:** A soft block is pushed toward a slot.
- **What physically happens:** Blender soft body, pushed by a kinematic piston.
- **Main visual attraction:** Squishing.
- **Escalation / challenge:** Gap narrows.
- **Final payoff:** The cube passes or ruptures.
- **Objects and physics required:** Soft body is not in the engine; tuning risky.
- **Reusability as multiple videos:** Stiffness ladder.
- **Technical difficulty:** High
- **Why it deserves to be watched:** Satisfying, but crowded with softness videos.
- **Engine class:** Technically difficult or unsuitable

### 28. Fill It Up  (`liquid_glass`)

- **Viewer question:** How much liquid fits before it overflows?
- **Initial setup:** A glass fills with simulated liquid.
- **What physically happens:** Blender Mantaflow fluid.
- **Main visual attraction:** Pouring.
- **Escalation / challenge:** Pour rate.
- **Final payoff:** Overflow.
- **Objects and physics required:** Memory-heavy bakes, disk caches, long runtimes.
- **Reusability as multiple videos:** Other liquids.
- **Technical difficulty:** Very high
- **Why it deserves to be watched:** Not suitable for our Kaggle workflow at this stage.
- **Engine class:** Technically difficult or unsuitable

### 29. The Tablecloth Pull  (`tablecloth`)

- **Viewer question:** Can the cloth be pulled out without moving the objects?
- **Initial setup:** A cloth under objects on a table.
- **What physically happens:** Cloth and rigid bodies interact only one way in Blender.
- **Main visual attraction:** Fast pull.
- **Escalation / challenge:** More objects.
- **Final payoff:** Objects stay.
- **Objects and physics required:** Two-way coupling does not exist; faking it breaks the honesty rule.
- **Reusability as multiple videos:** Other cloths.
- **Technical difficulty:** Very high
- **Why it deserves to be watched:** Classic trick, but our physics stack cannot honestly show it.
- **Engine class:** Technically difficult or unsuitable

### 30. The Perfect Break  (`billiard_break`)

- **Viewer question:** Where do 15 balls go after one break?
- **Initial setup:** A triangle of 15 balls on a felt table and one cue ball.
- **What physically happens:** Bullet rigid spheres: one impulse scatters the rack.
- **Main visual attraction:** A burst of colour across a table.
- **Escalation / challenge:** Cue speed 1x/2x/4x; same rack each time.
- **Final payoff:** Slow-motion replay of the scatter with ball trails.
- **Objects and physics required:** Spheres, felt plane, one initial velocity (already supported).
- **Reusability as multiple videos:** Different racks, cue angles.
- **Technical difficulty:** Low
- **Why it deserves to be watched:** Familiar and cheap, but a crowded idea; low originality.
- **Engine class:** Already supported

## 7. Scores and ranking

| Rank | Concept | Cur | Vis | Pay | Orig | Feas | Reuse | Cost | Total | Engine class |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | The Great Roll-Off | 5 | 4 | 5 | 4 | 5 | 5 | 4 | **4.6** | Supported with small extensions |
| 2 | What's Under the Sheet? | 5 | 4 | 5 | 5 | 4 | 5 | 4 | **4.6** | Supported with small extensions |
| 3 | Is the Jar Full? | 5 | 4 | 5 | 4 | 5 | 4 | 3 | **4.45** | Supported with small extensions |
| 4 | Each One 1.5x Bigger | 5 | 4 | 5 | 3 | 5 | 4 | 4 | **4.35** | Supported with small extensions |
| 5 | The Giant Always Rises | 5 | 4 | 5 | 5 | 4 | 3 | 3 | **4.35** | Requires a new physics template |
| 6 | Fifteen Pendulums, One Pattern | 4 | 5 | 5 | 3 | 4 | 4 | 5 | **4.25** | Requires a new physics template |
| 7 | Which Tower Survives? | 5 | 4 | 5 | 4 | 3 | 4 | 3 | **4.15** | Requires a new physics template |
| 8 | Through the Eye of the Needle | 4 | 5 | 4 | 5 | 3 | 4 | 3 | **4.15** | Supported with small extensions |
| 9 | Why Every Pile Looks the Same | 4 | 4 | 4 | 3 | 5 | 5 | 4 | **4.1** | Supported with small extensions |
| 10 | How Hard Can the Wind Blow? | 3 | 5 | 4 | 4 | 4 | 5 | 4 | **4.1** | Supported with small extensions |
| 11 | Do Dice Obey the Odds? | 5 | 3 | 5 | 5 | 3 | 4 | 3 | **4.1** | Requires a new physics template |
| 12 | Marbles Paint a Picture | 3 | 5 | 5 | 4 | 4 | 4 | 3 | **4.1** | Supported with small extensions |
| 13 | One Giant or a Thousand Little | 5 | 3 | 5 | 5 | 3 | 3 | 3 | **4.0** | Requires a new physics template |
| 14 | How Big a Ball Breaks the Wall? | 4 | 5 | 5 | 3 | 3 | 4 | 3 | **4.0** | Requires a new physics template |
| 15 | The Endless Flip | 3 | 5 | 4 | 4 | 4 | 4 | 3 | **3.95** | Requires a new physics template |
| 16 | Bounce Ladder | 4 | 3 | 4 | 3 | 5 | 5 | 5 | **3.95** | Already supported |
| 17 | The Attractor | 4 | 5 | 4 | 4 | 3 | 3 | 3 | **3.9** | Requires a new physics template |
| 18 | The Ball Elevator | 4 | 4 | 4 | 5 | 3 | 3 | 3 | **3.85** | Technically difficult or unsuitable |
| 19 | Sorted By Size | 3 | 4 | 4 | 3 | 5 | 4 | 4 | **3.8** | Supported with small extensions |
| 20 | Why Some Piles Are Steeper | 3 | 4 | 3 | 4 | 5 | 4 | 4 | **3.8** | Supported with small extensions |
| 21 | Cube Tornado | 4 | 5 | 4 | 3 | 3 | 3 | 3 | **3.75** | Requires a new physics template |
| 22 | The Perfect Break | 3 | 4 | 4 | 2 | 5 | 4 | 5 | **3.7** | Already supported |
| 23 | The Machine | 4 | 5 | 5 | 3 | 2 | 3 | 2 | **3.7** | Technically difficult or unsuitable |
| 24 | Shape Sorter | 4 | 3 | 4 | 4 | 3 | 4 | 3 | **3.6** | Supported with small extensions |
| 25 | The Squish | 4 | 4 | 4 | 4 | 2 | 3 | 2 | **3.5** | Technically difficult or unsuitable |
| 26 | The Bridge Test | 4 | 3 | 4 | 3 | 3 | 4 | 3 | **3.45** | Requires a new physics template |
| 27 | Gumball Drum | 3 | 4 | 3 | 3 | 4 | 3 | 3 | **3.35** | Requires a new physics template |
| 28 | The Tablecloth Pull | 4 | 4 | 5 | 3 | 1 | 2 | 2 | **3.25** | Technically difficult or unsuitable |
| 29 | Fill It Up | 3 | 5 | 4 | 2 | 1 | 3 | 1 | **3.0** | Technically difficult or unsuitable |
| 30 | Cradle Counts | 3 | 4 | 4 | 2 | 2 | 2 | 3 | **2.95** | Technically difficult or unsuitable |

Ties: ranks 1 and 2 (4.6), ranks 9 to 12 (4.1). `dice_hist` and `mosaic` tie the top ten at 4.1 and are the next picks.

## 8. Top ten storyboards

Timestamps are targets; each storyboard has real scene changes rather than five equal stages.

### 1. The Great Roll-Off (4.6)

| Time (s) | Scene |
|---|---|
| 0.0-1.5 | Top-down-tilted close shot of six shapes lined up at a gate; hook text: 'Which one wins?' |
| 1.5-6 | Gate drops, camera follows the pack down the ramp; shapes spread out. |
| 6-8 | Cut to a side-on slow-motion pass at the bumpy section; one shape tumbles off. |
| 8-14 | Round 2 on a steeper ramp, same lineup, camera wider; order shuffles. |
| 14-19 | Round 3: ramp ends in a cliff; camera drops to the floor and tracks landings. |
| 19-23 | Finish-line slow motion; winner stays in frame, the others fade to grey; last frame matches the gate opening for the loop. |

### 2. What's Under the Sheet? (4.6)

| Time (s) | Scene |
|---|---|
| 0.0-2 | Bare studio floor, a big sheet hangs in frame. Hook: 'What's under it?' |
| 2-6 | Sheet falls and drapes over a hidden stack; silhouette appears. |
| 6-9 | Slow orbit; ghost-shaded outline of the true shape fades in beside it. |
| 9-15 | Sheet 2 drapes over a harder shape; camera pulls back. |
| 15-21 | Sheet 3 drapes over a deliberately misleading arrangement; folds hide a wide gap. |
| 21-24 | Sheets lift away in reverse so the first frame returns for the loop. |

### 3. Is the Jar Full? (4.45)

| Time (s) | Scene |
|---|---|
| 0-2 | Empty tall jar, hook 'Is it full?' |
| 2-7 | Large rocks pour in until one touches the rim. |
| 7-9 | Beat: hold on the 'full' jar. |
| 9-15 | Medium pebbles pour; they sink into gaps, level barely rises. |
| 15-21 | Fine beads pour; the level creeps up a sliver. |
| 21-24 | Slow push-in on the settled surface; jar shape matches the first frame. |

### 4. Each One 1.5x Bigger (4.35)

| Time (s) | Scene |
|---|---|
| 0-2 | Thumb-sized domino next to a coin for scale, hook 'How big can the last one be?' |
| 2-7 | Chain starts; camera dollies back as each domino grows 1.5x. |
| 7-14 | Mid-chain, dominoes the size of doors; camera lifts to a high angle. |
| 14-20 | Last giants fall in slow motion with a heavy thud. |
| 20-23 | Wide shot of the whole fallen line from thumb to tower. |

### 5. The Giant Always Rises (4.35)

| Time (s) | Scene |
|---|---|
| 0-2 | Glass tank full of grey balls with a red ball visible at the bottom; hook 'Can it climb out?' |
| 2-8 | Gentle shaking; the red ball inches up. |
| 8-15 | Stronger shaking; the red ball rises faster. |
| 15-20 | The red ball surfaces. |
| 20-23 | Shaking stops; hold on the red ball on top. |

### 6. Fifteen Pendulums, One Pattern (4.25)

| Time (s) | Scene |
|---|---|
| 0-2 | Fifteen pendulums at rest in a line, hook 'Will they line up again?' |
| 2-10 | Release; wave patterns form. |
| 10-17 | Chaos and split patterns. |
| 17-23 | Realign; the end pose equals the start pose (loop). |

### 7. Which Tower Survives? (4.15)

| Time (s) | Scene |
|---|---|
| 0-2 | Four towers on one platform, hook 'Which survives?' |
| 2-8 | Level 1 shaking; the zig-zag tower collapses. |
| 8-14 | Level 2; the column collapses. |
| 14-20 | Level 3; the arch falls. |
| 20-24 | Pyramid stands alone; slow push-in. |

### 8. Through the Eye of the Needle (4.15)

| Time (s) | Scene |
|---|---|
| 0-2 | Large sheet hovering over a small ring; hook 'Will it fit?' |
| 2-8 | Wide ring: sheet slides through easily. |
| 8-14 | Medium ring: the sheet bunches. |
| 14-21 | Tiny ring: folds jam, then slowly feed through. |
| 21-24 | The last corner drops through; the sheet lies flat below. |

### 9. Why Every Pile Looks the Same (4.1)

| Time (s) | Scene |
|---|---|
| 0-2 | Peg field above empty bins, hook 'Where do they land?' |
| 2-8 | 50 balls fall; uneven piles. |
| 8-15 | 500 balls; the piles take a hump shape. |
| 15-22 | 5,000 balls; a smooth bell. |
| 22-24 | A ghost curve overlays the pile for a beat. |

### 10. How Hard Can the Wind Blow? (4.1)

| Time (s) | Scene |
|---|---|
| 0-2 | Flag hanging limp, hook 'How much wind?' |
| 2-8 | Breeze: gentle ripple. |
| 8-14 | Gale: strong waves. |
| 14-20 | Storm: the flag snaps taut. |
| 20-24 | The wind drops; the flag falls limp (loop). |

## 9. Technical feasibility against the repository

Engine facts (inspected, not changed): registry-driven templates (`cloth_drape`, `multiple_balls`, `ball_funnel`, `ring_toss`, `cloth_objects`); Bullet rigid bodies baked to keyframes; cloth bake against static colliders only; no constraints/hinges, no kinematic animated colliders, no force fields, no soft body, no fluids. `PLANNED_EXPERIMENTS` lists `softbody_collision`.

| Class | Concepts |
|---|---|
| Already supported | bounce_lanes, billiard_break |
| Supported with small extensions | shape_race, sheet_reveal, jar_rocks, domino_giants, cloth_ring, pachinko_bell, wind_flag (needs a wind force field on cloth, small), mosaic, sieve_sort, repose_piles, shape_sorter |
| Requires a new physics template | brazil_nut, pendulum_wave, earthquake, dice_hist, seesaw_mass, break_wall, tumble_loop, gumball_drum, magnet_swarm, tornado, rope_bridge |
| Technically difficult or unsuitable | newton_cradle, chain_machine, archimedes, soft_squeeze, liquid_glass, tablecloth |

Reusable components that unlock the most concepts:
1. **Parametric ramp / lane track** (shape_race, bounce_lanes, domino path): small.
2. **Kinematic animated collider** (earthquake, brazil_nut, tumble_loop, gumball_drum): one component, four concepts. This is the best new-template investment.
3. **Force fields** (wind_flag, tornado, magnet_swarm): Blender has them; need bake integration.
4. **Rigid-body constraints** (seesaw, rope bridge, break_wall): Blender supports hinge and breakable fixed constraints.

Do not fake: tablecloth pull needs two-way cloth-rigid coupling we do not have; Newton's cradle needs near-elastic solver behaviour Bullet does not reliably give; chain machines are tuning-heavy. Rated unsuitable for now rather than faked.

## 10. Recommended next experiments

1. Prototype the three concepts in section 11 with 1 to 2 videos each at low resolution; check each against the 12-dimension table before any batch.
2. Add one reusable component (kinematic collider) only after the first three are judged.
3. Before any of this, supply 20 to 30 competitor video URLs so sections 2 to 4 can be redone from observation.
4. Add a plain sound design pass (impact variety, a slow-motion whoosh) since sound looked central in the sources I could see.

## 11. First three to implement

1. **The Great Roll-Off** (`shape_race`): needs only a ramp/lane builder on existing rigid-body code; strongest viewer question; reusable for many shape sets.
2. **What's Under the Sheet?** (`sheet_reveal`): reuses `cloth_objects`; most original of the cheap options; cloth is already our most distinctive visual.
3. **Is the Jar Full?** (`jar_rocks`): needs a container and a three-size pour, both small; real packing physics with a clear wrong guess.

## 12. Sources

- https://www.creativebloq.com/3d/theres-nothing-more-mesmerising-than-a-jelly-cube-being-prodded
- https://80.lv/articles/weirdly-satisfying-blender-animation-of-soft-golden-cube-getting-crushed
- https://www.inkl.com/news/there-s-nothing-more-mesmerising-than-a-jelly-cube-being-prodded
- https://bazaar.blendernation.com/listing/super-satisfying-physics-loop-made-in-blender/
- https://web.kartcsainz.com/physics-simulation.html
- https://sales.communityimpact.com/the-most-satisfying-simulations-of-2025-3d-physics-showcase.html
- https://sales.communityimpact.com/next-level-3d-blender-physics-showcase-9-minutes-of-pure-satisfaction.html
- https://nyc1.lr.ggtyler.dev/r/simulated
- https://lr.us.psf.lt/r/Simulated/new
- https://www.patreon.com/posts/65716919
- https://rosetta.to/u/twominutepapers/this-isn-t-ai-it-s-even-wilder-squishy-physics-that-learn-to-move
- https://www.tubefilter.com/?p=158090

The five channel URLs given in the brief were attempted and are listed here for completeness: https://www.youtube.com/@rollingqub, https://www.youtube.com/@3d4func4d, https://www.youtube.com/@blopblop-yt, https://www.youtube.com/@ShortForm3D, https://www.youtube.com/@KineticGarden. No data was retrieved from any of them.

## 13. Limitations (summary)

No playback; no verified views or durations for the named channels; fewer than 20 videos identified; patterns are hypotheses; concept scores are my judgment; feasibility is from reading the repo, not from prototyping.

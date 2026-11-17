# Prototype report, round 2 (redesigned)

Kaggle run 44079728141 (commit 9d1bd82+, 720p GPU). All three rendered and passed QC (720x1280 h264+aac).
Durations: jar_packing 19.5 s, roll_off 16.5 s, sheet_reveal 17.5 s.

Visual review is of 18 evenly spaced frames per final MP4 (contact sheets printed by the workflow's review mode,
run 44093358669). Audio was checked from the audio timeline and QC only; it was not listened to.

| | hook | curiosity | visual | physics | originality | escalation | payoff | replay | total /10 |
|---|---|---|---|---|---|---|---|---|---|
| Jar packing | 7 | 8 | 8 | 8 | 7 | 8 | 7 | 7 | 7.5 |
| Hidden movement cloth | 8 | 8 | 7 | 6 | 8 | 7 | 6 | 6 | 6.5 |
| Roll-off | 5 | 4 | 7 | 5 | 5 | 4 | 6 | 4 | 5 |

Jar: clear jar, large blue rocks look full, orange, yellow and tiny white stones sink into the gaps, "406 MORE FIT INSIDE",
final close-up. Weak: the last close-up is a soft macro of a few rocks and shows little packing; tiny stones sit on top and clutter the rim.
Cloth: moving bulges under the pink cloth are a real mystery; reveal "3 BALLS AND A CUBE!". Weak: one frame early on is a flat pink
camera glitch; the reveal is abrupt; revealed objects are small; the jagged "tentacle" edges look like cloth artefacts.
Roll-off: studio look is good and the winner close-up is attractive. Weak: cone, cube and prism stall near the top for most of the run so the
middle is nearly static; only sphere, can and ring really race; title text overlaps the bright ramp.

# Jar Packing, final video (round 3)

- Final video: GitHub Actions run 44119753841, artifact `kaggle-baseline-44119753841`, `result/proto_jar_packing/proto_jar_packing.mp4`
  (Kaggle Tesla T4, commit a2ade78). Not committed to git. Metadata and YouTube text: `docs/youtube/jar_packing_001.json`.
- 19.5 s, 720x1280, 30 fps, h264 + aac (audio duration equals video duration), QC passed.
- What changed: the jar is tapped after every pour (kinematic jar bottom/wall hops, real rigid-body settling), so stones sink into
  gaps instead of piling on the rim (stones above the rim: 0; fill level falls 2.16 -> 1.8 m as the pile compacts); an invisible
  guard collar above the rim; tiny stones are teal; steadier final shot; first rock released at 0.5 s (`lead_in`).
- Inspected frames of the real MP4 (18 across the video, plus the first 2.4 s and the last 4 s). Audio was not listened to; only
  the audio stream and QC were checked.
- Scores: hook 7, visual 8, physics 8, creativity 7, progression 8, payoff 7, audio 7 (unchecked by ear), replayability 7; overall 7.4.
  That is below the 8 target.
- Known limitations: in the last shot the medium orange stones hide most of the large blue rocks behind the glass; teal/yellow
  stones form a layer on the top of the orange mound (inside the jar, not above the rim) as well as filling gaps lower down;
  the first ~0.8 s is mostly an empty jar before the first rock enters the frame.
- Tests: 478 passed / 35 skipped without bpy; with real Blender (bpy) 512 passed, 1 skipped.

# Creative prototype report (roll_off, sheet_reveal, jar_packing)

Kaggle run 43859343410 (commit 42debee, 720p, GPU): all three rendered, QC passed, 720x1280 h264 + aac.
Durations: roll_off 14.0 s, sheet_reveal 10.0 s, jar_packing 13.5 s.

**Review limitation:** the 720p mp4s sit in a GitHub artifact whose storage host is blocked for the sandbox shell, and
folder access for a browser download was denied. The visual review below is therefore of real rendered frames of the same
scenes at 360x640 / low samples (local Blender), plus QC/ffprobe/audio-timeline data from the real 720p run. It is not a
review of the final 720p files.

| | Q | first 3 s | action | progression | payoff | different | muted | final | score |
|---|---|---|---|---|---|---|---|---|---|
| Roll-off | 2 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 7.5 |
| Sheet | 2 | 1 | 1 | 1 | 2 | 2 | 1 | 2 | 7 |
| Jar | 2 | 2 | 2 | 2 | 1 | 2 | 1 | 1 | 7.5 |
(approximate; each criterion 0-1.25 weighted by judgement)

Physics: roll_off heat 1 (14 deg) sphere wins, can 3.5 frames behind, cube/prism last, nothing fails to finish; heat 2 on
a frictionless ramp is an exact dead heat ("ALL TIE!"). Sheet: sheet drapes, silhouette reads as a ghost, dissolves top-down
to a snowman. Jar: no stone outside the jar, level stays at the rim while medium/small/tiny stones fill the gaps.

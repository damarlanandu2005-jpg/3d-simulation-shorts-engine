# Third-party components

**No third-party source code or assets are copied into this repository.** Everything under
`shorts_engine/` was written for this project. This file must be updated whenever that changes
(record the source URL, license, and which files incorporate it).

## Runtime dependencies (installed by the user, not redistributed here)

| Component | Used for | License |
| --- | --- | --- |
| Blender 4.5 LTS (or the `bpy` PyPI module) | scene creation, cloth physics, rendering | GPL-3.0-or-later |
| FFmpeg (system binary) | encoding and joining clips | LGPL/GPL depending on build |
| NumPy | dependency of `bpy` | BSD-3-Clause |
| pytest | tests only | MIT |

Because Blender is GPL, any `.blend` *scripts* that import `bpy` are normally treated as Blender
add-on/script code. This repository is therefore best kept GPL-compatible. **The repository owner has
not chosen a license for this project yet: add a `LICENSE` file before sharing it publicly.**

## Projects reviewed but NOT incorporated

These were evaluated during planning. Nothing from them was copied. Entries marked "reference only"
may be read for ideas; any future copy must be added to the table above first.

| Project | License | Decision |
| --- | --- | --- |
| [ClothDrop-Reborn](https://github.com/hartface/ClothDrop-Reborn) | GPL-3.0-or-later | reference only |
| [clothcode](https://github.com/Aeturnis-Development-Labs-LLC/clothcode) | MIT | reference only (targets Blender 5.2) |
| [blender-headless-render](https://github.com/bardia-ardakanian/blender-headless-render) | MIT | reference only |
| [Modeling-Cloth](https://github.com/the3dadvantage/Modeling-Cloth) | MIT | not used |
| [BlenderPython_Animations](https://github.com/ugurcansonm/BlenderPython_Animations) | **none listed** | **do not copy** (no license = all rights reserved) |
| [Smoothie](https://github.com/danromik/smoothie) | GPL-3.0-or-later | not used (needs Claude subscription/API key) |
| [RFX-Blender-Asset-Library](https://github.com/Pixelguru26/RFX-Blender-Asset-Library) | CC0-1.0 | not used |

## Reference videos

Other creators' videos were watched only to understand the general format (vertical, short,
increasing mesh resolution with labels). No footage, scenes, assets, titles or branding are reused.
Each video this engine makes should use its own concept and parameters.

Blender Minecraft JSON Import/Export
=======================================
Fork of [phonon's add-on](https://github.com/phonon/blender-minecraft-json), tested with **Blender 5.2.3 LTS**. Import, edit and export cuboid Minecraft models using modern XYZ element rotations, including Horizon / Lunatic models.

The default **Modern 26.3 / Horizon** exporter preserves actual object transforms, existing image texture identifiers, edited UVs, omitted faces, display transforms, and imported model metadata. It does not snap rotations or automatically resize the model. The older exporter remains available explicitly as **Legacy Java / generated colors**.

Modern editing
---------------------------------------
1. Use **File > Import > Minecraft (.json)** and choose the model inside its resource pack's `assets/<namespace>/models/` directory. Textures are resolved from the corresponding `assets/<namespace>/textures/` directory. Recoverable bare texture names from Blockbench exports are repaired when the matching local image exists.
2. The imported cuboids are selected. Rotate them in **Object Mode**; edit UVs in Blender's UV editor. Leave each cuboid as a separate mesh object. One Blender unit equals one JSON model unit (1/16 block).
3. Use **File > Export > Minecraft (.json)**. Leave **Model Format: Modern 26.3 / Horizon** and **Selection Only** enabled. Export into the original resource pack's models directory (or a copy with the same `assets` layout).
4. Save texture painting separately to the existing PNG; JSON export writes geometry, UV coordinates and texture references, not image pixels. Save a `.blend` to retain imported model metadata between sessions.

For a half-turn of the entire centered gourd around its vertical axis, set the transform pivot to **3D Cursor**, leave the cursor at `(0,0,0)`, and use **R, Z, 180** in Object Mode. Imported cuboids can retain their original authored rotation pivots, so Median Point may rotate the selection around a different point.

Modern export supports arbitrary XYZ object rotations, positive object scale and rectangular face UVs, including mirrored rectangles and 90-degree UV rotations. It reports an error for unsupported meshes, modifiers, shear or nonrectangular UVs before replacing an existing output. Apply negative scale and recalculate normals before export. A cube must retain its eight cuboid vertices; faces omitted in the JSON remain omitted. Multiple imported models must be exported separately.

**Modern XYZ output targets modern 26.3 models and Horizon.** Use the legacy exporter for consumers that require the old single `axis` / `angle` rotation schema; its restrictions and options are documented below.


Installation
---------------------------------------
1. Clone or copy the add-on into a package directory named `blender_minecraft_json` inside Blender's `scripts/addons` folder. On Linux for Blender 5.2, this is `~/.config/blender/5.2/scripts/addons/blender_minecraft_json/`. That directory must contain this repository's `__init__.py`, `io_scene_minecraft_json/`, and `minecraft_utils/`.
2. Enable in **Edit > Preferences > Add-ons** (search for *Minecraft JSON Import/Export*)


Legacy Export Guide
---------------------------------------
- **Only exports cuboid objects** e.g. Object meshes must be rectangular prisms (8 vertices and 6 faces). The local mesh coordinates must be aligned to global XYZ axis. **Do not rotate the mesh vertices in edit mode.**
- **All cuboids must be separate objects.**
- **Apply rotations at the Object level (outside of mesh edit).** Only one axis can have a **net rotation** with 5 possible degree values: [-45, -22.5, 0, 22.5, 45]. What **net rotation** means is that the object can have any multiple of 90 deg rotations on any axis (because the object is still a cuboid), but only one axis can have a further rotation of values listed. Objects with invalid rotations will be rounded to their closest valid rotation. Examples of valid/invalid rotations:

|x   | y   | z  |       |
|----|---- |----|------ |
|0   |22.5 |0   | valid |
|90  |270  |45  | valid |
|90  |270  |135 | valid |
|45  |135  |0   | invalid (two net rotations) |
|30  |0    |0   | invalid (value not allowed) |

- **Apply all scale to objects before exporting.** Use `ctrl + A` to bring up Apply menu then hit `Apply > Scale`. (Also found in `Object > Apply > Scale` tab in viewport)
- **Recalculate normals if textures are on wrong faces.** Applying negative scales can sometimes flip face normals inside, which causes incorrect auto-generated texture colors. Recalculate normals on all meshes to fix (`Select All` > `Edit Mode` > `Select All` > `ctrl + shift + N` to recalculate and **uncheck inside**).

Example `.blend` files and generated `.json` models are in **examples** folder.


Legacy Export Options
---------------------------------------
|  Option  |  Default   | Description  |
|----------|------------|------------- |
| Selection Only | True | If True, export only selected objects|
| Recenter Coordinates | True | Recenters Blender origin `(0,0,0)` to Minecraft origin `(8,8,8)`|
| Rescale to Max | True | Rescale exported model so the largest axis fits the 48x48x48 Minecraft model volume.
| Recenter Model to Origin | True | Recenter model so its center is at the origin.
| Texture Subfolder | "item" | Subfolder for model texture path: `assets/minecraft/textures/[subfolder]` |
| Texture Name | | Name of texture generated `[name].png` (blank defaults to `.json` filename) |
| Export UVs | True | Exports face UVs |
| Generate Color Texture | True | Auto-textures solid material colors and generates a `.png` image texture exported alongside model (overwrites UVs). By default will get colors from all materials in the Blender file. |
| Only Use Exported Object Colors | False | When exporting auto-generated color texture, only use materials colors on exported objects (instead of all materials in file). |
| Minify .json | False | Enable options to reduce .json file size |
| Decimal Precision | 8 | Number of digits after decimal point in output .json (-1 to disable) |
| Export Bones | False | Export model in chunks by associated bones (experimental) |
| Export Animations | False | Export bone animations into a separate .json file (see docs, experimental) |


Import Options
---------------------------------------
|  Option  |  Default   | Description  |
|----------|------------|------------- |
| Import UVs | True | Import face UVs |
| Translate by (-8, -8, -8) | False | Fixed `(-8,-8,-8)` translation to convert from Minecraft `[-16,32]` space |
| Recenter to Origin | True | Centers model on Blender world origin (overrides translate option) |


Legacy Minecraft Geometry Restrictions Overview
---------------------------------------
Detailed overview: https://minecraft.gamepedia.com/Model
- Uses a Y-up coordinate system (Blender uses Z-up, exporter handles the conversion).
- Coordinates must be from [-16, 32]
- Single axis rotations with 5 possible values: [-45, -22.5, 0, 22.5, 45]
- Minecraft UV axis is top-left (0, 0) to bottom-right (16, 16) while Blender is bottom-left (0, 0) to top-right (1, 1)  
- Each face UVs specified as in format [xmin, ymin, xmax, ymax] where each value in range [0, 16]

Validation
---------------------------------------
Tests run inside Blender, without changing user preferences or startup files:

```sh
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tests/test_rotations.py
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tests/test_resources.py
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tests/test_workflow.py
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tests/test_roundtrip.py
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tests/test_uvs.py
```

Set `MC_JSON_MODEL=/absolute/path/to/ibuki_gourd_3d.json` for the last two commands to additionally verify the real local gourd. Test outputs use temporary directories; the source JSON, texture and `.blend` files are never overwritten. Coverage includes world-space cuboid geometry, a 180-degree turn, compound rotations, UV orientation and edits, namespace repair, sparse faces, display/group metadata, safe export failure and saved `.blend` persistence. Game assets are not included in this repository.

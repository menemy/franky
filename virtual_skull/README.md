# Virtual Skull - 3D Animated Skull for Franky

This module provides a realistic 3D skull with animated jaw and glowing eyes, synchronized with Franky's speech via MQTT.

## Features

- Realistic 3D skull model (CC0/CC-BY licensed)
- Animated lower jaw (mandible) with 60° max rotation
- Glowing red eyes that brighten when speaking
- MQTT integration for real-time synchronization
- Smooth animations at 60 FPS

## Quick Start

```bash
cd virtual_skull
./run_simple.sh
```

This will open a 3D viewer with the skull and red glowing eyes!

## Setup

### 1. Install Dependencies

**IMPORTANT:** Use pyglet 1.5.x (not 2.x) for compatibility:

```bash
pip3 install trimesh "pyglet<2" numpy paho-mqtt
```

### 2. Model Status

✅ **The skull model is already processed and ready to use!**

The repository includes `models/skull_separated.glb` (1.5 MB) with:
- **Cranium** - Upper skull (34.6K vertices)
- **Mandible** - Lower jaw (3.3K vertices)
- **Red glowing eyes** - Two spheres with emission material (symmetric)
- **Properly separated** - Cranium and mandible are separate objects for jaw animation

**No Blender processing needed** - just run the viewer!

### 3. Optional: Process Your Own Model

**Open Blender and import the skull:**

1. File → Import → glTF 2.0 (.glb)
2. Select `skull_original.glb`

**Separate the mandible (lower jaw):**

1. Enter Edit Mode (Tab)
2. Select all vertices of the lower jaw (mandible)
   - Use Box Select (B) or Lasso Select (Ctrl+Left Click)
   - Typically: everything below the temporal-mandibular joint
3. Press P → Selection (separate by selection)
4. Rename objects:
   - Upper part → "UpperJaw"
   - Lower part → "LowerJaw"

**Set rotation pivot for LowerJaw:**

1. Select LowerJaw object
2. Set 3D Cursor to joint position:
   - Switch to Edit Mode
   - Select vertices at the hinge point (temporal-mandibular joint)
   - Shift+S → Cursor to Selected
3. Switch to Object Mode
4. Object → Set Origin → Origin to 3D Cursor

**Export as .glb:**

1. Select both UpperJaw and LowerJaw (Shift+Click)
2. File → Export → glTF 2.0 (.glb)
3. Settings:
   - Format: glTF Binary (.glb)
   - Include: Selected Objects
   - Transform: +Y Up
4. Save as `virtual_skull/models/skull_separated.glb`

### 4. Add Eye Glow Materials (Optional)

For better eye glow effect:

1. In Blender, create two small spheres for eyes
2. Position them in eye sockets
3. Add Emission material with bright red color
4. Export together with skull

## Directory Structure

```
virtual_skull/
├── README.md                    # This file
├── skull_viewer.py              # 3D skull viewer with modern OpenGL shaders
├── run_simple.sh                # Quick launcher
├── requirements.txt             # Python dependencies
└── models/
    ├── skull_separated.glb      # Processed model with jaw animation (ready to use)
    └── the_skull_complex.glb    # Alternative complex model

../experiments/                  # Legacy experimental code (moved to root)
```

## Usage

### Run the Skull Viewer

```bash
cd virtual_skull
./run_simple.sh
```

Features:
- ✅ Full 3D skull rendering with modern OpenGL shaders
- ✅ Animated jaw (60° rotation)
- ✅ MQTT sync with Franky
- ✅ No auto-rotation (static camera view)

The viewer will:
- Connect to MQTT broker at localhost:1883
- Listen for jaw position on `franky/jaw` topic (0.0-1.0)
- Listen for speaking status on `franky/speaking` topic
- Animate jaw with 60° max rotation (if separated)
- Glow eyes red when speaking

### Integration with Franky

The skull viewer runs as a separate process and receives jaw position via MQTT from `franky.py`:

```python
# In franky.py, jaw position is published:
mqtt_client.publish("franky/jaw", jaw_position)
mqtt_client.publish("franky/speaking", "1" if speaking else "0")
```

## Jaw Animation Details

- **Max rotation:** 60° (more expressive than 30°)
- **Hinge point:** Temporal-mandibular joint
- **Rotation axis:** X-axis (pitch)
- **Smoothing:** Direct sync with audio (no interpolation)

## Eye Glow Effect

- **Idle:** Dark red (RGB: 0.3, 0.0, 0.0)
- **Speaking:** Bright red (RGB: 1.0, 0.0, 0.0)
- **Implementation:** Emissive material or simple spheres

## License & Attribution

**3D Skull Model:**
- Model: "CT Derived Human Skeleton" from Sketchfab
- Author: https://sketchfab.com/3d-models/ct-derived-human-skeleton-7235c83248574ce986dd9e8b35159afa
- License: CC Attribution (CC-BY 4.0)
- Modifications: Extracted cranium and mandible, added red emission eyes

**Code:**
- Same as Franky project license

## Troubleshooting

**Model not loading:**
- Check file path: `models/skull_separated.glb`
- Verify .glb format (not .gltf or .obj)
- Try re-exporting from Blender

**Jaw not rotating correctly:**
- Verify pivot point is set to hinge in Blender
- Check mesh naming: must be "LowerJaw" or "Mandible"

**Eyes not glowing:**
- Check MQTT connection: `franky/speaking` topic
- Verify emission material in model

## Technical Details

The skull viewer uses modern OpenGL 3.3 Core Profile with:
- GLSL 330 vertex and fragment shaders
- Phong lighting model (ambient + diffuse + specular)
- VAO/VBO/EBO architecture for efficient mesh rendering
- Real-time jaw animation synchronized via MQTT
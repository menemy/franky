# Blender Guide: Separating Skull Jaw

This guide shows how to manually separate the skull's mandible (lower jaw) for animation.

## Prerequisites

- Blender 3.0+ installed
- `models/skull_original.glb` file

## Method 1: Manual Separation (Recommended)

### Step 1: Import Model

1. Open Blender
2. Delete default cube (X → Delete)
3. File → Import → glTF 2.0 (.glb)
4. Navigate to `virtual_skull/models/skull_original.glb`
5. Click "Import glTF 2.0"

### Step 2: Inspect the Model

1. Select the skull object in the outliner
2. Press `Numpad 0` to view from camera
3. Press `Numpad 7` for top view
4. Press `Numpad 1` for front view
5. Use mouse wheel to zoom

**Identify the temporal-mandibular joint (TMJ):**
- The hinge point where the mandible connects to the skull
- Located approximately at ear level
- Usually marked by a condyle on the mandible

### Step 3: Enter Edit Mode

1. Select the skull object
2. Press `Tab` to enter Edit Mode
3. Press `Z` → Wireframe (to see through the model)
4. Press `3` to switch to Face selection mode

### Step 4: Select Lower Jaw

**Option A: Box Select**
1. Press `B` for Box Select
2. Click and drag to select all faces of the lower jaw
3. Be careful not to select upper jaw faces
4. Use `Middle Mouse Button` while selecting to deselect

**Option B: Select Linked (Faster)**
1. Right-click on any face of the lower jaw
2. Press `L` to select all linked faces
3. This works if the jaw is already separated geometrically

**Option C: Manual Selection**
1. Hold `Shift` and click individual faces
2. Rotate view with `Middle Mouse Button` to see all angles
3. Select all faces that belong to the mandible

### Step 5: Verify Selection

1. Press `H` to hide selected faces
2. Check that only the lower jaw is hidden
3. Press `Alt+H` to unhide all

**Anatomical landmarks of the mandible:**
- Lower teeth and alveolar process
- Body of the mandible (chin area)
- Ramus (vertical posterior part)
- Condylar process (articulates with skull)
- Coronoid process (muscle attachment)

### Step 6: Separate the Jaw

1. With lower jaw faces selected
2. Press `P` → Selection
3. This creates a separate object
4. Press `Tab` to return to Object Mode

You should now see two objects in the outliner.

### Step 7: Rename Objects

1. In the Outliner (top-right panel)
2. Double-click the first object → rename to "UpperJaw"
3. Double-click the second object → rename to "LowerJaw"

### Step 8: Set Pivot Point for LowerJaw

1. Press `Numpad 1` for front view
2. Select LowerJaw object
3. Press `Tab` to enter Edit Mode
4. Press `Alt+A` to deselect all
5. Press `Z` → Wireframe

**Locate the condyle (hinge point):**
6. Find the rounded condylar process on each side
7. Select the vertices at the center of rotation
8. Press `Shift+S` → Cursor to Selected

9. Press `Tab` to return to Object Mode
10. Right-click LowerJaw → Set Origin → Origin to 3D Cursor

### Step 9: Test Rotation

1. Select LowerJaw
2. Press `R` → `X` → type `30` → Enter
3. The jaw should rotate around the hinge point
4. Press `Ctrl+Z` to undo rotation

### Step 10: Export

1. Select both UpperJaw and LowerJaw (Shift+Click)
2. File → Export → glTF 2.0 (.glb)
3. Settings:
   - Format: **glTF Binary (.glb)**
   - Include: **Selected Objects** ✓
   - Transform: **+Y Up**
   - Geometry: **Apply Modifiers** ✓
4. Navigate to `virtual_skull/models/`
5. Filename: `skull_separated.glb`
6. Click "Export glTF 2.0"

## Method 2: Automatic Separation (Experimental)

Use the provided Python script:

```bash
blender --background --python blender_separate_jaw.py
```

**Warning:** This uses Y-coordinate threshold which may not be accurate for all skull models. Manual separation is more reliable.

## Troubleshooting

### Issue: Can't separate the jaw

**Solution:** The model might already be a single merged mesh. Use "Select Linked" (L) on a face to check. If the entire skull is selected, you need to manually select faces.

### Issue: Rotation pivot is wrong

**Solution:**
1. In Edit Mode, select the vertices at the actual hinge point
2. Shift+S → Cursor to Selected
3. Object Mode → Set Origin → Origin to 3D Cursor

### Issue: Jaw rotates incorrectly

**Solution:** The pivot might be too far forward or back. Adjust by:
1. Moving the 3D cursor manually (Shift+Right Click in 3D view)
2. Setting origin to cursor again

### Issue: Exported model looks wrong

**Solution:**
- Make sure both objects are selected before export
- Check "Selected Objects" in export settings
- Verify +Y Up orientation

## Verification

After export, test the model:

```bash
cd virtual_skull
python3 skull_viewer.py
```

The viewer will:
- Load `skull_separated.glb`
- Detect UpperJaw and LowerJaw meshes
- Animate the jaw rotation
- Show glowing red eyes

## Advanced: Fine-tuning

### Adjust Hinge Point

If the jaw rotation looks unnatural:

1. Open `skull_separated.glb` in Blender
2. Select LowerJaw
3. Tab → Edit Mode
4. Select different vertices at the condyle
5. Shift+S → Cursor to Selected
6. Tab → Object Mode
7. Set Origin → Origin to 3D Cursor
8. Re-export

### Smooth Rotation

If rotation looks jumpy:

1. Select LowerJaw
2. Object Properties → Transform
3. Note the exact origin coordinates
4. These are your hinge point coordinates
5. Update in `skull_viewer.py`:

```python
self.jaw_hinge_point = np.array([x, y, z])  # Your coordinates
```

## Additional Tips

- **Save often:** Blender crashes can happen
- **Use layers:** Keep original and separated versions
- **Backup:** Keep `skull_original.glb` unchanged
- **Lighting:** Add lights in Blender to preview better
- **Camera:** Set up camera view for reference

## References

- [Blender Manual: Separating Meshes](https://docs.blender.org/manual/en/latest/modeling/meshes/editing/mesh/separate.html)
- [Skull Anatomy](https://en.wikipedia.org/wiki/Human_skull)
- [Temporal-Mandibular Joint](https://en.wikipedia.org/wiki/Temporomandibular_joint)
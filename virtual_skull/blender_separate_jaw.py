#!/usr/bin/env python3
"""
Blender script to separate skull into upper and lower jaw
Run this script in Blender's scripting console or via command line:

    blender --background --python blender_separate_jaw.py

This script:
1. Imports skull_original.glb
2. Separates mandible (lower jaw) from upper skull
3. Sets rotation pivot point at temporal-mandibular joint
4. Exports as skull_separated.glb with two objects: UpperJaw and LowerJaw
"""

import bpy
import bmesh
import os
from mathutils import Vector

# Configuration
INPUT_MODEL = "models/skull_original.glb"
OUTPUT_MODEL = "models/skull_separated.glb"

# Y-coordinate threshold to separate jaw (adjust based on model)
# Vertices below this Y will be considered lower jaw
JAW_SEPARATION_Y = -0.05  # Adjust this value after inspecting the model

# Hinge point for jaw rotation (approximate temporal-mandibular joint)
HINGE_POINT = Vector((0.0, -0.03, 0.0))  # Adjust based on model


def clear_scene():
    """Remove all objects from scene"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()


def import_model():
    """Import the skull model"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, INPUT_MODEL)

    print(f"Importing {model_path}...")

    if not os.path.exists(model_path):
        print(f"ERROR: Model not found at {model_path}")
        return None

    # Import glTF
    bpy.ops.import_scene.gltf(filepath=model_path)

    # Get imported object
    obj = bpy.context.selected_objects[0]
    print(f"Imported: {obj.name}")

    return obj


def separate_jaw_by_y_coordinate(obj, threshold_y):
    """
    Separate lower jaw from skull based on Y coordinate
    This is a simple approach - for better results, manually select in Blender
    """
    print(f"Separating jaw at Y = {threshold_y}...")

    # Enter edit mode
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')

    # Get mesh
    mesh = bmesh.from_edit_mesh(obj.data)

    # Deselect all
    bpy.ops.mesh.select_all(action='DESELECT')

    # Select vertices below threshold
    bpy.ops.mesh.select_mode(type='VERT')
    mesh = bmesh.from_edit_mesh(obj.data)

    for vert in mesh.verts:
        # Convert to world coordinates
        world_co = obj.matrix_world @ vert.co
        if world_co.y < threshold_y:
            vert.select = True

    # Update mesh
    bmesh.update_edit_mesh(obj.data)

    # Separate selection
    bpy.ops.mesh.separate(type='SELECTED')

    # Return to object mode
    bpy.ops.object.mode_set(mode='OBJECT')

    # Get the two objects
    selected = bpy.context.selected_objects
    if len(selected) == 2:
        print("✅ Successfully separated into 2 objects")
        return selected
    else:
        print(f"⚠️  Expected 2 objects, got {len(selected)}")
        return None


def set_jaw_pivot(lower_jaw, pivot_point):
    """Set the rotation pivot point for lower jaw"""
    print(f"Setting pivot point at {pivot_point}...")

    # Set 3D cursor to pivot point
    bpy.context.scene.cursor.location = pivot_point

    # Select lower jaw
    bpy.context.view_layer.objects.active = lower_jaw
    lower_jaw.select_set(True)

    # Set origin to 3D cursor
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

    print("✅ Pivot point set")


def export_separated_model(upper_jaw, lower_jaw):
    """Export the separated model as .glb"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, OUTPUT_MODEL)

    # Rename objects
    upper_jaw.name = "UpperJaw"
    lower_jaw.name = "LowerJaw"

    print(f"Renamed objects: {upper_jaw.name}, {lower_jaw.name}")

    # Select both objects
    bpy.ops.object.select_all(action='DESELECT')
    upper_jaw.select_set(True)
    lower_jaw.select_set(True)

    # Export as glTF
    print(f"Exporting to {output_path}...")
    bpy.ops.export_scene.gltf(
        filepath=output_path,
        export_format='GLB',
        use_selection=True,
        export_apply=True
    )

    print(f"✅ Exported to {output_path}")


def main():
    """Main processing pipeline"""
    print("=" * 60)
    print("Skull Jaw Separation Script for Franky")
    print("=" * 60)

    # Clear scene
    clear_scene()

    # Import model
    skull = import_model()
    if not skull:
        return

    # Separate jaw
    objects = separate_jaw_by_y_coordinate(skull, JAW_SEPARATION_Y)
    if not objects or len(objects) != 2:
        print("❌ Failed to separate jaw")
        return

    # Determine which is upper and which is lower
    # Lower jaw should have lower average Y coordinate
    obj1_y = sum(v.co.y for v in objects[0].data.vertices) / len(objects[0].data.vertices)
    obj2_y = sum(v.co.y for v in objects[1].data.vertices) / len(objects[1].data.vertices)

    if obj1_y < obj2_y:
        lower_jaw = objects[0]
        upper_jaw = objects[1]
    else:
        lower_jaw = objects[1]
        upper_jaw = objects[0]

    print(f"Upper jaw: {upper_jaw.name} (avg Y: {max(obj1_y, obj2_y):.3f})")
    print(f"Lower jaw: {lower_jaw.name} (avg Y: {min(obj1_y, obj2_y):.3f})")

    # Set pivot point
    set_jaw_pivot(lower_jaw, HINGE_POINT)

    # Export
    export_separated_model(upper_jaw, lower_jaw)

    print("=" * 60)
    print("✅ Processing complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Open models/skull_separated.glb in Blender to verify")
    print("2. Adjust JAW_SEPARATION_Y and HINGE_POINT if needed")
    print("3. Run python3 skull_viewer.py to test animation")


if __name__ == "__main__":
    main()
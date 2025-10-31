#!/usr/bin/env python3
"""
Test the_skull.glb to see if jaw is already separated
"""

import trimesh
import sys

model_path = sys.argv[1] if len(sys.argv) > 1 else "~/Downloads/skull-downloadable/the_skull.glb"
model_path = model_path.replace("~", "/Users/maksimnagaev")

print(f"Testing: {model_path}\n")

try:
    scene = trimesh.load(model_path)

    if isinstance(scene, trimesh.Scene):
        print(f"✅ Scene with {len(scene.geometry)} geometries:\n")

        for name, geom in scene.geometry.items():
            print(f"📦 {name}")
            print(f"   Vertices: {len(geom.vertices):,}")
            print(f"   Faces: {len(geom.faces):,}")
            print(f"   Bounds: {geom.bounds[0]} to {geom.bounds[1]}")
            print()

            # Check if name suggests it's a jaw part
            if 'lower' in name.lower() or 'mandible' in name.lower() or 'jaw' in name.lower():
                print(f"   🦴 Potential LOWER JAW detected!")
            if 'upper' in name.lower() or 'skull' in name.lower() or 'cranium' in name.lower():
                print(f"   🦴 Potential UPPER JAW detected!")
            print()

    else:
        print(f"Single mesh with {len(scene.vertices):,} vertices")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

#!/usr/bin/env python3
"""
Check all skull models to find one with separated jaw
"""

import trimesh
import os

models = [
    ("skull_downloadable.glb", "~/Downloads/skull-downloadable/source/skull_downloadable.glb"),
    ("skull_downloadable-2.glb", "~/Downloads/skull-downloadable/source/skull_downloadable-2.glb"),
    ("the_skull.glb", "~/Downloads/skull-downloadable/the_skull.glb"),
]

def analyze_model(name, path):
    path = path.replace("~", os.path.expanduser("~"))

    print(f"\n{'='*70}")
    print(f"📦 {name}")
    print(f"{'='*70}")

    if not os.path.exists(path):
        print(f"❌ Not found: {path}")
        return

    try:
        scene = trimesh.load(path)

        if isinstance(scene, trimesh.Scene):
            print(f"✅ Scene with {len(scene.geometry)} geometries\n")

            jaw_candidates = []
            skull_candidates = []

            for obj_name, geom in scene.geometry.items():
                vertices = len(geom.vertices)
                faces = len(geom.faces)
                bounds = geom.bounds

                # Calculate center Y position
                center_y = (bounds[0][1] + bounds[1][1]) / 2

                print(f"  {obj_name}:")
                print(f"    Vertices: {vertices:,}")
                print(f"    Faces: {faces:,}")
                print(f"    Center Y: {center_y:.3f}")
                print(f"    Y Range: [{bounds[0][1]:.3f}, {bounds[1][1]:.3f}]")

                # Check naming
                name_lower = obj_name.lower()
                if any(x in name_lower for x in ['lower', 'mandible', 'jaw', 'mandibula']):
                    print(f"    🦴 LOWER JAW DETECTED BY NAME!")
                    jaw_candidates.append(obj_name)
                elif any(x in name_lower for x in ['upper', 'skull', 'cranium', 'maxilla']):
                    print(f"    🦴 UPPER SKULL DETECTED BY NAME!")
                    skull_candidates.append(obj_name)

                # Check by position (jaw is typically lower, Y < 0 or Y < -0.3)
                if center_y < -0.3:
                    print(f"    📍 Positioned like LOWER JAW (Y < -0.3)")
                    if obj_name not in jaw_candidates:
                        jaw_candidates.append(obj_name)

                print()

            print(f"{'='*70}")
            if jaw_candidates:
                print(f"✅ Potential LOWER JAW parts: {jaw_candidates}")
            if skull_candidates:
                print(f"✅ Potential UPPER SKULL parts: {skull_candidates}")

            if jaw_candidates and skull_candidates:
                print(f"\n🎉 THIS MODEL MIGHT BE ALREADY SEPARATED!")
            elif len(scene.geometry) > 5:
                print(f"\n⚠️  Multiple objects but unclear naming - may need manual inspection")
            else:
                print(f"\n❌ No clear separation detected")

        else:
            print(f"Single mesh: {len(scene.vertices):,} vertices")
            print(f"❌ Not separated")

    except Exception as e:
        print(f"❌ Error: {e}")

print("🔍 Analyzing skull models for separated jaw parts...")

for name, path in models:
    analyze_model(name, path)

print(f"\n{'='*70}")
print("📊 SUMMARY")
print(f"{'='*70}")
print("\nRecommendation:")
print("1. If any model shows 'ALREADY SEPARATED' - use that one!")
print("2. Otherwise, process skull_original.glb in Blender")
print("3. the_skull.glb has 21 objects but unclear structure")

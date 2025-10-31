#!/usr/bin/env python3
"""
Quick test to verify skull model loads correctly
"""

import trimesh
import os

def test_load():
    model_path = "models/skull_original.glb"

    if not os.path.exists(model_path):
        print(f"❌ Model not found: {model_path}")
        return False

    print(f"Loading {model_path}...")

    try:
        scene = trimesh.load(model_path)

        print(f"\n✅ Loaded successfully!")
        print(f"Type: {type(scene)}")

        if isinstance(scene, trimesh.Scene):
            print(f"\nScene contains {len(scene.geometry)} geometries:")
            for name, geom in scene.geometry.items():
                print(f"  - {name}:")
                print(f"    Vertices: {len(geom.vertices)}")
                print(f"    Faces: {len(geom.faces)}")
                print(f"    Bounds: {geom.bounds}")
        else:
            print(f"\nSingle mesh:")
            print(f"  Vertices: {len(scene.vertices)}")
            print(f"  Faces: {len(scene.faces)}")
            print(f"  Bounds: {scene.bounds}")

        return True

    except Exception as e:
        print(f"❌ Error loading model: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_load()
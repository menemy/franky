#!/usr/bin/env python3
"""
Простейший viewer черепа используя встроенный trimesh viewer
"""
import trimesh
import numpy as np

# Загружаем модель
print("🦴 Loading skull...")
scene = trimesh.load('models/skull_separated.glb')

print(f"✅ Loaded {len(scene.geometry)} objects:")
for name, geom in scene.geometry.items():
    print(f"   - {name}: {len(geom.vertices):,} vertices")

# Показываем
print("\n👀 Opening viewer...")
print("   Rotate: Click and drag")
print("   Zoom: Scroll wheel")
print("   Close window to exit")
scene.show()

#!/usr/bin/env python3
"""
Quick test of jaw animation with separated skull model
"""

import os
import time
import math
import numpy as np
import trimesh
import pyglet
from pyglet.gl import *
from OpenGL.GL import *
from OpenGL.GLU import *


class JawAnimationTest:
    def __init__(self):
        self.jaw_open_amount = 0.0
        self.auto_animate = True
        self.animation_time = 0
        self.window = None
        self.upper_mesh = None
        self.lower_mesh = None

    def load_model(self):
        model_path = "models/skull_separated.glb"
        print(f"🦴 Loading {model_path}...")

        scene = trimesh.load(model_path)

        if isinstance(scene, trimesh.Scene):
            geometries = list(scene.geometry.items())

            # Object_10 это челюсть (больше вершин)
            # Object_0 это верхняя часть
            for name, geom in geometries:
                print(f"  - {name}: {len(geom.vertices):,} vertices")
                if 'Object_10' in name:
                    self.lower_mesh = geom
                else:
                    self.upper_mesh = geom

            print(f"✅ Loaded skull with separated jaw")
            return True
        else:
            print(f"❌ Expected scene with 2 objects")
            return False

    def setup_window(self):
        self.window = pyglet.window.Window(
            width=800,
            height=800,
            caption="Jaw Animation Test",
            resizable=True
        )

        @self.window.event
        def on_draw():
            self.render()

        @self.window.event
        def on_key_press(symbol, modifiers):
            if symbol == pyglet.window.key.SPACE:
                self.auto_animate = not self.auto_animate
                print(f"Auto-animate: {self.auto_animate}")
            elif symbol == pyglet.window.key.UP:
                self.jaw_open_amount = min(1.0, self.jaw_open_amount + 0.1)
                print(f"Jaw: {self.jaw_open_amount:.1f}")
            elif symbol == pyglet.window.key.DOWN:
                self.jaw_open_amount = max(0.0, self.jaw_open_amount - 0.1)
                print(f"Jaw: {self.jaw_open_amount:.1f}")

        # OpenGL setup
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glEnable(GL_NORMALIZE)

        glLightfv(GL_LIGHT0, GL_POSITION, (GLfloat * 4)(5, 5, 5, 1))
        glLightfv(GL_LIGHT0, GL_AMBIENT, (GLfloat * 4)(0.3, 0.3, 0.3, 1))
        glLightfv(GL_LIGHT0, GL_DIFFUSE, (GLfloat * 4)(0.8, 0.8, 0.8, 1))

        glClearColor(0.1, 0.05, 0.15, 1.0)

    def draw_mesh(self, mesh, transform=None):
        if mesh is None:
            return

        glPushMatrix()

        if transform is not None:
            matrix = transform.T.flatten()
            glMultMatrixf((GLfloat * 16)(*matrix))

        glColor3f(0.9, 0.9, 0.85)

        vertices = mesh.vertices.astype(np.float32)
        normals = mesh.vertex_normals.astype(np.float32)
        faces = mesh.faces.flatten().astype(np.uint32)

        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)

        glVertexPointer(3, GL_FLOAT, 0, vertices.ctypes.data)
        glNormalPointer(GL_FLOAT, 0, normals.ctypes.data)

        glDrawElements(GL_TRIANGLES, len(faces), GL_UNSIGNED_INT, faces.ctypes.data)

        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_NORMAL_ARRAY)

        glPopMatrix()

    def render(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Projection
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = self.window.width / self.window.height
        gluPerspective(45, aspect, 0.1, 50.0)

        # Modelview
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        gluLookAt(0, 0, 3, 0, 0, 0, 0, 1, 0)

        # Rotate
        glRotatef(-90, 1, 0, 0)
        glRotatef(self.animation_time * 10, 0, 0, 1)

        # Scale
        glScalef(0.007, 0.007, 0.007)

        # Draw upper skull
        self.draw_mesh(self.upper_mesh)

        # Draw lower jaw with rotation
        jaw_angle_rad = math.radians(self.jaw_open_amount * 60)  # Max 60 degrees

        # Rotation around hinge point
        # Hinge point from Blender: (-0.001, 0.548, -0.772)
        hinge = np.array([-0.001, 0.548, -0.772])

        transform = trimesh.transformations.rotation_matrix(
            jaw_angle_rad,
            [1, 0, 0],
            hinge
        )

        self.draw_mesh(self.lower_mesh, transform)

    def update(self, dt):
        self.animation_time += dt

        if self.auto_animate:
            # Sine wave animation
            self.jaw_open_amount = (math.sin(self.animation_time * 2) + 1) / 2

    def run(self):
        if not self.load_model():
            return

        self.setup_window()

        pyglet.clock.schedule_interval(self.update, 1/60.0)

        print("\n🎮 Controls:")
        print("  SPACE - Toggle auto-animation")
        print("  UP    - Open jaw")
        print("  DOWN  - Close jaw")
        print("\n🦴 Starting animation test...")

        pyglet.app.run()


if __name__ == "__main__":
    import sys
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    test = JawAnimationTest()
    test.run()

#!/usr/bin/env python3
"""
Simple 3D Skull Viewer - works with any skull model (no jaw separation needed)
Shows full skull with glowing eyes effect only
"""

import os
import time
import math
import numpy as np
import trimesh
import pyglet
pyglet.options['shadow_window'] = False
from pyglet.gl import *
from OpenGL.GL import *
from OpenGL.GLU import *
import paho.mqtt.client as mqtt


class SimpleSkullViewer:
    def __init__(self, model_path="models/skull_separated.glb"):
        self.model_path = model_path
        self.jaw_open_amount = 0.0
        self.eyes_glowing = False
        self.rotation_y = 0
        self.rotation_x = -15  # Slight tilt for better view

        # MQTT setup
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message

        self.window = None
        self.skull_meshes = []

    def on_mqtt_connect(self, client, userdata, flags, rc):
        print(f"🦴 Connected to MQTT broker (rc={rc})")
        client.subscribe("franky/jaw")
        client.subscribe("franky/speaking")

    def on_mqtt_message(self, client, userdata, msg):
        try:
            if msg.topic == "franky/jaw":
                value = float(msg.payload.decode())
                self.jaw_open_amount = max(0.0, min(1.0, value))
                self.eyes_glowing = value > 0.05
            elif msg.topic == "franky/speaking":
                self.eyes_glowing = msg.payload.decode() == "1"
        except:
            pass

    def load_model(self):
        """Load skull model"""
        print(f"🦴 Loading skull model: {self.model_path}")

        if not os.path.exists(self.model_path):
            print(f"❌ Model not found: {self.model_path}")
            return False

        try:
            scene = trimesh.load(self.model_path)

            if isinstance(scene, trimesh.Scene):
                print(f"✅ Loaded scene with {len(scene.geometry)} geometries")
                self.skull_meshes = list(scene.geometry.values())
            else:
                print(f"✅ Loaded single mesh with {len(scene.vertices)} vertices")
                self.skull_meshes = [scene]

            return True

        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return False

    def setup_window(self):
        """Setup pyglet window and OpenGL"""
        self.window = pyglet.window.Window(
            width=800,
            height=800,
            caption="Franky's Skull (Simple Viewer)",
            resizable=True
        )

        @self.window.event
        def on_draw():
            self.render()

        # Setup OpenGL (no lighting - simple rendering)
        glEnable(GL_DEPTH_TEST)

        # Background color - spooky dark
        glClearColor(0.1, 0.05, 0.15, 1.0)

    def draw_mesh(self, mesh):
        """Draw a trimesh mesh using OpenGL"""
        if mesh is None:
            return

        # Set material color - bone white
        glColor3f(0.9, 0.9, 0.85)

        # Draw mesh using vertex arrays
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

    def draw_eyes(self):
        """Draw glowing eyes"""
        glDisable(GL_LIGHTING)

        # Eye color based on speaking/jaw state
        if self.eyes_glowing or self.jaw_open_amount > 0.05:
            # Bright red when speaking/moving
            intensity = 0.5 + 0.5 * self.jaw_open_amount
            glColor3f(intensity, 0.0, 0.0)
        else:
            # Dark red when idle
            glColor3f(0.3, 0.0, 0.0)

        # Eye positions - adjust these for your model
        eye_positions = [
            (-0.15, 0.1, 0.15),  # Left eye
            (0.15, 0.1, 0.15)    # Right eye
        ]

        for x, y, z in eye_positions:
            glPushMatrix()
            glTranslatef(x, y, z)

            # Draw sphere for eye glow
            quadric = gluNewQuadric()
            gluSphere(quadric, 0.03, 16, 16)
            gluDeleteQuadric(quadric)

            glPopMatrix()

        glEnable(GL_LIGHTING)

    def render(self):
        """Render the skull"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Setup projection
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = self.window.width / self.window.height
        gluPerspective(45, aspect, 0.1, 50.0)

        # Setup modelview
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        gluLookAt(0, 0, 3,  # Camera position
                  0, 0, 0,  # Look at origin
                  0, 1, 0)  # Up vector

        # Rotate view
        glRotatef(self.rotation_x, 1, 0, 0)  # Tilt
        glRotatef(self.rotation_y, 0, 1, 0)  # Spin

        # Scale model to fit view (adjust based on your model)
        glScalef(0.01, 0.01, 0.01)

        # Draw all skull meshes
        for mesh in self.skull_meshes:
            self.draw_mesh(mesh)

        # Draw eyes
        glScalef(100, 100, 100)  # Scale back for eyes
        self.draw_eyes()

    def update(self, dt):
        """Update animation state"""
        # Auto-rotate
        self.rotation_y += dt * 20

    def run(self):
        """Main application loop"""
        # Load model
        if not self.load_model():
            print("❌ Failed to load model. Exiting.")
            return

        # Setup window
        self.setup_window()

        # Connect to MQTT
        try:
            print("🦴 Connecting to MQTT broker...")
            self.mqtt_client.connect("localhost", 1883, 60)
            self.mqtt_client.loop_start()
            print("✅ Connected to MQTT")
        except Exception as e:
            print(f"⚠️  MQTT connection failed: {e}")
            print("Continuing without MQTT...")

        # Schedule update
        pyglet.clock.schedule_interval(self.update, 1/60.0)

        # Run
        print("🦴 Starting skull viewer...")
        print("   Eyes will glow red when Franky speaks!")
        pyglet.app.run()

        # Cleanup
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()


if __name__ == "__main__":
    # Get model path from command line or use default
    import sys

    script_dir = os.path.dirname(os.path.abspath(__file__))

    if len(sys.argv) > 1:
        model_path = sys.argv[1]
    else:
        model_path = os.path.join(script_dir, "models/skull_original.glb")

    print(f"🎃 Simple Skull Viewer for Franky")
    print(f"Model: {model_path}\n")

    viewer = SimpleSkullViewer(model_path)
    viewer.run()

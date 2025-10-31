#!/usr/bin/env python3
"""
3D Skull Viewer for Franky
Loads realistic skull model and animates jaw synchronized with speech
"""

import os
import sys
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


class SkullViewer:
    def __init__(self, model_path="models/skull_separated.glb"):
        self.model_path = model_path
        self.jaw_open_amount = 0.0
        self.target_jaw_open = 0.0
        self.eyes_glowing = False
        self.rotation_y = 0

        # MQTT setup
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message

        # Window and rendering
        self.window = None
        self.scene = None
        self.upper_jaw_mesh = None
        self.lower_jaw_mesh = None

        # Animation settings
        self.max_jaw_angle = 60.0  # Maximum jaw opening in degrees
        self.jaw_hinge_point = np.array([0.0, -0.1, 0.0])  # Will be updated from model

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
        """Load skull model from .glb file"""
        print(f"🦴 Loading skull model: {self.model_path}")

        if not os.path.exists(self.model_path):
            print(f"❌ Model not found: {self.model_path}")
            print("Please download the model first. See README.md")
            return False

        try:
            # Load the entire scene
            self.scene = trimesh.load(self.model_path)

            # Check if it's a scene with multiple meshes or single mesh
            if isinstance(self.scene, trimesh.Scene):
                print(f"✅ Loaded scene with {len(self.scene.geometry)} geometries")

                # Try to find UpperJaw and LowerJaw meshes
                for name, geometry in self.scene.geometry.items():
                    print(f"   - {name}: {len(geometry.vertices)} vertices")

                    # Object_10.001 is the lower jaw (more vertices)
                    # Object_0.001 is the upper skull
                    if 'Object_10' in name or 'LowerJaw' in name or 'lower' in name.lower() or 'mandible' in name.lower():
                        self.lower_jaw_mesh = geometry
                        print(f"   ✅ Found lower jaw: {name}")
                    elif 'Object_0' in name or 'UpperSkull' in name or 'upper' in name.lower() or 'skull' in name.lower():
                        self.upper_jaw_mesh = geometry
                        print(f"   ✅ Found upper jaw: {name}")

                # If not found by name, try to split by Y coordinate
                if self.lower_jaw_mesh is None:
                    print("⚠️  Lower jaw not found by name, will use entire model")
                    # For now, use the first mesh as the entire skull
                    # User will need to separate in Blender for proper animation
                    self.upper_jaw_mesh = list(self.scene.geometry.values())[0]

            else:
                # Single mesh - user needs to separate in Blender
                print(f"✅ Loaded single mesh with {len(self.scene.vertices)} vertices")
                print("⚠️  Model is not separated. For jaw animation, process in Blender (see README.md)")
                self.upper_jaw_mesh = self.scene

            return True

        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return False

    def setup_window(self):
        """Setup pyglet window and OpenGL"""
        # Create window without projection shaders (compatible with legacy OpenGL)
        self.window = pyglet.window.Window(
            width=800,
            height=800,
            caption="Franky's Skull",
            resizable=True,
            style=pyglet.window.Window.WINDOW_STYLE_DEFAULT
        )

        # Disable pyglet's automatic projection setup
        self.window.projection = pyglet.math.Mat4()

        @self.window.event
        def on_draw():
            self.render()

        @self.window.event
        def on_resize(width, height):
            glViewport(0, 0, width, height)
            return pyglet.event.EVENT_HANDLED

        # Setup OpenGL - simple depth testing only
        glEnable(GL_DEPTH_TEST)

        # Background color - dark purple
        glClearColor(0.1, 0.05, 0.15, 1.0)

    def draw_mesh(self, mesh, transform=None):
        """Draw a trimesh mesh using OpenGL"""
        if mesh is None:
            return

        glPushMatrix()

        # Apply transformation if provided
        if transform is not None:
            # Convert to column-major for OpenGL
            matrix = transform.T.flatten()
            glMultMatrixf((GLfloat * 16)(*matrix))

        # Set material color
        glColor3f(0.9, 0.9, 0.85)  # Bone white

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

        glPopMatrix()

    def draw_eyes(self):
        """Draw glowing eyes"""
        # Eye color based on speaking state
        if self.eyes_glowing:
            glColor3f(1.0, 0.0, 0.0)  # Bright red
        else:
            glColor3f(0.3, 0.0, 0.0)  # Dark red

        # Eye positions (adjust based on actual skull model)
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
        glRotatef(-90, 1, 0, 0)  # Rotate to face forward
        glRotatef(20, 1, 0, 0)   # Tilt skull 20° up
        glRotatef(self.rotation_y, 0, 0, 1)  # Auto-rotate (disabled)

        # Scale model to fit view
        glScalef(0.01, 0.01, 0.01)  # Adjust based on model scale

        # Draw upper jaw (static)
        if self.upper_jaw_mesh:
            self.draw_mesh(self.upper_jaw_mesh)

        # Draw lower jaw (animated)
        if self.lower_jaw_mesh:
            # Create rotation matrix for jaw
            jaw_angle_rad = math.radians(self.jaw_open_amount * self.max_jaw_angle)

            # Rotation around X-axis at hinge point
            transform = trimesh.transformations.rotation_matrix(
                jaw_angle_rad,
                [1, 0, 0],
                self.jaw_hinge_point
            )

            self.draw_mesh(self.lower_jaw_mesh, transform)

        # Draw eyes
        glScalef(100, 100, 100)  # Scale back for eyes
        self.draw_eyes()

    def update(self, dt):
        """Update animation state"""
        # Auto-rotate disabled
        pass

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
        pyglet.app.run()

        # Cleanup
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()


if __name__ == "__main__":
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, "models/skull_separated.glb")

    viewer = SkullViewer(model_path)
    viewer.run()
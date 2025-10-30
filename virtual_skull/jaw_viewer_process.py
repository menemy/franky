#!/usr/bin/env python3
"""
3D Jaw visualization process for Franky
Receives jaw position via MQTT and animates accordingly
"""

import glfw
from OpenGL.GL import *
from OpenGL.GLU import *
import time
import paho.mqtt.client as mqtt

class JawViewer:
    def __init__(self):
        self.jaw_open_amount = 0.0
        self.target_jaw_open = 0.0
        self.window = None
        self.rotation_y = 0
        self.eyes_glowing = False  # Eyes glow red when speaking

        # MQTT setup
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message

    def on_mqtt_connect(self, client, userdata, flags, rc):
        print(f"🦴 Connected to MQTT broker (rc={rc})")
        client.subscribe("franky/jaw")
        client.subscribe("franky/speaking")  # Listen for speaking status

    def on_mqtt_message(self, client, userdata, msg):
        try:
            if msg.topic == "franky/jaw":
                value = float(msg.payload.decode())
                # Напрямую устанавливаем позицию для синхронизации с аудио
                self.jaw_open_amount = max(0.0, min(1.0, value))
                # Eyes glow when jaw is moving (speaking)
                self.eyes_glowing = value > 0.05
            elif msg.topic == "franky/speaking":
                # Alternative: explicit speaking status
                self.eyes_glowing = msg.payload.decode() == "1"
        except:
            pass

    def init_gl(self):
        """Initialize OpenGL"""
        if not glfw.init():
            raise Exception("GLFW initialization failed")

        self.window = glfw.create_window(400, 400, "Franky's Jaw", None, None)
        if not self.window:
            glfw.terminate()
            raise Exception("GLFW window creation failed")

        glfw.make_context_current(self.window)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)

        glLightfv(GL_LIGHT0, GL_POSITION, [5, 5, 5, 1])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1])
        glClearColor(0.1, 0.05, 0.15, 1.0)

    def draw_upper_jaw(self):
        glPushMatrix()
        glColor3f(0.9, 0.9, 0.85)
        glBegin(GL_QUADS)

        # Front
        glNormal3f(0, 0, 1)
        glVertex3f(-0.8, 0.2, 0.3)
        glVertex3f(0.8, 0.2, 0.3)
        glVertex3f(0.6, -0.1, 0.3)
        glVertex3f(-0.6, -0.1, 0.3)

        # Back
        glNormal3f(0, 0, -1)
        glVertex3f(-0.8, 0.2, -0.3)
        glVertex3f(-0.6, -0.1, -0.3)
        glVertex3f(0.6, -0.1, -0.3)
        glVertex3f(0.8, 0.2, -0.3)

        # Sides
        glNormal3f(-1, 0, 0)
        glVertex3f(-0.8, 0.2, -0.3)
        glVertex3f(-0.8, 0.2, 0.3)
        glVertex3f(-0.6, -0.1, 0.3)
        glVertex3f(-0.6, -0.1, -0.3)

        glNormal3f(1, 0, 0)
        glVertex3f(0.8, 0.2, -0.3)
        glVertex3f(0.6, -0.1, -0.3)
        glVertex3f(0.6, -0.1, 0.3)
        glVertex3f(0.8, 0.2, 0.3)

        # Top
        glNormal3f(0, 1, 0)
        glVertex3f(-0.8, 0.2, -0.3)
        glVertex3f(0.8, 0.2, -0.3)
        glVertex3f(0.8, 0.2, 0.3)
        glVertex3f(-0.8, 0.2, 0.3)

        glEnd()

        # Teeth
        glColor3f(0.95, 0.95, 0.9)
        for i in range(-3, 4):
            glPushMatrix()
            glTranslatef(i * 0.25, -0.05, 0.35)
            glScalef(0.08, 0.15, 0.05)
            self.draw_cube()
            glPopMatrix()

        glPopMatrix()

    def draw_lower_jaw(self):
        glPushMatrix()

        jaw_angle = self.jaw_open_amount * 60  # Увеличил с 30 до 60 градусов
        glTranslatef(0, -0.1, 0)
        glRotatef(jaw_angle, 1, 0, 0)
        glTranslatef(0, 0.1, 0)

        glColor3f(0.9, 0.9, 0.85)
        glBegin(GL_QUADS)

        # Front
        glNormal3f(0, 0, 1)
        glVertex3f(-0.6, -0.1, 0.3)
        glVertex3f(0.6, -0.1, 0.3)
        glVertex3f(0.5, -0.5, 0.3)
        glVertex3f(-0.5, -0.5, 0.3)

        # Back
        glNormal3f(0, 0, -1)
        glVertex3f(-0.6, -0.1, -0.3)
        glVertex3f(-0.5, -0.5, -0.3)
        glVertex3f(0.5, -0.5, -0.3)
        glVertex3f(0.6, -0.1, -0.3)

        # Sides
        glNormal3f(-1, 0, 0)
        glVertex3f(-0.6, -0.1, -0.3)
        glVertex3f(-0.6, -0.1, 0.3)
        glVertex3f(-0.5, -0.5, 0.3)
        glVertex3f(-0.5, -0.5, -0.3)

        glNormal3f(1, 0, 0)
        glVertex3f(0.6, -0.1, -0.3)
        glVertex3f(0.5, -0.5, -0.3)
        glVertex3f(0.5, -0.5, 0.3)
        glVertex3f(0.6, -0.1, 0.3)

        # Bottom
        glNormal3f(0, -1, 0)
        glVertex3f(-0.5, -0.5, -0.3)
        glVertex3f(-0.5, -0.5, 0.3)
        glVertex3f(0.5, -0.5, 0.3)
        glVertex3f(0.5, -0.5, -0.3)

        glEnd()

        # Teeth
        glColor3f(0.95, 0.95, 0.9)
        for i in range(-3, 4):
            glPushMatrix()
            glTranslatef(i * 0.25, -0.15, 0.35)
            glScalef(0.08, 0.15, 0.05)
            self.draw_cube()
            glPopMatrix()

        glPopMatrix()

    def draw_eyes(self):
        """Draw glowing red eyes"""
        # Disable lighting for emissive effect
        glDisable(GL_LIGHTING)

        # Set eye color based on speaking state
        if self.eyes_glowing:
            glColor3f(1.0, 0.0, 0.0)  # Bright red when speaking
        else:
            glColor3f(0.3, 0.0, 0.0)  # Dark red when idle

        # Left eye
        glPushMatrix()
        glTranslatef(-0.35, 0.05, 0.35)
        self.draw_sphere(0.12, 16, 16)
        glPopMatrix()

        # Right eye
        glPushMatrix()
        glTranslatef(0.35, 0.05, 0.35)
        self.draw_sphere(0.12, 16, 16)
        glPopMatrix()

        # Re-enable lighting
        glEnable(GL_LIGHTING)

    def draw_sphere(self, radius, slices, stacks):
        """Draw a sphere using quad strips"""
        import math

        for i in range(stacks):
            lat0 = math.pi * (-0.5 + float(i) / stacks)
            z0 = radius * math.sin(lat0)
            zr0 = radius * math.cos(lat0)

            lat1 = math.pi * (-0.5 + float(i + 1) / stacks)
            z1 = radius * math.sin(lat1)
            zr1 = radius * math.cos(lat1)

            glBegin(GL_QUAD_STRIP)
            for j in range(slices + 1):
                lng = 2 * math.pi * float(j) / slices
                x = math.cos(lng)
                y = math.sin(lng)

                glNormal3f(x * zr0, y * zr0, z0)
                glVertex3f(x * zr0, y * zr0, z0)
                glNormal3f(x * zr1, y * zr1, z1)
                glVertex3f(x * zr1, y * zr1, z1)
            glEnd()

    def draw_cube(self):
        glBegin(GL_QUADS)
        # All 6 faces
        glNormal3f(0, 0, 1)
        glVertex3f(-0.5, -0.5, 0.5); glVertex3f(0.5, -0.5, 0.5)
        glVertex3f(0.5, 0.5, 0.5); glVertex3f(-0.5, 0.5, 0.5)

        glNormal3f(0, 0, -1)
        glVertex3f(-0.5, -0.5, -0.5); glVertex3f(-0.5, 0.5, -0.5)
        glVertex3f(0.5, 0.5, -0.5); glVertex3f(0.5, -0.5, -0.5)

        glNormal3f(-1, 0, 0)
        glVertex3f(-0.5, -0.5, -0.5); glVertex3f(-0.5, -0.5, 0.5)
        glVertex3f(-0.5, 0.5, 0.5); glVertex3f(-0.5, 0.5, -0.5)

        glNormal3f(1, 0, 0)
        glVertex3f(0.5, -0.5, -0.5); glVertex3f(0.5, 0.5, -0.5)
        glVertex3f(0.5, 0.5, 0.5); glVertex3f(0.5, -0.5, 0.5)

        glNormal3f(0, 1, 0)
        glVertex3f(-0.5, 0.5, -0.5); glVertex3f(-0.5, 0.5, 0.5)
        glVertex3f(0.5, 0.5, 0.5); glVertex3f(0.5, 0.5, -0.5)

        glNormal3f(0, -1, 0)
        glVertex3f(-0.5, -0.5, -0.5); glVertex3f(0.5, -0.5, -0.5)
        glVertex3f(0.5, -0.5, 0.5); glVertex3f(-0.5, -0.5, 0.5)
        glEnd()

    def render(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, 1.0, 0.1, 50.0)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        gluLookAt(0, 0, 4, 0, 0, 0, 0, 1, 0)

        glRotatef(self.rotation_y, 0, 1, 0)

        # No interpolation - direct sync with audio output
        self.draw_upper_jaw()
        self.draw_lower_jaw()
        self.draw_eyes()  # Draw glowing red eyes

        glfw.swap_buffers(self.window)

    def run(self):
        # Connect to MQTT broker
        print("🦴 Connecting to MQTT broker...")
        self.mqtt_client.connect("localhost", 1883, 60)
        self.mqtt_client.loop_start()

        # Initialize OpenGL
        self.init_gl()
        last_time = time.time()

        while not glfw.window_should_close(self.window):
            current_time = time.time()
            delta_time = current_time - last_time
            last_time = current_time

            self.rotation_y += delta_time * 20
            self.render()
            glfw.poll_events()
            time.sleep(0.016)

        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        glfw.terminate()

if __name__ == "__main__":
    viewer = JawViewer()
    viewer.run()
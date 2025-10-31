#!/usr/bin/env python3
"""
3D Jaw visualization for Franky the skeleton
Shows animated jaw movement synchronized with speech
"""

import glfw
from OpenGL.GL import *
from OpenGL.GLU import *
import math
import threading
import time


class JawViewer:
    def __init__(self):
        self.jaw_open_amount = 0.0  # 0.0 = closed, 1.0 = fully open
        self.target_jaw_open = 0.0
        self.window = None
        self.running = False
        self.rotation_x = 0
        self.rotation_y = 0

    def set_jaw_open(self, amount):
        """Set target jaw open amount (0.0 to 1.0)"""
        self.target_jaw_open = max(0.0, min(1.0, amount))

    def init_gl(self):
        """Initialize OpenGL"""
        if not glfw.init():
            raise Exception("GLFW initialization failed")

        # Create window
        self.window = glfw.create_window(400, 400, "Franky's Jaw", None, None)
        if not self.window:
            glfw.terminate()
            raise Exception("GLFW window creation failed")

        glfw.make_context_current(self.window)

        # Set up OpenGL
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)

        # Light setup
        glLightfv(GL_LIGHT0, GL_POSITION, [5, 5, 5, 1])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1])

        # Set background color (dark for Halloween)
        glClearColor(0.1, 0.05, 0.15, 1.0)

    def draw_upper_jaw(self):
        """Draw the upper jaw/skull"""
        glPushMatrix()
        glColor3f(0.9, 0.9, 0.85)  # Bone white color

        # Upper jaw (simplified trapezoid shape)
        glBegin(GL_QUADS)

        # Front face
        glNormal3f(0, 0, 1)
        glVertex3f(-0.8, 0.2, 0.3)
        glVertex3f(0.8, 0.2, 0.3)
        glVertex3f(0.6, -0.1, 0.3)
        glVertex3f(-0.6, -0.1, 0.3)

        # Back face
        glNormal3f(0, 0, -1)
        glVertex3f(-0.8, 0.2, -0.3)
        glVertex3f(-0.6, -0.1, -0.3)
        glVertex3f(0.6, -0.1, -0.3)
        glVertex3f(0.8, 0.2, -0.3)

        # Left face
        glNormal3f(-1, 0, 0)
        glVertex3f(-0.8, 0.2, -0.3)
        glVertex3f(-0.8, 0.2, 0.3)
        glVertex3f(-0.6, -0.1, 0.3)
        glVertex3f(-0.6, -0.1, -0.3)

        # Right face
        glNormal3f(1, 0, 0)
        glVertex3f(0.8, 0.2, -0.3)
        glVertex3f(0.6, -0.1, -0.3)
        glVertex3f(0.6, -0.1, 0.3)
        glVertex3f(0.8, 0.2, 0.3)

        # Top face
        glNormal3f(0, 1, 0)
        glVertex3f(-0.8, 0.2, -0.3)
        glVertex3f(0.8, 0.2, -0.3)
        glVertex3f(0.8, 0.2, 0.3)
        glVertex3f(-0.8, 0.2, 0.3)

        glEnd()

        # Draw teeth on upper jaw
        glColor3f(0.95, 0.95, 0.9)
        for i in range(-3, 4):
            glPushMatrix()
            glTranslatef(i * 0.25, -0.05, 0.35)
            glScalef(0.08, 0.15, 0.05)
            self.draw_cube()
            glPopMatrix()

        glPopMatrix()

    def draw_lower_jaw(self):
        """Draw the lower jaw (moves when speaking)"""
        glPushMatrix()

        # Rotate jaw around hinge point based on jaw_open_amount
        jaw_angle = self.jaw_open_amount * 30  # Max 30 degrees open
        glTranslatef(0, -0.1, 0)  # Move to hinge point
        glRotatef(jaw_angle, 1, 0, 0)  # Rotate around X axis
        glTranslatef(0, 0.1, 0)  # Move back

        glColor3f(0.9, 0.9, 0.85)  # Bone white color

        # Lower jaw (simplified trapezoid shape)
        glBegin(GL_QUADS)

        # Front face
        glNormal3f(0, 0, 1)
        glVertex3f(-0.6, -0.1, 0.3)
        glVertex3f(0.6, -0.1, 0.3)
        glVertex3f(0.5, -0.5, 0.3)
        glVertex3f(-0.5, -0.5, 0.3)

        # Back face
        glNormal3f(0, 0, -1)
        glVertex3f(-0.6, -0.1, -0.3)
        glVertex3f(-0.5, -0.5, -0.3)
        glVertex3f(0.5, -0.5, -0.3)
        glVertex3f(0.6, -0.1, -0.3)

        # Left face
        glNormal3f(-1, 0, 0)
        glVertex3f(-0.6, -0.1, -0.3)
        glVertex3f(-0.6, -0.1, 0.3)
        glVertex3f(-0.5, -0.5, 0.3)
        glVertex3f(-0.5, -0.5, -0.3)

        # Right face
        glNormal3f(1, 0, 0)
        glVertex3f(0.6, -0.1, -0.3)
        glVertex3f(0.5, -0.5, -0.3)
        glVertex3f(0.5, -0.5, 0.3)
        glVertex3f(0.6, -0.1, 0.3)

        # Bottom face
        glNormal3f(0, -1, 0)
        glVertex3f(-0.5, -0.5, -0.3)
        glVertex3f(-0.5, -0.5, 0.3)
        glVertex3f(0.5, -0.5, 0.3)
        glVertex3f(0.5, -0.5, -0.3)

        glEnd()

        # Draw teeth on lower jaw
        glColor3f(0.95, 0.95, 0.9)
        for i in range(-3, 4):
            glPushMatrix()
            glTranslatef(i * 0.25, -0.15, 0.35)
            glScalef(0.08, 0.15, 0.05)
            self.draw_cube()
            glPopMatrix()

        glPopMatrix()

    def draw_cube(self):
        """Draw a simple cube (for teeth)"""
        glutSolidCube = lambda size: None  # Placeholder if needed
        # Simple cube using GL_QUADS
        glBegin(GL_QUADS)

        # Front
        glNormal3f(0, 0, 1)
        glVertex3f(-0.5, -0.5, 0.5)
        glVertex3f(0.5, -0.5, 0.5)
        glVertex3f(0.5, 0.5, 0.5)
        glVertex3f(-0.5, 0.5, 0.5)

        # Back
        glNormal3f(0, 0, -1)
        glVertex3f(-0.5, -0.5, -0.5)
        glVertex3f(-0.5, 0.5, -0.5)
        glVertex3f(0.5, 0.5, -0.5)
        glVertex3f(0.5, -0.5, -0.5)

        # Left
        glNormal3f(-1, 0, 0)
        glVertex3f(-0.5, -0.5, -0.5)
        glVertex3f(-0.5, -0.5, 0.5)
        glVertex3f(-0.5, 0.5, 0.5)
        glVertex3f(-0.5, 0.5, -0.5)

        # Right
        glNormal3f(1, 0, 0)
        glVertex3f(0.5, -0.5, -0.5)
        glVertex3f(0.5, 0.5, -0.5)
        glVertex3f(0.5, 0.5, 0.5)
        glVertex3f(0.5, -0.5, 0.5)

        # Top
        glNormal3f(0, 1, 0)
        glVertex3f(-0.5, 0.5, -0.5)
        glVertex3f(-0.5, 0.5, 0.5)
        glVertex3f(0.5, 0.5, 0.5)
        glVertex3f(0.5, 0.5, -0.5)

        # Bottom
        glNormal3f(0, -1, 0)
        glVertex3f(-0.5, -0.5, -0.5)
        glVertex3f(0.5, -0.5, -0.5)
        glVertex3f(0.5, -0.5, 0.5)
        glVertex3f(-0.5, -0.5, 0.5)

        glEnd()

    def render(self):
        """Render the scene"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Set up projection
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, 1.0, 0.1, 50.0)

        # Set up modelview
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        gluLookAt(0, 0, 4,  # Camera position
                  0, 0, 0,  # Look at origin
                  0, 1, 0)  # Up vector

        # Rotate view
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)

        # Smoothly interpolate jaw position
        jaw_speed = 0.3
        if self.jaw_open_amount < self.target_jaw_open:
            self.jaw_open_amount = min(self.jaw_open_amount + jaw_speed, self.target_jaw_open)
        elif self.jaw_open_amount > self.target_jaw_open:
            self.jaw_open_amount = max(self.jaw_open_amount - jaw_speed, self.target_jaw_open)

        # Draw the jaw parts
        self.draw_upper_jaw()
        self.draw_lower_jaw()

        glfw.swap_buffers(self.window)

    def run_loop(self):
        """Main rendering loop (runs in separate thread)"""
        self.running = True
        self.init_gl()

        # Auto-rotate
        last_time = time.time()

        while self.running and not glfw.window_should_close(self.window):
            current_time = time.time()
            delta_time = current_time - last_time
            last_time = current_time

            # Auto-rotate slowly
            self.rotation_y += delta_time * 20

            self.render()
            glfw.poll_events()
            time.sleep(0.016)  # ~60 FPS

        glfw.terminate()

    def start(self):
        """Start the viewer - NOT USED, use as separate process instead"""
        pass

    def stop(self):
        """Stop the viewer"""
        self.running = False


if __name__ == "__main__":
    # Test the jaw viewer
    viewer = JawViewer()
    viewer.run_loop()
#!/usr/bin/env python3
"""
3D Skull Viewer for Franky - Modern OpenGL with Shaders
Loads realistic skull model and animates jaw synchronized with speech
"""

import os
import math
import struct
import numpy as np
import trimesh
import pyglet
from pyglet import gl
from pyglet.math import Mat4, Vec3
import paho.mqtt.client as mqtt


# Vertex shader - modern GLSL
VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 position;
layout(location = 1) in vec3 normal;

uniform mat4 projection;
uniform mat4 view;
uniform mat4 model;

out vec3 FragPos;
out vec3 Normal;

void main() {
    vec4 worldPos = model * vec4(position, 1.0);
    FragPos = worldPos.xyz;
    Normal = mat3(transpose(inverse(model))) * normal;
    gl_Position = projection * view * worldPos;
}
"""

# Fragment shader with simple lighting
FRAGMENT_SHADER = """
#version 330 core
in vec3 FragPos;
in vec3 Normal;

out vec4 FragColor;

uniform vec3 lightPos;
uniform vec3 viewPos;
uniform vec3 objectColor;

void main() {
    // Ambient
    float ambientStrength = 0.3;
    vec3 ambient = ambientStrength * vec3(1.0);

    // Diffuse
    vec3 norm = normalize(Normal);
    vec3 lightDir = normalize(lightPos - FragPos);
    float diff = max(dot(norm, lightDir), 0.0);
    vec3 diffuse = diff * vec3(1.0);

    // Specular
    float specularStrength = 0.5;
    vec3 viewDir = normalize(viewPos - FragPos);
    vec3 reflectDir = reflect(-lightDir, norm);
    float spec = pow(max(dot(viewDir, reflectDir), 0.0), 32);
    vec3 specular = specularStrength * spec * vec3(1.0);

    vec3 result = (ambient + diffuse + specular) * objectColor;
    FragColor = vec4(result, 1.0);
}
"""


class SkullViewer:
    def __init__(self, model_path="models/skull_separated.glb"):
        self.model_path = model_path
        self.jaw_open_amount = 0.0
        self.eyes_glowing = False

        # MQTT setup
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message

        # Rendering
        self.window = None
        self.shader = None
        self.upper_jaw_vao = None
        self.lower_jaw_vao = None
        self.upper_jaw_count = 0
        self.lower_jaw_count = 0

        # Animation
        self.max_jaw_angle = 60.0  # degrees

        # Camera
        self.camera_pos = Vec3(0, -4, 0)
        self.camera_target = Vec3(0, 0, 0)
        self.camera_up = Vec3(0, 0, 1)

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
            return False

        try:
            scene = trimesh.load(self.model_path)

            if not isinstance(scene, trimesh.Scene):
                print(f"❌ Expected a scene with multiple meshes")
                return False

            print(f"✅ Loaded scene with {len(scene.geometry)} geometries")

            upper_jaw_mesh = None
            lower_jaw_mesh = None

            for name, geometry in scene.geometry.items():
                print(f"   - {name}: {len(geometry.vertices)} vertices")

                if 'mandible' in name.lower() or 'lower' in name.lower():
                    lower_jaw_mesh = geometry
                    print(f"   ✅ Found lower jaw: {name}")
                elif 'cranium' in name.lower() or 'upper' in name.lower() or 'skull' in name.lower():
                    upper_jaw_mesh = geometry
                    print(f"   ✅ Found upper jaw: {name}")

            if not upper_jaw_mesh:
                print("❌ Upper jaw mesh not found")
                return False

            # Create VBOs for upper jaw
            self.upper_jaw_vao = self.create_vao(upper_jaw_mesh)
            self.upper_jaw_count = len(upper_jaw_mesh.faces) * 3

            # Create VBOs for lower jaw if available
            if lower_jaw_mesh:
                self.lower_jaw_vao = self.create_vao(lower_jaw_mesh)
                self.lower_jaw_count = len(lower_jaw_mesh.faces) * 3
                print(f"✅ Jaw animation enabled")
            else:
                print(f"⚠️  No lower jaw found - jaw animation disabled")

            return True

        except Exception as e:
            print(f"❌ Error loading model: {e}")
            import traceback
            traceback.print_exc()
            return False

    def create_vao(self, mesh):
        """Create VAO and VBO for a mesh"""
        # Get vertices and normals
        vertices = mesh.vertices.astype(np.float32)
        normals = mesh.vertex_normals.astype(np.float32)
        indices = mesh.faces.flatten().astype(np.uint32)

        # Create VAO
        vao = gl.GLuint()
        gl.glGenVertexArrays(1, vao)
        gl.glBindVertexArray(vao)

        # Create VBO for vertices
        vbo_vertices = gl.GLuint()
        gl.glGenBuffers(1, vbo_vertices)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo_vertices)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices.ctypes.data, gl.GL_STATIC_DRAW)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
        gl.glEnableVertexAttribArray(0)

        # Create VBO for normals
        vbo_normals = gl.GLuint()
        gl.glGenBuffers(1, vbo_normals)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo_normals)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, normals.nbytes, normals.ctypes.data, gl.GL_STATIC_DRAW)
        gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
        gl.glEnableVertexAttribArray(1)

        # Create EBO for indices
        ebo = gl.GLuint()
        gl.glGenBuffers(1, ebo)
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices.ctypes.data, gl.GL_STATIC_DRAW)

        gl.glBindVertexArray(0)

        return vao

    def setup_window(self):
        """Setup pyglet window and OpenGL"""
        self.window = pyglet.window.Window(
            width=800,
            height=800,
            caption="Franky's Skull",
            resizable=True
        )

        @self.window.event
        def on_draw():
            self.render()

        @self.window.event
        def on_resize(width, height):
            gl.glViewport(0, 0, width, height)
            return pyglet.event.EVENT_HANDLED

        # OpenGL setup
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glClearColor(0.1, 0.05, 0.15, 1.0)

        # Compile shaders
        self.shader = self.create_shader_program(VERTEX_SHADER, FRAGMENT_SHADER)

    def create_shader_program(self, vertex_src, fragment_src):
        """Compile and link shaders"""
        # Compile vertex shader
        vertex_shader = gl.glCreateShader(gl.GL_VERTEX_SHADER)
        gl.glShaderSource(vertex_shader, 1, [vertex_src.encode()], None)
        gl.glCompileShader(vertex_shader)

        # Check vertex shader
        success = gl.GLint()
        gl.glGetShaderiv(vertex_shader, gl.GL_COMPILE_STATUS, success)
        if not success:
            log = gl.glGetShaderInfoLog(vertex_shader)
            print(f"❌ Vertex shader compilation failed: {log.decode() if isinstance(log, bytes) else log}")
            return None

        # Compile fragment shader
        fragment_shader = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
        gl.glShaderSource(fragment_shader, 1, [fragment_src.encode()], None)
        gl.glCompileShader(fragment_shader)

        # Check fragment shader
        gl.glGetShaderiv(fragment_shader, gl.GL_COMPILE_STATUS, success)
        if not success:
            log = gl.glGetShaderInfoLog(fragment_shader)
            print(f"❌ Fragment shader compilation failed: {log.decode() if isinstance(log, bytes) else log}")
            return None

        # Link program
        program = gl.glCreateProgram()
        gl.glAttachShader(program, vertex_shader)
        gl.glAttachShader(program, fragment_shader)
        gl.glLinkProgram(program)

        # Check program
        gl.glGetProgramiv(program, gl.GL_LINK_STATUS, success)
        if not success:
            log = gl.glGetProgramInfoLog(program)
            print(f"❌ Shader program linking failed: {log.decode() if isinstance(log, bytes) else log}")
            return None

        gl.glDeleteShader(vertex_shader)
        gl.glDeleteShader(fragment_shader)

        print("✅ Shaders compiled successfully")
        return program

    def render(self):
        """Render the skull"""
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        if not self.shader:
            return

        gl.glUseProgram(self.shader)

        # Setup matrices
        aspect = self.window.width / self.window.height
        projection = Mat4.perspective_projection(aspect, 45.0, 0.1, 100.0)
        view = Mat4.look_at(self.camera_pos, self.camera_target, self.camera_up)

        # Base model transformation - scale and tilt
        base_model = Mat4()
        base_model = base_model.scale(Vec3(0.01, 0.01, 0.01))  # Scale down
        base_model = base_model.rotate(-math.pi/2 + math.radians(20), Vec3(1, 0, 0))  # -90° + 20° tilt

        # Set uniforms
        self.set_mat4(self.shader, "projection", projection)
        self.set_mat4(self.shader, "view", view)
        self.set_vec3(self.shader, "lightPos", Vec3(5, 5, 10))
        self.set_vec3(self.shader, "viewPos", self.camera_pos)
        self.set_vec3(self.shader, "objectColor", Vec3(0.9, 0.9, 0.85))  # Bone white

        # Draw upper jaw
        if self.upper_jaw_vao:
            self.set_mat4(self.shader, "model", base_model)
            gl.glBindVertexArray(self.upper_jaw_vao)
            gl.glDrawElements(gl.GL_TRIANGLES, self.upper_jaw_count, gl.GL_UNSIGNED_INT, None)

        # Draw lower jaw with rotation
        if self.lower_jaw_vao:
            jaw_angle = math.radians(self.jaw_open_amount * self.max_jaw_angle)
            jaw_model = base_model @ Mat4.from_rotation(jaw_angle, Vec3(1, 0, 0))

            self.set_mat4(self.shader, "model", jaw_model)
            gl.glBindVertexArray(self.lower_jaw_vao)
            gl.glDrawElements(gl.GL_TRIANGLES, self.lower_jaw_count, gl.GL_UNSIGNED_INT, None)

        gl.glBindVertexArray(0)
        gl.glUseProgram(0)

    def set_mat4(self, program, name, matrix):
        """Set mat4 uniform"""
        location = gl.glGetUniformLocation(program, name.encode())
        # Convert to column-major array
        m = (gl.GLfloat * 16)(*matrix)
        gl.glUniformMatrix4fv(location, 1, gl.GL_FALSE, m)

    def set_vec3(self, program, name, vec):
        """Set vec3 uniform"""
        location = gl.glGetUniformLocation(program, name.encode())
        gl.glUniform3f(location, vec.x, vec.y, vec.z)

    def update(self, dt):
        """Update animation state"""
        pass  # Auto-rotation disabled

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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, "models/skull_separated.glb")

    viewer = SkullViewer(model_path)
    viewer.run()

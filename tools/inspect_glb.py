"""Print the world-space bounds of a GLB using Blender.

Run:
  blender --background --python tools/inspect_glb.py -- path/to/model.glb
"""

import bpy
import sys


arguments = sys.argv[sys.argv.index("--") + 1 :]
if not arguments:
    raise SystemExit("Provide a GLB path after --")

bpy.ops.import_scene.gltf(filepath=arguments[0])
vertices = [
    obj.matrix_world @ vertex.co
    for obj in bpy.context.scene.objects
    if obj.type == "MESH"
    for vertex in obj.data.vertices
]
if not vertices:
    raise SystemExit("The GLB has no mesh vertices")

minimum = tuple(round(min(vertex[index] for vertex in vertices), 3) for index in range(3))
maximum = tuple(round(max(vertex[index] for vertex in vertices), 3) for index in range(3))
print(f"bounds_metres: min={minimum}, max={maximum}")
print(f"mesh_objects: {sum(obj.type == 'MESH' for obj in bpy.context.scene.objects)}")

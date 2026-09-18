"""Combine the detailed bridge GLB with OpenStreetMap context in Blender.

The scene uses a local east/north metre plane centred at the F4map reference
pin.  The bridge is manually registered by the transform constants below.
Use Blender to tune those constants against surveyed control points when they
become available, then re-run the export.

Run:
  blender --background --python tools/build_binh_loi_osm_scene.py -- \
    data/osm/binh_loi_context.json app/static/models/binh-loi-v5.glb \
    app/static/models/binh-loi-osm-context.glb
"""

import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import bpy
from mathutils import Vector


REFERENCE_LAT = 10.8249547
REFERENCE_LON = 106.7090760
# Bridge-GLB origin in the local east/north coordinate plane. These values
# provide an initial visual registration and are intentionally easy to tune.
BRIDGE_OFFSET_X = 275.0
BRIDGE_OFFSET_Y = 0.0
BRIDGE_ROTATION_DEGREES = 0.0
CONTEXT_RADIUS_METRES = 550.0

arguments = sys.argv[sys.argv.index("--") + 1 :]
if len(arguments) != 3:
    raise SystemExit("Expected: <osm-json> <bridge-glb> <output-glb>")
osm_path, bridge_path, output_path = map(Path, arguments)

METRES_PER_DEGREE_LAT = 111_320.0
METRES_PER_DEGREE_LON = METRES_PER_DEGREE_LAT * math.cos(math.radians(REFERENCE_LAT))


def local_position(latitude, longitude):
    return (
        (longitude - REFERENCE_LON) * METRES_PER_DEGREE_LON,
        (latitude - REFERENCE_LAT) * METRES_PER_DEGREE_LAT,
    )


def numeric_height(tags):
    raw = tags.get("height", "")
    try:
        return max(3.0, min(float(raw.lower().replace("m", "").strip()), 80.0))
    except (AttributeError, ValueError):
        return max(3.0, min(float(tags.get("building:levels", 3)) * 3.2, 80.0))


def material(name, colour, roughness=0.8):
    item = bpy.data.materials.new(name)
    item.diffuse_color = (*colour, 1.0)
    item.use_nodes = True
    bsdf = item.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*colour, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    return item


BUILDING = material("OSM buildings", (0.63, 0.57, 0.48))
ROAD = material("OSM roads", (0.14, 0.16, 0.18))
WATER = material("OSM water", (0.07, 0.30, 0.43), 0.35)
GROUND = material("OSM ground", (0.22, 0.33, 0.20))


def polygon_mesh(name, points, z, mat, extrude=0.0):
    if len(points) < 3:
        return None
    bottom = [(x, y, z) for x, y in points]
    if extrude:
        top = [(x, y, z + extrude) for x, y in points]
        vertices = bottom + top
        count = len(points)
        faces = [list(range(count)), list(range(count, count * 2))]
        faces += [[index, (index + 1) % count, (index + 1) % count + count, index + count] for index in range(count)]
    else:
        vertices = bottom
        faces = [list(range(len(vertices)))]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    object_ = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(object_)
    object_.data.materials.append(mat)
    return object_


def road_curve(name, points, width):
    if len(points) < 2:
        return
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = width / 2
    curve.bevel_resolution = 1
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, (x, y) in zip(spline.points, points):
        point.co = (x, y, 0.35, 1)
    object_ = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(object_)
    object_.data.materials.append(ROAD)


if osm_path.suffix.lower() == ".osm":
    root = ET.parse(osm_path).getroot()
    nodes = {
        int(item.attrib["id"]): {"lat": float(item.attrib["lat"]), "lon": float(item.attrib["lon"])}
        for item in root.findall("node")
    }
    ways = [
        {
            "nodes": [int(node.attrib["ref"]) for node in item.findall("nd")],
            "tags": {tag.attrib["k"]: tag.attrib["v"] for tag in item.findall("tag")},
        }
        for item in root.findall("way")
    ]
else:
    with osm_path.open(encoding="utf-8") as source:
        elements = json.load(source)["elements"]
    nodes = {item["id"]: item for item in elements if item["type"] == "node"}
    ways = [item for item in elements if item["type"] == "way"]

# Start from the high-detail bridge. The old generic land, road, river and
# building meshes stay hidden in the temporary Blender scene and are excluded
# from the GLB export below; avoiding destructive deletion keeps the importer
# stable with this large source asset.
bpy.ops.import_scene.gltf(filepath=str(bridge_path))
bridge_objects = [item for item in bpy.context.scene.objects if item.type == "MESH" and item.name.strip().startswith("BR")]
for object_ in bpy.context.scene.objects:
    if object_.type == "MESH" and not object_.name.strip().startswith("BR"):
        object_.hide_render = True
for object_ in bridge_objects:
    object_.location.x += BRIDGE_OFFSET_X
    object_.location.y += BRIDGE_OFFSET_Y
    object_.rotation_euler[2] += math.radians(BRIDGE_ROTATION_DEGREES)

# A subtle local ground plane makes the combined scene readable without adding
# a satellite texture or unverified terrain elevation.
radius = CONTEXT_RADIUS_METRES
polygon_mesh("OSM local ground", [(-radius, -radius), (radius, -radius), (radius, radius), (-radius, radius)], -0.2, GROUND)

road_widths = {"motorway": 16, "trunk": 13, "primary": 11, "secondary": 9, "tertiary": 8, "residential": 6, "service": 4}
for way in ways:
    tags = way.get("tags", {})
    points = [local_position(nodes[node]["lat"], nodes[node]["lon"]) for node in way.get("nodes", []) if node in nodes]
    if not points:
        continue
    centre_x = sum(point[0] for point in points) / len(points)
    centre_y = sum(point[1] for point in points) / len(points)
    if math.hypot(centre_x, centre_y) > CONTEXT_RADIUS_METRES:
        continue
    if tags.get("building"):
        polygon_mesh("OSM building", points, 0.0, BUILDING, numeric_height(tags))
    elif tags.get("natural") == "water" or tags.get("waterway") == "riverbank":
        polygon_mesh("OSM water", points, 0.02, WATER)
    elif tags.get("highway") in road_widths:
        road_curve("OSM road", points, road_widths[tags["highway"]])

bpy.context.scene.world.color = (0.03, 0.04, 0.06)
bpy.ops.object.select_all(action="DESELECT")
for object_ in bpy.context.scene.objects:
    if object_.name.strip().startswith("BR") or object_.name.startswith("OSM"):
        object_.select_set(True)
bpy.ops.export_scene.gltf(
    filepath=str(output_path),
    export_format="GLB",
    export_materials="EXPORT",
    export_cameras=False,
    export_lights=False,
    export_apply=True,
    use_selection=True,
)
print(f"Wrote combined scene: {output_path}")

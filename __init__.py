bl_info = {
    "name": "Minecraft JSON Import/Export",
    "author": "phonon, eltanschauung",
    "version": (0, 5, 0),
    "blender": (5, 2, 0),
    "location": "File > Import/Export > Minecraft (.json)",
    "description": "Modern Minecraft / Horizon cuboid JSON and UV editing",
    "warning": "",
    "doc_url": "https://github.com/eltanschauung/blender-minecraft-json#readme",
    "tracker_url": "https://github.com/eltanschauung/blender-minecraft-json/issues",
    "category": "Minecraft",
}

from . import io_scene_minecraft_json
from . import minecraft_utils

# reload imported modules
import importlib
importlib.reload(io_scene_minecraft_json) 
importlib.reload(minecraft_utils)

def register():
    io_scene_minecraft_json.register()
    minecraft_utils.register()

def unregister():
    minecraft_utils.unregister()
    io_scene_minecraft_json.unregister()

import os
import json
import numpy as np
import math
from math import inf
import bpy
from mathutils import Vector
from .transforms import BASIS, rotation_matrix
from .resources import resolve_resource
from .roundtrip import remember_element, remember_model
from .cuboid_uv import apply_face_data

def merge_dict_properties(dict_original, d):
    """Merge inner dict properties"""
    for k in d:
        if k in dict_original and isinstance(dict_original[k], dict):
            dict_original[k].update(d[k])
        else:
            dict_original[k] = d[k]
    
    return dict_original


def create_textured_principled_bsdf(mat_name, tex_path):
    """Create new material with `mat_name` and texture path `tex_path`
    """
    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    node_tree = mat.node_tree
    nodes = node_tree.nodes
    bsdf = nodes.get("Principled BSDF") 

    # add texture node
    if bsdf is not None:
        if "Base Color" in bsdf.inputs:
            tex_input = nodes.new(type="ShaderNodeTexImage")
            tex_input.interpolation = "Closest"

            # load image, if fail make a new image with filepath set to tex path
            try:
                img = bpy.data.images.load(tex_path, check_existing=True)
            except:
                print("FAILED TO LOAD IMAGE:", tex_path)
                img = bpy.data.images.new(os.path.split(tex_path)[-1], width=16, height=16)
                img.filepath = tex_path
        
            tex_input.image = img
            node_tree.links.new(tex_input.outputs[0], bsdf.inputs["Base Color"])
        
        # disable shininess
        specular = bsdf.inputs.get("Specular IOR Level") or bsdf.inputs.get("Specular")
        if specular is not None:
            specular.default_value = 0.0
        bsdf.inputs["Roughness"].default_value = 1.0
    
    return mat


def load(context,
         filepath,
         import_uvs = True,               # import face uvs
         import_textures = True,          # import textures into materials
         translate_origin_by_8 = False,   # shift model by (-8, -8, -8)
         recenter_to_origin = True,       # recenter model to origin, overrides translate origin
         **kwargs):
    """Main import function"""

    with open(filepath, "r") as f:
        data = json.load(f)
    
    # chunks of import file path, to get base directory
    filepath_parts = filepath.split(os.path.sep)
    
    # check if parent exists, need to merge data into parent
    if "parent" in data:
        # build stack of data dicts, then write backwards:
        # data_hierarchy = [this, parent1, parent2, ...]
        data_hierarchy = [data]
        curr_data = data
        
        # in case circular dependency...
        curr_level = 0
        MAX_PARENT_LEVEL = 10

        # find path models merge point:
        # - normal model location is "assets/models"
        # - if "models" does not exist, check for "model"
        path_models_merge_point = None
        for p in reversed(filepath_parts):
            if p == "models" or p == "model":
                path_models_merge_point = p
                break

        while True:
            # parent path without namespacing, e.g. "minecraft:block/cobblestone" -> "block/cobblestone"
            parent_path = curr_data["parent"]
            
            # get parent path
            _, filepath_parent = resolve_resource(filepath, parent_path, 'models')

            if os.path.exists(filepath_parent):
                with open(filepath_parent, "r") as f:
                    data_parent = json.load(f)
                    data_hierarchy.append(data_parent)
                    curr_data = data_parent
            else:
                print("FAILED TO FIND PARENT:", filepath_parent)
                break

            curr_level += 1

            if "parent" not in curr_data or curr_level > MAX_PARENT_LEVEL:
                break
    
        # merge together data, need to specially merge inner dict values
        data = {}
        for d in reversed(data_hierarchy):
            data = merge_dict_properties(data, d)

    # main object elements
    elements = data["elements"]

    # check if groups in .json
    # not a minecraft .json spec, used by this exporter + Blockbench
    # as additional data to group models together
    if "groups" in data:
        groups = data["groups"]
    else:
        groups = {}
    
    # objects created
    objects = []

    # model bounding box vector
    model_v_min = np.array([inf, inf, inf])
    model_v_max = np.array([-inf, -inf, -inf])

    # minecraft coordinate system origin
    if translate_origin_by_8:
        minecraft_origin = np.array([8., 8., 8.])
    else:
        # ignore if not translating
        minecraft_origin = np.array([0., 0., 0.])

    # set scene collection as active
    scene_collection = bpy.context.view_layer.layer_collection
    bpy.context.view_layer.active_layer_collection = scene_collection
    
    # re-used buffers for every object
    v_world = np.zeros((3, 8))

    # =============================================
    # import textures, create map of material name => material
    # =============================================
    """Note two type of texture formats:
        "textures:" {
            "down": "#bottom",                         # texture alias to another texture
            "bottom": "minecraft:block/cobblestone",   # actual texture image
        }

    Loading textures is two pass:
        1. load all actual texture images
        2. map aliases to loaded texture images
    """
    textures = {}
    if import_textures and "textures" in data:
        # get textures path for models, replace "model" or "models" with "textures"
        filepath_textures = filepath_parts
        idx = -1
        for i, p in enumerate(filepath_parts):
            if p == "models" or p == "model":
                idx = i
                break
        if idx != -1:
            filepath_textures[idx] = "textures"
        
        # load texture images
        for tex_name, tex_path in data["textures"].items():
            # skip aliases
            if tex_path[0] == "#":
                continue

            canonical, filepath_tex = resolve_resource(filepath, tex_path)
            textures[tex_name] = create_textured_principled_bsdf(tex_name, str(filepath_tex))
            textures[tex_name]["minecraft_texture"] = canonical
            data["textures"][tex_name] = canonical

        # map texture aliases
        for tex_name, tex_path in data["textures"].items():
            if tex_path[0] == "#":
                tex_path = tex_path[1:]
                if tex_path in textures:
                    textures[tex_name] = textures[tex_path]

    # =============================================
    # import geometry, uvs
    # =============================================
    for element_index, e in enumerate(elements):
        # get cube min/max
        v_min = np.array([e["from"][2], e["from"][0], e["from"][1]])
        v_max = np.array([e["to"][2], e["to"][0], e["to"][1]])

        # get rotation + origin
        rot = e.get("rotation")
        if rot is not None:
            location = np.array([rot["origin"][2], rot["origin"][0], rot["origin"][1]]) - minecraft_origin
            converted = BASIS @ rotation_matrix(rot) @ BASIS.transposed()
            rot_euler = converted.to_euler('XYZ')
        else:
            # default location to center of mass
            location = 0.5 * (v_min + v_max)
            rot_euler = (0.0, 0.0, 0.0)
        
        # Direct data creation avoids a dependency-graph rebuild per voxel.
        mesh = bpy.data.meshes.new('Minecraft Cuboid')
        face_vertices = {'north':(0,1,3,2), 'south':(4,6,7,5),
                         'west':(0,4,5,1), 'east':(2,3,7,6),
                         'down':(0,2,6,4), 'up':(1,5,7,3)}
        mesh.from_pydata([(x,y,z) for x in (-1,1) for y in (-1,1) for z in (-1,1)], [],
                         [vertices for name,vertices in face_vertices.items() if name in e.get('faces',{})])
        mesh.uv_layers.new(name='UVMap')
        obj = bpy.data.objects.new('cube', mesh)
        context.scene.collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = rot_euler
        if rot is not None:
            obj.matrix_world = converted.to_4x4()
            obj.location = location

        # center local mesh coordiantes
        v_min = v_min - minecraft_origin - location
        v_max = v_max - minecraft_origin - location
        
        # set vertices
        mesh.vertices[0].co[:] = v_min[0], v_min[1], v_min[2]
        mesh.vertices[1].co[:] = v_min[0], v_min[1], v_max[2]
        mesh.vertices[2].co[:] = v_min[0], v_max[1], v_min[2]
        mesh.vertices[3].co[:] = v_min[0], v_max[1], v_max[2]
        mesh.vertices[4].co[:] = v_max[0], v_min[1], v_min[2]
        mesh.vertices[5].co[:] = v_max[0], v_min[1], v_max[2]
        mesh.vertices[6].co[:] = v_max[0], v_max[1], v_min[2]
        mesh.vertices[7].co[:] = v_max[0], v_max[1], v_max[2]

        mesh.update()
        apply_face_data(obj, e, textures, import_uvs)

        # set name (choose whatever is available or "cube" if no name or comment is given)
        obj.name = e.get("name") or e.get("__comment") or "cube"

        remember_element(obj, e, element_index)

        # save created object
        objects.append(obj)

        # ================================
        # update global model bounding box
        # ================================
        # get world coordinates
        mat_world = obj.matrix_world
        for i, v in enumerate(mesh.vertices):
            v_world[0:3,i] = mat_world @ v.co
        
        model_v_min = np.amin(np.append(v_world, model_v_min[...,np.newaxis], axis=1), axis=1)
        model_v_max = np.amax(np.append(v_world, model_v_max[...,np.newaxis], axis=1), axis=1)

    offset = Vector(minecraft_origin)

    # model post-processing
    if recenter_to_origin:
        mean = 0.5 * (model_v_min + model_v_max)
        mean = Vector((mean[0], mean[1], mean[2]))
        offset += mean
        for o in objects:
            o.location = o.location - mean
    
    # import groups as collections
    for g in groups:
        name = g["name"]
        if name == "Master Collection":
            continue
        
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
        for index in g["children"]:
            col.objects.link(objects[index])
            bpy.context.scene.collection.objects.unlink(objects[index])
    
    remember_model(context, data, filepath, objects, BASIS.transposed() @ offset)
    context.view_layer.update()

    # select newly imported objects
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    if objects:
        context.view_layer.objects.active = objects[0]
    
    return {"FINISHED"}

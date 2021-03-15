# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
#
# Copyright (C) 2021  Bruno Tuma <bruno.tuma@outlook.com>

import copy
import math
import os
import sys
import struct
import webbrowser

import maya.api.OpenMaya as OpenMaya
import pymel.core as pm
import maya.OpenMayaMPx as OpenMayaMPx

from body_info import body_names
from hqrreader import HQRReader

main_window = pm.language.melGlobals['gMainWindow']
kPluginCmdName = "loadLBA2Model"
menu_obj = "LBA2MayaMenu"
menu_label = "LBA2 Loader"
WORLD_SCALE = 0.15
LINE_RADIUS = 0.25
LINE_RESOLUTION = 3
SPHERE_RESOLUTION = 10
REPO_URL = 'https://github.com/b-tuma/LBA2Maya'
resources = []
lba_path = ''
palette = []
body_file = None
anim_file = None
import_menu = None
lba_importer_menu = None


def create_menus():
    print(os.path.dirname(os.path.realpath(sys.argv[0])))
    global lba_importer_menu
    global import_menu
    if pm.menu(menu_obj, label=menu_label, exists=True, parent=main_window):
        pm.deleteUI(pm.menu(menu_obj, e=True, deleteAllItems=True))

    lba_importer_menu = pm.menu(menu_obj, label=menu_label, parent=main_window, tearOff=True)

    pm.menuItem(label='Select LBA2 Folder...', command=load_lba2_folder)
    import_menu = pm.menuItem(label="Import Model", command=open_model_importer, enable=False)
    pm.menuItem(divider=True)
    pm.menuItem(label="Open on GitHub", image='menuIconHelp.png', command=about)


def about(*args):
    webbrowser.open(REPO_URL)


def open_model_importer(*args):
    def palette_change(*args):
        settings.use_palette = palette_checkbox.getValue()

    def rigging_change(*args):
        settings.use_rigging = rigging_checkbox.getValue()
        anim_checkbox.setEnable(val=settings.use_rigging)

    def anim_change(*args):
        settings.use_animation = anim_checkbox.getValue()
        rigging_checkbox.setEditable(val=not settings.use_animation)

    def import_command(*args):
        global lba_path
        global body_file
        if body_file is None:
            body_file = HQRReader(lba_path + "/BODY.HQR")
        settings.line_radius = line_radius_checkbox.getValue()
        settings.line_resolution = line_res_checkbox.getValue()
        settings.sphere_resolution = sphere_res_checkbox.getValue()
        loading_box = pm.progressWindow(title="LBA2 Model Generator", status="Starting...", isInterruptable=False,
                                        progress=0)
        import_model(scroll_list.getSelectIndexedItem()[0] - 1, settings, loading_box)
        pm.deleteUI(window)

    def scroll_select(*args):
        selected = len(scroll_list.getSelectIndexedItem()) > 0
        import_button.setEnable(val=selected)

    settings = Settings()
    window = pm.window(title="LBA2 Model Importer")
    form = pm.formLayout(numberOfDivisions=100)
    scroll_list = pm.textScrollList(numberOfRows=30, allowMultiSelection=False, append=body_names,
                                    selectCommand=scroll_select)
    import_button = pm.button(label="Import", command=import_command, enable=False)
    column = pm.columnLayout(rowSpacing=10)
    pm.text(label='Converter', font='boldLabelFont')
    pm.rowLayout(numberOfColumns=2, columnWidth=[1, 100])
    pm.text(label='Lines radius')
    line_radius_checkbox = pm.floatField(min=0.0, max=1.0, value=LINE_RADIUS, tze=False, s=0.05)
    pm.setParent('..')
    pm.rowLayout(numberOfColumns=2, columnWidth=[1, 100])
    pm.text(label='Lines resolution')
    line_res_checkbox = pm.intField(min=3, max=10, value=LINE_RESOLUTION, s=1)
    pm.setParent('..')
    pm.rowLayout(numberOfColumns=2, columnWidth=[1, 100])
    pm.text(label='Spheres resolution')
    sphere_res_checkbox = pm.intField(min=1, max=30, value=SPHERE_RESOLUTION, s=1)
    pm.setParent('..')
    pm.text(label='Palette', font='boldLabelFont')
    palette_checkbox = pm.checkBox(label='Include Colors', value=True, changeCommand=palette_change)
    pm.text(label='Rigging', font='boldLabelFont')
    rigging_checkbox = pm.checkBox(label='Include Rigging', value=True, changeCommand=rigging_change, editable=False)
    pm.text(label='Animations', font='boldLabelFont')
    anim_checkbox = pm.checkBox(label='Include Animations', value=True, changeCommand=anim_change)
    pm.formLayout(form, edit=True,
                  attachForm=[(scroll_list, 'top', 5), (scroll_list, 'left', 5), (import_button, 'left', 5),
                              (import_button, 'bottom', 5), (import_button, 'right', 5),
                              (column, 'top', 5), (column, 'right', 5)],
                  attachControl=[(scroll_list, 'bottom', 5, import_button), (column, 'bottom', 5, import_button)],
                  attachPosition=[(scroll_list, 'right', 5, 75), (column, 'left', 0, 75)],
                  attachNone=(import_button, 'top'))
    pm.showWindow(window)


def load_lba2_folder(*args):
    global lba_path
    global palette
    global resources
    global import_menu

    def find(name, path):
        for root, dirs, files in os.walk(path):
            if name in files:
                return os.path.join(root, name)

    directory = pm.fileDialog2(caption="Select LBA2 Installation Folder", fileMode=2, okCaption="Select")
    if directory is None:
        return
    # Look for essential files before accepting:
    if find("BODY.HQR", directory[0]) is None:
        pm.informBox("Incorrect Folder", "File BODY.HQR not found.")
        return
    if find("RESS.HQR", directory[0]) is None:
        pm.informBox("Incorrect Folder", "File RESS.HQR not found.")
        return
    if find("ANIM.HQR", directory[0]) is None:
        pm.informBox("Incorrect Folder", "File ANIM.HQR not found.")
        return

    lba_path = directory[0]
    # Read RESS.HQR relevant entries
    loading_box = pm.progressWindow(title="LBA2 Model Generator", status="Opening Folder...", isInterruptable=False,
                                    progress=0)
    ress_file = HQRReader(lba_path + "/RESS.HQR")
    pm.progressWindow(loading_box, edit=True, status="Loading Palette...", progress=10)
    palette = load_palette(ress_file[0])
    pm.progressWindow(loading_box, edit=True, status="Loading Resources...", progress=20)
    resources = load_information(ress_file[44], loading_box)
    import_menu.setEnable(val=True)
    pm.progressWindow(loading_box, endProgress=1)


# Read palette entry from RESS.HQR
def load_palette(entry):
    r = EntryReader(entry)
    colors = []
    for i in range(256):
        red = r.u8()
        green = r.u8()
        blue = r.u8()
        colors.append((red, green, blue))
    return colors


# Read characters information entry from RESS.HQR
def load_information(entry, loading_box):
    r = EntryReader(entry)
    _resources = []
    while True:
        ress = Resource()
        ress.offset = r.s32()
        _resources.append(ress)
        if _resources[0].offset == r.currentIndex:
            break

    for i in range(len(_resources)):
        pm.progressWindow(loading_box, edit=True, progress=20 + math.floor((80.0 / len(_resources)) * i))
        r.goto(_resources[i].offset)
        if i != len(_resources) - 1:
            while r.currentIndex < _resources[i + 1].offset - 1:
                _resources[i].op_code = r.u8()
                if _resources[i].op_code == 1:  # is Body
                    body = RessBody()
                    body.index = r.u8()
                    body.dataSize = r.u8()
                    body.realIndex = r.s16()
                    body.collisionBoxFlag = r.u8()
                    if body.collisionBoxFlag == 1:
                        r.skip(13)
                    _resources[i].bodies.append(body)
                else:  # is Anim
                    anim = RessAnim()
                    anim.index = r.u16()
                    anim.dataSize = r.u8()
                    anim.realIndex = r.u16()
                    r.skip(anim.dataSize - 3)
                    _resources[i].animations.append(anim)
                if i == len(_resources) - 1:
                    break
        else:
            _resources.pop(len(_resources) - 1)
    return _resources


class Resource(object):
    offset = 0
    op_code = 0

    def __init__(self):
        self.bodies = []
        self.animations = []
        pass


class RessBody(object):
    index = 0
    dataSize = 0
    realIndex = 0
    collisionBoxFlag = 0

    def __init__(self):
        pass


class RessAnim(object):
    index = 0
    realIndex = 0
    dataSize = 0

    def __init__(self):
        pass


# File Reader
class EntryReader(object):

    def __init__(self, path):
        self.path = path
        self.currentIndex = 0

    def skip(self, n):
        self.path.read(n)
        self.currentIndex += n

    def u8(self):
        self.currentIndex += 1
        return struct.unpack('<B', self.path.read(1))[0]

    def u16(self):
        self.currentIndex += 2
        return struct.unpack('<H', self.path.read(2))[0]

    def u16_div(self, n):
        x = self.u16()
        if x % n != 0:
            raise RuntimeError("%u is not divisible by %u" % (x, n))
        return x // n

    def s16_div(self, n):
        x = self.s16()
        if x == -1:
            return x
        if x % n != 0:
            raise RuntimeError("%u is not divisible by %u" % (x, n))
        return x // n

    def s16(self):
        self.currentIndex += 2
        return struct.unpack('<h', self.path.read(2))[0]

    def s32(self):
        self.currentIndex += 4
        return struct.unpack('<i', self.path.read(4))[0]

    def u32(self):
        self.currentIndex += 4
        return struct.unpack('<I', self.path.read(4))[0]

    def goto(self, offset):
        if offset > self.currentIndex:
            self.path.read(offset - self.currentIndex)
            self.currentIndex += offset - self.currentIndex


class LBA2Model(object):
    def __init__(self):
        self.normals = None
        self.vertices = None
        self.bones = None
        self.lines = None
        self.spheres = None
        self.polygons = None


class OriginalBone(object):
    parent = 0
    vertex = 0
    unk1 = 0
    unk2 = 0

    def __init__(self):
        pass


class GeneratedBone(object):
    parent = 0
    pos = []
    created = False

    def __init__(self):
        pass


class Vertex(object):
    index = 0
    x = 0
    y = 0
    z = 0
    bone = 0

    def __init__(self):
        pass


class Normal(object):
    x = 0
    y = 0
    z = 0
    unk1 = 0

    def __init__(self):
        pass


class Unknown1(object):
    unk1 = 0
    unk2 = 0
    unk3 = 0
    unk4 = 0

    def __init__(self):
        pass


class Settings(object):
    use_palette = True
    use_rigging = True
    use_animation = True
    line_resolution = LINE_RESOLUTION
    line_radius = LINE_RADIUS
    sphere_resolution = SPHERE_RESOLUTION

    def __init__(self):
        pass


class Polygon(object):
    renderType = 0
    vertex = []
    colour = 0
    intensity = 0
    u = []
    v = []
    tex = 0
    numVertex = 0
    hasTex = False
    hasExtra = False
    hasTransparency = False

    def __init__(self):
        pass


class Line(object):
    unk1 = 0
    colour = 0
    vertex1 = 0
    vertex2 = 0

    def __init__(self):
        pass


class Sphere(object):
    unk1 = 0
    colour = 0
    vertex = 0
    size = 0

    def __init__(self):
        pass


class UVGroup(object):
    x = 0
    y = 0
    w = 0
    h = 0

    def __init__(self):
        pass


class BoneframeCanFall(object):
    boneframe = []
    can_fall = False

    def __init__(self):
        pass


class Boneframe(object):
    has_both_types = False
    bone_type = 0
    vector = []

    def __init__(self):
        pass


class Keyframe(object):
    length = 0
    x = 0
    y = 0
    z = 0
    can_fall = False
    boneframes = []

    def __init__(self):
        pass


class Anim(object):
    num_keyframes = 0
    num_boneframes = 0
    loop_frame = 0
    unk1 = 0

    def __init__(self):
        self.buffer = []
        self.keyframes = []
        pass


# Read lm2 entry from BODY.HQR
def read_lba2_model(lm2):
    r = EntryReader(lm2)

    # # HEADER # #
    body_flag = r.s32()  # 0x00
    unk1 = r.s32()  # 0x04
    x_min = r.s32()  # 0x08
    x_max = r.s32()  # 0x0C
    y_min = r.s32()  # 0x10
    y_max = r.s32()  # 0x14
    z_min = r.s32()  # 0x18
    z_max = r.s32()  # 0x1C
    bones_size = r.u32()  # 0x20
    bones_offset = r.u32()  # 0x24
    vertices_size = r.u32()  # 0x28
    vertices_offset = r.u32()  # 0x2C
    normals_size = r.u32()  # 0x30
    normals_offset = r.u32()  # 0x34
    unk1_size = r.u32()  # 0x38
    unk1_offset = r.u32()  # 0x3C
    polygons_size = r.u32()  # 0x40
    polygons_offset = r.u32()  # 0x44
    lines_size = r.u32()  # 0x48
    lines_offset = r.u32()  # 0x4C
    spheres_size = r.u32()  # 0x50
    spheres_offset = r.u32()  # 0x54
    uv_groups_size = r.u32()  # 0x58
    uv_groups_offset = r.u32()  # 0x5C
    version = body_flag & 0xff
    has_animation = body_flag & (1 << 8)
    no_sort = body_flag & (1 << 9)
    has_transparency = body_flag & (1 << 10)

    # # BONE # #
    r.goto(bones_offset)
    bones = []
    for i in range(bones_size):
        bone = OriginalBone()
        bone.parent = r.u16()
        bone.vertex = r.u16()
        bone.unk1 = r.u16()
        bone.unk2 = r.u16()
        """
        print(
            "Bone" + str(i) +
            ", parent: " + str(bone.parent) +
            ", vertex: " + str(bone.vertex) +
            ", unk1: " + str(bone.unk1) +
            ", unk2: " + str(bone.unk2))
        """
        bones.append(bone)

    # # VERTEX # #
    r.goto(vertices_offset)
    vertices = []
    for i in range(vertices_size):
        vertex = Vertex()
        vertex.index = i
        vertex.x = r.s16() * WORLD_SCALE
        vertex.y = r.s16() * WORLD_SCALE
        vertex.z = r.s16() * WORLD_SCALE
        vertex.bone = r.u16()
        vertices.append(vertex)
    old_vertices = copy.deepcopy(vertices)
    for i in range(vertices_size):
        vertex = vertices[i]
        found_root = False
        next_bone = bones[vertex.bone]
        while found_root is False:
            vertex.x += old_vertices[next_bone.vertex].x
            vertex.y += old_vertices[next_bone.vertex].y
            vertex.z += old_vertices[next_bone.vertex].z
            if next_bone.parent > 1000:
                found_root = True
            else:
                next_bone = bones[next_bone.parent]
        """
        print(
            "x: " + str(vertex.x) +
            ", y: " + str(vertex.y) +
            ", z: " + str(vertex.z) +
            ", bone: " + str(vertex.bone))
        """
    vert_groups = []
    for i in range(len(bones)):
        group = []
        for j in range(len(vertices)):
            if vertices[j].bone == i:
                group.append(j)
        vert_groups.append(group)

    # # NORMAL # #
    r.goto(normals_offset)
    normals = []
    for i in range(normals_size):
        normal = Normal()
        normal.x = r.s16() * WORLD_SCALE
        normal.y = r.s16() * WORLD_SCALE
        normal.z = r.s16() * WORLD_SCALE
        normal.unk1 = r.u16()
        normals.append(normal)
        """
        print(
            "x: " + str(normal.x) +
            ", y: " + str(normal.y) +
            ", z: " + str(normal.z) +
            ", unk1: " + str(normal.unk1))
        """

    # # UNKNOWN1 # #
    r.goto(unk1_offset)
    unknown1s = []
    for i in range(unk1_size):
        unknown1 = Unknown1()
        unknown1.unk1 = r.u16()
        unknown1.unk2 = r.u16()
        unknown1.unk3 = r.u16()
        unknown1.unk4 = r.u16()
        """
        print(
            "Unknown1" + str(i) +
            ", unk1: " + str(unknown1.unk1) +
            ", unk2: " + str(unknown1.unk2) +
            ", unk3: " + str(unknown1.unk3) +
            ", unk4: " + str(unknown1.unk4))
        """
        unknown1s.append(unknown1)

    # # POLYGON # #
    r.goto(polygons_offset)
    polygons = []
    offset = r.currentIndex
    start_point = r.currentIndex
    while offset < start_point + (lines_offset - polygons_offset):
        render_type = r.u16()
        num_polygons = r.u16()
        section_size = r.u16()
        unk1 = r.u16()
        offset += 8

        if section_size == 0:
            break

        block_size = ((section_size - 8) / num_polygons)
        for i in range(num_polygons):
            poly = load_polygon(r, offset, render_type, block_size)
            polygons.append(poly)
            offset += block_size

    # # LINE # #
    r.goto(lines_offset)
    lines = []
    for i in range(lines_size):
        line = Line()
        line.unk1 = r.u16()
        line.colour = int(math.floor((r.u16() & 0x00FF) / 16))
        line.vertex1 = r.u16()
        line.vertex2 = r.u16()
        """
        print(
            "unk1: " + str(line.unk1) +
            ", colour: " + str(line.colour) +
            ", vertex1: " + str(line.vertex1) +
            ", vertex2: " + str(line.vertex2))
        """
        lines.append(line)

    # # SPHERE # #
    r.goto(spheres_offset)
    spheres = []
    for i in range(spheres_size):
        sphere = Sphere()
        sphere.unk1 = r.u16()
        sphere.colour = int(math.floor((r.u16() & 0x00FF) / 16))
        sphere.vertex = r.u16()
        sphere.size = r.u16()
        """
        print(
            "unk1: " + str(sphere.unk1) +
            ", colour: " + str(sphere.colour) +
            ", vertex: " + str(sphere.vertex) +
            ", size: " + str(sphere.size))
        """
        spheres.append(sphere)

    # # TEXTURE # #
    r.goto(uv_groups_offset)
    uvgroups = []
    for i in range(uv_groups_size):
        uvgroup = UVGroup()
        uvgroup.x = r.u8()
        uvgroup.y = r.u8()
        uvgroup.w = r.u8()
        uvgroup.h = r.u8()
        """"
        print(
            "x: " + str(uvgroup.x) +
            ", y: " + str(uvgroup.y) +
            ", w: " + str(uvgroup.w) +
            ", h: " + str(uvgroup.h))
        """
        uvgroups.append(uvgroup)

    lba2_model = LBA2Model()
    lba2_model.vertices = vertices
    lba2_model.bones = bones
    lba2_model.normals = normals
    lba2_model.polygons = polygons
    lba2_model.lines = lines
    lba2_model.spheres = spheres
    lba2_model.uvgroups = uvgroups
    lba2_model.vertgroups = vert_groups
    return lba2_model


def load_polygon(data, offset, render_type, block_size):
    data.goto(offset)  # is it needed?
    poly = Polygon()
    poly.numVertex = 4 if (render_type & 0x8000) else 3
    poly.hasExtra = (render_type & 0x4000) is True
    poly.hasTex = (render_type & 0x8 and block_size > 16) is True
    poly.hasTransparency = (render_type == 2)
    """
    print(
        "numVertex: " + str(poly.numVertex) +
        ", hasExtra: " + str(poly.hasExtra) +
        ", hasTex: " + str(poly.hasTex) +
        ", hasTransparency: " + str(poly.hasTransparency))
    """
    poly.vertex = []
    for i in range(poly.numVertex):
        poly.vertex.append(data.u16())

    if poly.hasTex and poly.numVertex == 3:
        poly.tex = data.u8()

    data.goto(offset + 8)
    poly.colour = int(math.floor((data.u16() & 0x00FF) / 16))

    poly.intensity = data.s16()
    data.goto(offset + 12)
    if poly.hasTex:
        for i in range(poly.numVertex):
            data.skip(1)
            poly.u.append(data.u8())
            data.skip(1)
            poly.v.append(data.u8())

        if poly.numVertex == 4:
            data.goto(offset + 27)
            poly.tex = data.u8()
    return poly


def bone_generator(source_bones, source_verts):
    bone_count = len(source_bones)
    maya_bones = []
    bones = [None] * bone_count
    # setup bones
    for i in range(bone_count):
        g_bone = GeneratedBone()
        bone = source_bones[i]
        vert = source_verts[bone.vertex]
        g_bone.parent = bone.parent
        g_bone.pos = (vert.x, vert.y, vert.z)
        maya_bones.append(g_bone)

    created_bones = 0
    while created_bones != bone_count:
        for i in range(bone_count):
            bone = maya_bones[i]
            if bone.created is True:
                continue
            if bone.parent > 1000:
                root_bone = pm.joint(p=bone.pos, name='joint0', rad=0.2)
                root_bone.setRotationOrder('YZX', True)
                bones[0] = root_bone
                bone.created = True
                created_bones += 1
            else:
                # look if parent has been already created
                parent_bone = maya_bones[bone.parent]
                if parent_bone.created is True:
                    # has bone parent
                    pm.select(bones[bone.parent])
                    bn = pm.joint(p=bone.pos, name='joint' + str(i), rad=0.2)
                    bn.setRotationOrder('YZX', True)
                    bones[i] = bn
                    bone.created = True
                    created_bones += 1
    return bones


def mesh_generator(source_verts, source_polys, source_norms, materials, source_bones, gen_bones, settings):
    vertex_count = len(source_verts)
    face_count = len(source_polys)

    vertices = OpenMaya.MFloatPointArray()
    for i in range(len(source_verts)):
        vert = source_verts[i]
        vertices.append(OpenMaya.MFloatPoint(vert.x, vert.y, vert.z))

    face_vertexes = OpenMaya.MIntArray()
    vertex_indexes = OpenMaya.MIntArray()
    for i in range(len(source_polys)):
        poly = source_polys[i]
        face_vertexes.append(poly.numVertex)
        vertex_indexes += poly.vertex

    mesh_object = OpenMaya.MObject()
    mesh = OpenMaya.MFnMesh()
    mesh.create(vertices, face_vertexes,
                vertex_indexes, [], [], mesh_object)
    mesh.updateSurface()
    py_obj = pm.ls(mesh.name())[0]

    if settings.use_palette:
        face_list = []
        for i in range(len(materials)):
            faces = [materials[i]]
            for j in range(face_count):
                if source_polys[j].colour == materials[i]:
                    faces.append(j)
            if len(faces) > 0:
                face_list.append(faces)

        for i in range(len(face_list)):
            if len(face_list[i]) == 1:
                continue
            m_faces = []
            for j in range(len(face_list[i])):
                if j == 0:
                    continue
                m_faces.append(py_obj.f[face_list[i][j]])
            sg = "paletteSG" + str(face_list[i][0])
            pm.sets(sg, edit=True, forceElement=m_faces)
    else:
        pm.sets("initialShadingGroup", edit=True, forceElement=py_obj)

    space = OpenMaya.MSpace.kObject
    for i in range(len(source_norms)):
        norm = source_norms[i]
        normal = OpenMaya.MVector(norm.x, norm.y, norm.z)
        mesh.setVertexNormal(normal, i, space)

    if settings.use_rigging:
        cluster = pm.skinCluster(gen_bones[0], py_obj, tsb=True, mi=1, hmf=1.0, dr=10, nw=0)
        # create vertex groups
        vertex_groups = []
        for i in range(len(source_bones)):
            if i != 0:
                pm.skinCluster(cluster, edit=True, ai=gen_bones[i], tsb=True, hmf=1.0, dr=10, wt=0)
            group = []
            for j in range(vertex_count):
                if source_verts[j].bone == i:
                    group.append(j)
            vertex_groups.append(group)
        # set influences
        transform_zeros = []
        for i in range(len(source_bones)):
            value = [gen_bones[i], 0]
            transform_zeros.append(value)
        for i in range(len(vertex_groups)):
            group = vertex_groups[i]
            pm.select(clear=True)
            # select vertices
            for j in range(len(group)):
                pm.select(py_obj.vtx[group[j]], add=True)
            for j in range(len(transform_zeros)):
                transform_zeros[j][1] = 1 if i == j else 0
            pm.skinPercent(cluster, transformValue=transform_zeros, nrm=True)
    return mesh.name()


def sphere_generator(source_sphrs, source_verts, gen_bones, settings):
    spheres = []
    for i in range(len(source_sphrs)):
        sphere = source_sphrs[i]
        core_vert = source_verts[sphere.vertex]
        coords = [core_vert.x, core_vert.y, core_vert.z]

        poly_transform, poly_sphere = pm.polySphere(
            name="Sphere" + str(i),
            r=sphere.size * WORLD_SCALE,
            sx=settings.sphere_resolution, sy=settings.sphere_resolution)
        poly_transform.translate.set(coords)
        poly_transform.rotate.set([90, 0, 0])
        poly_shape = poly_transform.getShape()

        if settings.use_palette:
            sg = "paletteSG" + str(sphere.colour)
            pm.sets(
                sg,
                edit=True,
                forceElement=poly_transform)

        pm.polySoftEdge(a=180)
        if settings.use_rigging:
            pm.skinCluster(gen_bones[core_vert.bone], poly_shape, tsb=True)

        spheres.append(poly_shape)
    return spheres


def line_generator(source_lines, source_verts, gen_bones, settings):
    lines = []
    for i in range(len(source_lines)):
        line = source_lines[i]
        vert1 = source_verts[line.vertex1]
        vert2 = source_verts[line.vertex2]
        dx = vert2.x - vert1.x
        dy = vert2.y - vert1.y
        dz = vert2.z - vert1.z
        dist = math.sqrt(dx ** 2 + dy ** 2 + dz ** 2)

        poly_transform, poly_cylinder = pm.polyCylinder(
            n="Line" + str(i),
            h=dist, r=settings.line_radius, sa=settings.line_resolution)
        poly_transform.translate.set((
            dx / 2 + vert1.x,
            dy / 2 + vert1.y,
            dz / 2 + vert1.z))
        phi = math.degrees(math.atan2(dz, -dx))
        theta = math.degrees(math.acos(dy / dist))
        poly_transform.setRotationOrder('XZY', True)
        poly_transform.rotate.set([0, phi, theta])
        poly_shape = poly_transform.getShape()

        if settings.use_palette:
            sg = "paletteSG" + str(line.colour)
            pm.sets(
                sg,
                edit=True,
                forceElement=poly_transform)
        pm.polySoftEdge(a=180)
        if settings.use_rigging:
            pm.select(d=True)
            cluster = pm.skinCluster(gen_bones[vert1.bone], gen_bones[vert2.bone], poly_shape, tsb=True)
            if vert1.bone != vert2.bone:
                pm.select(poly_shape.vtx[:3])
                pm.skinPercent(cluster, transformValue=[(gen_bones[vert1.bone], 1), (gen_bones[vert2.bone], 0)])
                pm.select(d=True)
                pm.select(poly_shape.vtx[3:])
                pm.skinPercent(cluster, transformValue=[(gen_bones[vert1.bone], 0), (gen_bones[vert2.bone], 1)])
        lines.append(poly_shape)
    pm.select(d=True)
    return lines


def read_lba2_anim(anm):
    r = EntryReader(anm)
    anim = Anim()
    anim.num_keyframes = r.u16()
    anim.num_boneframes = r.u16()
    anim.loop_frame = r.u16()
    anim.unk1 = r.u16()
    anim.keyframes = []
    for i in range(anim.num_keyframes):
        keyframe = Keyframe()
        keyframe.length = r.u16()
        keyframe.x = r.s16() * WORLD_SCALE
        keyframe.y = r.s16() * WORLD_SCALE
        keyframe.z = r.s16() * WORLD_SCALE
        keyframe.can_fall = False
        keyframe.boneframes = []
        """
        print(
            "numKeyframe: " + str(i) +
            ", x: " + str(keyframe.x) +
            ", y: " + str(keyframe.y) +
            ", z: " + str(keyframe.z))
        """
        for j in range(anim.num_boneframes):
            bf_return = load_boneframe(r)
            boneframe = bf_return[0]
            can_fall = bf_return[1]
            keyframe.can_fall = keyframe.can_fall or can_fall
            keyframe.boneframes.append(boneframe)
        anim.keyframes.append(keyframe)
    return anim


def load_boneframe(reader):
    boneframe = Boneframe()
    boneframe.bone_type = reader.s16()
    can_fall = False
    multiplier = 360. / 4096.

    x = reader.s16()
    y = reader.s16()
    z = reader.s16()

    if boneframe.bone_type == 0:
        boneframe.vector = (
            (multiplier * x),
            (multiplier * y),
            (multiplier * z))
    else:
        boneframe.vector = (x * WORLD_SCALE, y * WORLD_SCALE, z * WORLD_SCALE)
        can_fall = True
    return boneframe, can_fall


def rotation_calculator(prev, new):
    prev_v = prev
    new_v = new
    calc_v = [0, 0, 0]
    for i in range(len(prev_v)):
        diff_v = new_v[i] - prev_v[i]
        if diff_v < -180:
            diff_v += 360
        elif diff_v > 180:
            diff_v -= 360
        computed_v = prev_v[i] + diff_v
        calc_v[i] = computed_v
    return calc_v, prev_v


def add_key(bone, origin_bone, tm, is_rotate, is_translate):
    time = str((tm / 100.)) + 'sec'
    if is_rotate:
        pm.setKeyframe(bone, t=time, at='rotateX', v=0, ott='step', itt='linear')
        pm.setKeyframe(bone, t=time, at='rotateY', v=0, ott='step', itt='linear')
        pm.setKeyframe(bone, t=time, at='rotateZ', v=0, ott='step', itt='linear')
    if is_translate:
        pm.setKeyframe(bone, t=time, at='translateX', v=origin_bone[0], ott='step', itt='linear')
        pm.setKeyframe(bone, t=time, at='translateY', v=origin_bone[1], ott='step', itt='linear')
        pm.setKeyframe(bone, t=time, at='translateZ', v=origin_bone[2], ott='step', itt='linear')


def anim_importer(bones, animations, loading_box):
    global lba_path
    global anim_file

    if anim_file is None:
        anim_file = HQRReader(lba_path + "/ANIM.HQR")
    clips_list = ""

    origin_bones = []
    for i in range(len(bones)):
        origin_bones.append(bones[i].getTranslation())
    current_time = 0
    for i in range(len(animations)):
        pm.progressWindow(loading_box, edit=True, progress=50 + math.floor((50.0 / len(animations)) * i))
        lba_anim = read_lba2_anim(anim_file[animations[i].realIndex])
        cut_t = -1
        time = current_time
        start_t = time * 0.3
        # add first frame keys
        for b in range(len(bones)):
            if lba_anim.num_boneframes <= b:
                add_key(bones[b], origin_bones[b], time, True, True)
            else:
                is_rotate = True if lba_anim.keyframes[0].boneframes[b].bone_type == 0 else False
                if b != 0:
                    add_key(bones[b], origin_bones[b], time, not is_rotate, is_rotate)
        for b in range(len(bones)):
            prev_v = [0, 0, 0]
            bone = bones[b]
            time = current_time
            if b >= lba_anim.num_boneframes:
                continue  # skip bone if there are no boneframes
            # how many frames this anim has, if the loopframe is different from the last frame add 1 extra frame.
            length_frames = lba_anim.num_keyframes + 1 if lba_anim.loop_frame != (
                    lba_anim.num_keyframes - 1) else lba_anim.num_keyframes
            root_x = 0
            root_y = 0
            root_z = 0
            # process the curves simultaneously, it has to be this way!
            for d in range(length_frames):
                index = d
                last_key = False
                if d == length_frames - 1:  # if it's the last frame
                    index = lba_anim.loop_frame  # last frame is always the loopframe
                    last_key = True
                boneframe = lba_anim.keyframes[index].boneframes[b]
                time += lba_anim.keyframes[index].length / 10. if d != 0 else 0
                if d == lba_anim.loop_frame and cut_t == -1 and d != 0:
                    cut_t = time * 0.3
                time_string = str((time / 100.)) + 'sec'
                calc_v, prev_v = rotation_calculator(prev_v, boneframe.vector)
                bone_vector = boneframe.vector
                if b == 0:
                    boneframe.bone_type = 0
                    root_x += lba_anim.keyframes[index].x
                    root_y += lba_anim.keyframes[index].y
                    root_z += lba_anim.keyframes[index].z
                    bone_vector = (root_x, root_y, root_z)

                if boneframe.bone_type == 0:
                    pm.setKeyframe(bone, t=time_string, at='rotateX', v=calc_v[0],
                                   ott=('step' if last_key is True else 'linear'), itt='linear')
                    pm.setKeyframe(bone, t=time_string, at='rotateY', v=calc_v[1],
                                   ott=('step' if last_key is True else 'linear'), itt='linear')
                    pm.setKeyframe(bone, t=time_string, at='rotateZ', v=calc_v[2],
                                   ott=('step' if last_key is True else 'linear'), itt='linear')
                if boneframe.bone_type != 0 or b == 0:
                    pm.setKeyframe(bone, t=time_string, at='translateX', v=bone_vector[0] + origin_bones[b][0],
                                   ott=('step' if last_key is True else 'linear'), itt='linear')
                    pm.setKeyframe(bone, t=time_string, at='translateY', v=bone_vector[1] + origin_bones[b][1],
                                   ott=('step' if last_key is True else 'linear'), itt='linear')
                    pm.setKeyframe(bone, t=time_string, at='translateZ', v=bone_vector[2] + origin_bones[b][2],
                                   ott=('step' if last_key is True else 'linear'), itt='linear')
        end_t = time * 0.3
        current_time = time + 100
        if cut_t == -1:
            clips_list += str(i + 1).zfill(3) + ";" + str(start_t) + ";" + str(end_t) + ";"
        else:
            clips_list += str(i + 1).zfill(3) + "Start" + ";" + str(start_t) + ";" + str(cut_t) + ";"
            clips_list += str(i + 1).zfill(3) + "Loop" + ";" + str(cut_t) + ";" + str(end_t) + ";"

    if clips_list[-1] is ';':
        clips_list = clips_list.rstrip(';')

    print(clips_list)
    pm.delete(all=True, sc=True)


def create_materials(model_materials):
    # verify if there are palette materials
    current_materials = []
    for shading_engine in pm.ls(type=pm.nt.ShadingEngine):
        if len(shading_engine):
            for material in shading_engine.surfaceShader.listConnections():
                if 'palette' in str(material):
                    current_materials.append(int(filter(str.isdigit, str(material))))

    # create a material for each one of the palette values not added yet
    new_materials = [x for x in model_materials if x not in current_materials]
    for i in range(len(new_materials)):
        lba_color = palette[2 + new_materials[i] * 16]
        material = pm.shadingNode('lambert', asShader=1, name=('palette' + str(new_materials[i])))
        sg = pm.sets(renderable=1, noSurfaceShader=1, empty=1, name=('paletteSG' + str(new_materials[i])))
        pm.connectAttr((material + '.outColor'), (sg + '.surfaceShader'), f=1)
        pm.setAttr('palette%s.color' % new_materials[i], lba_color[0] / 255., lba_color[1] / 255.,
                   lba_color[2] / 255.)


def import_model(body_index, settings, loading_box):
    global body_file
    global palette
    global resources

    lba_model = read_lba2_model(body_file[body_index])
    materials = []
    if settings.use_palette:
        pm.progressWindow(loading_box, edit=True, status="Generating Palette...", progress=5)
        # get list with all used palette values
        for i in range(len(lba_model.polygons)):
            materials.append(lba_model.polygons[i].colour)
        for i in range(len(lba_model.spheres)):
            materials.append(lba_model.spheres[i].colour)
        for i in range(len(lba_model.lines)):
            materials.append(lba_model.lines[i].colour)
        materials = list(dict.fromkeys(materials))
        create_materials(materials)

    bones = None
    if settings.use_rigging:
        pm.progressWindow(loading_box, edit=True, status="Generating Bones...", progress=10)
        bones = bone_generator(lba_model.bones, lba_model.vertices)

    # generate the main mesh
    pm.progressWindow(loading_box, edit=True, status="Generating Mesh...", progress=15)
    model = mesh_generator(lba_model.vertices, lba_model.polygons, lba_model.normals, materials, lba_model.bones, bones,
                           settings)
    # generate the spheres
    pm.progressWindow(loading_box, edit=True, status="Generating Spheres...", progress=20)
    spheres = sphere_generator(lba_model.spheres, lba_model.vertices, bones, settings)
    # generate the lines
    pm.progressWindow(loading_box, edit=True, status="Generating Lines...", progress=25)
    lines = line_generator(lba_model.lines, lba_model.vertices, bones, settings)

    # unite all the rigged meshes
    pm.progressWindow(loading_box, edit=True, status="Unifying...", progress=40)
    pm.select(clear=True)
    pm.select(model, add=True)
    pm.polyAutoProjection()
    pm.select(clear=True)
    pm.select(model, add=True)
    pm.select(spheres, add=True)
    pm.select(lines, add=True)
    unified_mesh = None
    if len(lba_model.spheres) > 0 or len(lba_model.lines) > 0:
        unified_mesh = pm.polyUniteSkinned() if settings.use_rigging else pm.polyUnite()
    if settings.use_rigging:
        if unified_mesh is None:
            pm.select(model, r=True)
        else:
            pm.select(unified_mesh, r=True)
        pm.select(bones[0], add=True)
        pm.group()
        # ## Load Animations ## #
        if settings.use_animation:
            pm.progressWindow(loading_box, edit=True, status="Loading Animations...", progress=45)
            for resource in resources:
                for body in resource.bodies:
                    if body.realIndex == body_index:
                        if len(resource.animations) > 0:
                            pm.progressWindow(loading_box, edit=True, status="Generating Animations...", progress=50)
                            anim_importer(bones, resource.animations, loading_box)
                            pm.progressWindow(loading_box, endProgress=1)
                            return
        else:
            pm.progressWindow(loading_box, endProgress=1)


# ##### Maya Plugin Requirements ##### #

# Initialize the script plug-in
def initializePlugin(mobject):
    mplugin = OpenMayaMPx.MFnPlugin(mobject, "Bruno Tuma", "1.0")
    create_menus()

# Uninitialize the script plug-in
def uninitializePlugin(mobject):
    mplugin = OpenMayaMPx.MFnPlugin(mobject)
    pm.deleteUI(lba_importer_menu)

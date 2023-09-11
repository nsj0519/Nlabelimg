#!/usr/bin/env python
# -*- coding: utf8 -*-
import re
import sys
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement
from lxml import etree
import codecs
from libs.constants import DEFAULT_ENCODING
from libs.ustr import ustr


XML_EXT = '.xml'
ENCODE_METHOD = DEFAULT_ENCODING

class PascalVocWriter:

    def __init__(self, folder_name, filename, img_size, database_src='Unknown', local_img_path=None):
        self.folder_name = folder_name
        self.filename = filename
        self.database_src = database_src
        self.img_size = img_size
        self.box_list = []
        self.local_img_path = local_img_path
        self.verified = False#空格改变验证状态，图片背景变成绿色

    def prettify(self, elem):
        """
            Return a pretty-printed XML string for the Element.
        """
        rough_string = ElementTree.tostring(elem, 'utf8')
        root = etree.fromstring(rough_string)
        return etree.tostring(root, pretty_print=True, encoding=ENCODE_METHOD).replace("  ".encode(), "\t".encode())
        # minidom does not support UTF-8
        # reparsed = minidom.parseString(rough_string)
        # return reparsed.toprettyxml(indent="\t", encoding=ENCODE_METHOD)

    def gen_xml(self):
        """
            Return XML root
        """
        # Check conditions
        if self.filename is None or \
                self.folder_name is None or \
                self.img_size is None:
            return None

        top = Element('annotation')
        if self.verified:
            top.set('verified', 'yes')

        folder = SubElement(top, 'folder')
        folder.text = self.folder_name

        filename = SubElement(top, 'filename')
        filename.text = self.filename

        if self.local_img_path is not None:
            local_img_path = SubElement(top, 'path')
            local_img_path.text = self.local_img_path

        source = SubElement(top, 'source')
        database = SubElement(source, 'database')
        database.text = self.database_src

        size_part = SubElement(top, 'size')
        width = SubElement(size_part, 'width')
        height = SubElement(size_part, 'height')
        depth = SubElement(size_part, 'depth')
        width.text = str(self.img_size[1])
        height.text = str(self.img_size[0])
        if len(self.img_size) == 3:
            depth.text = str(self.img_size[2])
        else:
            depth.text = '1'

        segmented = SubElement(top, 'segmented')
        segmented.text = '0'
        return top

    def add_bnd_box(self, x_min, y_min, x_max, y_max, name, group_id, shape_type, difficult):
        bnd_box = {'xmin': x_min, 'ymin': y_min, 'xmax': x_max, 'ymax': y_max}
        bnd_box['name'] = name
        bnd_box['group_id'] = group_id
        bnd_box['shape_type'] = shape_type
        bnd_box['difficult'] = difficult
        self.box_list.append(bnd_box)

    def add_Other(self,points,name,group_id,shape_type,difficult):
        other_points = {'points':points}
        other_points['name'] = name
        other_points['group_id'] = group_id
        other_points['shape_type'] = shape_type
        other_points['difficult'] = difficult
        self.box_list.append(other_points)

    def append_objects(self, top):
        for each_object in self.box_list:
            object_item = SubElement(top, 'object')
            name = SubElement(object_item, 'name')
            name.text = ustr(each_object['name'])
            group = SubElement(object_item, 'group_id')
            if each_object['group_id'] is None:
                group.text = ustr("none")
            else:
                group.text = ustr(str(each_object['group_id']))
            shape_type = SubElement(object_item, 'shape_type')
            shape_type.text = ustr(each_object['shape_type'])

            pose = SubElement(object_item, 'pose')
            pose.text = "Unspecified"
            truncated = SubElement(object_item, 'truncated')
            difficult = SubElement(object_item, 'difficult')
            difficult.text = str(bool(each_object['difficult']) & 1)

            if each_object["shape_type"] == "rectangle":
                if int(float(each_object['ymax'])) == int(float(self.img_size[0])) or (
                        int(float(each_object['ymin'])) == 1):
                    truncated.text = "1"  # max == height or min
                elif (int(float(each_object['xmax'])) == int(float(self.img_size[1]))) or (
                        int(float(each_object['xmin'])) == 1):
                    truncated.text = "1"  # max == width or min
                else:
                    truncated.text = "0"
                bnd_box = SubElement(object_item, 'bndbox')
                x_min = SubElement(bnd_box, 'xmin')
                x_min.text = str(each_object['xmin'])
                y_min = SubElement(bnd_box, 'ymin')
                y_min.text = str(each_object['ymin'])
                x_max = SubElement(bnd_box, 'xmax')
                x_max.text = str(each_object['xmax'])
                y_max = SubElement(bnd_box, 'ymax')
                y_max.text = str(each_object['ymax'])

            elif each_object["shape_type"] == "polygon" or each_object["shape_type"] == "linestrip":
                polygon_Points = SubElement(object_item, each_object["shape_type"])
                points = SubElement(polygon_Points, 'points')
                point_str = ""
                truncated_str = "0"
                for p in each_object['points']:
                    point_str += f"({p[0]},{p[1]})"
                    if int(float(p[0])) == int(float(self.img_size[1])) or (int(float(p[0])) == 1):
                        truncated_str = "1"  # max == height or min
                    elif int(float(p[1])) == int(float(self.img_size[0])) or (int(float(p[1])) == 1):
                        truncated_str = "1"
                    truncated.text = truncated_str
                points.text = point_str

            elif each_object["shape_type"] == "circle":
                circle_Points = SubElement(object_item, 'circle')
                C_x = SubElement(circle_Points, 'center_x')
                C_x.text = str(each_object['points'][0][0])
                C_y = SubElement(circle_Points, 'center_y')
                C_y.text = str(each_object['points'][0][1])
                R_x = SubElement(circle_Points, 'other_x')
                R_x.text = str(each_object['points'][1][0])
                R_y = SubElement(circle_Points, 'other_y')
                R_y.text = str(each_object['points'][1][1])
                if each_object['points'][2][0] == 1 or each_object['points'][3][1] == 1:
                    truncated.text = "1"
                elif each_object['points'][4][0] == int(float(self.img_size[1])) or each_object['points'][5][1] == int(float(self.img_size[0])):
                    truncated.text = "1"
                else:
                    truncated.text = "0"

            elif each_object["shape_type"] == "line":
                line_Points = SubElement(object_item, 'line')
                F_x = SubElement(line_Points, 'first_x')
                F_x.text = str(each_object['points'][0][0])
                F_y = SubElement(line_Points, 'first_y')
                F_y.text = str(each_object['points'][0][1])
                L_x = SubElement(line_Points, 'last_x')
                L_x.text = str(each_object['points'][1][0])
                L_y = SubElement(line_Points, 'last_y')
                L_y.text = str(each_object['points'][1][1])
                if each_object['points'][0][0] == 1 or each_object['points'][0][1] == 1:
                    truncated.text = "1"
                elif each_object['points'][0][0] == int(float(self.img_size[1])) or each_object['points'][0][1] == int(float(self.img_size[0])):
                    truncated.text = "1"
                elif each_object['points'][1][0] == 1 or each_object['points'][1][1] == 1:
                    truncated.text = "1"
                elif each_object['points'][1][0] == int(float(self.img_size[1])) or each_object['points'][1][1] == int(float(self.img_size[0])):
                    truncated.text = "1"
                else:
                    truncated.text = "0"

            elif each_object["shape_type"] == "point":
                point_Points = SubElement(object_item, 'point')
                P_x = SubElement(point_Points, 'x')
                P_x.text = str(each_object['points'][0][0])
                P_y = SubElement(point_Points, 'y')
                P_y.text = str(each_object['points'][0][1])
                if each_object['points'][0][0] == 1 or each_object['points'][0][1] == 1:
                    truncated.text = "1"
                elif each_object['points'][0][0] == int(float(self.img_size[1])) or each_object['points'][0][1] == int(float(self.img_size[0])):
                    truncated.text = "1"
                else:
                    truncated.text = "0"


    def save(self, target_file=None):
        root = self.gen_xml()
        self.append_objects(root)
        out_file = None
        if target_file is None:
            out_file = codecs.open(
                self.filename + XML_EXT, 'w', encoding=ENCODE_METHOD)
        else:
            out_file = codecs.open(target_file, 'w', encoding=ENCODE_METHOD)

        prettify_result = self.prettify(root)
        out_file.write(prettify_result.decode('utf8'))
        out_file.close()


class PascalVocReader:

    def __init__(self, file_path):
        # shapes type:
        # [labbel, [(x1,y1), (x2,y2), (x3,y3), (x4,y4)], color, color, difficult]
        self.shapes = []
        self.file_path = file_path
        self.verified = False
        try:
            self.parse_xml()
        except:
            pass

    def get_shapes(self):
        return self.shapes

    def add_shape(self, label,group_id,shape_type, points, difficult):
        self.shapes.append((label,group_id,shape_type, points, None, None, difficult))

    def parse_xml(self):
        assert self.file_path.endswith(XML_EXT), "Unsupported file format"
        parser = etree.XMLParser(encoding=ENCODE_METHOD)
        xml_tree = ElementTree.parse(self.file_path, parser=parser).getroot()
        filename = xml_tree.find('filename').text
        try:
            verified = xml_tree.attrib['verified']
            if verified == 'yes':
                self.verified = True
        except KeyError:
            self.verified = False

        for object_iter in xml_tree.findall('object'):
            points = []
            try:
                group_id = object_iter.find('group_id').text
                shape_type = object_iter.find('shape_type').text
            except:
                group_id = None
                shape_type = "rectangle"
            label = object_iter.find('name').text
            difficult = False
            if object_iter.find('difficult') is not None:
                difficult = bool(int(object_iter.find('difficult').text))

            if shape_type == "rectangle":
                bnd_box = object_iter.find("bndbox")
                x_min = int(float(bnd_box.find('xmin').text))
                y_min = int(float(bnd_box.find('ymin').text))
                x_max = int(float(bnd_box.find('xmax').text))
                y_max = int(float(bnd_box.find('ymax').text))
                points = [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]

            elif shape_type == "polygon" or shape_type == "linestrip":
                points_str = object_iter.find(shape_type).find("points").text
                pattern = r"\((\d+),(\d+)\)"
                results = re.findall(pattern, points_str)
                for point in results:
                    points.append((int(point[0]), int(point[1])))

            elif shape_type == "circle":
                C_x = int(float(object_iter.find("circle").find("center_x").text))
                C_y = int(float(object_iter.find("circle").find("center_y").text))
                R_x = int(float(object_iter.find("circle").find("other_x").text))
                R_y = int(float(object_iter.find("circle").find("other_y").text))
                points = [(C_x, C_y), (R_x, R_y)]

            elif shape_type == "line":
                F_x = int(float(object_iter.find("line").find("first_x").text))
                F_y = int(float(object_iter.find("line").find("first_y").text))
                L_x = int(float(object_iter.find("line").find("last_x").text))
                L_y = int(float(object_iter.find("line").find("last_y").text))
                points = [(F_x, F_y), (L_x, L_y)]

            elif shape_type == "point":
                P_x = int(float(object_iter.find("point").find("x").text))
                P_y = int(float(object_iter.find("point").find("y").text))
                points = [(P_x, P_y)]
            # Add chris
            self.add_shape(label,group_id,shape_type, points, difficult)
        return True

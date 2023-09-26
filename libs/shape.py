#!/usr/bin/python
# -*- coding: utf-8 -*-
import math

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs import utils
import sys

DEFAULT_LINE_COLOR = QColor(0, 255, 0, 128)
DEFAULT_FILL_COLOR = QColor(255, 0, 0, 128)
DEFAULT_SELECT_LINE_COLOR = QColor(255, 255, 255)
DEFAULT_SELECT_FILL_COLOR = QColor(0, 128, 255, 155)
DEFAULT_VERTEX_FILL_COLOR = QColor(0, 255, 0, 255)
DEFAULT_HVERTEX_FILL_COLOR = QColor(255, 0, 0)


class Shape(object):
    P_SQUARE, P_ROUND = range(2)

    MOVE_VERTEX, NEAR_VERTEX = range(2)

    # The following class variables influence the drawing
    # of _all_ shape objects.
    line_color = DEFAULT_LINE_COLOR
    fill_color = DEFAULT_FILL_COLOR
    select_line_color = DEFAULT_SELECT_LINE_COLOR
    select_fill_color = DEFAULT_SELECT_FILL_COLOR
    vertex_fill_color = DEFAULT_VERTEX_FILL_COLOR
    h_vertex_fill_color = DEFAULT_HVERTEX_FILL_COLOR
    point_type = P_ROUND
    point_size = 8
    scale = 1.0
    label_font_size = 8

    def __init__(self, label=None, line_color=None,shape_type=None,group_id=None, difficult=False, paint_label=False):
        self.label = label
        self.group_id = None if group_id =="none" else group_id
        self.points = []
        self.point_labels = []
        self.fill = False
        self.selected = False
        self.difficult = difficult
        self.paint_label = paint_label
        self.shape_type = shape_type

        self._highlight_index = None
        self._highlight_mode = self.NEAR_VERTEX
        self._highlight_settings = {
            self.NEAR_VERTEX: (4, self.P_ROUND),
            self.MOVE_VERTEX: (1.5, self.P_SQUARE),
        }

        self._closed = False

        if line_color is not None:
            # Override the class line_color attribute
            # with an object attribute. Currently this
            # is used for drawing the pending line a different color.
            self.line_color = line_color

    def close(self):
        self._closed = True
    def addPoint(self, point, label=1):
        if self.points and point == self.points[0]:#如果点和第一个点重合，就闭合
            self.close()
        else:
            self.points.append(point)#否则就添加点
            self.point_labels.append(label)#添加标签
    def reach_max_points(self):
        if len(self.points) >= 4:
            return True
        return False
    def canAddPoint(self):
        return self.shape_type in ["polygon", "linestrip","rectangle"]
    # def add_point(self, point):
    #     if not self.reach_max_points():
    #         self.points.append(point)

    def pop_point(self):
        if self.points:
            return self.points.pop()
        return None
    def insertPoint(self, i, point, label=1):
        self.points.insert(i, point)
        self.point_labels.insert(i, label)

    def removePoint(self, i):
        if not self.canAddPoint() or self.shape_type == "rectangle":
            # logger.warning(
            #     "Cannot remove point from: shape_type=%r",
            #     self.shape_type,
            # )
            return

        if self.shape_type == "polygon" and len(self.points) <= 3:
            # logger.warning(
            #     "Cannot remove point from: shape_type=%r, len(points)=%d",
            #     self.shape_type,
            #     len(self.points),
            # )
            return

        if self.shape_type == "linestrip" and len(self.points) <= 2:
            # logger.warning(
            #     "Cannot remove point from: shape_type=%r, len(points)=%d",
            #     self.shape_type,
            #     len(self.points),
            # )
            return

        self.points.pop(i)
        self.point_labels.pop(i)
    def is_closed(self):
        return self._closed

    def set_open(self):
        self._closed = False
    def getRectFromLine(self, pt1, pt2, pt3, pt4):
        x1, y1 = pt1.x(), pt1.y()
        x3, y3 = pt3.x(), pt3.y()
        return QRectF(x1, y1, x3 - x1, y3 - y1)
    def getCircleRectFromLine(self, line):
        """Computes parameters to draw with `QPainterPath::addEllipse`"""
        if len(line) != 2:
            return None
        (c, point) = line
        r = line[0] - line[1]
        d = math.sqrt(math.pow(r.x(), 2) + math.pow(r.y(), 2))
        rectangle = QRectF(c.x() - d, c.y() - d, 2 * d, 2 * d)
        return rectangle
    def paint(self, painter):
        if self.points:
            color = self.select_line_color if self.selected else self.line_color
            pen = QPen(color)
            # Try using integer sizes for smoother drawing(?)
            pen.setWidth(max(1, int(round(2.0 / self.scale))))
            painter.setPen(pen)

            line_path = QPainterPath()
            vertex_path = QPainterPath()
            negative_vrtx_path = QPainterPath()
            # line_path.moveTo(self.points[0])
            # Uncommenting the following line will draw 2 paths
            # for the 1st vertex, and make it non-filled, which
            # may be desirable.
            # self.drawVertex(vertex_path, 0)

            # for i, p in enumerate(self.points):
            #     line_path.lineTo(p)
            #     self.draw_vertex(vertex_path, i)
            # if self.is_closed():
            #     line_path.lineTo(self.points[0])
            if self.shape_type == "rectangle":
                assert len(self.points) in [1, 2,3,4]
                if len(self.points) == 4:
                    rectangle = self.getRectFromLine(*self.points)
                    line_path.addRect(rectangle)
                for i in range(len(self.points)):
                    self.draw_vertex(vertex_path, i)
            elif self.shape_type == "circle":
                assert len(self.points) in [1, 2]
                if len(self.points) == 2:
                    rectangle = self.getCircleRectFromLine(self.points)
                    line_path.addEllipse(rectangle)
                for i in range(len(self.points)):
                    self.draw_vertex(vertex_path, i)
            elif self.shape_type == "linestrip":
                line_path.moveTo(self.points[0])
                for i, p in enumerate(self.points):
                    line_path.lineTo(p)
                    self.draw_vertex(vertex_path, i)
            elif self.shape_type == "points":
                assert len(self.points) == len(self.point_labels)
                for i, (p, l) in enumerate(
                    zip(self.points, self.point_labels)
                ):
                    if l == 1:
                        self.draw_vertex(vertex_path, i)
                    else:
                        self.draw_vertex(negative_vrtx_path, i)
            else:
                line_path.moveTo(self.points[0])
                # Uncommenting the following line will draw 2 paths
                # for the 1st vertex, and make it non-filled, which
                # may be desirable.
                # self.drawVertex(vrtx_path, 0)
                for i, p in enumerate(self.points):
                    line_path.lineTo(p)
                    self.draw_vertex(vertex_path, i)
                if self.is_closed():
                    line_path.lineTo(self.points[0])

            painter.drawPath(line_path)
            painter.drawPath(vertex_path)
            painter.fillPath(vertex_path, self.vertex_fill_color)

            # Draw text at the top-left在左上角绘制文本
            if self.paint_label:
                min_x = sys.maxsize
                min_y = sys.maxsize
                min_y_label = int(1.25 * self.label_font_size)
                for point in self.points:
                    min_x = min(min_x, point.x())
                    min_y = min(min_y, point.y())
                if min_x != sys.maxsize and min_y != sys.maxsize:
                    font = QFont()
                    font.setPointSize(self.label_font_size)
                    font.setBold(True)
                    painter.setFont(font)
                    if self.label is None:
                        self.label = ""
                    if min_y < min_y_label:
                        min_y += min_y_label
                    painter.drawText(min_x, min_y, self.label)

            if self.fill:#如果是填充的
                color = self.select_fill_color if self.selected else self.fill_color
                painter.fillPath(line_path, color)

    def draw_vertex(self, path, i):
        d = self.point_size / self.scale
        shape = self.point_type
        point = self.points[i]
        if i == self._highlight_index:
            size, shape = self._highlight_settings[self._highlight_mode]
            d *= size
        if self._highlight_index is not None:
            self.vertex_fill_color = self.h_vertex_fill_color
        else:
            self.vertex_fill_color = Shape.vertex_fill_color
        if shape == self.P_SQUARE:
            path.addRect(point.x() - d / 2, point.y() - d / 2, d, d)
        elif shape == self.P_ROUND:
            path.addEllipse(point, d / 2.0, d / 2.0)
        else:
            assert False, "unsupported vertex shape"

    def nearest_vertex(self, point, epsilon):
        for i, p in enumerate(self.points):
            if utils.distance(p - point) <= epsilon:
                return i
        return None
    def nearestEdge(self, point, epsilon):
        min_distance = float("inf")#用于将字符串"inf"转换为浮点数类型的正无穷大值
        post_i = None
        for i in range(len(self.points)):
            line = [self.points[i - 1], self.points[i]]
            dist = utils.distancetoline(point, line)
            if dist <= epsilon and dist < min_distance:
                min_distance = dist
                post_i = i
        return post_i
    def contains_point(self, point):
        return self.make_path().contains(point)

    def make_path(self):
        if self.shape_type == "rectangle":
            path = QPainterPath()
            if len(self.points) == 4:
                rectangle = self.getRectFromLine(*self.points)
                path.addRect(rectangle)
                return path
        elif self.shape_type == "circle":
            path = QPainterPath()
            if len(self.points) == 2:
                rectangle = self.getCircleRectFromLine(self.points)
                path.addEllipse(rectangle)
                return path
        else:
            path = QPainterPath(self.points[0])
            for p in self.points[1:]:
                path.lineTo(p)
            return path

    def bounding_rect(self):
        return self.make_path().boundingRect()

    def move_by(self, offset,pixma_w,pixma_h):
        if self.shape_type == "circle":
            if self.points[0].x()<=0 and offset.x()<0:
                return
            if self.points[0].x()>=pixma_w and offset.x()>0:
                return
            if self.points[0].y()<=0 and offset.y()<0:
                return
            if self.points[0].y()>=pixma_h and offset.y()>0:
                return
        # and  (self.points[0].x()<=0 or self.points[0].x()>= pixma_w or self.points[0].y()<=0 or self.points[0].y()>=pixma_h):
        #     print("out of range")
        #     return
        self.points = [p + offset for p in self.points]

    def move_vertex_by(self, i, offset):
        # print("move_vertex_by",offset)
        self.points[i] = self.points[i] + offset

    def highlight_vertex(self, i, action):
        self._highlight_index = i
        self._highlight_mode = action

    def highlight_clear(self):
        self._highlight_index = None

    def copy(self):
        shape = Shape("%s" % self.label)
        shape.points = [p for p in self.points]
        shape.fill = self.fill
        shape.selected = self.selected
        shape.shape_type = self.shape_type
        shape.group_id = self.group_id
        shape._closed = self._closed
        if self.line_color != Shape.line_color:
            shape.line_color = self.line_color
        if self.fill_color != Shape.fill_color:
            shape.fill_color = self.fill_color
        shape.difficult = self.difficult
        return shape

    def __len__(self):
        return len(self.points)

    def __getitem__(self, key):
        return self.points[key]

    def __setitem__(self, key, value):
        self.points[key] = value

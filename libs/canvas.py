# -*- coding: utf-8 -*-
try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

# from PyQt4.QtOpenGL import *

from libs.shape import Shape
from libs.utils import distance

CURSOR_DEFAULT = Qt.ArrowCursor
CURSOR_POINT = Qt.PointingHandCursor
CURSOR_DRAW = Qt.CrossCursor
CURSOR_MOVE = Qt.ClosedHandCursor
CURSOR_GRAB = Qt.OpenHandCursor

# class Canvas(QGLWidget):


class Canvas(QWidget):
    zoomRequest = pyqtSignal(int)
    scrollRequest = pyqtSignal(int, int)
    newShape = pyqtSignal()
    selectionChanged = pyqtSignal(bool)
    shapeMoved = pyqtSignal()
    drawingPolygon = pyqtSignal(bool)
    vertexSelected = pyqtSignal(bool)

    CREATE, EDIT = list(range(2))
    _createMode = None
    _fill_drawing = False
    epsilon = 11.0

    def __init__(self, *args, **kwargs):
        super(Canvas, self).__init__(*args, **kwargs)
        # Initialise local state.
        self.mode = self.EDIT
        self.shapes = []
        self.shapesBackups = []
        self.current = None
        self.selected_shape = None  # save the selected shape here
        self.selected_shape_copy = None
        self.drawing_line_color = QColor(0, 0, 255)
        self.drawing_rect_color = QColor(0, 0, 255)
        self.line = Shape(line_color=self.drawing_line_color)
        self.prev_point = QPointF()
        self.prevMovePoint = QPoint()
        self.offsets = QPointF(), QPointF()
        self.scale = 1.0
        self.label_font_size = 8
        self.pixmap = QPixmap()
        self.visible = {}
        self._hide_background = False
        self.hide_background = False
        self.h_shape = None
        self.prevhShape = None
        self.h_vertex = None
        self.prevhVertex = None
        self.hEdge = None
        self.prevhEdge = None
        self.movingShape = False
        self.snapping = True
        self.hShapeIsSelected = False
        self._painter = QPainter()
        self._cursor = CURSOR_DEFAULT
        # Menus:
        self.menus = (QMenu(), QMenu())
        # Set widget options.
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.WheelFocus)
        self.verified = False
        self.draw_square = False
        self.draw_double = False

        # initialisation for panning平移的初始化
        self.pan_initial_pos = QPoint()

    def set_drawing_color(self, qcolor):
        self.drawing_line_color = qcolor
        self.drawing_rect_color = qcolor

    def enterEvent(self, ev):
        self.override_cursor(self._cursor)

    def leaveEvent(self, ev):
        self.restore_cursor()

    def focusOutEvent(self, ev):
        self.restore_cursor()

    def isVisible(self, shape):
        return self.visible.get(shape, True)

    def drawing(self):
        return self.mode == self.CREATE

    def editing(self):
        return self.mode == self.EDIT

    def set_editing(self, value=True):
        self.mode = self.EDIT if value else self.CREATE
        if not value:  # EDIT -> CREATE
            self.un_highlight()
            self.de_select_shape()
        # CREATE -> EDIT
        self.prev_point = QPointF()
        self.repaint()

    def un_highlight(self):
        if self.h_shape:
            self.h_shape.highlight_clear()
            self.update()
        self.prevhShape = self.h_shape
        self.prevhVertex = self.h_vertex
        self.prevhEdge = self.hEdge
        self.h_shape = self.h_vertex = self.hEdge = None

    def selected_vertex(self):
        return self.h_vertex is not None

    def selected_Edge(self):
        return self.hEdge is not None

    @property
    def createMode(self):
        return self._createMode

    @createMode.setter
    def createMode(self, value):  # 如果value不在列表中，就报错
        if value not in [
            "polygon",
            "rectangle",
            "circle",
            "line",
            "point",
            "linestrip",
        ]:
            raise ValueError("Unsupported createMode: %s" % value)
        self._createMode = value
    def mouseMoveEvent(self, ev):
        """Update line with last point and current coordinates.用最后一点和当前坐标更新行"""
        pos = self.transform_pos(ev.pos())
        # Update coordinates in status bar if image is opened如果打开图像，更新状态栏中的坐标
        window = self.parent().window()
        if window.file_path is not None:
            self.parent().window().label_coordinates.setText(
                'X: %d; Y: %d' % (pos.x(), pos.y()))
        '''在 PyQt 中，当某个事件发生时，可以通过事件对象（例如鼠标事件或键盘事件）的 modifiers() 方法来获取与事件相关的修饰键状态。修饰键是指与普通按键同时按下的特殊键，如 Shift、Ctrl、Alt 等。
        QtCore.Qt.ShiftModifier 是 Qt 中的一个枚举值，表示 Shift 修饰键。通过将 ev.modifiers() 与 QtCore.Qt.ShiftModifier 进行按位与运算，可以判断 Shift 修饰键是否被按下。'''
        self.prevMovePoint = pos  # 不断更新鼠标移动的位置
        is_shift_pressed = ev.modifiers() & Qt.ShiftModifier
        # Polygon drawing.
        if self.drawing():#选则标注类型时候进入到该状态
            self.override_cursor(CURSOR_DRAW)#如果是标注模式，就将鼠标变成十字形状
            self.line.shape_type = self.createMode
            if self.current:#如果在标注一个对象的过程中
                # Display annotation width and height while drawing绘图时显示注释的宽度和高度
                current_width = abs(self.current[0].x() - pos.x())
                current_height = abs(self.current[0].y() - pos.y())
                self.parent().window().label_coordinates.setText(
                        'Width: %d, Height: %d / X: %d; Y: %d' % (current_width, current_height, pos.x(), pos.y()))
                color = self.drawing_line_color
                if self.out_of_pixmap(pos):
                    # Don't allow the user to draw outside the pixmap.
                    # Clip the coordinates to 0 or max,
                    # if they are outside the range [0, max]
                    # 不要允许用户在位图之外绘制。
                    # 剪辑坐标为0或max，
                    # 如果它们在[0,max]范围之外
                    size = self.pixmap.size()
                    clipped_x = min(max(0, pos.x()), size.width())
                    clipped_y = min(max(0, pos.y()), size.height())
                    pos = QPointF(clipped_x, clipped_y)

                elif self.snapping and len(self.current) > 1 and self.createMode == "polygon" and self.close_enough(pos, self.current[0]):#如果有两个点，且当前点和第一个点距离很近
                    # 如果满足以上条件，没有按下alt键，存在多个点，创建模式为多边形，且当前点与第一个点距离足够近
                    # Attract line to starting point and colorise to alert the
                    #将线吸引到起始点并着色以提醒
                    # user:
                    pos = self.current[0]
                    self.override_cursor(CURSOR_POINT)
                    self.current.highlight_vertex(0, Shape.NEAR_VERTEX)

                if self.createMode in ["polygon", "linestrip"]:
                    self.line.points = [self.current[-1], pos]
                    self.line.point_labels = [1, 1]
                elif self.createMode == "rectangle" and not self.draw_square:
                    self.line.points = [self.current[0], pos]
                    self.line.point_labels = [1, 1]
                    self.line.close()
                elif self.createMode == "rectangle" and self.draw_square:
                    init_pos = self.current[0]
                    min_x = init_pos.x()
                    min_y = init_pos.y()
                    min_size = min(abs(pos.x() - min_x), abs(pos.y() - min_y))  # 最短边作为尺寸
                    direction_x = -1 if pos.x() - min_x < 0 else 1
                    direction_y = -1 if pos.y() - min_y < 0 else 1
                    spos = QPointF(min_x + direction_x * min_size, min_y + direction_y * min_size)
                    self.line.points = [self.current[0], spos]
                    self.line.point_labels = [1, 1]
                    self.line.close()
                elif self.createMode == "circle":
                    self.line.points = [self.current[0], pos]
                    self.line.point_labels = [1, 1]
                    self.line.shape_type = "circle"
                elif self.createMode == "line":
                    self.line.points = [self.current[0], pos]
                    self.line.point_labels = [1, 1]
                    self.line.close()
                elif self.createMode == "point":
                    self.line.points = [self.current[0]]
                    self.line.point_labels = [1]
                    self.line.close()
                # 有一个点时候，鼠标移动时候，将当前点的坐标赋值给line的第二个点
                # else:
                #     self.line[1] = pos
                self.line.line_color = color
                self.prev_point = QPointF()
                self.current.highlight_clear()
            else:
                self.prev_point = pos
            self.repaint()
            return

        # Polygon copy moving.#鼠标右键拖动标注框是否会直接复制一个新的框跟着鼠标移动
        if Qt.RightButton & ev.buttons():#监控鼠标右键是否按下
            if self.selected_shape_copy and self.prev_point:
                self.override_cursor(CURSOR_MOVE)
                self.bounded_move_shape(self.selected_shape_copy, pos)
                self.repaint()
            elif self.selected_shape:
                self.selected_shape_copy = self.selected_shape.copy()
                self.repaint()
            return

        # Polygon/Vertex moving.#移动顶点或者多边形
        if Qt.LeftButton & ev.buttons():
            if self.selected_vertex():#选择顶点
                self.bounded_move_vertex(pos)
                # self.shapeMoved.emit()#设置为脏的，保存按钮可触发
                self.repaint()
                self.movingShape = True
                # Display annotation width and height while moving vertex移动顶点时显示注释的宽度和高度
                if self.h_shape.shape_type == "rectangle":
                    point1 = self.h_shape[1]
                    point3 = self.h_shape[3]
                    current_width = abs(point1.x() - point3.x())
                    current_height = abs(point1.y() - point3.y())
                    self.parent().window().label_coordinates.setText(
                            'Width: %d, Height: %d / X: %d; Y: %d' % (current_width, current_height, pos.x(), pos.y()))
            elif self.selected_Edge() and not self.snapping:#选择边
                self.bounded_move_edge(pos)
                self.repaint()
                self.movingShape = True
                self.prev_point = pos
                self.calculate_offsets(self.selected_shape, pos)
            elif self.selected_shape and self.prev_point:
                self.override_cursor(CURSOR_MOVE)
                self.bounded_move_shape(self.selected_shape, pos)
                self.movingShape = True
                self.repaint()
                # Display annotation width and height while moving shape
                if self.h_shape.shape_type == "rectangle":
                    point1 = self.selected_shape[1]
                    point3 = self.selected_shape[3]
                    current_width = abs(point1.x() - point3.x())
                    current_height = abs(point1.y() - point3.y())
                    self.parent().window().label_coordinates.setText(
                            'Width: %d, Height: %d / X: %d; Y: %d' % (current_width, current_height, pos.x(), pos.y()))
            else:
                # self.pan_initial_pos在鼠标按下时候赋值按下的坐标，这里按下后继续移动即计算与按下时候的偏移距离，触发滚动条滚动实现拖拽画面的效果
                delta_x = pos.x() - self.pan_initial_pos.x()
                delta_y = pos.y() - self.pan_initial_pos.y()
                self.scrollRequest.emit(delta_x, Qt.Horizontal)
                self.scrollRequest.emit(delta_y, Qt.Vertical)
                self.update()
            return

        # Just hovering over the canvas, 2 possibilities:
        # - Highlight shapes
        # - Highlight vertex
        # Update shape/vertex fill and tooltip value accordingly.
        # 只是悬停在画布上，2种可能性:
        # -高亮形状
        # -高亮顶点
        # 更新形状/顶点填充和工具提示值
        self.setToolTip("Image")
        # for shape in reversed([s for s in self.shapes if self.isVisible(s)]):
        for shape in sorted([s for s in self.shapes if self.isVisible(s)],key=lambda shape_i: (shape_i.bounding_rect().x(),shape_i.bounding_rect().y()),reverse=True):#按照xy坐标从大到小排序，处于包含状态的框就可以被优先选中
        # for shape in reversed([s for s in self.shapes if self.isVisible(s)]):
            # Look for a nearby vertex to highlight. If that fails,
            # check if we happen to be inside a shape.
            # 寻找一个附近的顶点高亮。如果失败了，
            # 检查我们是否恰好在一个形状内。
            index = shape.nearest_vertex(pos, self.epsilon)
            index_edge = shape.nearestEdge(pos, self.epsilon / self.scale)

            if index is not None:
                if self.selected_vertex():
                    self.h_shape.highlight_clear()
                # self.h_vertex, self.h_shape = index, shape
                self.prevhVertex = self.h_vertex = index
                self.prevhShape = self.h_shape = shape
                self.prevhEdge = self.hEdge
                self.hEdge = None
                shape.highlight_vertex(index, shape.MOVE_VERTEX)
                self.override_cursor(CURSOR_POINT)
                self.setToolTip("Click & drag to move point")
                self.setStatusTip(self.toolTip())
                self.update()
                break
            elif index_edge is not None and shape.canAddPoint():
                if self.selected_Edge():
                    self.h_shape.highlight_clear()
                self.prevhVertex = self.h_vertex
                self.h_vertex = None
                self.prevhShape = self.h_shape = shape
                self.prevhEdge = self.hEdge = index_edge
                shape.highlight_vertex(index, shape.MOVE_VERTEX)
                self.override_cursor(CURSOR_POINT)
                self.setToolTip(self.tr("Click to create point"))
                self.setStatusTip(self.toolTip())
                self.update()
                break
            elif shape.contains_point(pos):#判断鼠标是否在框内
                if self.selected_vertex():#如果已经选中顶点，就清除高亮
                    self.h_shape.highlight_clear()
                # self.h_vertex, self.h_shape = None, shape
                self.prevhVertex = self.h_vertex
                self.h_vertex = None
                self.prevhShape = self.h_shape = shape
                self.prevhEdge = self.hEdge
                self.hEdge = None
                self.setToolTip(
                    "Click & drag to move shape '%s'" % shape.label)
                self.setStatusTip(self.toolTip())
                self.override_cursor(CURSOR_GRAB)
                self.update()

                # Display annotation width and height while hovering inside在内部悬停时显示注释的宽度和高度
                if self.h_shape.shape_type == "rectangle":
                    point1 = self.h_shape[1]
                    point3 = self.h_shape[3]
                    current_width = abs(point1.x() - point3.x())
                    current_height = abs(point1.y() - point3.y())
                    self.parent().window().label_coordinates.setText(
                            'Width: %d, Height: %d / X: %d; Y: %d' % (current_width, current_height, pos.x(), pos.y()))
                break
            else:  # Nothing found, clear highlights, reset state.没有发现，高光显示清晰，重置状态
                self.un_highlight()
                self.override_cursor(CURSOR_DEFAULT)
    def addPointToEdge(self):
        shape = self.prevhShape
        index = self.prevhEdge
        point = self.prevMovePoint
        if shape is None or index is None or point is None:
            return
        shape.insertPoint(index, point)
        shape.highlight_vertex(index, shape.MOVE_VERTEX)
        self.h_shape = shape
        self.h_vertex = index
        self.hEdge = None
        self.movingShape = True

    def removeSelectedPoint(self):
        shape = self.prevhShape
        index = self.prevhVertex
        if shape is None or index is None:
            return
        shape.removePoint(index)
        shape.highlight_clear()
        self.h_shape = shape
        self.prevhVertex = None
        self.movingShape = True  # Save changes
    def mousePressEvent(self, ev):#鼠标按下事件触发
        is_shift_pressed = ev.modifiers() & Qt.ShiftModifier
        pos = self.transform_pos(ev.pos())
        if ev.button() == Qt.LeftButton:
            if self.drawing():
                if self.current:
                    # Add point to existing shape.向现有形状添加点
                    if self.createMode == "polygon":#如果是标注多边形，可以一直添加点，直到最后一点和第一点重合，此时结束该目标的标注
                        self.current.addPoint(self.line[1])
                        self.line[0] = self.current[-1]
                        if self.current.is_closed():
                            self.finalise()#结束标注，触发new_shape信号弹出标签选择框,完成一个shape对象的标注，将其加入到shapes列表中，弹出新建标注框的对话框，赋予信息.如果对话框取消，则删除该shape对象并且进入编辑状态
                    elif self.createMode =="rectangle":
                        self.handle_drawing(pos)
                    elif self.createMode in [ "circle", "line"]:#如果是矩形、圆、线，那么此前就已经有了一个点，现在添加第二个点即结束一个目标的标注。
                        assert len(self.current.points) == 1
                        self.current.points = self.line.points
                        self.finalise()
                    elif self.createMode == "linestrip":#如果是标注折线，可以可以一直添加点，直到同时按下ctrl键结束
                        self.current.addPoint(self.line[1])
                        self.line[0] = self.current[-1]
                        if int(ev.modifiers()) == Qt.ControlModifier:
                            self.finalise()

                elif not self.out_of_pixmap(pos):#否则如果按下鼠标左键时候，鼠标位置不在图片外
                    # Create new shape.创建新形状
                    self.current = Shape(#current是当前的形状,Shape是形状类
                        shape_type=self.createMode
                    )
                    self.current.addPoint(#添加一个点
                        pos, label=0 if is_shift_pressed else 1
                    )
                    if self.createMode == "point":#如果是标注点，即只有一个点，那么此时就结束了一个目标的标注
                        self.finalise()
                    else:
                        if self.createMode == "circle":
                            self.current.shape_type = "circle"
                        self.line.points = [pos, pos]#当标注类型是圆的时候，line也是shape对象，有两个point
                        self.line.point_labels = [1, 1]
                        self.set_hiding()
                        self.drawingPolygon.emit(True)#携带参数发射drawingPolygon信号，labelimg.py中接收到信号执行toggle_drawing_sensitive函数
                        #标注过程中,编辑按钮不可选状态，如果是非标注状态下，主动设置为编辑状态
                        self.update()

            else:
                if self.selected_Edge():#如果编辑时点击线条边缘,如果是polygon和linestrip，那么可以在线条上添加一个点.是rectangle，可以拖拽边改变大小
                    if self.prevhShape.shape_type in ["polygon", "linestrip"]:
                        self.addPointToEdge()#在线条上添加一个点
                elif (
                    self.selected_vertex()#否则选中顶点，并且按下shift键
                    and int(ev.modifiers()) == Qt.ShiftModifier
                ):
                    # Delete point if: left-click + SHIFT on a point删除点:在一个点上左键单击+ SHIFT
                    self.removeSelectedPoint()
                selection = self.select_shape_point(pos)#返回选中的点或者形状
                self.prev_point = pos
                if selection is None:#如果没有选中的点或者形状,更改鼠标样式，并且把按下的当前点坐标位置赋值给pan_initial_pos,
                # 以便在鼠标移动的时候，可以计算出鼠标移动的距离，从而拖拽移动图片
                    # pan
                    QApplication.setOverrideCursor(QCursor(Qt.OpenHandCursor))
                    self.pan_initial_pos = pos

        elif ev.button() == Qt.RightButton and self.editing():
            self.select_shape_point(pos)
            self.prev_point = pos
        self.update()

    def mouseReleaseEvent(self, ev):#鼠标释放事件触发
        if ev.button() == Qt.RightButton:
            menu = self.menus[bool(self.selected_shape_copy)]
            self.restore_cursor()
            if not menu.exec_(self.mapToGlobal(ev.pos()))\
               and self.selected_shape_copy:
                # Cancel the move by deleting the shadow copy.
                self.selected_shape_copy = None
                self.repaint()
        elif ev.button() == Qt.LeftButton and self.selected_shape:#如果有点击按下时选中过shape
            if self.selected_vertex():#如果按下时是顶点，松开时鼠标变手指
                self.override_cursor(CURSOR_POINT)#手指
            else:#否则是按下时为shape,松开后变手掌
                self.override_cursor(CURSOR_GRAB)#手掌
        elif ev.button() == Qt.LeftButton:
            pos = self.transform_pos(ev.pos())
            if self.drawing() and not self.draw_double:
                if self.createMode == "rectangle":
                    self.handle_drawing(pos)
                elif self.createMode in ["circle", "line"]:  # 如果是矩形、圆、线，那么此前就已经有了一个点，现在添加第二个点即结束一个目标的标注。
                    assert len(self.current.points) == 1
                    self.current.points = self.line.points
                    self.finalise()
            else:
                # pan
                QApplication.restoreOverrideCursor()
        if self.movingShape:
            self.shapeMoved.emit()
            self.movingShape = False

    def end_move(self, copy=False):
        assert self.selected_shape and self.selected_shape_copy
        shape = self.selected_shape_copy
        # del shape.fill_color
        # del shape.line_color
        if copy:
            self.shapes.append(shape)
            self.selected_shape.selected = False
            self.selected_shape = shape
            self.repaint()
        else:
            self.selected_shape.points = [p for p in shape.points]
        self.selected_shape_copy = None

    def hide_background_shapes(self, value):
        self.hide_background = value
        if self.selected_shape:
            # Only hide other shapes if there is a current selection.
            # Otherwise the user will not be able to select a shape.
            # 只隐藏其他形状，如果有当前选择。
            # 否则用户将无法选择形状。
            self.set_hiding(True)
            self.repaint()

    def handle_drawing(self, pos):
        if self.current and self.current.reach_max_points() is False:
            init_pos = self.current[0]
            min_x = init_pos.x()
            min_y = init_pos.y()
            target_pos = self.line[1]
            max_x = target_pos.x()
            max_y = target_pos.y()
            self.current.addPoint(QPointF(max_x, min_y))
            self.current.addPoint(target_pos)
            self.current.addPoint(QPointF(min_x, max_y))
            self.finalise()
        elif not self.out_of_pixmap(pos):
            self.current = Shape()
            self.current.addPoint(pos)
            self.line.points = [pos, pos]
            self.set_hiding()
            self.drawingPolygon.emit(True)
            self.update()

    def set_hiding(self, enable=True):
        self._hide_background = self.hide_background if enable else False

    def can_close_shape(self):
        return self.drawing() and self.current and len(self.current) > 2

    def mouseDoubleClickEvent(self, ev):
        # We need at least 4 points here, since the mousePress handler
        # adds an extra one before this handler is called.
        if self.can_close_shape() and len(self.current) > 3:
            self.current.pop_point()
            self.finalise()

    def select_shape(self, shape):
        self.de_select_shape()
        shape.selected = True
        self.selected_shape = shape
        self.set_hiding()
        self.selectionChanged.emit(True)
        self.update()

    def select_shape_point(self, point):#point是鼠标当前位置
        #当鼠标按下时，如果之前有选定的形状，那么就取消选定,以下再判断当前按下之前是否有悬停选定的顶点，或者形状
        """Select the first shape created which contains this point.选择第一个包含这个点的形状"""
        self.de_select_shape()#删除其他选中的对象
        if self.selected_vertex():  # A vertex is marked for selection.标记一个顶点以供选择
            index, shape = self.h_vertex, self.h_shape
            shape.highlight_vertex(index, shape.MOVE_VERTEX)#高亮顶点
            self.select_shape(shape)
            return self.h_vertex
        if self.selected_Edge():  # A vertex is marked for selection.标记一个顶点以供选择
            index, shape = self.hEdge, self.h_shape
            shape.highlight_vertex(index, shape.MOVE_VERTEX)#高亮顶点
            self.select_shape(shape)
            self.calculate_offsets(shape, point)
            return self.h_vertex
        # for shape in reversed(self.shapes):#reversed()函数返回一个反转的迭代器。将所有的标注在列表中反转，这样最先画框就在最后面，最先找到上面的框被其他框覆盖不可选中
        # for shape in reversed([s for s in self.shapes if self.isVisible(s)]):
        for shape in sorted([s for s in self.shapes if self.isVisible(s)],key=lambda shape_i: (shape_i.bounding_rect().x(), shape_i.bounding_rect().y()),reverse=True):  # 按照xy坐标从大到小排序，处于包含状态的框就可以被优先选中
            if self.isVisible(shape) and shape.contains_point(point):
                self.select_shape(shape)
                self.calculate_offsets(shape, point)
                return self.selected_shape
        return None

    def calculate_offsets(self, shape, point):
        rect = shape.bounding_rect()
        x1 = rect.x() - point.x()
        y1 = rect.y() - point.y()
        x2 = (rect.x() + rect.width()) - point.x()
        y2 = (rect.y() + rect.height()) - point.y()
        self.offsets = QPointF(x1, y1), QPointF(x2, y2)

    def snap_point_to_canvas(self, x, y):
        """
        Moves a point x,y to within the boundaries of the canvas.
        :return: (x,y,snapped) where snapped is True if x or y were changed, False if not.
        """
        if x < 0 or x > self.pixmap.width() or y < 0 or y > self.pixmap.height():
            x = max(x, 0)
            y = max(y, 0)
            x = min(x, self.pixmap.width())
            y = min(y, self.pixmap.height())
            return x, y, True

        return x, y, False

    def bounded_move_vertex(self, pos):#移动顶点操作
        index, shape = self.h_vertex, self.h_shape
        point = shape[index]
        if self.out_of_pixmap(pos):
            size = self.pixmap.size()
            clipped_x = min(max(0, pos.x()), size.width())
            clipped_y = min(max(0, pos.y()), size.height())
            pos = QPointF(clipped_x, clipped_y)

        if self.draw_square:
            opposite_point_index = (index + 2) % 4
            opposite_point = shape[opposite_point_index]

            min_size = min(abs(pos.x() - opposite_point.x()), abs(pos.y() - opposite_point.y()))
            direction_x = -1 if pos.x() - opposite_point.x() < 0 else 1
            direction_y = -1 if pos.y() - opposite_point.y() < 0 else 1
            shift_pos = QPointF(opposite_point.x() + direction_x * min_size - point.x(),
                                opposite_point.y() + direction_y * min_size - point.y())
        else:
            shift_pos = pos - point#shift_pos是鼠标的偏移，用于调整顶点位置
        if shape.shape_type == "rectangle":
            shape.move_vertex_by(index, shift_pos)
            left_index = (index + 1) % 4
            right_index = (index + 3) % 4
            left_shift = None
            right_shift = None
            if index % 2 == 0:
                right_shift = QPointF(shift_pos.x(), 0)
                left_shift = QPointF(0, shift_pos.y())
            else:
                left_shift = QPointF(shift_pos.x(), 0)
                right_shift = QPointF(0, shift_pos.y())
            shape.move_vertex_by(right_index, right_shift)
            shape.move_vertex_by(left_index, left_shift)
        else:
            shape.move_vertex_by(index, shift_pos)

    def bounded_move_edge(self, pos):
        index, shape = self.hEdge, self.h_shape
        if self.out_of_pixmap(pos):
            size = self.pixmap.size()
            clipped_x = min(max(0, pos.x()), size.width())
            clipped_y = min(max(0, pos.y()), size.height())
            pos = QPointF(clipped_x, clipped_y)
        if shape.shape_type == "rectangle" and not self.draw_square:
            point_index_1 = (index-1) % 4  # 边的第一个点
            point_index_2 = index % 4 # 边的第二个点
            point_1 = shape[point_index_1]
            point_2 = shape[point_index_2]
            if index % 2 == 0:#只改变边的两端点的y坐标
                shift_pos = QPointF(pos.x() - point_1.x(), 0)
            else:#只改变边的两端点的x坐标
                shift_pos = QPointF(0, pos.y() - point_1.y())
            shape.move_vertex_by(point_index_1, shift_pos)
            shape.move_vertex_by(point_index_2, shift_pos)
        else:
            return

    def bounded_move_shape(self, shape, pos):
        pixma_w = self.pixmap.width()
        pixma_h = self.pixmap.height()
        if shape.shape_type != "circle":
            if self.out_of_pixmap(pos):
                return False  # No need to move

            # offsets的是鼠标按下时候相对于目标左上点对于图像的左上点偏移量。
            # 最终o1和o2就是图像的外接矩形框左上、右下坐标
            o1 = pos + self.offsets[0]
            if self.out_of_pixmap(o1):
                pos -= QPointF(min(0, o1.x()), min(0, o1.y()))
            o2 = pos + self.offsets[1]
            if self.out_of_pixmap(o2):
                pos += QPointF(min(0, pixma_w - o2.x()),
                               min(0, pixma_h - o2.y()))
            # The next line tracks the new position of the cursor
            # relative to the shape, but also results in making it
            # a bit "shaky" when nearing the border and allows it to
            # go outside of the shape's area for some reason. XXX
            # self.calculateOffsets(self.selectedShape, pos)
        dp = pos - self.prev_point
        if dp:
            print(dp)
            shape.move_by(dp,pixma_w,pixma_h)
            self.prev_point = pos
            return True
        return False

    def de_select_shape(self):
        if self.selected_shape:
            self.selected_shape.selected = False
            self.selected_shape = None
            self.set_hiding(False)
            self.selectionChanged.emit(False)
            self.update()

    def delete_selected(self):
        if self.selected_shape:
            shape = self.selected_shape
            self.shapes.remove(self.selected_shape)
            self.selected_shape = None
            self.update()
            return shape

    def copy_selected_shape(self):
        if self.selected_shape:
            shape = self.selected_shape.copy()
            self.de_select_shape()
            self.shapes.append(shape)
            shape.selected = True
            self.selected_shape = shape
            self.bounded_shift_shape(shape)
            return shape

    def bounded_shift_shape(self, shape):
        # Try to move in one direction, and if it fails in another.
        # Give up if both fail.
        point = shape[0]
        offset = QPointF(2.0, 2.0)
        self.calculate_offsets(shape, point)
        self.prev_point = point
        if not self.bounded_move_shape(shape, point - offset):
            self.bounded_move_shape(shape, point + offset)

    def paintEvent(self, event):
        if not self.pixmap:
            return super(Canvas, self).paintEvent(event)

        p = self._painter
        p.begin(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.HighQualityAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        p.scale(self.scale, self.scale)
        p.translate(self.offset_to_center())

        p.drawPixmap(0, 0, self.pixmap)
        Shape.scale = self.scale
        Shape.label_font_size = self.label_font_size
        for shape in self.shapes:
            if (shape.selected or not self._hide_background) and self.isVisible(shape):
                shape.fill = shape.selected or shape == self.h_shape
                shape.paint(p)
        if self.current:
            self.current.paint(p)
            self.line.paint(p)
        if self.selected_shape_copy:
            self.selected_shape_copy.paint(p)

        # Paint rect
        if self.current is not None and len(self.line) >= 2:
            left_top = self.line[0]
            right_bottom = self.line[1]
            rect_width = right_bottom.x() - left_top.x()
            rect_height = right_bottom.y() - left_top.y()
            # p.setPen(self.drawing_rect_color)#设置引导线颜色
            p.setPen(self.drawing_line_color)
            if self.current.shape_type == 'rectangle':
                brush = QBrush(Qt.BDiagPattern)#斜线填充
                p.setBrush(brush)
                p.drawRect(left_top.x(), left_top.y(), rect_width, rect_height)
            elif self.current.shape_type == 'polygon':
                drawing_shape = self.current.copy()
                if drawing_shape.fill_color.getRgb()[3] == 0:
                    drawing_shape.fill_color.setAlpha(64)
                drawing_shape.addPoint(self.line[1])
                drawing_shape.fill = True
                drawing_shape.paint(p)
        if self.drawing() and not self.prev_point.isNull() and not self.out_of_pixmap(self.prev_point) and self.createMode == "rectangle":
            # p.setPen(QColor(0, 0, 0))
            p.setPen(self.drawing_line_color)
            p.drawLine(self.prev_point.x(), 0, self.prev_point.x(), self.pixmap.height())
            p.drawLine(0, self.prev_point.y(), self.pixmap.width(), self.prev_point.y())

        self.setAutoFillBackground(True)
        if self.verified:
            pal = self.palette()
            pal.setColor(self.backgroundRole(), QColor(184, 239, 38, 128))
            self.setPalette(pal)
        else:
            pal = self.palette()
            pal.setColor(self.backgroundRole(), QColor(232, 232, 232, 255))
            self.setPalette(pal)

        p.end()

    def transform_pos(self, point):
        """Convert from widget-logical coordinates to painter-logical coordinates."""
        return point / self.scale - self.offset_to_center()

    def offset_to_center(self):
        s = self.scale
        area = super(Canvas, self).size()
        w, h = self.pixmap.width() * s, self.pixmap.height() * s
        aw, ah = area.width(), area.height()
        x = (aw - w) / (2 * s) if aw > w else 0
        y = (ah - h) / (2 * s) if ah > h else 0
        return QPointF(x, y)

    def out_of_pixmap(self, p):
        w, h = self.pixmap.width(), self.pixmap.height()
        return not (0 <= p.x() <= w and 0 <= p.y() <= h)

    def finalise(self):#完成一个shape对象的标注，将其加入到shapes列表中，弹出新建标注框的对话框，赋予信息.如果对话框取消，则删除该shape对象并且进入编辑状态
        assert self.current
        if self.createMode != "point" and self.current.points[0] == self.current.points[-1]:
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
            return
        self.current.close()
        self.shapes.append(self.current)
        self.current = None
        self.set_hiding(False)
        self.newShape.emit()#弹出新建标注框的对话框，赋予信息
        self.update()

    def close_enough(self, p1, p2):
        # d = distance(p1 - p2)
        # m = (p1-p2).manhattanLength()
        # print "d %.2f, m %d, %.2f" % (d, m, d - m)
        return distance(p1 - p2) < self.epsilon

    # These two, along with a call to adjustSize are required for the
    # scroll area.
    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        if self.pixmap:
            return self.scale * self.pixmap.size()
        return super(Canvas, self).minimumSizeHint()

    def wheelEvent(self, ev):
        qt_version = 4 if hasattr(ev, "delta") else 5
        if qt_version == 4:
            if ev.orientation() == Qt.Vertical:
                v_delta = ev.delta()
                h_delta = 0
            else:
                h_delta = ev.delta()
                v_delta = 0
        else:
            delta = ev.angleDelta()
            h_delta = delta.x()
            v_delta = delta.y()

        mods = ev.modifiers()
        if Qt.ControlModifier == int(mods) and v_delta:
            self.zoomRequest.emit(v_delta)
        else:
            v_delta and self.scrollRequest.emit(v_delta, Qt.Vertical)
            h_delta and self.scrollRequest.emit(h_delta, Qt.Horizontal)
        ev.accept()

    def keyPressEvent(self, ev):
        modifiers = ev.modifiers()
        key = ev.key()
        if key == Qt.Key_Escape and self.current:
            print('ESC press')
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
        elif key == Qt.Key_Return and self.can_close_shape():
            self.finalise()
        elif modifiers == Qt.ControlModifier:
            self.snapping = False
        elif key == Qt.Key_Left and self.selected_shape:
            self.move_one_pixel('Left')
        elif key == Qt.Key_Right and self.selected_shape:
            self.move_one_pixel('Right')
        elif key == Qt.Key_Up and self.selected_shape:
            self.move_one_pixel('Up')
        elif key == Qt.Key_Down and self.selected_shape:
            self.move_one_pixel('Down')
    def keyReleaseEvent(self, ev):
        modifiers = ev.modifiers()
        if int(modifiers) == 0:#表示没有任何键被按下
            self.snapping = True
        # if self.editing():
        #     if self.movingShape and self.selectedShapes:
        #         index = self.shapes.index(self.selectedShapes[0])
        #         if (
        #             self.shapesBackups[-1][index].points
        #             != self.shapes[index].points
        #         ):
        #             self.storeShapes()
        #             self.shapeMoved.emit()
        #         self.movingShape = False

    def move_one_pixel(self, direction):
        # print(self.selectedShape.points)
        if direction == 'Left' and not self.move_out_of_bound(QPointF(-1.0, 0)):
            # print("move Left one pixel")
            for point in self.selected_shape.points:
                point += QPointF(-1.0, 0)

        elif direction == 'Right' and not self.move_out_of_bound(QPointF(1.0, 0)):
            # print("move Right one pixel")
            for point in self.selected_shape.points:
                point += QPointF(1.0, 0)

        elif direction == 'Up' and not self.move_out_of_bound(QPointF(0, -1.0)):
            # print("move Up one pixel")
            for point in self.selected_shape.points:
                point += QPointF(0, -1.0)

        elif direction == 'Down' and not self.move_out_of_bound(QPointF(0, 1.0)):
            # print("move Down one pixel")
            for point in self.selected_shape.points:
                point += QPointF(0, 1.0)

        self.movingShape = True
        self.repaint()

    def move_out_of_bound(self, step):
        points = [p1 + p2 for p1, p2 in zip(self.selected_shape.points, [step] * 4)]
        return True in map(self.out_of_pixmap, points)

    def set_last_label(self, text, line_color=None, fill_color=None):
        assert text
        self.shapes[-1].label = text
        if line_color:
            self.shapes[-1].line_color = line_color

        if fill_color:
            self.shapes[-1].fill_color = fill_color

        return self.shapes[-1]

    def undo_last_line(self):
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.set_open()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)

    def reset_all_lines(self):
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.set_open()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)
        self.current = None
        self.drawingPolygon.emit(False)
        self.update()

    def load_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.shapes = []
        self.repaint()

    def load_shapes(self, shapes):
        self.shapes = list(shapes)
        self.current = None
        self.h_shape = None
        self.h_vertex = None
        self.hEdge = None
        self.repaint()
        self.update()

    def set_shape_visible(self, shape, value):
        self.visible[shape] = value
        self.repaint()

    def current_cursor(self):
        cursor = QApplication.overrideCursor()
        if cursor is not None:
            cursor = cursor.shape()
        return cursor

    def override_cursor(self, cursor):
        self._cursor = cursor
        if self.current_cursor() is None:
            QApplication.setOverrideCursor(cursor)
        else:
            QApplication.changeOverrideCursor(cursor)

    def restore_cursor(self):
        QApplication.restoreOverrideCursor()

    def reset_state(self):
        self.restore_cursor()
        self.pixmap = None
        self.update()

    def set_drawing_shape_to_square(self, status):
        self.draw_square = status

    def set_drawing_shape_to_double(self, status):
        self.draw_double = status
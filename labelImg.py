#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import codecs
import distutils.spawn
import os.path
import platform
import re
import sys
import subprocess
import shutil
import webbrowser as wb

from functools import partial
from collections import defaultdict

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    # needed for py3+qt4
    # Ref:
    # http://pyqt.sourceforge.net/Docs/PyQt4/incompatible_apis.html
    # http://stackoverflow.com/questions/21217399/pyqt4-qtcore-qvariant-object-instead-of-a-string
    if sys.version_info.major >= 3:
        import sip
        sip.setapi('QVariant', 2)
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs.combobox import ComboBox
from libs.resources import *
from libs.constants import *
from libs.utils import *
from libs.settings import Settings
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from libs.stringBundle import StringBundle
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.labelDialog import LabelDialog
from libs.colorDialog import ColorDialog
from libs.labelFile import LabelFile, LabelFileError, LabelFileFormat
from libs.toolBar import ToolBar
from libs.pascal_voc_io import PascalVocReader
from libs.pascal_voc_io import XML_EXT
from libs.yolo_io import YoloReader
from libs.yolo_io import TXT_EXT
from libs.create_ml_io import CreateMLReader
from libs.create_ml_io import JSON_EXT
from libs.ustr import ustr
from libs.hashableQListWidgetItem import HashableQListWidgetItem

__appname__ = 'labelImg'


class WindowMixin(object):

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            add_actions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            add_actions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


class MainWindow(QMainWindow, WindowMixin):#MainWindow
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(self, default_filename=None, default_prefdef_class_file=None, default_save_dir=None):#生成MainWindow类的实例对象时自动调用，当命令行有传入时则分别赋值，否则除了class会有默认的label配置文件外，其他为None
        super(MainWindow, self).__init__()#调用两个父类中的初始化方法
        self.setWindowTitle(__appname__)#设置窗口名"labelImg"

        # Load setting in the main thread 在主线程中加载配置文件
        self.settings = Settings()
        self.settings.load()
        settings = self.settings

        self.os_name = platform.system()#返回操作系统，windows

        # Load string bundle for i18n 加载i18n的字符串束,软件的国际化就是软件的多语言化
        self.string_bundle = StringBundle.get_bundle()
        get_str = lambda str_id: self.string_bundle.get_string(str_id)#作用就是判断传入的str_id是否在id_to_message中，在的话返回str_id

        # Save as Pascal voc xml 保存为Pascal voc xml
        self.default_save_dir = default_save_dir#保存路径
        self.label_file_format = settings.get(SETTING_LABEL_FILE_FORMAT, LabelFileFormat.PASCAL_VOC)#设置标注文件格式为pascal_voc

        # For loading all image under a directory 用于加载目录下的所有图像
        self.m_img_list = []#存放图片列表
        self.dir_name = None#文件夹路径
        self.label_hist = []#存放label标签列表
        self.last_open_dir = None#最后打开的文件夹路径
        self.last_open_file = None#关闭程序前最后打开的文件
        self.cur_img_idx = 0 #当前图片数
        self.img_count = 1 #图片总数
        self.combo_list = []#存放可视化box类型的列表
        self.combo_text_list = []

        # Whether we need to save or not. 判断是否自动保存，默认是不自动保存
        self.dirty = False

        self._no_selection_slot = False
        self._beginner = True
        self.screencast = "https://youtu.be/p0nR2YsCY_U"

        # Load predefined classes to the list 将预定义类加载到列表中
        self.load_predefined_classes(default_prefdef_class_file)#获取label标签到label_hist(label可选列表)

        # Main widgets and related state. 主要小部件和相关状态
        self.label_dialog = LabelDialog(parent=self, list_item=self.label_hist)#创建一个label_dialog实例，作用是画框后弹出标签选择操作，其中list_item是读取标签配置文件后获取的一个列表

        self.items_to_shapes = {}
        self.shapes_to_items = {}
        self.prev_label_text = ''

        list_layout = QVBoxLayout()#在垂直方向上排列控件
        list_layout.setContentsMargins(0, 0, 0, 0)#设置边距

        # Create a widget for using default label 创建一个使用默认标签的小部，BoxLabels  （右上角的Box Label部件）
        self.use_default_label_checkbox = QCheckBox(get_str('useDefaultLabel'))#创建一个复选框，框后面内容是‘useDefaultLabel’
        self.use_default_label_checkbox.setChecked(False)#设置未选择状态
        self.default_label_text_line = QLineEdit()#创建一个单行文本控件，用于输入默认标签
        use_default_label_qhbox_layout = QHBoxLayout()#在水平方向上排列控件，水平布局按照从左到右的顺序进行添加按钮部件
        use_default_label_qhbox_layout.addWidget(self.use_default_label_checkbox)#将复选框添加到水平布局中
        use_default_label_qhbox_layout.addWidget(self.default_label_text_line)
        use_default_label_container = QWidget()#创建一个外层容器，用于存放复选框和单行文本控件所在的布局
        use_default_label_container.setLayout(use_default_label_qhbox_layout)#将水平布局放入到Qwidget控件中

        # Create a widget for edit and diffc button， 为edit和difficult按钮创建一个小部件
        self.diffc_button = QCheckBox(get_str('useDifficult'))#创建选择框
        self.diffc_button.setChecked(False)#设置该选择框为未选择状态
        self.diffc_button.stateChanged.connect(self.button_state)#stateChanged信号会在复选框状态发生变化时发出，该信号会触发后面的button_state方法
        self.edit_button = QToolButton()#创建一个按钮(编辑label)
        self.edit_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)#设置该工具按钮属性，文字在图片旁边

        # Add some of widgets to list_layout，在list_layout中添加一些小部件
        list_layout.addWidget(self.edit_button)#将edit_button组件添加到list_layout布局当中
        list_layout.addWidget(self.diffc_button)#将difficult复选框添加到list_layout布局当中
        list_layout.addWidget(use_default_label_container)#添加设置默认label的容器添加到list_layout垂直布局当中

        # Create and add combobox for showing unique labels in group 创建并添加组合框，用于显示组中唯一的标签(所有标注框的标签类型，同一种标签只显示一个)
        self.qline = QLineEdit(self)#创建一个单行文本控件，用于输入标签
        self.qline.setStyleSheet("background-color: white; border: none;")
        self.combo_box = ComboBox(self)#创建了一个下拉框实例
        list_layout.addWidget(self.combo_box)#添加到box labels
        list_layout.addWidget(self.qline)  # 添加到box labels

        # Create and add a widget for showing current label items 创建并添加用于显示当前标签项的小部件
        self.label_list = QListWidget()#创建一个列表展示控件，label_list是展示标注框的列表
        label_list_container = QWidget()#创建一个容器用来放list_layout布局
        label_list_container.setLayout(list_layout)#垂直排布
        self.label_list.itemActivated.connect(self.label_selection_changed)#itemActivated当项激活时发射，项激活是指鼠标单击或双击项，具体依赖于系统配置。
        self.label_list.itemSelectionChanged.connect(self.label_selection_changed)#itemSelectionChanged当列表部件中进行了选择操作后触发，无论选中项是否改变。
        self.label_list.itemDoubleClicked.connect(self.edit_label)#当组件双击双击时，调用修改该标签框的标注信息弹窗。
        # Connect to itemChanged to detect checkbox changes.，连接到itemChanged以检测复选框的更改
        self.label_list.itemChanged.connect(self.label_item_changed)
        list_layout.addWidget(self.label_list)



        self.dock = QDockWidget(get_str('boxLabelText'), self)#悬浮窗口，BoxLabel
        self.dock.setObjectName(get_str('labels'))#设置悬浮窗名命
        self.dock.setWidget(label_list_container)#右上角工具的BoxLabels添加到悬浮窗口

        self.file_list_widget = QListWidget()#创建一个列表展示控件，file_list_widget是展示需要标注图片文件的列表
        self.file_list_widget.itemDoubleClicked.connect(self.file_item_double_clicked)
        file_list_layout = QVBoxLayout()
        file_list_layout.setContentsMargins(0, 0, 0, 0)
        file_list_layout.addWidget(self.file_list_widget)
        file_list_container = QWidget()
        file_list_container.setLayout(file_list_layout)
        self.file_dock = QDockWidget(get_str('fileList'), self)
        self.file_dock.setObjectName(get_str('files'))
        self.file_dock.setWidget(file_list_container)

        self.zoom_widget = ZoomWidget()#初始化缩放值显示控件Zoomin和Zoomout之间
        self.color_dialog = ColorDialog(parent=self)#颜色调节对话框

        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoom_request)
        self.canvas.set_drawing_shape_to_square(settings.get(SETTING_DRAW_SQUARE, False))

        scroll = QScrollArea()#创建滚动区域  QScrollArea的使用是将widget作为子窗口，然后当子窗口的宽高大于滚动的窗口的时候进行滚动。
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)#setWidgetResizable为False时，滚动条出现
        self.scroll_bars = {
            Qt.Vertical: scroll.verticalScrollBar(),#垂直滚动
            Qt.Horizontal: scroll.horizontalScrollBar()#水平滚动
        }
        self.scroll_area = scroll
        self.canvas.scrollRequest.connect(self.scroll_request)#当画布发生位置变动，滚动条位置也发生变化

        self.canvas.newShape.connect(self.new_shape)
        self.canvas.shapeMoved.connect(self.set_dirty)
        self.canvas.selectionChanged.connect(self.shape_selection_changed)
        self.canvas.drawingPolygon.connect(self.toggle_drawing_sensitive)

        self.setCentralWidget(scroll)#setCentraWidget设置中央小部件
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.file_dock)
        self.file_dock.setFeatures(QDockWidget.DockWidgetFloatable)

        self.dock_features = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() ^ self.dock_features)

        # Actions 添加操作
        action = partial(new_action, self)#partial(偏函数)，把一个函数的参数固定住，返回一个新的函数,添加enabled=False，即该功能失效，默认是打开程序就可用
        quit = action(get_str('quit'), self.Quet_event,#改为其他函数做处理后再调用关闭操作
                      'Ctrl+Q', 'quit', get_str('quitApp'))

        open = action(get_str('openFile'), self.open_file,
                      'Ctrl+O', 'open', get_str('openFileDetail'))

        open_dir = action(get_str('openDir'), self.open_dir_dialog,
                          'Ctrl+u', 'open', get_str('openDir'))

        change_save_dir = action(get_str('changeSaveDir'), self.change_save_dir_dialog,
                                 'Ctrl+r', 'open', get_str('changeSavedAnnotationDir'))

        open_annotation = action(get_str('openAnnotation'), self.open_annotation_dialog,
                                 'Ctrl+Shift+O', 'open', get_str('openAnnotationDetail'))
        copy_prev_bounding = action(get_str('copyPrevBounding'), self.copy_previous_bounding_boxes, 'Ctrl+v', 'copy', get_str('copyPrevBounding'))

        open_next_image = action(get_str('nextImg'), self.open_next_image,
                                 'd', 'next', get_str('nextImgDetail'))

        open_prev_image = action(get_str('prevImg'), self.open_prev_image,
                                 'a', 'prev', get_str('prevImgDetail'))

        verify = action(get_str('verifyImg'), self.verify_image,
                        'space', 'verify', get_str('verifyImgDetail'))

        save = action(get_str('save'), self.save_file,
                      'Ctrl+S', 'save', get_str('saveDetail'), enabled=False)

        def get_format_meta(format):
            """
            returns a tuple containing (title, icon_name) of the selected format 获取标注类型选项，以及对应图标
            """
            if format == LabelFileFormat.PASCAL_VOC:
                return '&PascalVOC', 'format_voc'
            elif format == LabelFileFormat.YOLO:
                return '&YOLO', 'format_yolo'
            elif format == LabelFileFormat.CREATE_ML:
                return '&CreateML', 'format_createml'

        save_format = action(get_format_meta(self.label_file_format)[0],
                             self.change_format, 'Ctrl+',
                             get_format_meta(self.label_file_format)[1],
                             get_str('changeSaveFormat'), enabled=True)

        save_as = action(get_str('saveAs'), self.save_file_as,
                         'Ctrl+Shift+S', 'save-as', get_str('saveAsDetail'), enabled=False)

        close = action(get_str('closeCur'), self.close_file, 'Ctrl+W', 'close', get_str('closeCurDetail'))

        delete_image = action(get_str('deleteImg'), self.delete_image, 'Ctrl+Shift+D', 'close', get_str('deleteImgDetail'))

        reset_all = action(get_str('resetAll'), self.reset_all, None, 'resetall', get_str('resetAllDetail'))

        color1 = action(get_str('boxLineColor'), self.choose_color1,
                        'Ctrl+L', 'color_line', get_str('boxLineColorDetail'))

        create_mode = action(get_str('crtBox'), self.set_create_mode,
                             'w', 'new', get_str('crtBoxDetail'), enabled=False)
        edit_mode = action(get_str('editBox'), self.set_edit_mode,
                           'Ctrl+J', 'edit', get_str('editBoxDetail'), enabled=False)

        create = action(get_str('crtBox'), self.create_shape,
                        'w', 'new', get_str('crtBoxDetail'), enabled=False)
        delete = action(get_str('delBox'), self.delete_selected_shape,
                        'Delete', 'delete', get_str('delBoxDetail'), enabled=False)
        copy = action(get_str('dupBox'), self.copy_selected_shape,
                      'Ctrl+D', 'copy', get_str('dupBoxDetail'),
                      enabled=False)

        advanced_mode = action(get_str('advancedMode'), self.toggle_advanced_mode,
                               'Ctrl+Shift+A', 'expert', get_str('advancedModeDetail'),
                               checkable=True)
        # save_zoom = action(get_str('saveZoom'), self.toggle_advanced_mode,
        #                        'Ctrl+Shift+Z', 'expert', get_str('saveZoomvalue'),
        #                        checkable=True)

        hide_all = action(get_str('hideAllBox'), partial(self.toggle_polygons, False),
                          'Ctrl+H', 'hide', get_str('hideAllBoxDetail'),
                          enabled=False)
        show_all = action(get_str('showAllBox'), partial(self.toggle_polygons, True),
                          'Ctrl+A', 'hide', get_str('showAllBoxDetail'),
                          enabled=False)
        delete_all = action(get_str('deleteAll'), self.delete_all_shape,
                          'Ctrl+Z', 'delete', get_str('delAllBox'),
                          enabled=False)

        help_default = action(get_str('tutorialDefault'), self.show_default_tutorial_dialog, None, 'help', get_str('tutorialDetail'))
        show_info = action(get_str('info'), self.show_info_dialog, None, 'help', get_str('info'))
        show_shortcut = action(get_str('shortcut'), self.show_shortcuts_dialog, None, 'help', get_str('shortcut'))

        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoom_widget)
        self.zoom_widget.setWhatsThis(
            u"Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas." % (format_shortcut("Ctrl+[-+]"),
                                             format_shortcut("Ctrl+Wheel")))
        self.zoom_widget.setEnabled(False)

        zoom_in = action(get_str('zoomin'), partial(self.add_zoom, 10),#放大10%
                         'Ctrl++', 'zoom-in', get_str('zoominDetail'), enabled=False)
        zoom_out = action(get_str('zoomout'), partial(self.add_zoom, -10),#缩小10%
                          'Ctrl+-', 'zoom-out', get_str('zoomoutDetail'), enabled=False)
        zoom_org = action(get_str('originalsize'), partial(self.set_zoom, 100),#设置原始的尺寸，100%
                          'Ctrl+=', 'zoom', get_str('originalsizeDetail'), enabled=False)
        fit_window = action(get_str('fitWin'), self.set_fit_window,
                            'Ctrl+F', 'fit-window', get_str('fitWinDetail'),
                            checkable=True, enabled=False)
        fit_width = action(get_str('fitWidth'), self.set_fit_width,
                           'Ctrl+Shift+F', 'fit-width', get_str('fitWidthDetail'),
                           checkable=True, enabled=False)
        # Group zoom controls into a list for easier toggling.将缩放控件分组到一个列表中，以便于切换。
        zoom_actions = (self.zoom_widget, zoom_in, zoom_out,
                        zoom_org, fit_window, fit_width)
        self.zoom_mode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scale_fit_window,
            self.FIT_WIDTH: self.scale_fit_width,
            # Set to one to scale to 100% when loading files.设置为1，以在加载文件时缩放到100%
            self.MANUAL_ZOOM: lambda: 1,
        }

        edit = action(get_str('editLabel'), self.edit_label,
                      'Ctrl+E', 'edit', get_str('editLabelDetail'),
                      enabled=False)
        self.edit_button.setDefaultAction(edit)

        shape_line_color = action(get_str('shapeLineColor'), self.choose_shape_line_color,
                                  icon='color_line', tip=get_str('shapeLineColorDetail'),
                                  enabled=False)
        shape_fill_color = action(get_str('shapeFillColor'), self.choose_shape_fill_color,
                                  icon='color', tip=get_str('shapeFillColorDetail'),
                                  enabled=False)

        labels = self.dock.toggleViewAction()
        labels.setText(get_str('showHide'))
        labels.setShortcut('Ctrl+Shift+L')

        # Label list context menu.标签列表上下文菜单。
        label_menu = QMenu()
        add_actions(label_menu, (edit, delete))
        self.label_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.label_list.customContextMenuRequested.connect(
            self.pop_label_list_menu)

        # Draw squares/rectangles画正方形/长方形
        self.draw_squares_option = QAction(get_str('drawSquares'), self)
        self.draw_squares_option.setShortcut('Ctrl+Shift+R')
        self.draw_squares_option.setCheckable(True)
        self.draw_squares_option.setChecked(settings.get(SETTING_DRAW_SQUARE, False))
        self.draw_squares_option.triggered.connect(self.toggle_draw_square)

        # Store actions for further handling.存储操作以供进一步处理。
        self.actions = Struct(save=save, save_format=save_format, saveAs=save_as, open=open, close=close, resetAll=reset_all, deleteImg=delete_image,delete_all=delete_all,
                              lineColor=color1, create=create, delete=delete, edit=edit, copy=copy,
                              createMode=create_mode, editMode=edit_mode, advancedMode=advanced_mode,
                              shapeLineColor=shape_line_color, shapeFillColor=shape_fill_color,
                              zoom=zoom, zoomIn=zoom_in, zoomOut=zoom_out, zoomOrg=zoom_org,
                              fitWindow=fit_window, fitWidth=fit_width,
                              zoomActions=zoom_actions,
                              fileMenuActions=(
                                  open, open_dir, save, save_as, close, reset_all, quit),
                              beginner=(), advanced=(),
                              editMenu=(edit, copy, delete,delete_all,
                                        None, color1, self.draw_squares_option),
                              beginnerContext=(create, edit, copy, delete),
                              advancedContext=(create_mode, edit_mode, edit, copy,
                                               delete,shape_line_color, shape_fill_color,delete_all),
                              onLoadActive=(
                                  close, create, create_mode, edit_mode,delete_all),
                              onShapesPresent=(save_as, hide_all, show_all))

        self.menus = Struct(#添加菜单栏
            file=self.menu(get_str('menu_file')),
            edit=self.menu(get_str('menu_edit')),
            view=self.menu(get_str('menu_view')),
            help=self.menu(get_str('menu_help')),
            recentFiles=QMenu(get_str('menu_openRecent')),
            labelList=label_menu)

        # Auto saving : Enable auto saving if pressing next,自动保存:如果按下“下一步”，启用自动保存
        self.auto_saving = QAction(get_str('autoSaveMode'), self)
        self.auto_saving.setCheckable(True)
        self.auto_saving.setChecked(settings.get(SETTING_AUTO_SAVE, False))#如果之前没有设置为True默认就是False

        self.save_zoom = QAction(get_str('saveZoom'), self)
        self.save_zoom.setCheckable(True)
        self.save_zoom.setChecked(settings.get(SETTING_SAVE_ZOOM, False))

        self.pure_mode = QAction(get_str('puremode'), self)
        self.pure_mode.setCheckable(True)
        self.pure_mode.setChecked(settings.get(SETTING_PURE_MODE, False))

        # Sync single class mode from PR#106
        self.single_class_mode = QAction(get_str('singleClsMode'), self)
        self.single_class_mode.setShortcut("Ctrl+Shift+S")
        self.single_class_mode.setCheckable(True)
        self.single_class_mode.setChecked(settings.get(SETTING_SINGLE_CLASS, False))
        self.lastLabel = None
        # Add option to enable/disable labels being displayed at the top of bounding boxes增加选项启用/禁用标签显示在边界框的顶部
        self.display_label_option = QAction(get_str('displayLabel'), self)
        self.display_label_option.setShortcut("Ctrl+Shift+P")
        self.display_label_option.setCheckable(True)
        self.display_label_option.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.display_label_option.triggered.connect(self.toggle_paint_labels_option)
        #菜单栏里面各个菜单下添加二级功能
        add_actions(self.menus.file,
                    (open, open_dir, change_save_dir, open_annotation, copy_prev_bounding, self.menus.recentFiles, save, save_format, save_as, close, reset_all, delete_image, quit))
        add_actions(self.menus.help, (help_default, show_info, show_shortcut))
        add_actions(self.menus.view, (#把操作添加到view中
            self.auto_saving,
            self.save_zoom,
            self.pure_mode,
            self.single_class_mode,
            self.display_label_option,
            labels, advanced_mode,None,
            hide_all, show_all, None,
            zoom_in, zoom_out, zoom_org, None,
            fit_window, fit_width))

        self.menus.file.aboutToShow.connect(self.update_file_menu)

        # Custom context menu for the canvas widget:画布小部件的自定义上下文菜单
        add_actions(self.canvas.menus[0], self.actions.beginnerContext)
        add_actions(self.canvas.menus[1], (
            action('&Copy here', self.copy_shape),
            action('&Move here', self.move_shape)))

        self.tools = self.toolbar('Tools')
        self.actions.beginner = (
            open, open_dir, change_save_dir, open_next_image, open_prev_image, verify, save, save_format, None, create, copy, delete,delete_all, None,
            zoom_in, zoom, zoom_out, fit_window, fit_width)

        self.actions.advanced = (
            open, open_dir, change_save_dir, open_next_image, open_prev_image, save, save_format, None,
            create_mode, edit_mode, None,
            hide_all, show_all)

        self.statusBar().showMessage('%s started.' % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.file_path = ustr(default_filename)#初始化时的传入的目录，ustr统一编码格式
        self.last_open_dir = None
        self.recent_files = []
        self.max_recent = 7
        self.line_color = None
        self.fill_color = None
        self.zoom_level = 100
        self.fit_window = False
        # Add Chris
        self.difficult = False

        # Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(SETTING_RECENT_FILES):
            if have_qstring():
                recent_file_qstring_list = settings.get(SETTING_RECENT_FILES)
                self.recent_files = [ustr(i) for i in recent_file_qstring_list]
            else:
                self.recent_files = recent_file_qstring_list = settings.get(SETTING_RECENT_FILES)

        size = settings.get(SETTING_WIN_SIZE, QSize(600, 500))
        position = QPoint(0, 0)
        saved_position = settings.get(SETTING_WIN_POSE, position)
        # Fix the multiple monitors issue
        for i in range(QApplication.desktop().screenCount()):
            if QApplication.desktop().availableGeometry(i).contains(saved_position):
                position = saved_position
                break
        self.resize(size)#重置窗口大小
        self.move(position)
        save_dir = ustr(settings.get(SETTING_SAVE_DIR, None))
        self.last_open_dir = ustr(settings.get(SETTING_LAST_OPEN_DIR, None))
        if self.default_save_dir is None and save_dir is not None and os.path.exists(save_dir):
            self.default_save_dir = save_dir
            self.statusBar().showMessage('%s started. Annotation will be saved to %s' %
                                         (__appname__, self.default_save_dir))
            self.statusBar().show()

        self.restoreState(settings.get(SETTING_WIN_STATE, QByteArray()))
        Shape.line_color = self.line_color = QColor(settings.get(SETTING_LINE_COLOR, DEFAULT_LINE_COLOR))
        Shape.fill_color = self.fill_color = QColor(settings.get(SETTING_FILL_COLOR, DEFAULT_FILL_COLOR))
        self.canvas.set_drawing_color(self.line_color)
        # Add chris
        Shape.difficult = self.difficult

        def xbool(x):
            if isinstance(x, QVariant):
                return x.toBool()
            return bool(x)

        if xbool(settings.get(SETTING_ADVANCE_MODE, False)):
            self.actions.advancedMode.setChecked(True)
            self.toggle_advanced_mode()

        # Populate the File menu dynamically.动态填充File菜单
        self.update_file_menu()

        # Since loading the file may take some time, make sure it runs in the background.由于加载文件可能需要一些时间，请确保它在后台运行。
        if self.file_path and os.path.isdir(self.file_path):
            self.queue_event(partial(self.import_dir_images, self.file_path or ""))
        elif self.file_path:
            self.queue_event(partial(self.load_file, self.file_path or ""))

        # Callbacks:
        self.zoom_widget.valueChanged.connect(self.paint_canvas)

        self.populate_mode_actions()

        # Display cursor coordinates at the right of status bar在状态栏右侧显示光标坐标
        self.label_coordinates = QLabel('')
        self.statusBar().addPermanentWidget(self.label_coordinates)

        # Open Dir if default file打开默认文件的目录
        if self.file_path and os.path.isdir(self.file_path):#初始化时候，如果启动程序的时候有传入file_path参数的话，并且是一个目录
            self.open_dir_dialog(dir_path=self.file_path, silent=True)#调用打开文件方法，传入该路径。等于说自动实现打开文件夹操作。

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.canvas.set_drawing_shape_to_square(False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control:
            # Draw rectangle if Ctrl is pressed如果按下Ctrl，绘制矩形
            self.canvas.set_drawing_shape_to_square(True)

    # Support Functions #支持功能
    def set_format(self, save_format):#设置标注格式
        if save_format == FORMAT_PASCALVOC:
            self.actions.save_format.setText(FORMAT_PASCALVOC)
            self.actions.save_format.setIcon(new_icon("format_voc"))
            self.label_file_format = LabelFileFormat.PASCAL_VOC
            LabelFile.suffix = XML_EXT

        elif save_format == FORMAT_YOLO:
            self.actions.save_format.setText(FORMAT_YOLO)
            self.actions.save_format.setIcon(new_icon("format_yolo"))
            self.label_file_format = LabelFileFormat.YOLO
            LabelFile.suffix = TXT_EXT

        elif save_format == FORMAT_CREATEML:
            self.actions.save_format.setText(FORMAT_CREATEML)
            self.actions.save_format.setIcon(new_icon("format_createml"))
            self.label_file_format = LabelFileFormat.CREATE_ML
            LabelFile.suffix = JSON_EXT

    def change_format(self):#选择标注格式
        if self.label_file_format == LabelFileFormat.PASCAL_VOC:
            self.set_format(FORMAT_YOLO)
        elif self.label_file_format == LabelFileFormat.YOLO:
            self.set_format(FORMAT_CREATEML)
        elif self.label_file_format == LabelFileFormat.CREATE_ML:
            self.set_format(FORMAT_PASCALVOC)
        else:
            raise ValueError('Unknown label file format.')
        self.set_dirty()

    def no_shapes(self):
        return not self.items_to_shapes#调用no_shape方法时候，如果items_to_shapes为空返回true，否则返回false

    def toggle_advanced_mode(self, value=True):
        self._beginner = not value
        self.canvas.set_editing(True)
        self.populate_mode_actions()
        self.edit_button.setVisible(not value)
        if value:
            self.actions.createMode.setEnabled(True)
            self.actions.editMode.setEnabled(False)
            self.dock.setFeatures(self.dock.features() | self.dock_features)
        else:
            self.dock.setFeatures(self.dock.features() ^ self.dock_features)

    def populate_mode_actions(self):
        if self.beginner():
            tool, menu = self.actions.beginner, self.actions.beginnerContext
        else:
            tool, menu = self.actions.advanced, self.actions.advancedContext
        self.tools.clear()
        add_actions(self.tools, tool)
        self.canvas.menus[0].clear()
        add_actions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        actions = (self.actions.create,) if self.beginner()\
            else (self.actions.createMode, self.actions.editMode)
        add_actions(self.menus.edit, actions + self.actions.editMenu)

    def set_beginner(self):
        self.tools.clear()
        add_actions(self.tools, self.actions.beginner)

    def set_advanced(self):
        self.tools.clear()
        add_actions(self.tools, self.actions.advanced)

    def set_dirty(self):#设置为脏的，也就是画布上是否有去标注，有的话save功能可以触发
        self.dirty = True
        self.actions.save.setEnabled(True)

    def set_clean(self):#设置为干净模式，关闭save功能，打开创建标注框功能
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.create.setEnabled(True)

    def toggle_actions(self, value=True):
        """Enable/Disable widgets which depend on an opened image.启用/禁用依赖于打开的图像的小部件"""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

    def queue_event(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def reset_state(self):
        self.items_to_shapes.clear()
        self.shapes_to_items.clear()
        self.label_list.clear()
        self.file_path = None
        self.image_data = None
        self.label_file = None
        self.canvas.reset_state()
        self.label_coordinates.clear()
        self.combo_box.cb.clear()

    def current_item(self):
        items = self.label_list.selectedItems()#返回label_list组件中所有被选中的项列表
        if items:
            return items[0]
        return None

    def add_recent_file(self, file_path):
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        elif len(self.recent_files) >= self.max_recent:
            self.recent_files.pop()
        self.recent_files.insert(0, file_path)

    def beginner(self):
        return self._beginner

    def advanced(self):
        return not self.beginner()

    def show_tutorial_dialog(self, browser='default', link=None):
        if link is None:
            link = self.screencast

        if browser.lower() == 'default':
            wb.open(link, new=2)
        elif browser.lower() == 'chrome' and self.os_name == 'Windows':
            if shutil.which(browser.lower()):  # 'chrome' not in wb._browsers in windows
                wb.register('chrome', None, wb.BackgroundBrowser('chrome'))
            else:
                chrome_path="D:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
                if os.path.isfile(chrome_path):
                    wb.register('chrome', None, wb.BackgroundBrowser(chrome_path))
            try:
                wb.get('chrome').open(link, new=2)
            except:
                wb.open(link, new=2)
        elif browser.lower() in wb._browsers:
            wb.get(browser.lower()).open(link, new=2)

    def show_default_tutorial_dialog(self):
        self.show_tutorial_dialog(browser='default')

    def show_info_dialog(self):
        from libs.__init__ import __version__
        msg = u'Name:{0} \nApp Version:{1} \n{2} '.format(__appname__, __version__, sys.version_info)
        QMessageBox.information(self, u'Information', msg)

    def show_shortcuts_dialog(self):
        self.show_tutorial_dialog(browser='default', link='https://github.com/tzutalin/labelImg#Hotkeys')

    def create_shape(self):
        assert self.beginner()
        self.canvas.set_editing(False)
        self.actions.create.setEnabled(False)

    def toggle_drawing_sensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled.在绘图过程中，应该禁止在模式之间切换"""
        self.actions.editMode.setEnabled(not drawing)
        if not drawing and self.beginner():
            # Cancel creation.，取消创建
            print('Cancel creation.')
            self.canvas.set_editing(True)
            self.canvas.restore_cursor()
            self.actions.create.setEnabled(True)

    def toggle_draw_mode(self, edit=True):#切换模式
        self.canvas.set_editing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def set_create_mode(self):
        assert self.advanced()
        self.toggle_draw_mode(False)

    def set_edit_mode(self):
        assert self.advanced()
        self.toggle_draw_mode(True)
        self.label_selection_changed()

    def update_file_menu(self):
        curr_file_path = self.file_path

        def exists(filename):
            return os.path.exists(filename)
        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recent_files if f !=
                 curr_file_path and exists(f)]
        for i, f in enumerate(files):
            icon = new_icon('labels')
            action = QAction(
                icon, '&%d %s' % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.load_recent, f))
            menu.addAction(action)

    def pop_label_list_menu(self, point):
        self.menus.labelList.exec_(self.label_list.mapToGlobal(point))

    def edit_label(self):
        if not self.canvas.editing():
            return
        item = self.current_item()
        if not item:
            return
        text = self.label_dialog.pop_up(item.text())
        if text is not None:
            item.setText(text)
            item.setBackground(generate_color_by_text(text))
            self.set_dirty()
            self.update_combo_box()

    # Tzutalin 20160906 : Add file list and dock to move faster 添加文件列表和dock移动更快
    def file_item_double_clicked(self, item=None):
        self.cur_img_idx = self.m_img_list.index(ustr(item.text()))
        filename = self.m_img_list[self.cur_img_idx]
        if filename:
            self.load_file(filename)

    # Add chris
    def button_state(self, item=None):
        """ Function to handle difficult examples
        Update on each object 函数来处理复杂的示例
        更新每个对象"""
        if not self.canvas.editing():
            return

        item = self.current_item()
        if not item:  # If not selected Item, take the first one，如果没有选中Item(标签)，选择第一个(标签)
            item = self.label_list.item(self.label_list.count() - 1)

        difficult = self.diffc_button.isChecked()

        try:
            shape = self.items_to_shapes[item]
        except:
            pass
        # Checked and Update
        try:
            if difficult != shape.difficult:
                shape.difficult = difficult
                self.set_dirty()
            else:  # User probably changed item visibility，用户可能改变了项目可见性
                self.canvas.set_shape_visible(shape, item.checkState() == Qt.Checked)
        except:
            pass

    # React to canvas signals.对画布信号作出反应
    def shape_selection_changed(self, selected=False):
        if self._no_selection_slot:
            self._no_selection_slot = False
        else:
            shape = self.canvas.selected_shape
            if shape:
                self.shapes_to_items[shape].setSelected(True)
            else:
                self.label_list.clearSelection()
        self.actions.delete.setEnabled(selected)
        self.actions.copy.setEnabled(selected)
        self.actions.edit.setEnabled(selected)
        self.actions.shapeLineColor.setEnabled(selected)
        self.actions.shapeFillColor.setEnabled(selected)

    def add_label(self, shape):
        shape.paint_label = self.display_label_option.isChecked()
        item = HashableQListWidgetItem(shape.label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setBackground(generate_color_by_text(shape.label))
        self.items_to_shapes[item] = shape
        self.shapes_to_items[shape] = item
        self.label_list.addItem(item)
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)
        self.update_combo_box()

    def remove_label(self, shape):
        if shape is None:
            # print('rm empty label')
            return
        item = self.shapes_to_items[shape]
        self.label_list.takeItem(self.label_list.row(item))
        del self.shapes_to_items[shape]
        del self.items_to_shapes[item]
        self.update_combo_box()

    def load_labels(self, shapes):
        s = []
        for label, points, line_color, fill_color, difficult in shapes:
            shape = Shape(label=label)
            for x, y in points:

                # Ensure the labels are within the bounds of the image. If not, fix them.确保标签在图像的范围内。如果不是，就修复它们。
                x, y, snapped = self.canvas.snap_point_to_canvas(x, y)
                if snapped:
                    self.set_dirty()

                shape.add_point(QPointF(x, y))
            shape.difficult = difficult
            shape.close()
            s.append(shape)

            if line_color:
                shape.line_color = QColor(*line_color)
            else:
                shape.line_color = generate_color_by_text(label)

            if fill_color:
                shape.fill_color = QColor(*fill_color)
            else:
                shape.fill_color = generate_color_by_text(label)

            self.add_label(shape)
        self.update_combo_box()
        self.canvas.load_shapes(s)

    def update_combo_box(self):#控制label类型的显示
        # Get the unique labels and add them to the Combobox.获取唯一的标签，并将它们添加到组合框中。
        items_text_list = [str(self.label_list.item(i).text()) for i in range(self.label_list.count())]
        unique_text_list = list(set(items_text_list))
        # Add a null row for showing all the labels添加一个空行来显示所有的标签
        unique_text_list.append("")
        for i in unique_text_list:
            if i not in self.combo_list:
                self.combo_list.append(i)
        self.combo_list.sort()
        self.combo_box.update_items(self.combo_list)
        # self.combo_box.cb.setCurrentText(",".join(self.combo_text_list))
        self.qline.setText(",".join(self.combo_text_list))
        self.combo_set_show_label()

    def save_labels(self, annotation_file_path):
        annotation_file_path = ustr(annotation_file_path)
        if self.label_file is None:
            self.label_file = LabelFile()
            self.label_file.verified = self.canvas.verified

        def format_shape(s):
            return dict(label=s.label,
                        line_color=s.line_color.getRgb(),
                        fill_color=s.fill_color.getRgb(),
                        points=[(p.x(), p.y()) for p in s.points],
                        # add chris
                        difficult=s.difficult)

        shapes = [format_shape(shape) for shape in self.canvas.shapes]

        # Can add different annotation formats here可以在这里添加不同的注释格式
        try:
            if self.label_file_format == LabelFileFormat.PASCAL_VOC:
                if annotation_file_path[-4:].lower() != ".xml":
                    annotation_file_path += XML_EXT
                if self.pure_mode.isChecked() and len(shapes) == 0:
                    if os.path.exists(annotation_file_path):
                        os.remove(annotation_file_path)
                        return True
                    else:
                        return True
                self.label_file.save_pascal_voc_format(annotation_file_path, shapes, self.file_path, self.image_data,
                                                       self.line_color.getRgb(), self.fill_color.getRgb())
            elif self.label_file_format == LabelFileFormat.YOLO:
                if annotation_file_path[-4:].lower() != ".txt":
                    annotation_file_path += TXT_EXT
                if self.pure_mode.isChecked() and len(shapes) == 0:
                    if os.path.exists(annotation_file_path):
                        os.remove(annotation_file_path)
                        return True
                    else:
                        return True
                self.label_file.save_yolo_format(annotation_file_path, shapes, self.file_path, self.image_data, self.label_hist,
                                                 self.line_color.getRgb(), self.fill_color.getRgb())
            elif self.label_file_format == LabelFileFormat.CREATE_ML:
                if annotation_file_path[-5:].lower() != ".json":
                    annotation_file_path += JSON_EXT
                if self.pure_mode.isChecked() and len(shapes) == 0:
                    if os.path.exists(annotation_file_path):
                        os.remove(annotation_file_path)
                        return True
                    else:
                        return True
                self.label_file.save_create_ml_format(annotation_file_path, shapes, self.file_path, self.image_data,
                                                      self.label_hist, self.line_color.getRgb(), self.fill_color.getRgb())
            else:
                if self.pure_mode.isChecked() and len(shapes) == 0:
                    if os.path.exists(annotation_file_path):
                        os.remove(annotation_file_path)
                        return True
                    else:
                        return True
                self.label_file.save(annotation_file_path, shapes, self.file_path, self.image_data,
                                     self.line_color.getRgb(), self.fill_color.getRgb())
            print('Image:{0} -> Annotation:{1}'.format(self.file_path, annotation_file_path))
            return True
        except LabelFileError as e:
            self.error_message(u'Error saving label data', u'<b>%s</b>' % e)
            return False

    def copy_selected_shape(self):
        self.add_label(self.canvas.copy_selected_shape())
        # fix copy and delete修复复制和删除
        self.shape_selection_changed(True)

    def combo_selection_changed(self):
        combo_text = self.combo_box.cb.currentText()
        if combo_text == "":
            self.combo_text_list.clear()
        elif combo_text not in self.combo_text_list:
            self.combo_text_list.append(combo_text)
        elif combo_text in self.combo_text_list:
            self.combo_text_list.remove(combo_text)
        self.combo_set_show_label()
        self.qline.setText(",".join(self.combo_text_list))
    def combo_set_show_label(self):
        for i in range(self.label_list.count()):
            if self.combo_text_list == []:
                self.label_list.item(i).setCheckState(2)
            elif self.label_list.item(i).text() in self.combo_text_list:
                self.label_list.item(i).setCheckState(2)
            else:
                self.label_list.item(i).setCheckState(0)
            # if self.combo_text == "":
            #     self.label_list.item(i).setCheckState(2)
            # elif self.combo_text != self.label_list.item(i).text():
            #     self.label_list.item(i).setCheckState(0)
            # else:
            #     self.label_list.item(i).setCheckState(2)
    def label_selection_changed(self):#通过items选择box框
        item = self.current_item()
        if item and self.canvas.editing():
            self._no_selection_slot = True
            self.canvas.select_shape(self.items_to_shapes[item])#
            shape = self.items_to_shapes[item]
            # Add Chris
            self.diffc_button.setChecked(shape.difficult)

    def label_item_changed(self, item):
        shape = self.items_to_shapes[item]
        label = item.text()#
        if label != shape.label:
            shape.label = item.text()
            shape.line_color = generate_color_by_text(shape.label)
            self.set_dirty()
        else:  # User probably changed item visibility用户可能改变了项目可见性
            self.canvas.set_shape_visible(shape, item.checkState() == Qt.Checked)

    # Callback functions:
    def new_shape(self):#创建box框调用
        """Pop-up and give focus to the label editor.弹出并将焦点放在标签编辑器上

        position MUST be in global coordinates.position必须是全局坐标
        """
        if not self.use_default_label_checkbox.isChecked() or not self.default_label_text_line.text():#如果不使用默认标签
            if len(self.label_hist) > 0:
                self.label_dialog = LabelDialog(
                    parent=self, list_item=self.label_hist)

            # Sync single class mode from PR#106
            if self.single_class_mode.isChecked() and self.lastLabel:
                text = self.lastLabel#把text设置为最后标注框的标签
            else:#没有上一个标签的时候，text等于自己选择或者输入的标签
                text = self.label_dialog.pop_up(text=self.prev_label_text)
                self.lastLabel = text#把lastlabel设置为刚才自己选择或输入的标签
        else:#否者使用默认标签的话，text等于默认标签里面的值
            text = self.default_label_text_line.text()

        # Add Chris
        self.diffc_button.setChecked(False)#把difficult设置为未选择状态
        if text is not None:
            self.prev_label_text = text
            generate_color = generate_color_by_text(text)#调用函数返回颜色属性，传入的参数是标签，所以相同标签的标注框颜色相同
            shape = self.canvas.set_last_label(text, generate_color, generate_color)#返回shape对象
            self.add_label(shape)#把shape对象
            if self.beginner():  # Switch to edit mode.
                self.canvas.set_editing(True)
                self.actions.create.setEnabled(True)
            else:
                self.actions.editMode.setEnabled(True)
            self.set_dirty()

            if text not in self.label_hist:#如果刚才的标签不在label_hist中就加入到这个标签列表当中。所以默认label_hist是只有配置文件中的标签，但是当我们标注过程中产生新标签，那么会一直在label_hist中出现，直到关闭程序。
                self.label_hist.append(text)
        else:#否则画了框以后，但是最后没为其设置标签(取消)，那么画布上重置刚才画的线
            # self.canvas.undoLastLine()
            self.canvas.reset_all_lines()

    def scroll_request(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scroll_bars[orientation]
        bar.setValue(bar.value() + bar.singleStep() * units)

    def set_zoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoom_mode = self.MANUAL_ZOOM
        self.zoom_widget.setValue(value)

    def add_zoom(self, increment=10):
        self.set_zoom(self.zoom_widget.value() + increment)

    def zoom_request(self, delta):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates 获取当前滚动条的位置计算百分比~坐标
        h_bar = self.scroll_bars[Qt.Horizontal]#
        v_bar = self.scroll_bars[Qt.Vertical]

        # get the current maximum, to know the difference after zooming获得当前最大值，以了解缩放后的差异
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        #获取光标位置和画布大小
        # 计算从0到1所需的移动
        # where 0 =向左移动
        # 1 =向右移动
        # 上下类似
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)

        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()

        w = self.scroll_area.width()
        h = self.scroll_area.height()

        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        # 从0到1的缩放有一些填充
        # #你不需要点击最左边的像素来实现最大左移动
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)

        # clamp the values from 0 to 1将值从0固定到1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)

        # zoom in放大
        units = delta / (8 * 15)
        scale = 10
        self.add_zoom(scale * units)

        # get the difference in scrollbar values
        # this is how far we can move
        # 获取滚动条值的差异
        # 这就是我们能走多远
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max

        # get the new scrollbar values获取新的滚动条值
        new_h_bar_value = h_bar.value() + move_x * d_h_bar_max
        new_v_bar_value = v_bar.value() + move_y * d_v_bar_max

        # print(f"水平移动{move_x * d_h_bar_max}，竖直移动{move_y * d_v_bar_max}")
        # print(f"水平移动{new_h_bar_value}，竖直移动{new_v_bar_value}")

        h_bar.setValue(new_h_bar_value)
        v_bar.setValue(new_v_bar_value)

    def set_fit_window(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoom_mode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjust_scale()

    def set_fit_width(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoom_mode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjust_scale()

    def toggle_polygons(self, value):
        for item, shape in self.items_to_shapes.items():
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

    def load_file(self, file_path=None):
        """Load the specified file, or the last opened file if None. 加载指定的文件，如果为None则加载最后打开的文件"""
        self.reset_state()
        self.canvas.setEnabled(False)
        if file_path is None:
            file_path = self.settings.get(SETTING_FILENAME)

        # Make sure that filePath is a regular python string, rather than QString 确保filePath是一个常规的python字符串，而不是QString
        file_path = ustr(file_path)

        # Fix bug: An  index error after select a directory when open a new file. 修复错误:当打开一个新文件时，在选择目录后索引错误
        unicode_file_path = ustr(file_path)
        unicode_file_path = os.path.abspath(unicode_file_path)
        # Tzutalin 20160906 : Add file list and dock to move faster，Tzutalin 20160906:增加文件列表和码头移动更快
        # Highlight the file item 突出显示文件项
        if unicode_file_path and self.file_list_widget.count() > 0:
            if unicode_file_path in self.m_img_list:
                index = self.m_img_list.index(unicode_file_path)
                file_widget_item = self.file_list_widget.item(index)
                file_widget_item.setSelected(True)
            else:
                self.file_list_widget.clear()
                self.m_img_list.clear()

        if unicode_file_path and os.path.exists(unicode_file_path):
            if LabelFile.is_label_file(unicode_file_path):
                try:
                    self.label_file = LabelFile(unicode_file_path)
                except LabelFileError as e:
                    self.error_message(u'Error opening file',
                                       (u"<p><b>%s</b></p>"
                                        u"<p>Make sure <i>%s</i> is a valid label file.")
                                       % (e, unicode_file_path))
                    self.status("Error reading %s" % unicode_file_path)
                    return False
                self.image_data = self.label_file.image_data
                self.line_color = QColor(*self.label_file.lineColor)
                self.fill_color = QColor(*self.label_file.fillColor)
                self.canvas.verified = self.label_file.verified
            else:
                # Load image:
                # read data first and store for saving into label file.
                self.image_data = read(unicode_file_path, None)
                self.label_file = None
                self.canvas.verified = False

            if isinstance(self.image_data, QImage):
                image = self.image_data
            else:
                image = QImage.fromData(self.image_data)
            if image.isNull():
                self.error_message(u'Error opening file',
                                   u"<p>Make sure <i>%s</i> is a valid image file." % unicode_file_path)
                self.status("Error reading %s" % unicode_file_path)
                return False
            self.status("Loaded %s" % os.path.basename(unicode_file_path))
            self.image = image
            self.file_path = unicode_file_path
            self.canvas.load_pixmap(QPixmap.fromImage(image))
            if self.label_file:
                self.load_labels(self.label_file.shapes)
            self.update_combo_box()
            self.set_clean()
            self.canvas.setEnabled(True)
            self.adjust_scale(initial=True)
            self.paint_canvas()
            self.add_recent_file(self.file_path)
            self.toggle_actions(True)
            self.show_bounding_box_from_annotation_file(file_path)

            counter = self.counter_str()
            self.setWindowTitle(__appname__ + ' ' + file_path + ' ' + counter)

            # Default : select last item if there is at least one item,Default:如果至少有一项，则选择最后一项
            if self.label_list.count():
                self.label_list.setCurrentItem(self.label_list.item(self.label_list.count() - 1))
                self.label_list.item(self.label_list.count() - 1).setSelected(True)

            self.canvas.setFocus(True)
            return True
        return False

    def counter_str(self):
        """
        Converts image counter to string representation.
        """
        return '[{} / {}]'.format(self.cur_img_idx + 1, self.img_count)

    def show_bounding_box_from_annotation_file(self, file_path):
        if self.default_save_dir is not None:
            basename = os.path.basename(os.path.splitext(file_path)[0])
            xml_path = os.path.join(self.default_save_dir, basename + XML_EXT)
            txt_path = os.path.join(self.default_save_dir, basename + TXT_EXT)
            json_path = os.path.join(self.default_save_dir, basename + JSON_EXT)

            """Annotation file priority:
            PascalXML > YOLO 
            """
            #注释文件优先级:PascalXML > YOLO
            if os.path.isfile(xml_path):
                self.load_pascal_xml_by_filename(xml_path)
            elif os.path.isfile(txt_path):
                self.load_yolo_txt_by_filename(txt_path)
            elif os.path.isfile(json_path):
                self.load_create_ml_json_by_filename(json_path, file_path)

        else:
            xml_path = os.path.splitext(file_path)[0] + XML_EXT
            txt_path = os.path.splitext(file_path)[0] + TXT_EXT
            if os.path.isfile(xml_path):
                self.load_pascal_xml_by_filename(xml_path)
            elif os.path.isfile(txt_path):
                self.load_yolo_txt_by_filename(txt_path)

    def resizeEvent(self, event):
        if self.canvas and not self.image.isNull()\
           and self.zoom_mode != self.MANUAL_ZOOM:
            self.adjust_scale()
        super(MainWindow, self).resizeEvent(event)

    def paint_canvas(self):
        assert not self.image.isNull(), "cannot paint null image"#无法绘制空图像
        self.canvas.scale = 0.01 * self.zoom_widget.value()
        self.canvas.label_font_size = int(0.02 * max(self.image.width(), self.image.height()))
        self.canvas.adjustSize()
        self.canvas.update()

    def adjust_scale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoom_mode]()
        self.zoom_widget.setValue(int(100 * value))

    def scale_fit_window(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scale_fit_width(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event):
        if not self.may_continue():
            event.ignore()
        settings = self.settings
        # If it loads images from dir, don't load it at the beginning
        if self.dir_name is None:
            settings[SETTING_FILENAME] = self.file_path if self.file_path else ''
        else:
            settings[SETTING_FILENAME] = ''

        settings[SETTING_WIN_SIZE] = self.size()
        settings[SETTING_WIN_POSE] = self.pos()
        settings[SETTING_WIN_STATE] = self.saveState()
        settings[SETTING_LINE_COLOR] = self.line_color
        settings[SETTING_FILL_COLOR] = self.fill_color
        settings[SETTING_RECENT_FILES] = self.recent_files
        settings[SETTING_ADVANCE_MODE] = not self._beginner
        if self.default_save_dir and os.path.exists(self.default_save_dir):
            settings[SETTING_SAVE_DIR] = ustr(self.default_save_dir)
        else:
            settings[SETTING_SAVE_DIR] = ''

        if self.last_open_dir and os.path.exists(self.last_open_dir):
            settings[SETTING_LAST_OPEN_DIR] = self.last_open_dir
        else:
            settings[SETTING_LAST_OPEN_DIR] = ''

        settings[SETTING_AUTO_SAVE] = self.auto_saving.isChecked()
        settings[SETTING_SAVE_ZOOM] = self.save_zoom.isChecked()
        settings[SETTING_PURE_MODE] = self.pure_mode.isChecked()
        settings[SETTING_SINGLE_CLASS] = self.single_class_mode.isChecked()
        settings[SETTING_PAINT_LABEL] = self.display_label_option.isChecked()
        settings[SETTING_DRAW_SQUARE] = self.draw_squares_option.isChecked()
        settings[SETTING_LABEL_FILE_FORMAT] = self.label_file_format
        if self.cur_img_idx + 1 < self.img_count:#不是最后一个文件时，记录节点
            settings[self.last_open_dir] = self.last_open_file#把关闭前操作的文件写入序列化
        elif self.cur_img_idx + 1 == self.img_count:#是最后一个文件时，不记录节点，并删除节点
            if self.settings.get(self.last_open_dir):#如果有节点存在
                settings.pop(self.last_open_dir)
        settings.save()

    def load_recent(self, filename):
        if self.may_continue():
            self.load_file(filename)

    def scan_all_images(self, folder_path):
        extensions = ['.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        images = []

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relative_path = os.path.join(root, file)
                    path = ustr(os.path.abspath(relative_path))
                    images.append(path)
        natural_sort(images, key=lambda x: x.lower())
        return images

    def change_save_dir_dialog(self, _value=False):
        if self.default_save_dir is not None:
            path = ustr(self.default_save_dir)
        else:
            path = '.'

        dir_path = ustr(QFileDialog.getExistingDirectory(self,
                                                         '%s - Save annotations to the directory' % __appname__, path,  QFileDialog.ShowDirsOnly
                                                         | QFileDialog.DontResolveSymlinks))

        if dir_path is not None and len(dir_path) > 1:
            self.default_save_dir = dir_path

        self.statusBar().showMessage('%s . Annotation will be saved to %s' %
                                     ('Change saved folder', self.default_save_dir))
        self.statusBar().show()#选择保存路径后，工具底部中展示该提示

    def open_annotation_dialog(self, _value=False):
        if self.file_path is None:
            self.statusBar().showMessage('Please select image first')
            self.statusBar().show()
            return

        path = os.path.dirname(ustr(self.file_path))\
            if self.file_path else '.'
        if self.label_file_format == LabelFileFormat.PASCAL_VOC:
            filters = "Open Annotation XML file (%s)" % ' '.join(['*.xml'])
            filename = ustr(QFileDialog.getOpenFileName(self, '%s - Choose a xml file' % __appname__, path, filters))
            if filename:
                if isinstance(filename, (tuple, list)):
                    filename = filename[0]
            self.load_pascal_xml_by_filename(filename)

    def open_dir_dialog(self, _value=False, dir_path=None, silent=False):#打开数据目录操作
        if not self.may_continue():#当图片中没有标注框，或者有标注修改未保存时弹出的对话框选择No或者yes时不进入该判断。否则跳过打开文件夹选择的操作
            return

        default_open_dir_path = dir_path if dir_path else '.'
        if self.last_open_dir and os.path.exists(self.last_open_dir):#如果反序列化中有记录着最后打开的目录
            default_open_dir_path = self.last_open_dir#默认打开last_open_dir文件夹
        else:
            default_open_dir_path = os.path.dirname(self.file_path) if self.file_path else '.'#否则默认打开文件等于所选择目录
        if silent != True:#如果是主动点击触发的时候，silent=false,执行下面代码，弹出文件选择窗口，选择文件后规范编码，赋值给target_dir_path.
            target_dir_path = ustr(QFileDialog.getExistingDirectory(self,
                                                                    '%s - Open Directory' % __appname__, default_open_dir_path,
                                                                    QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        else:
            target_dir_path = ustr(default_open_dir_path)
        self.last_open_dir = target_dir_path
        self.import_dir_images(target_dir_path)

    def import_dir_images(self, dir_path):
        if not self.may_continue() or not dir_path:
            return

        self.last_open_dir = dir_path
        self.dir_name = dir_path
        self.file_path = None
        self.file_list_widget.clear()
        self.m_img_list = self.scan_all_images(dir_path)#扫描出所有image
        self.img_count = len(self.m_img_list)#图片数量
        self.open_next_image()#加载下一张图片
        for imgPath in self.m_img_list:#把所有列表中的图片名加载到列表组件中显示出来
            item = QListWidgetItem(imgPath)
            self.file_list_widget.addItem(item)

    def verify_image(self, _value=False):
        # Proceeding next image without dialog if having any label
        if self.file_path is not None:
            try:
                self.label_file.toggle_verify()
            except AttributeError:
                # If the labelling file does not exist yet, create if and
                # re-save it with the verified attribute.
                self.save_file()
                if self.label_file is not None:
                    self.label_file.toggle_verify()
                else:
                    return

            self.canvas.verified = self.label_file.verified
            self.paint_canvas()
            self.save_file()

    def open_prev_image(self, _value=False):
        # Proceeding prev image without dialog if having any label
        if self.auto_saving.isChecked():
            if self.default_save_dir is not None:
                if self.dirty is True:
                    self.save_file()
                elif self.dirty is False and self.no_shapes() and self.pure_mode.isChecked():
                    self.save_file()
            else:
                self.change_save_dir_dialog()
                return
        if not self.may_continue():
            return

        if self.img_count <= 0:
            return

        if self.file_path is None:
            return

        if self.cur_img_idx - 1 >= 0:
            self.cur_img_idx -= 1
            filename = self.m_img_list[self.cur_img_idx]
            if filename:
                self.last_open_file = filename
                if self.save_zoom.isChecked():  # 如果有勾选上保存缩放值，那么接下来该张图片使用这个缩放值a
                    zoomvalue = self.zoom_widget.value()
                    h_bar = self.scroll_bars[Qt.Horizontal]
                    v_bar = self.scroll_bars[Qt.Vertical]
                    save_h_bar = h_bar.value()
                    save_v_bar = v_bar.value()
                    # print(save_h_bar,save_v_bar)
                    self.load_file(filename)
                    self.set_zoom(zoomvalue)
                    h_bar.setValue(save_h_bar)
                    v_bar.setValue(save_v_bar)
                else:
                    self.load_file(filename)


    def open_next_image(self, _value=False):#切换下一张图片
        # Proceeding prev image without dialog if having any label如果有任何标签，无需对话框继续前视图像
        if self.auto_saving.isChecked():#如果自动保存选择了
            if self.default_save_dir is not None:#如果保存目录不为空
                if self.dirty is True:#如果有标注修改
                    self.save_file()
                elif self.dirty is False and self.no_shapes() and self.pure_mode.isChecked():
                    self.save_file()
            else:
                self.change_save_dir_dialog()#保存目录为空的话，弹出选择保存目录
                return
        if not self.may_continue():#may_continue方法中，如果没有画框操作，返回true,此处为not,所以没有画框操作就不直接结束open_next_image方法，画框后选择取消那就直接结束方法不跳到下一张，选择yes保存标注跳到下一张，选择no不保存标注跳到下一张
            return

        if self.img_count <= 0:
            return

        filename = None
        if self.file_path is None:#如果初次打开文件，那么file_path肯定为None
            if self.settings.get(self.last_open_dir):
                filename = self.settings.get(self.last_open_dir)
                if filename in self.m_img_list:
                    self.cur_img_idx = self.m_img_list.index(filename)
                else:#此文件夹有历史记录文件夹相同名命，当前文件夹下找不到该历史记录文件。
                    msg = u'The history file cannot be found in the current folder. Whether to open the first one'  #
                    if QMessageBox.warning(self, u'Attention', msg, QMessageBox.Yes) == QMessageBox.Yes:
                        filename = self.m_img_list[0]  # filename等于列表中的第一张图。
                        self.cur_img_idx = 0
            else:
                filename = self.m_img_list[0]#filename等于列表中的第一张图。
                self.cur_img_idx = 0
        else:#之后就打开下一张
            if self.cur_img_idx + 1 < self.img_count:
                self.cur_img_idx += 1
                filename = self.m_img_list[self.cur_img_idx]

        if filename:
            self.last_open_file = filename
            if self.save_zoom.isChecked():  # 如果有勾选上保存缩放值，那么接下来该张图片使用这个缩放值a
                zoomvalue = self.zoom_widget.value()
                h_bar = self.scroll_bars[Qt.Horizontal]
                v_bar = self.scroll_bars[Qt.Vertical]
                save_h_bar = h_bar.value()
                save_v_bar = v_bar.value()
                # print(save_h_bar, save_v_bar)
                self.load_file(filename)
                self.set_zoom(zoomvalue)
                h_bar.setValue(save_h_bar)
                v_bar.setValue(save_v_bar)

            else:
                self.load_file(filename)

    def open_file(self, _value=False):
        if not self.may_continue():
            return
        path = os.path.dirname(ustr(self.file_path)) if self.file_path else '.'
        formats = ['*.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        filters = "Image & Label files (%s)" % ' '.join(formats + ['*%s' % LabelFile.suffix])
        filename = QFileDialog.getOpenFileName(self, '%s - Choose Image or Label file' % __appname__, path, filters)
        if filename:
            if isinstance(filename, (tuple, list)):
                filename = filename[0]
            self.cur_img_idx = 0
            self.img_count = 1
            self.load_file(filename)

    def save_file(self, _value=False):
        if self.default_save_dir is not None and len(ustr(self.default_save_dir)):#如果有默认的保存路径
            if self.file_path:
                image_file_name = os.path.basename(self.file_path)#basename获取文件名，带后缀
                saved_file_name = os.path.splitext(image_file_name)[0]#拆分文件名和后缀
                saved_path = os.path.join(ustr(self.default_save_dir), saved_file_name)#拼接保存路径和文件名部分，不带路径
                self._save_file(saved_path)
        else:#否则没有选择保存路径的情况下
            image_file_dir = os.path.dirname(self.file_path)#图片文件所在的目录
            image_file_name = os.path.basename(self.file_path)
            saved_file_name = os.path.splitext(image_file_name)[0]
            saved_path = os.path.join(image_file_dir, saved_file_name)
            #执行保存操作传入保存文件夹路径，如果有标注文件就传入标注文件，否则传入save_file_dialog的返回值
            self._save_file(saved_path if self.label_file
                            else self.save_file_dialog(remove_ext=False))

    def save_file_as(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._save_file(self.save_file_dialog())

    def save_file_dialog(self, remove_ext=True):
        caption = '%s - Choose File' % __appname__
        filters = 'File (*%s)' % LabelFile.suffix#文件后缀类型
        open_dialog_path = self.current_path()#
        dlg = QFileDialog(self, caption, open_dialog_path, filters)#QFileDialog 是 Qt 框架提供的一个用于打开和保存文件的对话框。通过 QFileDialog，用户可以打开文件、保存文件或选择目录。它提供了以下常用的功能：caption标题，open_dialog_path是默认路径
        dlg.setDefaultSuffix(LabelFile.suffix[1:])#setDefaultSuffix 是 PyQt5 中 QFileDialog 类的一个方法，用于设置默认保存文件时的后缀名。如果用户没有指定文件名的后缀名，那么将使用默认的后缀名。
        dlg.setAcceptMode(QFileDialog.AcceptSave)#setAcceptMode 是 PyQt5 中 QFileDialog 类的一个方法，用于设置对话框的接受模式。它有两种不同的模式：保存模式和打开模式。在打开模式下，用户可以选择一个或多个文件，并将其用于后续操作。而在保存模式下，用户需要指定一个新的文件名并保存他们的更改。
        #QFileDialog.AcceptSave 是 PyQt5 中 QFileDialog 类的一个常量，表示对话框的接受模式为保存（Save）模式
        filename_without_extension = os.path.splitext(self.file_path)[0]
        dlg.selectFile(filename_without_extension)#selectFile 是 PyQt5 中 QFileDialog 类的方法之一，用于设置对话框初始选中的文件。
        dlg.setOption(QFileDialog.DontUseNativeDialog, False)#setOption 是 PyQt5 中 QFileDialog 类的方法之一，用于设置对话框的选项。使用该方法可以调整对话框的显示方式和功能。例如，可以使用该方法启用或禁用常规文件浏览器中可见的选项，例如“显示隐藏的文件”、“允许多个选择”、“文件名自动填充”等
        #QFileDialog.DontUseNativeDialog参数含义：是否使用本地系统对话框
        if dlg.exec_():#if dlg.exec_(): 语句用于检查用户是否执行了对话框中的操作，并根据返回值做出相应的响应。用户可以进行各种交互操作（例如输入文本、点击按钮）。当用户完成对话框中的操作并点击“确定”按钮时，dlg.exec_() 方法会返回 True，表示对话框已成功执行。
            full_file_path = ustr(dlg.selectedFiles()[0])
            if remove_ext:
                return os.path.splitext(full_file_path)[0]  # Return file path without the extension.获取不携带拓展名的路径
            else:
                return full_file_path
        return ''

    def _save_file(self, annotation_file_path):
        if annotation_file_path and self.save_labels(annotation_file_path):
            self.set_clean()#设置为干净模式
            self.statusBar().showMessage('Saved to  %s' % annotation_file_path)
            self.statusBar().show()#保存后工具底部展示该提示，保存在哪个位置。

    def close_file(self, _value=False):
        if not self.may_continue():
            return
        self.reset_state()
        self.set_clean()
        self.toggle_actions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    def delete_image(self):
        delete_path = self.file_path
        if delete_path is not None:
            self.open_next_image()
            self.cur_img_idx -= 1
            self.img_count -= 1
            if os.path.exists(delete_path):
                os.remove(delete_path)
            self.import_dir_images(self.last_open_dir)

    def reset_all(self):
        self.settings.reset()
        self.close()
        process = QProcess()
        process.startDetached(os.path.abspath(__file__))
    #按quet退出时在序列化文件中添加最后打开的目录：文件，从而实现下次打开该目录会直接定位到该文件，如果已经标注完即删除该记录。
    def Quet_event(self):
        self.close()
    def may_continue(self):
        if not self.dirty:#如果没有画标注框,标注没有变化，返回True
            if not self.auto_saving.isChecked() and self.no_shapes() and self.pure_mode.isChecked():
                self.save_file()
            return True
        else:#否则没有自动保存且有修改标注的情况下，弹出确认框
            discard_changes = self.discard_changes_dialog()#弹出确认框
            if discard_changes == QMessageBox.No:#点击No返回true
                return True
            elif discard_changes == QMessageBox.Yes:#点击Yes保存标注 返回True
                self.save_file()
                return True
            else:
                return False

    def discard_changes_dialog(self):#弹窗提示 是否要保存修改
        yes, no, cancel = QMessageBox.Yes, QMessageBox.No, QMessageBox.Cancel
        msg = u'You have unsaved changes, would you like to save them and proceed?\nClick "No" to undo all changes.'#您有未保存的更改，要保存它们并继续吗?点击“否”撤消所有更改
        return QMessageBox.warning(self, u'Attention', msg, yes | no | cancel)


    def error_message(self, title, message):
        return QMessageBox.critical(self, title,
                                    '<p><b>%s</b></p>%s' % (title, message))

    def current_path(self):
        return os.path.dirname(self.file_path) if self.file_path else '.'

    def choose_color1(self):
        color = self.color_dialog.getColor(self.line_color, u'Choose line color',
                                           default=DEFAULT_LINE_COLOR)
        if color:
            self.line_color = color
            Shape.line_color = color
            self.canvas.set_drawing_color(color)
            self.canvas.update()
            self.set_dirty()

    def delete_selected_shape(self):
        self.remove_label(self.canvas.delete_selected())
        self.set_dirty()
        if self.no_shapes():
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)
    def delete_all_shape(self):
        for shape in self.canvas.shapes:
            self.remove_label(shape)
            self.canvas.shapes.remove(shape)
            self.canvas.update()#删除框之后,更新画布
            self.set_dirty()
            if len(self.canvas.shapes) !=0:
                self.delete_all_shape()
            if self.no_shapes():
                for action in self.actions.onShapesPresent:
                    action.setEnabled(False)

    def choose_shape_line_color(self):
        color = self.color_dialog.getColor(self.line_color, u'Choose Line Color',
                                           default=DEFAULT_LINE_COLOR)
        if color:
            self.canvas.selected_shape.line_color = color
            self.canvas.update()
            self.set_dirty()

    def choose_shape_fill_color(self):
        color = self.color_dialog.getColor(self.fill_color, u'Choose Fill Color',
                                           default=DEFAULT_FILL_COLOR)
        if color:
            self.canvas.selected_shape.fill_color = color
            self.canvas.update()
            self.set_dirty()

    def copy_shape(self):
        self.canvas.end_move(copy=True)
        self.add_label(self.canvas.selected_shape)
        self.set_dirty()

    def move_shape(self):
        self.canvas.end_move(copy=False)
        self.set_dirty()

    def load_predefined_classes(self, predef_classes_file):#获取predefined_classes.txt中标签。
        if os.path.exists(predef_classes_file) is True:
            with codecs.open(predef_classes_file, 'r', 'utf8') as f:
                for line in f:
                    line = line.strip()
                    if self.label_hist is None:
                        self.label_hist = [line]
                    else:
                        self.label_hist.append(line)

    def load_pascal_xml_by_filename(self, xml_path):
        if self.file_path is None:
            return
        if os.path.isfile(xml_path) is False:
            return

        self.set_format(FORMAT_PASCALVOC)

        t_voc_parse_reader = PascalVocReader(xml_path)
        shapes = t_voc_parse_reader.get_shapes()
        self.load_labels(shapes)
        self.canvas.verified = t_voc_parse_reader.verified

    def load_yolo_txt_by_filename(self, txt_path):
        if self.file_path is None:
            return
        if os.path.isfile(txt_path) is False:
            return

        self.set_format(FORMAT_YOLO)
        t_yolo_parse_reader = YoloReader(txt_path, self.image)
        shapes = t_yolo_parse_reader.get_shapes()
        # print(shapes)
        self.load_labels(shapes)
        self.canvas.verified = t_yolo_parse_reader.verified

    def load_create_ml_json_by_filename(self, json_path, file_path):
        if self.file_path is None:
            return
        if os.path.isfile(json_path) is False:
            return

        self.set_format(FORMAT_CREATEML)

        create_ml_parse_reader = CreateMLReader(json_path, file_path)
        shapes = create_ml_parse_reader.get_shapes()
        self.load_labels(shapes)
        self.canvas.verified = create_ml_parse_reader.verified

    def copy_previous_bounding_boxes(self):
        current_index = self.m_img_list.index(self.file_path)
        if current_index - 1 >= 0:
            prev_file_path = self.m_img_list[current_index - 1]
            self.show_bounding_box_from_annotation_file(prev_file_path)
            self.save_file()

    def toggle_paint_labels_option(self):
        for shape in self.canvas.shapes:
            shape.paint_label = self.display_label_option.isChecked()

    def toggle_draw_square(self):
        self.canvas.set_drawing_shape_to_square(self.draw_squares_option.isChecked())

def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])


def read(filename, default=None):
    try:
        reader = QImageReader(filename)
        reader.setAutoTransform(True)
        return reader.read()
    except:
        return default


def get_main_app(argv=[]):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    标准样板Qt应用程序代码。
    做除了app.exec_()以外的所有事情——以便我们可以在一个线程中测试应用程序
    """
    app = QApplication(argv)
    app.setApplicationName(__appname__)#设置程序名称
    app.setWindowIcon(new_icon("app"))#设置应用图标
    # Tzutalin 201705+: Accept extra agruments to change predefined class file  zuttalin 201705+:接受额外的参数来更改预定义的类文件
    argparser = argparse.ArgumentParser()#ArgumentParser 对象包含将命令行解析成 Python 数据类型所需的全部信息。
    argparser.add_argument("image_dir", nargs="?")#添加image_dir参数， nargs="?"表示只可以添加一个或0个参数
    argparser.add_argument("class_file",
                           default=os.path.join(os.path.dirname(__file__), "data", "predefined_classes.txt"),
                           nargs="?")#添加class_file参数，默认值是default中的值
    argparser.add_argument("save_dir", nargs="?")#添加save_dir参数
    args = argparser.parse_args(argv[1:])#arg此时等于[image_dir,class_file,save_dir],因为第一个参数是程序本身。  parse_args() 解析指令

    args.image_dir = args.image_dir and os.path.normpath(args.image_dir)#规范路径写法
    args.class_file = args.class_file and os.path.normpath(args.class_file)
    args.save_dir = args.save_dir and os.path.normpath(args.save_dir)

    # Usage : labelImg.py image classFile saveDir使用方法:labelImg.py图像类文件保存目录
    win = MainWindow(args.image_dir,
                     args.class_file,
                     args.save_dir)#将三个参数传入到MainWindow方法中执行
    win.show()
    return app, win


def main():
    """construct main app and run it   构建主应用程序并运行它"""
    app, _win = get_main_app(sys.argv) #调用get_main_app(),sys.arg是调用sh
    return app.exec_()#exec_()进入程序的主循环，知道exit()被调用，说白了就是让这个程序运行。

if __name__ == '__main__':
    sys.exit(main())

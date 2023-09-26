# -*- coding: utf-8 -*-
try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs.utils import new_icon, label_validator,group_validator, trimmed

BB = QDialogButtonBox#多按钮控件


class LabelDialog(QDialog):#label对话框

    def __init__(self, text="Enter object label", parent=None, list_item=None):
        super(LabelDialog, self).__init__(parent)

        self.edit = QLineEdit()#单行文本控件
        self.edit.setText(text)#设置内容为text
        self.edit.setValidator(label_validator())#设置输入校验
        self.edit.editingFinished.connect(self.post_process)#editingFinished是一个信号，它在用户完成编辑一个可编辑的小部件
        self.edit_group_id = QLineEdit()
        self.edit_group_id.setPlaceholderText("Group ID")
        self.edit_group_id.setValidator(group_validator())  # 设置输入校验
        self.edit_group_id.editingFinished.connect(self.group_process)


        model = QStringListModel()#创建数据模型，该模型提供编辑和修改字符串列表数据的函数
        model.setStringList(list_item)#为数据模型设置Stringlist
        completer = QCompleter()#创建自动补全模型
        completer.setModel(model)#将数据模型添加到自动补全模型
        self.edit.setCompleter(completer)#将添加数据后的自动补全模型绑定到edit文本控件当中

        layout = QVBoxLayout()#垂直布局
        layout_edit = QHBoxLayout()
        layout_edit.addWidget(self.edit, 6)
        layout_edit.addWidget(self.edit_group_id, 2)
        layout.addLayout(layout_edit)
        # layout.addWidget(self.edit)#再layout中添加控件
        self.button_box = bb = BB(BB.Ok | BB.Cancel, Qt.Horizontal, self)#多按钮控件，ok和cancel按钮水平布局
        bb.button(BB.Ok).setIcon(new_icon('done'))#为ok按钮设置图标
        bb.button(BB.Cancel).setIcon(new_icon('undo'))
        bb.accepted.connect(self.validate)#点击这些按钮后会产生信号，ok按钮产生accepted信号，该信号连接validate方法
        bb.rejected.connect(self.reject)#cancel按钮产生rejected信号，触发reject。关闭dialog对话窗
        layout.addWidget(bb)

        if list_item is not None and len(list_item) > 0:#当label配置文件中读取出来的label_hist有标签项
            self.list_widget = QListWidget(self)#创建一个数据列表展示控件
            for item in list_item:
                self.list_widget.addItem(item)#为控件添加label选项
            self.list_widget.itemClicked.connect(self.list_item_click)#每个选项单击后的信号
            self.list_widget.itemDoubleClicked.connect(self.list_item_double_click)#每个选项双击后的信号
            layout.addWidget(self.list_widget)

        self.setLayout(layout)

    def validate(self):#
        if trimmed(self.edit.text()):#如果有取除开头结尾的空字符
            self.accept()#不明白

    def post_process(self):
        self.edit.setText(trimmed(self.edit.text()))
    def group_process(self):
        self.edit_group_id.setText(trimmed(self.edit_group_id.text()))
    def getGroupId(self):
        group_id = self.edit_group_id.text()
        if group_id:
            return int(group_id)
        return None
    def pop_up(self, text=None, move=True, group_id=None):
        """
        Shows the dialog, setting the current text to `text`, and blocks the caller until the user has made a choice.
        If the user entered a label, that label is returned, otherwise (i.e. if the user cancelled the action)
        `None` is returned.显示对话框，将当前文本设置为' text '，并阻止调用者，直到用户做出选择。
    如果用户输入了一个标签，则返回该标签，否则(例如，如果用户取消了操作)
    没有返回。
        """
        print(text,group_id)
        self.edit.setText(text)
        self.edit_group_id.setText(str(group_id))
        self.edit.setSelection(0, len(text))#默认选中文本
        self.edit.setFocus(Qt.PopupFocusReason)
        if move:
            cursor_pos = QCursor.pos()
            parent_bottom_right = self.parentWidget().geometry()
            max_x = parent_bottom_right.x() + parent_bottom_right.width() - self.sizeHint().width()
            max_y = parent_bottom_right.y() + parent_bottom_right.height() - self.sizeHint().height()
            max_global = self.parentWidget().mapToGlobal(QPoint(max_x, max_y))
            if cursor_pos.x() > max_global.x():
                cursor_pos.setX(max_global.x())
            if cursor_pos.y() > max_global.y():
                cursor_pos.setY(max_global.y())
            self.move(cursor_pos)
        if text is None:
            text = self.edit.text()
        if group_id is None:
            self.edit_group_id.clear()
        if self.exec_():
            return (
                self.edit.text(),
                self.getGroupId(),
            )
        else:
            return None, None

    def list_item_click(self, t_qlist_widget_item):#当点击列表中的哪个label后edit控件中的text设置为哪个label，选标签操作
        text = trimmed(t_qlist_widget_item.text())
        self.edit.setText(text)

    def list_item_double_click(self, t_qlist_widget_item):
        self.list_item_click(t_qlist_widget_item)
        self.validate()

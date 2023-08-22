import sys
try:
    from PyQt5.QtWidgets import QWidget, QHBoxLayout, QComboBox, QLineEdit
except ImportError:
    # needed for py3+qt4
    # Ref:
    # http://pyqt.sourceforge.net/Docs/PyQt4/incompatible_apis.html
    # http://stackoverflow.com/questions/21217399/pyqt4-qtcore-qvariant-object-instead-of-a-string
    if sys.version_info.major >= 3:
        import sip
        sip.setapi('QVariant', 2)
    from PyQt4.QtGui import QWidget, QHBoxLayout, QComboBox


class ComboBox(QWidget):
    def __init__(self, parent=None, items=[]):
        super(ComboBox, self).__init__(parent)

        layout = QHBoxLayout()#水平布局
        self.cb = QComboBox()#创建一个下拉框实例
        self.items = items
        self.cb.addItems(self.items)#添加下拉选项

        self.cb.activated.connect(parent.combo_selection_changed)

        layout.addWidget(self.cb)
        self.setLayout(layout)

    def update_items(self, items):
        self.items = items
        self.cb.clear()
        self.cb.addItems(self.items)
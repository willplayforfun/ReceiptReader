from PyQt5.QtCore import *
from PyQt5.QtCore import pyqtSignal as Signal
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

from rrWidgets.PhotoViewer import PhotoViewer
# OpStack
from rrUtilities.ImageOperations import *
# getting cv2_to_pixmap helper
from rrUtilities.TypeHelpers import *


def clearLayout(layout):
	if layout != None:
		while layout.count():
			child = layout.takeAt(0)
			if child.widget() is not None:
				child.widget().deleteLater()
			elif child.layout() is not None:
				clearLayout(child.layout())



# For a given operation, two images are shown: before and after the operation.
class OperationViewerWidget(QWidget):
	def __init__(self, parent = None):
		super(OperationViewerWidget, self).__init__(parent)
		self.setSizePolicy(self.getSizePolicy())
		self.setMinimumSize(QSize(200, 600))

		self.before_label = QLabel("BEFORE LABEL")
		self.after_label = QLabel("AFTER LABEL")

		self.before_img = PhotoViewer(self)
		#self.before_img = QLabel("BEFORE IMG")
		#self.before_img.setMinimumSize(QSize(20, 20))
		#self.before_img.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
		#self.before_img.setScaledContents(True)
		
		self.after_img = PhotoViewer(self)
		#self.after_img = QLabel("AFTER IMG")
		#self.after_img.setMinimumSize(QSize(20, 20))
		#self.after_img.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
		#self.after_img.setScaledContents(True)

		layout = QGridLayout()

		layout.addWidget(self.before_img,0,0)
		layout.addWidget(self.before_label,1,0)

		layout.addWidget(self.after_img,0,1)
		layout.addWidget(self.after_label,1,1)

		self.setLayout(layout)
		
	def getSizePolicy(self):
		sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		sizePolicy.setHorizontalStretch(0)
		sizePolicy.setVerticalStretch(0)
		return sizePolicy

	def setup(self, before, after, update=False):
		self.before = before
		self.after = after
		self.before_label.setText(before[1])
		self.after_label.setText(after[1])
		
		self.set_image_on_label(before[0], self.before_img)
		self.set_image_on_label(after[0], self.after_img)

		# HACK to not resize images when just updating, cuz I'm lazy
		if update:
			pass
			#self.before_img.just_updated = False
			#self.after_img.just_updated = False
			
	def set_image_on_label(self, cv2_img, label):
		pix = cv2_to_pixmap(cv2_img)
		label.setPixmap(pix)
			
	def selected(self):
		pass

# this widget has tabs across the top, one for each operation. 
class StackPreviewerWidget(QDockWidget):

	tabChanged = Signal(int)
	closeRequested = Signal(int)

	def __init__(self, parent = None):
		super(StackPreviewerWidget, self).__init__("Operation Previewer", parent)
		self.setFloating(False)
		self.setFeatures(self.DockWidgetMovable)
		self.setMinimumSize(QSize(200, 600))
		
		self.tabWidget = QTabWidget()
		self.tabWidget.currentChanged.connect(self.tab_changed)
		self.tabWidget.tabCloseRequested.connect(self.close_requested)
		self.setWidget(self.tabWidget)
		
		self.rebuildingTabs = False
		
		#bind to signals on StackEditor application
		if parent is not None:
			parent.onOperationSelected.connect(self.set_current_index)
	
	
	def clear(self):
		self.rebuildingTabs = True
		self.tabWidget.clear()
		self.rebuildingTabs = False
		
	def update_from_results(self, results):
		prev_result = results[0]
		for index, (tab, result) in enumerate(zip(self.tabs, results[1:])):
			tab.setup(prev_result, result, True)
			prev_result = result
			self.tabWidget.setTabText(index, result[1])
		
	def setup_from_results(self, results):
		self.rebuildingTabs = True
		
		self.tabWidget.clear()
		self.tabs = []
		prev_step = results[0]
		for ind in range(1, len(results)):
			step = results[ind]

			tab = OperationViewerWidget(self)
			tab.setup(prev_step, step)
			prev_step = step
			
			self.tabWidget.addTab(tab, step[1])
			self.tabs.append(tab)
			
		self.rebuildingTabs = False
		
	def tab_changed(self, index):
		if index >= 0 and len(self.tabs) > index and not self.rebuildingTabs:
			self.tabs[index].selected()
			self.tabChanged.emit(index)
		
	def close_requested(self, index):
		self.closeRequested.emit(index)
	
	def set_current_index(self, index):
		self.tabWidget.setCurrentIndex(index)


# this is a small button used in the StackModifierWidget to present options for moving
# on operation up or down, or deleting it
class OperationModifierButtonWidget(QPushButton):
	def __init__(self, label = "", parent = None):
		super(OperationModifierButtonWidget, self).__init__(label, parent)
		self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
		
	def minimumSizeHint(self):
		return QSize(10, 10)

	def sizeHint(self):
		return QSize(20, 20) 
		
# this widget presents an ordered list of each operation on the loaded stack.
# operations can be removed or added. 
# clicking on operation shows it in the operation viewer widget.
# operations can also be muted
class StackModifierWidget(QDockWidget):

	onOperationSelected = Signal(int)
	onOperationDeleted = Signal(int)
	onOperationMovedUp = Signal(int)
	onOperationMovedDown = Signal(int)
	onOperationAdded = Signal()
	onOperationMuted = Signal(int)

	def __init__(self, parent = None):
		super(StackModifierWidget, self).__init__("Stack Modifier", parent)
		self.setFloating(False)
		self.setFeatures(self.DockWidgetMovable)
		self.setMinimumSize(QSize(200, 600))
		
		self.rows = []
		self.layout = QVBoxLayout()
		self.container = QWidget()
		self.container.setLayout(self.layout)
		self.setWidget(self.container)
		
		#bind to signals on StackEditor application
		if parent is not None:
			parent.onOperationSelected.connect(self.set_current_index)
	
	def setup_from_stack(self, stack):
		# remove all widgets
		clearLayout(self.layout)
		self.rows = []
		
		self.latest_stack = stack
		
		for op in stack.get_stack():
			op.onLabelUpdatedCallbacks.append(self.handleLabelUpdated)
			self.add_row(op.get_label(), op.muted)
		
		add_button = QPushButton("+")
		add_button.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
		add_button.clicked.connect(self.add_operation)
			
		self.layout.addWidget(add_button)
		self.layout.addStretch()
		
	def handleLabelUpdated(self):
		self.update_names(self.latest_stack)
		
	def update_names(self, stack):
		# stack is of type OperationStack
		for index in range(len(stack.get_stack())):
			# assumes that the first widget in a row is a QPushButton
			self.rows[index].layout().itemAt(0).widget().setText(stack.get_label(index))
		
	def row_selected(self, index):
		self.onOperationSelected.emit(index)
	
	def mute_selected(self, index):
		self.onOperationMuted.emit(index)
		
	def remove_selected(self, index):
		self.onOperationDeleted.emit(index)
		
	def up_selected(self, index):
		self.onOperationMovedUp.emit(index)
		
	def down_selected(self, index):
		self.onOperationMovedDown.emit(index)
	
	def add_operation(self):
		self.onOperationAdded.emit()
	
	def add_row(self, name, muted):
		index = len(self.rows)
		container = QWidget()
		container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
		#container.setStyleSheet("background-color:green;");
		
		name_button = QPushButton(name)
		name_button.setFlat(True)
		name_button.clicked.connect(lambda: self.row_selected(index))
		
		mute_button = OperationModifierButtonWidget("M")
		mute_button.clicked.connect(lambda: self.mute_selected(index))
		if muted:
			mute_button.setStyleSheet("background-color:red;");
		
		up_button = OperationModifierButtonWidget("^")
		up_button.clicked.connect(lambda: self.up_selected(index))
		
		down_button = OperationModifierButtonWidget("V")
		down_button.clicked.connect(lambda: self.down_selected(index))

		remove_button = OperationModifierButtonWidget("X")
		remove_button.clicked.connect(lambda: self.remove_selected(index))

		hbox = QHBoxLayout()
		hbox.addWidget(name_button)
		hbox.addWidget(mute_button)
		hbox.addWidget(up_button)
		hbox.addWidget(down_button)
		hbox.addWidget(remove_button)

		hbox.setSpacing(0)
		hbox.setContentsMargins(0,0,0,0)
		
		container.setLayout(hbox)
		
		self.layout.addWidget(container)
		self.rows.append(container)
	
	def set_current_index(self, index):
		for i in range(0, len(self.rows)):
			myFont=QFont()
			myFont.setBold(i == index)
			# index 0 is the layout, buttons start at 1
			label = self.rows[i].children()[1]
			label.setFont(myFont)
			label.update()


# this widget shows a single step of a result array and can be selected
class FullStackPreviewerImageWidget(QPushButton):

	onSelected = Signal(int)
	
	def __init__(self, index, parent = None):
		super(FullStackPreviewerImageWidget, self).__init__("", parent)
		self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
		
		self.index = index
		self.clicked.connect(self.on_clicked)
		
	def sizeHint(self):
		return QSize(100, 100)

	def setup(self, result, update=False):
		pix = cv2_to_pixmap(result[0])
		icon = QIcon()
		icon.addPixmap(pix)
		self.setIcon(icon)
		self.setIconSize(QSize(95, 95))
		
	def set_selected(self, selected):
		if selected:
			self.setStyleSheet("border: 5px solid red;")
		else:
			self.setStyleSheet("")
		self.update()
	
	def on_clicked(self):
		self.onSelected.emit(self.index)

# this widget shows all the steps of a stack
class FullStackPreviewerWidget(QDockWidget):

	onOperationSelected = Signal(int)

	def __init__(self, parent = None):
		super(FullStackPreviewerWidget, self).__init__("Stack Previewer", parent)
		self.setFloating(False)
		self.setFeatures(self.DockWidgetMovable)
		self.setMinimumSize(QSize(600, 100))
		
		self.steps = []
		self.layout = QHBoxLayout()
		self.container = QWidget()
		self.container.setLayout(self.layout)
		self.setWidget(self.container)
		
		#bind to signals on StackEditor application
		if parent is not None:
			parent.onOperationSelected.connect(self.set_current_index)
	
	def operation_selected(self, index):
		#print("op selected: {}".format(index))
		self.onOperationSelected.emit(index)
	
	def clear(self):
		clearLayout(self.layout)
		
	def update_from_results(self, results):
		for img, result in zip(self.steps, results):
			img.setup(result, True)
		
	def setup_from_results(self, results):
		# remove all widgets
		clearLayout(self.layout)
		self.steps = []
		
		for ind in range(0, len(results)):
			step = results[ind]

			img = FullStackPreviewerImageWidget(max(0, ind - 1), self)
			img.onSelected.connect(self.operation_selected)
			img.setup(step)
			
			self.layout.addWidget(img)
			self.steps.append(img)
		
		self.layout.addStretch()
		
	def row_selected(self, index):
		self.onOperationSelected.emit(index)
	
	def set_current_index(self, index):
		for i in range(0, len(self.steps)):
			widget = self.steps[i]
			widget.set_selected(i - 1 == index)
			widget.update()

#EOF
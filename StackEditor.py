from PyQt5.QtCore import *
from PyQt5.QtCore import pyqtSignal as Signal
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

from rrUtilities.ImageCleaner import MorphologicalOperationType as Morph
from rrUtilities.ImageCleaner import *

# getting is_valid_file for argparse
from rrUtilities.TypeHelpers import *

from rrWidgets.StackWidgets import *
from rrWidgets.TesseractPreviewerWidget import *

import argparse
import os
import io
import yaml
from queue import Queue
from rrUtilities.DirWatcher import DirWatcher

# This program lets a user design a sequence of Computer Vision Operations, or "OpStack",
# that processes a raw image into a machine-readable result.

# It consists of several widgets and windows.
# The primary window is the **StackEditor**
# It has the following widgets:
# 	- Stack Previewer: this shows the result of the currently selected operation
#			It builds tabs, and contains an OperationViewer widget inside it
#			This OperationViewer actually shows the image
#	- Stack Modifier: this allows operations to be added, deleted, and re-arranged
# 	- Operation Editor: this pane contains the specific sliders and controls for the selected operation
#	- Full Stack Previewer: this widget sits at the bottom and shows each step as a thumbnail

# To the sides are two additional widgets: 
# 	the Dataset Viewer, which shows files to be loaded
# 	the Tesseract Preview, which shows a preview of how OCR will interpret the image
		
# TODO: 
# 	show open filename in window bar
# 	allow customizing of operation labels
# 	multi-thread tesseract
# 	grey out tesseract update button until the stack changes
# 	toggle overlay of actual image in tesseract preview
# 	allow slaving all the image viewing areas to the same scroll amount
# 	fix scrolling out on image viewers
# 	add a check box to auto-update tesseract preview
# 	add stack saving / opening
# 	add boundaries and warping operations
# 	add undo/redo stack
# 	fix behavior of threshold panel, disabled fields don't update properly
# 	add better logging system with verbosity


DEFAULT_APPLICATION_Y = 300
DEFAULT_DATASET_VIEWER_X = -300 #200
DEFAULT_MAIN_WINDOW_X = 0 #500
DEFAULT_TESSERACT_PREVIEW_X = -800 #1800

TESSERACT_PATH = r'C:\Program Files (x86)\Tesseract-OCR\tesseract'

# this widget shows all the images in the dataset, 
# and lets you select one as an example to play with
class DatasetViewerWidget(QDockWidget):

	fileSelected = Signal(str)

	def __init__(self, parent = None, floating = False):
		super(DatasetViewerWidget, self).__init__("Dataset Viewer", parent)
		self.setFloating(floating)
		self.setFeatures(self.DockWidgetMovable)
		self.setMinimumSize(QSize(200, 600))
		
		self.dir_change_queue = Queue()
		self.dir_watchers = []
		
		self.paths_to_watch = []
		self.file_list = []
		
		self.layout = QVBoxLayout()
		self.container = QWidget()
		self.container.setLayout(self.layout)
		self.setWidget(self.container)
		
		self.current_file = QLabel("Current Test Image: None")
		self.layout.addWidget(self.current_file)
		
		self.listbox = QListWidget()
		self.listbox.clicked.connect(self.clicked)
		self.listbox.doubleClicked.connect(self.doubleClicked)
		self.layout.addWidget(self.listbox)

		self.DIR_BLACKLIST = ["venv", "__pycache__", "Tesseract-OCR", "rrUtilities", "rrWidgets"]
		self.VALID_IMG_EXTS = [".png", ".jpg"]
		
	def setup(self):
		start_dir = os.getcwd()
		print("Scanning files starting in {}".format(start_dir))
		
		# we want to find valid directories and watch them for file add/delete actions
		self.paths_to_watch = []
		for root, dirs, files in os.walk(start_dir):
			# ignore blacklisted dirs
			ignore_dir = False
			for black_dir in self.DIR_BLACKLIST: 
				if black_dir in root:
					#print("IGNORING " + root)
					ignore_dir = True
					break
			if ignore_dir:
				continue
			
			print(root)
			self.paths_to_watch.append(root)
			
			# we also want to initialize our starting list of files
			for file in files:
				if os.path.splitext(file)[1].lower() in self.VALID_IMG_EXTS:
					self.file_list.append([file, os.path.join(root,file)])
		
		# now we setup the watchers on those dirs
		for p in self.paths_to_watch:
			watcher = DirWatcher(p, self.dir_change_queue)
			watcher.onDirUpdate.connect(self.on_dir_update)
			self.dir_watchers.append(watcher)

		self.updateListWidget()

	def onFileOpened(self, filename):
		self.current_file.setText("Current Test Image: \n{0}".format(filename))

	def updateListWidget(self):
		self.listbox.clear()
	
		for index, file in enumerate(self.file_list):
			self.listbox.insertItem(index, file[0])

	def clicked(self, qmodelindex):
		row = qmodelindex.row()
		item = self.listbox.currentItem()
		print(self.file_list[row][0])
		
	def doubleClicked(self, qmodelindex):
		item = self.listbox.currentItem()
		row = qmodelindex.row()
		print(self.file_list[row][1])
		
		self.fileSelected.emit(self.file_list[row][1])
	
	def on_dir_update(self):
		try:
			file_type, filename, action = self.dir_change_queue.get() #get_nowait()
			
			#ignore updates to non-image files
			if os.path.splitext(filename)[1].lower() not in self.VALID_IMG_EXTS: return
			
			print("{}, {}, {}".format(file_type, filename, action))
			
			if action in ["Created", "Renamed from something"]:
				print(action)
				self.file_list.append([os.path.basename(filename), filename])
				self.updateListWidget()
			
			if action in ["Deleted", "Renamed to something"]:
				print(action)
				for index in range(len(self.file_list)):
					if self.file_list[index][1] == filename:
						self.file_list.pop(index)
						break
				else:
					print("Failed to find file for removal!")
				self.updateListWidget()
				
		except Queue.Empty:
			print("Error: Received dir update signal but no update is queued")

# this widget allows an operation type to be changed, 
# and properties of the operation to be edited
class OperationEditorWidget(QDockWidget):

	onPropertyChanged = Signal()
	onPropertySoftChanged = Signal()

	def __init__(self, parent = None):
		super(OperationEditorWidget, self).__init__("Operation Editor", parent)
		self.setFloating(False)
		self.setFeatures(self.DockWidgetMovable)
		self.setMinimumSize(QSize(200, 600))
		
		self.rows = []
		self.layout = QVBoxLayout()
		self.container = QWidget()
		self.container.setLayout(self.layout)
		self.setWidget(self.container)
		
		#bind to signals on StackEditor application
		self.StackEditorApplication = parent
		if parent is not None:
			parent.onOperationSelected.connect(self.onOperationSelected)
		
	def onOperationSelected(self, index):
		self.setup(self.StackEditorApplication.loadedStack.get_op(index).get_parameters())
		
	def clear_widgets(self):
		# remove all widgets
		clearLayout(self.layout)
		self.rows = []
		
	def add_common(self):
		pass
		
	def add_parameter(self, param):
		row = QWidget(self.container)
		layout = QHBoxLayout()
		
		label = QLabel(param.label)
		layout.addWidget(label)
	
		if param.type == ParameterType.SLIDER:
			slider = QSlider(Qt.Horizontal)
			slider.setRange(param.min, param.max)
			slider.setTickInterval(param.tickInterval)
			slider.setValue(param.getter())
			slider.setTickPosition(QSlider.TicksBelow)
			slider.sliderReleased.connect(lambda: param.setter(slider.value()))
			slider.sliderReleased.connect(lambda: self.onValueChanged())
			# TODO only bind this if live update is enabled
			slider.valueChanged.connect(lambda x: param.setter(x))
			slider.valueChanged.connect(lambda: self.onValueSoftChanged())
			if not param.enabled:
				slider.setDisabled(True)
			layout.addWidget(slider)
			
		elif param.type == ParameterType.CHECKBOX:
			checkBox = QCheckBox("")
			checkBox.setCheckState(Qt.Checked if param.getter() else Qt.Unchecked)
			checkBox.stateChanged.connect(param.setter)
			checkBox.stateChanged.connect(lambda: self.onValueChanged())
			if not param.enabled:
				checkBox.setDisabled(True)
			layout.addWidget(checkBox)
			
		elif param.type == ParameterType.NUMBER:
			lineEdit = QLineEdit(str(param.getter()))
			lineEdit.editingFinished.connect(lambda: param.setter(lineEdit.text()))
			lineEdit.editingFinished.connect(lambda: self.onValueChanged())
			# TODO only bind this if live update is enabled
			lineEdit.textEdited.connect(param.setter)
			lineEdit.textEdited.connect(lambda: self.onValueSoftChanged())
			if not param.enabled:
				lineEdit.setDisabled(True)
			layout.addWidget(lineEdit)
			
		elif param.type == ParameterType.STRING:
			lineEdit = QLineEdit(str(param.getter()))
			lineEdit.textEdited.connect(param.setter)
			lineEdit.textEdited.connect(lambda: self.onValueChanged())
			if not param.enabled:
				lineEdit.setDisabled(True)
			layout.addWidget(lineEdit)
			
		elif param.type == ParameterType.DROPDOWN:
			comboBox = QComboBox(row)
			startingIndex = 0
			startingValue = param.getter()
			for index, choice in enumerate(param.choices):
				if str(choice) == str(startingValue):
					startingIndex = index
				comboBox.addItem(str(choice))
			comboBox.activated[str].connect(param.setter)
			comboBox.activated[str].connect(lambda: self.onValueChanged())
			comboBox.setCurrentIndex(startingIndex)
			if not param.enabled:
				comboBox.setDisabled(True)
			layout.addWidget(comboBox)
			
			
		row.setLayout(layout)
		self.layout.addWidget(row)
		self.rows.append(row)
		
	def onValueChanged(self):
		self.onPropertyChanged.emit()
		
	def onValueSoftChanged(self):
		self.onPropertySoftChanged.emit()
		
	def setup(self, params):
		self.clear_widgets()
		self.add_common()
		
		for param in params:
			self.add_parameter(param)
			
		self.layout.addStretch()
	
# a custom dialog box that has a combo box and an ok button 
# (for, e.g. choosing an op type when adding a new operation)
class ComboBoxDialog(QDialog):
	def __init__(self, items):
		super(ComboBoxDialog, self).__init__()
		
		self.layout = QVBoxLayout()
		self.setLayout(self.layout)

		self.box = QComboBox()
		self.box.addItems(items)
		self.layout.addWidget(self.box)


		self.button_layout = QHBoxLayout()
		self.button_container = QWidget()
		self.button_container.setLayout(self.button_layout)
		self.layout.addWidget(self.button_container)

		ok = QPushButton("OK")
		ok.clicked.connect(self.accept)
		ok.setFocus()
		self.button_layout.addWidget(ok)
		
		no = QPushButton("Cancel")
		no.clicked.connect(self.reject)
		self.button_layout.addWidget(no)

	def get_choice_index(self):
		return self.box.currentIndex()
		
# this is the main application class, that puts together all the pieces
# it also provides a menu bar with the ability to load an operation stack
class StackEditor(QMainWindow):

	onOperationSelected = Signal(int)
	onOperationDeleted = Signal(int)
	onOperationMovedUp = Signal(int)
	onOperationMovedDown = Signal(int)
	onOperationAdded = Signal()
	onOperationMuted = Signal(int)

	def __init__(self, parent = None, qtApp = None):
		super(StackEditor, self).__init__(parent)
		
		self.qtApp = qtApp 
		
		#members
		self.loadedStack = None
		self.currentImage = None
		self.currentOpIndex = 0
		
		
		self.op_types = [
			MorphologicalOperation,
			ThresholdOperation,
			BitwiseNotOperation,
			BlurOperation,
		]
		
		#UI
		self.setWindowTitle("CV Operation Stack Editor")
		self.setup_menubar()
		self.resize(1200, 800)
		
		self.stackModifierWidget = StackModifierWidget(self)
		self.stackPreviewerWidget = StackPreviewerWidget(self)
		self.operationEditorWidget = OperationEditorWidget(self)
		self.fullStackPreviewerWidget = FullStackPreviewerWidget(self)
		
		self.datasetViewerWidget = DatasetViewerWidget(self, True)
		self.datasetViewerWidget.setup()
		
		self.tesseractPreviewWidget = TesseractPreviewWidget(self, True)
		self.tesseractPreviewWidget.setup(TESSERACT_PATH)
		
		self.setCentralWidget(self.stackPreviewerWidget)
		self.addDockWidget(Qt.LeftDockWidgetArea, self.stackModifierWidget)
		self.addDockWidget(Qt.RightDockWidgetArea, self.operationEditorWidget)
		self.addDockWidget(Qt.BottomDockWidgetArea, self.fullStackPreviewerWidget)
		
		self.addDockWidget(Qt.NoDockWidgetArea, self.datasetViewerWidget)
		self.addDockWidget(Qt.NoDockWidgetArea, self.tesseractPreviewWidget)

		# hook up signals from stack modifier
		self.stackModifierWidget.onOperationSelected.connect(self.operationSelected)
		self.stackModifierWidget.onOperationDeleted.connect(self.operationDeleted)
		self.stackModifierWidget.onOperationMovedUp.connect(self.operationMovedUp)
		self.stackModifierWidget.onOperationMovedDown.connect(self.operationMovedDown)
		self.stackModifierWidget.onOperationAdded.connect(self.operationAdded)
		self.stackModifierWidget.onOperationMuted.connect(self.operationMuted)
		
		# hook up signals from operation previewer
		self.stackPreviewerWidget.tabChanged.connect(self.operationSelected)
		self.stackPreviewerWidget.closeRequested.connect(self.operationDeleted)
		
		# hook up signals from operation editor
		#self.operationEditorWidget.onPropertyChanged.connect(self.refresh)
		self.operationEditorWidget.onPropertyChanged.connect(self.refresh_image_only)
		self.operationEditorWidget.onPropertySoftChanged.connect(self.refresh_image_only)

		# hook up signals from dataset viewer
		self.datasetViewerWidget.fileSelected.connect(self.fileSelected)
		
		# hook up signals from full stack previewer
		self.fullStackPreviewerWidget.onOperationSelected.connect(self.operationSelected)

		# position windows on desktop
		self.datasetViewerWidget.move(DEFAULT_DATASET_VIEWER_X, DEFAULT_APPLICATION_Y)
		self.move(DEFAULT_MAIN_WINDOW_X, DEFAULT_APPLICATION_Y)
		self.tesseractPreviewWidget.move(DEFAULT_TESSERACT_PREVIEW_X, DEFAULT_APPLICATION_Y)

	def operationSelected(self, index):
		#print("operationSelected {}".format(index))
		self.currentOpIndex = index
		self.onOperationSelected.emit(index)
		
	def operationDeleted(self, index):
		#print("operationDeleted {}".format(index))
		box = QMessageBox()
		box.setWindowTitle("Delete Operation")
		box.setText("Are you sure?")
		box.setStandardButtons(QMessageBox.Yes)
		box.addButton(QMessageBox.No)
		box.setDefaultButton(QMessageBox.Yes)
		if(box.exec_() == QMessageBox.Yes):
			self.loadedStack.remove_op(index)
			if self.currentOpIndex >= len(self.loadedStack.get_stack()):
				self.currentOpIndex -= 1
			self.refresh()
		
	def operationMovedUp(self, index):
		#print("operationMovedUp {}".format(index))
		if index > 0 and len(self.loadedStack.get_stack()) > 1:
			self.loadedStack.swap_ops(index, index - 1)
			
			if self.currentOpIndex == index - 1: self.currentOpIndex += 1
			elif self.currentOpIndex == index: self.currentOpIndex -= 1
			
			self.refresh()
		
	def operationMovedDown(self, index):
		#print("operationMovedDown {}".format(index))
		if index < len(self.loadedStack.get_stack()) and len(self.loadedStack.get_stack()) > 1:
			self.loadedStack.swap_ops(index, index + 1)
			
			if self.currentOpIndex == index + 1: self.currentOpIndex -= 1
			elif self.currentOpIndex == index: self.currentOpIndex += 1
			
			self.refresh()
			
	def operationAdded(self):
		#print("operationAdded")
		box = ComboBoxDialog([op_type.get_type_label() for op_type in self.op_types])
		box.setWindowTitle("Add Operation")
		if(box.exec_() == QDialog.Accepted):
			op = self.op_types[box.get_choice_index()]()
			self.loadedStack.add_operation(op)
			self.currentOpIndex = len(self.loadedStack.get_stack()) - 1
			self.refresh()
		
	def operationMuted(self, index):
		#print("operationMuted {}".format(index))
		self.loadedStack.get_stack()[index].muted = not self.loadedStack.get_stack()[index].muted
		self.refresh()

	def fileSelected(self, file_path):
		print("fileSelected {}".format(file_path))
		img = cv2.imread(file_path,cv2.IMREAD_COLOR)
		if img is not None:
			self.datasetViewerWidget.onFileOpened(file_path)
			self.use_image(img)
		else:
			print("Image read failed!")
			

	def setup_menubar(self):
		bar = self.menuBar()
		file = bar.addMenu("File")
		newAction = file.addAction("New")
		saveAction = file.addAction("Save")
		saveAsAction = file.addAction("Save As")
		openAction = file.addAction("Open")
		quitAction = file.addAction("Quit")
		
		# key shortcuts
		newAction.setShortcut(QKeySequence(QKeySequence.New))
		saveAction.setShortcut(QKeySequence(QKeySequence.Save))
		saveAsAction.setShortcut(QKeySequence(QKeySequence.SaveAs))
		openAction.setShortcut(QKeySequence(QKeySequence.Open))
		quitAction.setShortcut(QKeySequence(QKeySequence.Quit))
		
		# actual function calls
		newAction.triggered.connect(self.MenuAction_New)
		saveAction.triggered.connect(self.MenuAction_Save)
		saveAsAction.triggered.connect(self.MenuAction_SaveAs)
		openAction.triggered.connect(self.MenuAction_Open)
		quitAction.triggered.connect(self.MenuAction_Quit)
		
	def MenuAction_New(self, checked):
		pass
	def MenuAction_Save(self, checked):
		pass
	def MenuAction_SaveAs(self, checked):
		pass
	def MenuAction_Open(self, checked):
		pass
	def MenuAction_Quit(self, checked):
		if self.qtApp:
			self.qtApp.quit()
		
	def edit_stack(self, stack):
		self.loadedStack = stack
		self.currentOpIndex = 0
		self.refresh()

	def use_image(self, img):
		self.currentImage = img
		self.refresh()
		
	
	def refresh_image_only(self):
		if self.loadedStack is not None and self.currentImage is not None:
			processer = ImageProcesser(self.loadedStack)
			processer.process_color_image(self.currentImage)
			self.processResults = processer.get_last_results()
			
			self.stackPreviewerWidget.update_from_results(self.processResults)
			self.fullStackPreviewerWidget.update_from_results(self.processResults)
			
			self.tesseractPreviewWidget.update_from_results(self.processResults)
		
			self.stackModifierWidget.update_names(self.loadedStack)
		
	def refresh(self):
		if self.loadedStack is not None:
			if self.currentImage is not None:
				processer = ImageProcesser(self.loadedStack)
				processer.process_color_image(self.currentImage)
				self.processResults = processer.get_last_results()
				
				self.stackPreviewerWidget.setup_from_results(self.processResults)
				self.fullStackPreviewerWidget.setup_from_results(self.processResults)
				
				self.tesseractPreviewWidget.update_from_results(self.processResults)
			else:
				self.stackPreviewerWidget.clear()
				self.fullStackPreviewerWidget.clear()
				self.tesseractPreviewWidget.clear()
			
			self.stackModifierWidget.setup_from_stack(self.loadedStack)
			
			self.operationSelected(self.currentOpIndex)


def start_stack_editor(img, stack):
	app = QApplication([])
	
	editor = StackEditor(None, app)
	editor.show()
	
	# load the initial image and opstack
	editor.use_image(img)
	editor.edit_stack(stack)
	
	app.exec_()


if __name__=="__main__":
	print("--- StackEditor ---")
	print("=================")


	parser = argparse.ArgumentParser()
	#parser.add_argument("--verbose", help="increase output verbosity", action="store_true")
	parser.add_argument("starting_image", default="default.png",
									help="starting image file", metavar="FILE",
									type=lambda x: is_valid_file(parser, x))
	parser.add_argument("-c", dest="config_textio", default="config.yaml",
								help="YAML config file", metavar="FILE",
								type=lambda x: is_valid_file(parser, x))
	args = parser.parse_args()
			
	config_textio = None
	if args.config_textio:
		config_textio = args.config_textio
	# --------------

	# PyYaml Config Parsing ----
	if config_textio:
		config_text = config_textio.read()
		config = yaml.load(config_text)
		
		print("YAML config:")
		print(config)

		if 'tesseract_path' in config:
			TESSERACT_PATH = config['tesseract_path']
	
	
	# default startup stack
	stack = OperationStack()
	stack.add_operation(ThresholdOperation().set_otsu_threshold(cv2.THRESH_BINARY))
	stack.add_operation(BitwiseNotOperation())
	stack.add_operation(MorphologicalOperation(Morph.DILATION, kernelSize = 3))
	
	# load an initial image
	print("Opening starter image: {0}".format(args.starting_image.name))
	img = cv2.imread(str(args.starting_image.name),cv2.IMREAD_COLOR)
	
	# start the program
	start_stack_editor(img, stack)
	
	print("=================")
	print("Execution complete.")
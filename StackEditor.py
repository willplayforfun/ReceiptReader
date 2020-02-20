#!venv/Scripts/python

from PyQt5.QtCore import *
from PyQt5.QtCore import pyqtSignal as Signal
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

# Operation Stack
from rrUtilities.ImageOperations import *
# DirWatcher for watching dataset directories for changes
from rrUtilities.DirWatcher import DirWatcher
# getting is_valid_file for argparse
from rrUtilities.TypeHelpers import *

from rrWidgets.StackWidgets import *
from rrWidgets.TesseractPreviewerWidget import *


import argparse
import os
import io
import yaml
import json
from queue import Queue


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
# 	[DONE] multi-thread tesseract
# 	[DONE] grey out tesseract update button until the stack changes
# 	toggle overlay of actual image in tesseract preview
# 	allow slaving all the image viewing areas to the same scroll amount
# 	fix scrolling out on image viewers 
# 	[DONE] add a check box to auto-update tesseract preview
# 	add stack saving / opening
# 	add boundaries and warping operations
# 	add undo/redo stack
# 	fix behavior of threshold panel, disabled fields don't update properly
# 	add better logging system with verbosity


DEFAULT_APPLICATION_Y = 300
DEFAULT_DATASET_VIEWER_X = -300 #200
DEFAULT_MAIN_WINDOW_X = 0 #500
DEFAULT_TESSERACT_PREVIEW_X = -800 #1800

TESSERACT_PATH = r'resources\Tesseract-OCR\tesseract'

DIR_BLACKLIST = ["venv", ".git", "__pycache__", "Tesseract-OCR", "rrUtilities", "rrWidgets"]
VALID_IMG_EXTS = [".png", ".jpg"]

# this widget shows all the images in the dataset, 
# and lets you select one as an example to play with
class DatasetViewerWidget(QDockWidget):

	fileSelected = Signal(str)

	def __init__(self, parent = None, floating = False):
		super(DatasetViewerWidget, self).__init__("Dataset Viewer", parent)
		self.setFloating(floating)
		self.setFeatures(self.DockWidgetFloatable)
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
		
	def setup(self):
		start_dir = os.getcwd()
		print("Scanning files starting in {}".format(start_dir))
		
		# we want to find valid directories and watch them for file add/delete actions
		self.paths_to_watch = []
		for root, dirs, files in os.walk(start_dir):
			# ignore blacklisted dirs
			ignore_dir = False
			for black_dir in DIR_BLACKLIST: 
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
				if os.path.splitext(file)[1].lower() in VALID_IMG_EXTS:
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
			if os.path.splitext(filename)[1].lower() not in VALID_IMG_EXTS: return
			
			print("{}, {}, {}".format(file_type, filename, action))
			
			if action in [WIN32_ACTION_CREATED, WIN32_ACTION_RENAMED_FROM]:
				print(action)
				self.file_list.append([os.path.basename(filename), filename])
				self.updateListWidget()
			
			if action in [WIN32_ACTION_DELETED, WIN32_ACTION_RENAMED_TO]:
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
	
	def appendStrToTitle(self, message):
		self.setWindowTitle("CV Operation Stack Editor - {0}".format(message))
	
	def closeEvent(self, event):
		success = self.askToSave()
		if success:
			event.accept()
		else:
			event.ignore()
			

	def __init__(self, parent = None, qtApp = None):
		super(StackEditor, self).__init__(parent)
		
		self.qtApp = qtApp 
		
		#members
		self.loadedStack = None
		self.currentImage = None
		self.currentOpIndex = 0
		self.stackDirty = False
		self.currentFilepath = None
		self.updateFilenameInTitle()
		
		self.op_types = [
			MorphologicalOperation,
			ThresholdOperation,
			BitwiseNotOperation,
			BlurOperation,
		]
		
		#UI
		#self.setWindowTitle("CV Operation Stack Editor")
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


	# ---------------------- MODIFYING OPERATION STACK -------------------------

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
			self.setStackDirty(True)
			if self.currentOpIndex >= len(self.loadedStack.get_stack()):
				self.currentOpIndex -= 1
			self.refresh()
		
	def operationMovedUp(self, index):
		#print("operationMovedUp {}".format(index))
		if index > 0 and len(self.loadedStack.get_stack()) > 1:
			self.loadedStack.swap_ops(index, index - 1)
			self.setStackDirty(True)
			
			if self.currentOpIndex == index - 1: self.currentOpIndex += 1
			elif self.currentOpIndex == index: self.currentOpIndex -= 1
			
			self.refresh()
		
	def operationMovedDown(self, index):
		#print("operationMovedDown {}".format(index))
		if index < len(self.loadedStack.get_stack()) and len(self.loadedStack.get_stack()) > 1:
			self.loadedStack.swap_ops(index, index + 1)
			self.setStackDirty(True)
			
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
			self.setStackDirty(True)
			self.currentOpIndex = len(self.loadedStack.get_stack()) - 1
			self.refresh()
		
	def operationMuted(self, index):
		#print("operationMuted {}".format(index))
		self.loadedStack.get_stack()[index].muted = not self.loadedStack.get_stack()[index].muted
		self.setStackDirty(True)
		self.refresh()


	def use_stack(self, stack):
		self.loadedStack = stack
		self.currentOpIndex = 0
		self.refresh()


	# ------------------ UPDATING PREVIEW IMAGES / STACK PROPERTIES ----------------------

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



	# ---------------------- HANDLE EXAMPLE IMAGE LOADING -------------------------


	def use_image(self, img):
		self.currentImage = img
		self.refresh()
		

	def fileSelected(self, file_path):
		print("fileSelected {}".format(file_path))
		img = cv2.imread(file_path,cv2.IMREAD_COLOR)
		if img is not None:
			self.datasetViewerWidget.onFileOpened(file_path)
			self.use_image(img)
		else:
			print("Image read failed!")
			

	# ---------------------- STACK FILE LOADING/SAVING -------------------------

	def showError(self, errorStr, details = ""):
		msg = QMessageBox()
		msg.setIcon(QMessageBox.Critical)
		msg.setText(errorStr)
		msg.setInformativeText(details)
		msg.setWindowTitle("Error")
		msg.exec_()

	def updateFilenameInTitle(self):
		fileStr = "New file"
		if self.currentFilepath and self.currentFilepath != "":
			fileStr = self.currentFilepath
		self.appendStrToTitle("{0}{1}".format(fileStr, "*" if self.stackDirty else ""))

	def setStackDirty(self, isDirty):
		self.stackDirty = isDirty
		self.updateFilenameInTitle()

	def set_current_filepath(self, filepath):
		self.currentFilepath = filepath
		self.updateFilenameInTitle()

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
		new_stack = OperationStack()
		self.use_stack(new_stack)
		self.set_current_filepath(None)
		self.setStackDirty(False)
	
	
	def MenuAction_Save(self, checked):
		# if this is a new (unnamed) file, we need a filepath
		if self.currentFilepath is None:
			self.set_current_filepath(self.ask_for_filepath(open = False))
		
		# if the filepath still isn't set, do nothing
		if self.currentFilepath is None:
			return False
			
		# save file
		success = self.save_stack_to_file(self.currentFilepath)
		
		if success:
			self.setStackDirty(False)
		
		return success
		
		
	def MenuAction_SaveAs(self, checked):
		# create file dialog
		filepath = self.ask_for_filepath(open = False)
		
		# if the filepath wasn't set, do nothing
		if filepath is None:
			return
		
		# save file
		success = self.save_stack_to_file(filepath)
		
		if success:
			# update working filepath
			self.set_current_filepath(filepath)
			self.setStackDirty(False)
		
		
	def MenuAction_Open(self, checked):
		if self.stackDirty:
			success = self.askToSave("opening")
			if not success:
				return
	
		# create file dialog
		filepath = self.ask_for_filepath()
		
		# if the filepath wasn't set, do nothing
		if filepath is None or filepath == "":
			return
		
		new_stack = self.open_stack_file(filepath)
		
		if new_stack is not None:
			self.use_stack(new_stack)
			self.set_current_filepath(filepath)
			self.setStackDirty(False)
		
	def askToSave(self, actionstr="exiting"):
		# ask if the user wants to save
		box = QMessageBox()
		box.setWindowTitle("Unsaved Changes")
		box.setText("Do you want to save before {0}?".format(actionstr))
		box.setStandardButtons(QMessageBox.Yes)
		box.addButton(QMessageBox.No)
		box.addButton(QMessageBox.Cancel)
		box.setDefaultButton(QMessageBox.Yes)
		result = box.exec_()
		if(result == QMessageBox.Yes):
			success = self.MenuAction_Save(None)
			if not success:
				# don't exit if we didn't save
				return False
		elif(result == QMessageBox.Cancel):
			# don't exit
			return False
			
		return True
		
	def MenuAction_Quit(self, checked):
		#check for unsaved changes
		if self.stackDirty:
			success = self.askToSave()
			if not success:
				return
		
		if self.qtApp:
			self.qtApp.quit()

		
	def ask_for_filepath(self, open = True):
		filePath = None
		
		file_dialog = QFileDialog(self)
		#file_dialog.setLabelText("Open file")
		file_dialog.setNameFilter("OpStack (*.ops)")
			
		if open:
			file_dialog.setAcceptMode(QFileDialog.AcceptOpen)
			file_dialog.setFileMode(QFileDialog.ExistingFile)
		else:
			file_dialog.setAcceptMode(QFileDialog.AcceptSave)
			file_dialog.setFileMode(QFileDialog.AnyFile)
		
		accepted = file_dialog.exec_()
		if accepted:
			file = file_dialog.selectedFiles()[0]
			filePath = os.path.join(file_dialog.directory().absolutePath(), file)
		else:
			return None
			
		print("QFileDialog returned: {0}".format(filePath))
		return filePath
		
	def save_stack_to_file(self, filepath):
		data = self.loadedStack.serialize()
		
		print("Attempting to serialize this data to a file: {0}".format(data))
		
		try:
			with open(filepath, 'w') as outfile:
				json.dump(data, outfile)
				return True
		except EnvironmentError as error:
			print("ERROR while opening file to write: {0}".format(error))
			# show error to user
			self.showError('Error while saving!','(see log for details)')
			return False
			

	def open_stack_file(self, filepath):
		try:
			with open(filepath, 'r') as infile:
				data = None
				
				try:
					data = json.load(infile)
				except json.decoder.JSONDecodeError as error:
					print("ERROR while parsing JSON: {0}".format(error))
					# show error to user
					self.showError('Error while loading!','(see log for details)')
					return None
				
				stack = OperationStack()
				stack.deserialize(data)
				return stack
					
		except EnvironmentError as error:
			print("ERROR while opening file to read: {0}".format(error))
			# show error to user
			self.showError('Error while loading!','(see log for details)')
			return None


# ================= APPLICATION ENTRY POINT ==================

if __name__=="__main__":
	print("--- StackEditor ---")
	print("=================")


	parser = argparse.ArgumentParser()
	#parser.add_argument("--verbose", help="increase output verbosity", action="store_true")
	parser.add_argument("-i", dest="starting_image",
								help="starting image file", metavar="FILE",
								type=lambda x: is_valid_file(parser, x))
	parser.add_argument("-c", dest="config_textio", default="resources/config.yaml",
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
	stack.add_operation(MorphologicalOperation(MorphologicalOperationType.DILATION, kernelSize = 3))
	
	# load an initial image
	img = None
	if args.starting_image:
		print("Opening starter image: {0}".format(args.starting_image.name))
		img = cv2.imread(str(args.starting_image.name),cv2.IMREAD_COLOR)
	
	
	# --------------
	# start the program
	app = QApplication([])
	
	editor = StackEditor(None, app)
	editor.show()
	
	# load the initial image and opstack
	editor.use_image(img)
	editor.use_stack(stack)
	
	app.exec_()	
	# --------------

	print("=================")
	print("Execution complete.")

#EOF
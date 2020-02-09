from PyQt5.QtCore import *
from PyQt5.QtCore import pyqtSignal as Signal
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

from rrUtilities.ImageCleaner import *
from rrUtilities.TextReader import *
from rrUtilities.DataVisualizer import *

from rrWidgets.PhotoViewer import PhotoViewer

# getting cv2_to_pixmap helper
from rrUtilities.TypeHelpers import *

import logging
import threading
import time


MAX_WIDTH = 400

# handles async calls to Tesseract on a separate thread to prevent stalls
class TesseractThreadManager:
	def __init__(self, tesseract_path):
		self.tesseract_path = tesseract_path
		self.cached_results = None
		
	def tesseract_thread_func(self, name):
		print("Thread {0}: starting".format(name))
		
		self.text_reader = TextReader(self.tesseract_path)
		
		time.sleep(2)
		
		self.cached_results = self.text_reader.read_image(self.cached_image)
		
		print("Thread {0}: finishing".format(name))
		
	def start_thread(self):
	
		# daemon means it will auto-shutdown
		self.thread = threading.Thread(target=self.tesseract_thread_func, args=(1,), daemon=True)
		self.thread.start()

	def start_read_image(self, image, callback):
		self.cached_image = image
		
		# send up semaphore
		
		
		
		callback()
		
	def get_cached_results(self):
		return self.cached_results


# this widget shows the result of an OCR operation on the open test image by the open stack
# it has an option to auto-refresh after a change, as well a manual refresh button
class TesseractPreviewWidget(QDockWidget):
	def __init__(self, parent = None, floating = False):
		super(TesseractPreviewWidget, self).__init__("Tesseract Preview", parent)
		self.setFloating(floating)
		self.setFeatures(self.DockWidgetMovable)
		self.setMinimumSize(QSize(200, 600))
		
		self.layout = QVBoxLayout()
		self.container = QWidget()
		self.container.setLayout(self.layout)
		self.setWidget(self.container)
		
		# add the preview area for the CV image
		self.preview_area = PhotoViewer(self)
		self.layout.addWidget(self.preview_area)
		
		# -- CONTROLS --
		self.controls_layout = QHBoxLayout()
		self.controls_container = QWidget()
		self.controls_container.setLayout(self.controls_layout)
		self.layout.addWidget(self.controls_container)
		
		# add a button that causes re-processing; it un-grays when an update occurs
		self.update_button = QPushButton("Update")
		self.update_button.clicked.connect(self.process_latest)
		self.update_button.setFocus()
		self.controls_layout.addWidget(self.update_button)
		
		# add a spinner to show during the async request
		self.spinner_label = QLabel()
		movie = QMovie("resources/loadspinner.gif");
		self.spinner_label.setMovie(movie)
		movie.start()
		self.controls_layout.addWidget(self.spinner_label)
		self.spinner_label.setVisible(False)
		
		# TODO add error label that appear if a tesseract operation fails
		# TODO add an auto-update checkbox
		
	def setup(self, tesseract_path):
		self.data_vis = DataVisualizer()
		
		self.thread_manager = TesseractThreadManager(tesseract_path)
		self.thread_manager.start_thread()
		
	def update_from_results(self, results):
	
		self.update_button.setEnabled(True)
			
		# -1 = last image, 0 = actual image object (1 = title)
		self.latest_image = results[-1][0]
		
		new_width = min(self.latest_image.shape[0], MAX_WIDTH)
		aspect_ratio = self.latest_image.shape[1] / self.latest_image.shape[0]
		self.resize(QSize(new_width, aspect_ratio * new_width))
		
	def clear(self):
		self.latest_image = None
		
	def process_latest(self, checked):
		if self.latest_image is not None:
		
			self.update_button.setEnabled(False)
			self.spinner_label.setVisible(True)
		
			self.thread_manager.start_read_image(self.latest_image, self.processing_finished)
			
		else:
			print("Latest processed image is None!")
			
	def processing_finished(self):
		self.spinner_label.setVisible(False)
	
		boxes = self.thread_manager.get_cached_results()

		if boxes is not None:
			# Draw the bounding box
			bounds_img = self.data_vis.draw_text_bounds(boxes, self.latest_image)
			
			#resize
			resizer = ImageResizer(bounds_img.shape)
			resizer.set_new_width(400)
			
			# create a representation of the tesseract data
			small_boxes = resizer.resize_tesseract_data(boxes)
			white_img = resizer.create_new_image_at_size()
			cvReconImg = self.data_vis.draw_text_chars(small_boxes, white_img)
			
			pix = cv2_to_pixmap(cvReconImg)
			self.preview_area.setPixmap(pix)
			
			#cv2.imshow('reconstruction',cvReconImg)

		else:
			print("Tesseract operation returned None!")

# OpenCV ----
import cv2
import numpy as np
# --------------
# PIL ----
try:
	import Image
	import ImageDraw
except ImportError:
	from PIL import Image, ImageDraw
# --------------
# Tesseract OCR ----
import pytesseract
# ---------------------
import math
import os

# we use Qt's threading so we can emit signals from the thread
from PyQt5.QtCore import QThread
from PyQt5.QtCore import pyqtSignal as Signal



# This class returns the actual data obtained from Tesseract
class TesseractWrapper:

	def __init__(self, tesseract_path):
		pytesseract.pytesseract.tesseract_cmd = tesseract_path
		print("Using pytesseract version: " + str(pytesseract.get_tesseract_version()))
		
		os.environ["OMP_THREAD_LIMIT"] = "4"
		
	def read_image(self, img):

		# read processed image using tesseract
		bare_tesseract_data = pytesseract.image_to_boxes(img)
		bare_tesseract_data = bare_tesseract_data.split('\n')
		
		boxes = []
		for d in bare_tesseract_data:
			boxes.append(d.split(' '))
			
		return boxes
		
		
# handles async calls to Tesseract on a separate thread to prevent stalls
class TesseractThreadManager (QThread):

	onOperationComplete = Signal()
	
	def __init__(self, tesseract_path):
		QThread.__init__(self)
		self.tesseract_path = tesseract_path
		self.cached_results = None
		self.read_image_flag = False
		
		self.start()

	def __del__(self):
		self.wait()
		
	def run (self):
		tess_wrapper = TesseractWrapper(self.tesseract_path)
		
		while True:
			if self.read_image_flag:
				print("TESSERACT THREAD: Read started")
				image = np.copy(self.cached_image)
				self.cached_results = tess_wrapper.read_image(image)
				self.read_image_flag = False
				print("TESSERACT THREAD: Read complete")
				self.onOperationComplete.emit()
			self.sleep(0)
			

	def start_read_image(self, image):
		self.cached_image = image
		# communicate to thread
		self.read_image_flag = True
		
		
	def get_cached_results(self):
		return self.cached_results


	"""
	
	def start_thread(self):
	
		# daemon means it will auto-shutdown
		self.thread = threading.Thread(target=self.tesseract_thread_func, args=(1,), daemon=True)
		self.thread.start()
		
	def __init__ (self, path_to_watch, results_queue, **kwds):
		threading.Thread.__init__ (self, **kwds)
		self.setDaemon (1)
		self.path_to_watch = path_to_watch
		self.results_queue = results_queue
		self.start ()
	"""


# This class can draw a visual representation of tesseract data back onto an image for debugging
class TesseractDataVisualizer:

	def __init__(self):
		pass
		
	def draw_text_bounds(self, boxes, img):
		
		cv2_im = cv2.cvtColor(img,cv2.COLOR_GRAY2RGB)
		h, w, channels = cv2_im.shape
		
		for b in boxes:
			cv2.rectangle(cv2_im, (int(b[1]), h-int(b[2])), (int(b[3]), h-int(b[4])),(0,0,255),2)
		
		return cv2_im
		
	def draw_text_chars(self, boxes, img):
		
		height, width, channels = img.shape
		
		pil_image = Image.fromarray(img.astype('uint8'), 'RGB')
		drawer = ImageDraw.Draw(pil_image)
			
		corners = [(0,0), (0, height - 20), (width - 100, 0), (width - 100, height - 20)]
		for corner in corners:
			drawer.text((corner[0], corner[1]), str(corner), fill=(0,255,0))

		for b in boxes:
			string = b[0]
			
			for i in range(len(string)):
				if ord(string[i]) > 255:
					#print("Encountered bad char [" + string[i] + "], ord = " + str(ord(string[i])))
					string = string[:i] + '?' + string[i+1:]
					#drawer.rectangle((int(b[1]),int(b[2]),int(b[3]),int(b[4])), fill=(0,0,0))
					#drawer.text((int(b[1]),int(b[2])), '?', fill=(255,0,0))
		
			posX = math.floor(int(b[1]))
			posY = height - math.floor(int(b[2]))
			drawer.text((posX, posY), string, fill=(0,0,0))
		
		return np.array(pil_image)

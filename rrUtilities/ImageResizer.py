# OpenCV ----
import cv2
import numpy as np
# --------------
# PIL ----
try:
	import Image
except ImportError:
	from PIL import Image
# --------------

class ImageResizer:
	def __init__(self, shape):
		self.origHeight = shape[0]
		self.origWidth = shape[1]
		self.origChannels = shape[2]
		
		self.newWidth = self.origWidth
		self.newHeight = self.origHeight
		
	def set_new_width(self, width):
		self.newWidth = width
		self.newHeight = round(self.origHeight*self.newWidth/self.origWidth)
		
	def set_new_height(self, height):
		self.newHeight = height
		self.newWidth = round(self.origWidth*self.newHeight/self.origHeight)
		
	def set_size_multiplier(self, scalar):
		self.newWidth = scalar * self.origWidth
		self.newHeight = scalar * self.origHeight
		
	def resize_tesseract_data(self, data):
		new_data = []
		for b in data:
			new_data.append(b)
			new_data[-1][1] = int(b[1])*self.newWidth/self.origWidth
			new_data[-1][2] = int(b[2])*self.newHeight/self.origHeight
		return new_data
		
	def resize_image(self, img):
		return cv2.resize(img, (self.newWidth, self.newHeight), interpolation = cv2.INTER_AREA)
	
	def create_new_image_at_size(self, pDrawColor = (255, 255, 255)):
		return np.array(Image.new('RGB', (self.newWidth, self.newHeight), color = pDrawColor))
		
		
		
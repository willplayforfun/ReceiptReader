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
import math

class DataVisualizer:

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
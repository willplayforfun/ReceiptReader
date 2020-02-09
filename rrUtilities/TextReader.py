# Tesseract OCR ----
import pytesseract
# ---------------------

import os

class TextReader:

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
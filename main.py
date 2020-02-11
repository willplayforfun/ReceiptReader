print("--- ReceiptReader ---")

import sys
import os
import argparse
import io
import yaml
# OpenCV ----
import cv2
import numpy as np
# --------------

from rrUtilities.ImageOperations import MorphologicalOperationType as Morph
from rrUtilities.ImageOperations import *

# TesseractThreadManager and TesseractDataVisualizer
from rrUtilities.TesseractWrapper import *
# ImageResizer
from rrUtilities.ImageResizer import *

# getting is_valid_file for argparse
from rrUtilities.TypeHelpers import *


print("Using Python version: " + sys.version)
print("Current working directory: " + os.getcwd())

DEBUG = True
config_textio = io.TextIOWrapper(open("resources/config.yaml", 'r'), encoding='utf8', newline='\n')
tesseract_path = r'resources\Tesseract-OCR\tesseract'
dataset_path = "dataset"


parser = argparse.ArgumentParser()
#parser.add_argument("--verbose", help="increase output verbosity", action="store_true")
parser.add_argument("-c", dest="config_textio", default="resources/config.yaml",
								help="YAML config file", metavar="FILE",
								type=lambda x: is_valid_file(parser, x))
args = parser.parse_args()

if args.config_textio:
	config_textio = args.config_textio
# --------------

# PyYaml Config Parsing ----
config_text = config_textio.read()
config = yaml.load(config_text)
if DEBUG:
	print("YAML config:")
	print(config)

if 'tesseract_path' in config:
	tesseract_path = config['tesseract_path']
if 'dataset_path' in config:
	dataset_path = config['dataset_path']
#------------------------------

text_reader = TesseractWrapper(tesseract_path)

# Load Dataset ----
dataset = []
for root, dirs, files in os.walk(dataset_path):
	for file in files:
		dataset.append(os.path.join(root, file))

dataset.sort()
		
if DEBUG:
	print("Loaded dataset:")
	for file in dataset:
		print("\t" + file)
# --------------------

print("=================")

for file in dataset:
	# Load an color image in grayscale
	# load image
	img = cv2.imread(file,cv2.IMREAD_GRAYSCALE)
	"""
	# Canny edge detection
	edges = cv2.Canny(img,100,200)
	
	# dilate to make edges thicker
	kernel = np.ones((3,3),np.uint8)
	dilation = cv2.dilate(edges,kernel,iterations = 1)
	
	# Hough line transform
	minLineLength = math.floor(0.5 * img.shape[0])
	lines = cv2.HoughLines(dilation,5,np.pi/2,minLineLength)	# image, pixel pos resolution, angular resolution, threshold (min length)
	
	# draw the lines on the img
	backtorgb = cv2.cvtColor(dilation, cv2.COLOR_GRAY2RGB)
	linelen = 1000
	if lines is not None:
		for rho,theta in [line[0] for line in lines]:
			a = np.cos(theta)
			b = np.sin(theta)
			x0 = a*rho
			y0 = b*rho 
			x1 = int(x0 + linelen*(-b))
			y1 = int(y0 + linelen*(a))
			x2 = int(x0 - linelen*(-b))
			y2 = int(y0 - linelen*(a))
			
			# img, pt1, pt2, color, thickness
			#cv2.circle(edges, 
			cv2.line(backtorgb,(x1,y1),(x2,y2),(0,255,0),1)
	"""
	
	# binary thresholding followed by morphological cleanup
	thresholds = [
	ThresholdOperation().set_threshold(127, cv2.THRESH_BINARY),
	ThresholdOperation().set_adaptive_threshold(cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2),
	ThresholdOperation().set_adaptive_threshold(cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2),
		
	# Otsu's thresholding
	ThresholdOperation().set_threshold(0, cv2.THRESH_BINARY+cv2.THRESH_OTSU),
	]
		
	# Otsu's thresholding after Gaussian filtering
	#ip2 = ImageProcesser()
	#ip2.add_operation(BlurOperation(kernelSize = 5))
	#ip2.add_operation(thresholds[3])
		
	# Otsu's thresholding
	stack = OperationStack()
	stack.add_operation(thresholds[3])
	stack.add_operation(BitwiseNotOperation())	

	# cleanup by dilating
	#stack.add_operation(MorphologicalOperation(Morph.OPENING, kernelSize = 5))
	stack.add_operation(MorphologicalOperation(Morph.DILATION, kernelSize = 3))
	
	cleaned_img = ImageProcesser(stack).process_image(img)
	
	# read processed image using tesseract
	boxes = text_reader.read_image(cleaned_img)
	
	# Draw the bounding box
	data_vis = TesseractDataVisualizer()
	bounds_img = data_vis.draw_text_bounds(boxes, cleaned_img)
	
	#resize
	resizer = ImageResizer(bounds_img.shape)
	resizer.set_new_width(400)
	
	small_boxes = resizer.resize_tesseract_data(boxes)
	imgSmall = resizer.resize_image(bounds_img)
	
	cv2.imshow('image',imgSmall)
	
	# create a representation of the tesseract data
	white_img = resizer.create_new_image_at_size()
	cvReconImg = data_vis.draw_text_chars(small_boxes, white_img)
	
	cv2.imshow('reconstruction',cvReconImg)
	
	
	#print("\n" + file)
	#print(pytesseract.image_to_string(cv2_im))
	
	
	# wait for key press or window close
	# pressing Escape will skip all remaining images
	stop = False
	while cv2.getWindowProperty('image', 0) >= 0:
		keyCode = cv2.waitKey(50)
		if keyCode == 27:
			stop = True
		if keyCode >= 0:
			break
	cv2.destroyAllWindows()
	if stop:
		break
	#break

	
print("=================")
print("Execution complete.")
input("Press Enter to continue...")
#EOF
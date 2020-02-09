from PyQt5.QtCore import *
from PyQt5.QtGui import *
import cv2
import os

def cv2_to_pixmap(cv2_img):
	color_img = cv2_img
	
	if len(cv2_img.shape) < 3:
		#if image comes in as grayscale, make it color
		color_img = cv2.cvtColor(cv2_img, cv2.COLOR_GRAY2RGB)
	else:
		if cv2_img.shape[2] != 3:
			print("CV2_to_Pixmap ERROR, channels not 1 or 3... ={0}".format(cv2_img.shape[2]))

	height, width, channels = color_img.shape
	byteValue = channels * width
	image = QImage(color_img, width, height, byteValue, QImage.Format_RGB888)
	return QPixmap.fromImage( image )


# ArgParse ----
# filepath validator
def is_valid_file(parser, arg):
    if not os.path.exists(arg):
        parser.error("The file %s does not exist!" % arg)
    else:
        return open(arg, 'r')  # return an open file handle

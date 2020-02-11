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
from enum import Enum
import re


def is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

class ParameterType(Enum):
	SLIDER = 0
	CHECKBOX = 1
	NUMBER = 2
	STRING = 3
	DROPDOWN = 4
	NONE = 5
	

#TODO clean up parameters so there isn't so much copy-pasting of getters/setters
	
class OperationParameter:
	def __init__(self, label, getter, setter):
		self.type = ParameterType.NONE
		self.label = label
		self.getter = getter
		self.setter = setter
		self.enabled = True
		
		self.choices = [] #for when type == DROPDOWN
		
		self.min = 0 #for when type == SLIDER
		self.max = 1 #for when type == SLIDER
		self.tickInterval = 1
		
	def set_enabled(self, enabled):
		self.enabled = enabled
		return self
	
	def set_type(self, type):
		self.type = type
		return self
		
	def set_dropdown(self, choices):
		self.choices = choices
		self.type = ParameterType.DROPDOWN
		return self
		
	def set_slider(self, min, max, interval = 1):		
		self.min = min
		self.max = max
		self.type = ParameterType.SLIDER
		self.tickInterval = interval
		return self
		

class ImageOperation:
	def __init__(self):
		self.label = self.get_default_label()
		self.muted = False
		self.parameters = []

	def apply_to_image(self, img):
		print("WARNING: Base apply_to_image function has been called on ImageOperation, something is probably wrong")
		return img
		
	@staticmethod
	def get_type_label():
		return "Operation"
		
	def get_default_label(self):
		return "Operation"
	
	def get_label(self):
		return self.label
		
	def set_label(self, new_label):
		self.label = new_label
	
	def get_parameters(self):
		return self.parameters


class NullOperation(ImageOperation):
	def apply_to_image(self, img):
		return img
		
	@staticmethod
	def get_type_label():
		return "Null Operation"
		
	def get_default_label(self):
		return "None"


class BitwiseNotOperation(ImageOperation):
	def apply_to_image(self, img):
		return cv2.bitwise_not(img)
		
	@staticmethod
	def get_type_label():
		return "Bitwise Not Operation"
		
	def get_default_label(self):
		return "Bitwise Not"

class ThresholdOperation(ImageOperation):

	@staticmethod
	def get_type_label():
		return "Threshold Operation"
		
	def get_default_label(self):
		return "Threshold"

	doc = """
https://docs.opencv.org/2.4/modules/imgproc/doc/miscellaneous_transformations.html?highlight=adaptivethreshold

Parameters:	
src – Source 8-bit single-channel image.

	maxValue – 
Non-zero value assigned to the pixels for which the condition is satisfied. 

	adaptiveMethod – 
Adaptive thresholding algorithm to use, ADAPTIVE_THRESH_MEAN_C or 
ADAPTIVE_THRESH_GAUSSIAN_C . See the details below.

	thresholdType – 
Thresholding type that must be either THRESH_BINARY or THRESH_BINARY_INV.

	blockSize – 
Size of a pixel neighborhood that is used to calculate a threshold 
value for the pixel: 3, 5, 7, and so on.
	
	C – 
Constant subtracted from the mean or weighted mean (see the details below). 
Normally, it is positive but may be zero or negative as well.
"""

	def __init__(self):
		super(ThresholdOperation, self).__init__()
			
		self.maxValue = 255
		self.thresholdType = cv2.THRESH_BINARY
		self.usesAdaptiveMethod = False
		self.usesOtsu = False
		
		# for cv2.threshold
		self.thresholdValue = 127
		
		#for cv2.adaptiveThreshold
		self.adaptiveMethod = cv2.ADAPTIVE_THRESH_MEAN_C
		self.blockSize = 11
		self.C = 2
		
		self.adaptiveParams = []
		self.normalParams = []
				
		self.thresholdTypeOptionLabels = ["THRESH_BINARY", "THRESH_BINARY_INV", "THRESH_TRUNC", "THRESH_TOZERO", "THRESH_TOZERO_INV"]
		self.adaptiveMethodOptionLabels = ["ADAPTIVE_THRESH_MEAN_C", "ADAPTIVE_THRESH_GAUSSIAN_C"]
		self.thresholdTypeOptions = [cv2.THRESH_BINARY, cv2.THRESH_BINARY_INV, cv2.THRESH_TRUNC, cv2.THRESH_TOZERO, cv2.THRESH_TOZERO_INV]
		self.adaptiveMethodOptions = [cv2.ADAPTIVE_THRESH_MEAN_C, cv2.ADAPTIVE_THRESH_GAUSSIAN_C]
		
		
		self.parameters.append(
		OperationParameter("Threshold Type", self.getThresholdTypeStr, self.callback_setThresholdType).set_dropdown(self.thresholdTypeOptionLabels))
	
		self.parameters.append(
		OperationParameter("Use Adaptive", self.getUsesAdaptive, self.callback_setUsesAdaptive).set_type(ParameterType.CHECKBOX))
		
		self.normalParams.append(
		OperationParameter("Use Otsu", self.getUsesOtsu, self.callback_setUsesOtsu).set_type(ParameterType.CHECKBOX))
		
		self.param_thresholdValue = OperationParameter("Threshold Value", self.getThresholdValue, self.callback_setThresholdValue).set_slider(0, 255, 5)
		self.normalParams.append(self.param_thresholdValue)
		
		self.adaptiveParams.append(
		OperationParameter("Adaptive Method", self.getAdaptiveMethodStr, self.callback_setAdaptiveMethod).set_dropdown(self.adaptiveMethodOptionLabels ))
		
		self.adaptiveParams.append(
		OperationParameter("Constant", self.getC, self.callback_setC).set_type(ParameterType.NUMBER))
		
		self.adaptiveParams.append(
		OperationParameter("Block Size",self.getBlockSize, self.callback_setBlockSize).set_slider(1, 21, 2))
		
		self.callback_setUsesAdaptive(False)
		self.callback_setUsesOtsu(False)
	
	def callback_setThresholdType(self, type):
		self.thresholdType = self.thresholdTypeOptions[self.thresholdTypeOptionLabels.index(type)]
	def callback_setThresholdValue(self, val):
		if is_int(val): self.thresholdValue = int(val)
	def callback_setUsesAdaptive(self, adaptive):
		self.usesAdaptiveMethod = True if adaptive else False
		for param in self.adaptiveParams:
			param.set_enabled(self.usesAdaptiveMethod)
		for param in self.normalParams:
			param.set_enabled(not self.usesAdaptiveMethod)
			
	def callback_setUsesOtsu(self, otsu):
		self.usesOtsu = True if otsu else False
		self.param_thresholdValue.set_enabled(not self.usesAdaptiveMethod and not self.usesOtsu)
	
	def callback_setAdaptiveMethod(self, method):
		self.adaptiveMethod = self.adaptiveMethodOptions[self.adaptiveMethodOptionLabels.index(method)]
	def callback_setC(self, val):
		if is_int(val): self.C = int(val)
	def callback_setBlockSize(self, size):
		if is_int(size): 
			val = int(size)
			if val % 2 == 1 and val > 1:
				self.blockSize = int(size)
		
	def getThresholdTypeStr(self):
		if self.thresholdType in self.thresholdTypeOptions:
			return self.thresholdTypeOptionLabels[self.thresholdTypeOptions.index(self.thresholdType)]
		else:
			return "NONE"
	def getThresholdValue(self):
		return self.thresholdValue
	def getUsesAdaptive(self):
		return self.usesAdaptiveMethod
	def getUsesOtsu(self):
		return self.usesOtsu
	def getAdaptiveMethodStr(self):
		if self.adaptiveMethod in self.adaptiveMethodOptions:
			return self.adaptiveMethodOptionLabels[self.adaptiveMethodOptions.index(self.adaptiveMethod)]
		else:
			return "NONE"
	def getC(self):
		return self.C
	def getBlockSize(self):
		return self.blockSize
		
	def get_parameters(self):
		return self.parameters + self.normalParams + self.adaptiveParams
		if self.usesAdaptiveMethod:
			return self.parameters + self.adaptiveParams
		else:
			return self.parameters + self.normalParams
		
	
	def set_output_value(self, pMaxValue):
		self.maxValue = pMaxValue
		
		return self
	
	def set_otsu_threshold(self, pThresholdType = cv2.THRESH_BINARY):
		self.callback_setUsesAdaptive(False)
		
		self.callback_setUsesOtsu(True)
		self.thresholdType = pThresholdType
		
		return self
		
	def set_threshold(self, pThresholdValue = 127, pThresholdType = cv2.THRESH_BINARY):
		self.callback_setUsesAdaptive(False)
		
		self.callback_setUsesOtsu(False)
		self.thresholdType = pThresholdType
		self.thresholdValue = pThresholdValue
		
		return self
		
	def set_adaptive_threshold(self, pAdaptiveMethod, pThresholdType = cv2.THRESH_BINARY, pBlockSize = 11, pC = 2):
		self.callback_setUsesAdaptive(True)
		
		self.callback_setUsesOtsu(False)
		self.thresholdType = pThresholdType
		self.adaptiveMethod = pAdaptiveMethod
		self.blockSize = pBlockSize
		self.C = pC
		
		return self
		
	def apply_to_image(self, img):
		if self.usesAdaptiveMethod:
			return cv2.adaptiveThreshold(img,
				self.maxValue,
				self.adaptiveMethod,
				self.thresholdType,
				self.blockSize,
				self.C)
		else:
			if self.usesOtsu:
				return cv2.threshold(img,
					0,
					self.maxValue,
					self.thresholdType+cv2.THRESH_OTSU)[1]
			else:
				return cv2.threshold(img,
					self.thresholdValue,
					self.maxValue,
					self.thresholdType)[1]

class BlurOperation(ImageOperation):

	@staticmethod
	def get_type_label():
		return "Blur Operation"
		
	def get_default_label(self):
		return "Blur"

	doc = """
	https://docs.opencv.org/2.4/modules/imgproc/doc/filtering.html#void%20GaussianBlur(InputArray%20src,%20OutputArray%20dst,%20Size%20ksize,%20double%20sigmaX,%20double%20sigmaY,%20int%20borderType)
    src – input image; the image can have any number of channels, which are processed independently, but the depth should be CV_8U, CV_16U, CV_16S, CV_32F or CV_64F.
	
    ksize – 
Gaussian kernel size. ksize.width and ksize.height can differ but they both must be positive and odd. 
Or, they can be zero’s and then they are computed from sigma* .

    sigmaX –
Gaussian kernel standard deviation in X direction.

    sigmaY – 
Gaussian kernel standard deviation in Y direction; if sigmaY is zero, it is set to be equal to sigmaX, 
if both sigmas are zeros, they are computed from ksize.width and ksize.height , respectively 
(see getGaussianKernel() for details); to fully control the result regardless of possible future modifications 
of all this semantics, it is recommended to specify all of ksize, sigmaX, and sigmaY.

    borderType – 
pixel extrapolation method (see borderInterpolate() for details).
"""

	def __init__(self, kernelSize = 5):
		super(BlurOperation, self).__init__()
			
		self.kernelSize = kernelSize
		self.sigma = 0
		self.borderType = cv2.BORDER_DEFAULT
		
		
		self.borderOptionLabels = ["Default", "Constant", "Replicate", "Reflect", "Wrap", "Reflect 101", "Transparent", "Isolated"]
		self.borderOptions = [
			cv2.BORDER_DEFAULT,
			cv2.BORDER_CONSTANT,
			cv2.BORDER_REPLICATE,
			cv2.BORDER_REFLECT,
			cv2.BORDER_WRAP,
			cv2.BORDER_REFLECT_101,
			cv2.BORDER_TRANSPARENT,
			cv2.BORDER_ISOLATED,
			]
			
		self.parameters.append(
		OperationParameter("Kernel Size",self.getKernelSize, self.callback_setKernelSize).set_slider(1, 11, 2))
		
		self.parameters.append(
		OperationParameter("Sigma",self.getSigma, self.callback_setSigma).set_slider(1, 20, 1))
		
		self.parameters.append(
		OperationParameter("Border Type", self.getBorderTypeStr, self.callback_setBorderType).set_dropdown(self.borderOptionLabels))
	
		
	def callback_setSigma(self, val):
		if is_int(val): self.sigma = int(val)
	def callback_setBorderType(self, border):
		self.borderType = self.borderOptions[self.borderOptionLabels.index(border)]
	def callback_setKernelSize(self, size):
		if is_int(size): 
			val = int(size)
			if val % 2 == 1 and val >= 1:
				self.kernelSize = int(size)

	def getSigma(self):
		return self.sigma
	def getBorderTypeStr(self):
		if self.borderType in self.borderOptions:
			return self.borderOptionLabels[self.borderOptions.index(self.borderType)]
		else:
			return "NONE"
	def getKernelSize(self):
		return self.kernelSize
		
	def apply_to_image(self, img):
		return cv2.GaussianBlur(img,
			(self.kernelSize, self.kernelSize),
			self.sigma)


class MorphologicalOperationType(Enum):
	NONE = 0
	EROSION = 1
	DILATION = 2
	OPENING = 3
	CLOSING = 4
	GRADIENT = 5 #the difference between dilation and erosion of an image
	
	def str(self):
		map = {
		self.EROSION: "Erosion",
		self.DILATION: "Dilation",
		self.OPENING: "Opening",
		self.CLOSING: "Closing",
		self.GRADIENT: "Gradient",
		}
		if self in map:
			return map[self]
		else:
			return "Morph"

class MorphologicalOperation(ImageOperation):
	#https://docs.opencv.org/3.0-beta/doc/py_tutorials/py_imgproc/py_morphological_ops/py_morphological_ops.html

	@staticmethod
	def get_type_label():
		return "Morphological Operation"
	
	def get_default_label(self):
		return self.type.str()
	
	def __init__(self, type = MorphologicalOperationType.NONE, kernelSize = 5):

		self.type = type
		self.iterations = 1
		self.kernelSize = kernelSize
		self.shape = cv2.MORPH_RECT
		
		# type is needed for setting the label, so we do the super after initing the type
		super(MorphologicalOperation, self).__init__()
		
		
		self.typeOptionLabels = ["None", "Erosion", "Dilation", "Opening", "Closing", "Gradient"]
		self.typeOptions = [
			MorphologicalOperationType.NONE,
			MorphologicalOperationType.EROSION,
			MorphologicalOperationType.DILATION,
			MorphologicalOperationType.OPENING,
			MorphologicalOperationType.CLOSING,
			MorphologicalOperationType.GRADIENT,
			]
		
		self.shapeOptionLabels = ["Rectangle", "Ellipse", "Cross"]
		self.shapeOptions = [
			cv2.MORPH_RECT,
			cv2.MORPH_ELLIPSE,
			cv2.MORPH_CROSS,
			]
		
		self.parameters.append(
		OperationParameter("Operation Type", self.getTypeStr, self.callback_setType).set_dropdown(self.typeOptionLabels))
	
		self.parameters.append(
		OperationParameter("Iterations",self.getIterations, self.callback_setIterations).set_slider(1, 20, 1))
		
		self.parameters.append(
		OperationParameter("Kernel Shape", self.getKernelShapeStr, self.callback_setKernelShape).set_dropdown(self.shapeOptionLabels))
	
		self.parameters.append(
		OperationParameter("Kernel Size",self.getKernelSize, self.callback_setKernelSize).set_slider(1, 11, 2))
	
	def callback_setType(self, type):
		self.set_type(self.typeOptions[self.typeOptionLabels.index(type)])
	def callback_setIterations(self, val):
		if is_int(val): self.iterations = int(val)
	def callback_setKernelShape(self, shape):
		self.shape = self.shapeOptions[self.shapeOptionLabels.index(shape)]
	def callback_setKernelSize(self, size):
		if is_int(size): 
			val = int(size)
			if val % 2 == 1 and val >= 1:
				self.kernelSize = int(size)
		
	def getTypeStr(self):
		if self.type in self.typeOptions:
			return self.typeOptionLabels[self.typeOptions.index(self.type)]
		else:
			return "NONE"
	def getIterations(self):
		return self.iterations
	def getKernelShapeStr(self):
		if self.shape in self.shapeOptions:
			return self.shapeOptionLabels[self.shapeOptions.index(self.shape)]
		else:
			return "NONE"
	def getKernelSize(self):
		return self.kernelSize
		
		
	
	def set_type(self, pType):
		should_update_label = (self.get_label() == self.get_default_label())
	
		self.type = pType
		
		print("Setting Morph type to {0}, should_update_label={1}".format(pType.str(), should_update_label))
		
		if should_update_label:
			self.set_label(self.get_default_label())
		
		return self
	
	def set_kernel(self, pKernelSize, pShape = cv2.MORPH_RECT):
		self.kernelSize = pKernelSize
		self.shape = pShape
		
		return self
		
	def apply_to_image(self, img):
		kernel = cv2.getStructuringElement(self.shape,(self.kernelSize,self.kernelSize))
		#np.ones((self.kernelSize,self.kernelSize),np.uint8)
		if self.type == MorphologicalOperationType.EROSION:
			return cv2.erode(img, kernel, iterations = self.iterations)
		elif self.type == MorphologicalOperationType.DILATION:
			return cv2.dilate(img, kernel, iterations = self.iterations)
		elif self.type == MorphologicalOperationType.OPENING:
			return cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)
		elif self.type == MorphologicalOperationType.CLOSING:
			return cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
		elif self.type == MorphologicalOperationType.GRADIENT:
			return cv2.morphologyEx(img, cv2.MORPH_GRADIENT, kernel)
		else:
			print ("WARNING: MorphologicalOperation was applied with an inoperable type: {}".format(self.type))
			return img

class OperationStack:
	def __init__(self):
		self.op_stack = []

	def add_operation(self, new_op, label = None):
		if not label:
			label = new_op.get_label()
			for index, op in reversed(list(enumerate(self.op_stack))):
				results = re.match(r'([A-Za-z\-\_ ]+)([0-9]*)', op.get_label()).groups()
				if results[0] == label:
					num = 0
					if results[1] and results[1].isdigit():
						num = int(results[1])
					label += str(num + 1)
					break
					
		new_op.set_label(label)
		self.op_stack.append(new_op)
	
	def get_op(self, index):
		if index < 0 or index >= len(self.op_stack):
			return None
		return self.op_stack[index]
		
	def get_label(self, index):
		if index < 0 or index >= len(self.op_stack):
			return None
		return self.op_stack[index].get_label()

	def get_stack(self):
		return self.op_stack

	def swap_ops(self, a, b):
		if a < 0 or a >= len(self.op_stack):
			print("WARNING: swap operation A index was out of bounds")
			return
		if b < 0 or b >= len(self.op_stack):
			print("WARNING: swap operation B index was out of bounds")
			return
		self.op_stack[a], self.op_stack[b] = self.op_stack[b], self.op_stack[a]

	def remove_op(self, index):
		self.op_stack.pop(index)
		

class ImageProcesser:

	def __init__(self, stack = None):
		if stack:
			self.op_stack = stack
		else:
			self.op_stack = OperationStack()
		self.results = []
	
	def add_operation(self, operation, label = None):
		self.op_stack.add_operation(operation, label)
	
	def process_color_image(self, img):
		self.process_image(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
	
	def process_image(self, img):
		results = [[img, "Original"]]
		temp = img
		for op in self.op_stack.get_stack():
			if not op.muted:
				temp = op.apply_to_image(temp)
			results.append([temp, op.get_label()])
		self.results = results
		return temp
		
	def get_last_results(self):
		return self.results
		

		
#EOF
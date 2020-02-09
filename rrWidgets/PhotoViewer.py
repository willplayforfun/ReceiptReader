from PyQt5 import QtCore, QtGui, QtWidgets

class PhotoViewer(QtWidgets.QGraphicsView):
	photoClicked = QtCore.pyqtSignal(QtCore.QPoint)

	def __init__(self, parent):
		super(PhotoViewer, self).__init__(parent)
		self._zoom = 0
		self._empty = True
		self._scene = QtWidgets.QGraphicsScene(self)
		self._photo = QtWidgets.QGraphicsPixmapItem()
		self._scene.addItem(self._photo)
		self.setScene(self._scene)
		self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
		self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
		self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30)))
		self.setFrameShape(QtWidgets.QFrame.NoFrame)
		
		# allows us to fit in view during painting, when the widget reports the correct size
		self.just_updated = False

	def hasPhoto(self):
		return not self._empty

	def fitInView(self, scale=True):
		rect = QtCore.QRectF(self._photo.pixmap().rect())
		if not rect.isNull():
			self.setSceneRect(rect)
			if self.hasPhoto():
				unity = self.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))
				#print("PhotoViewer::fitInView 'unity' = {0}; initial scalefactor = {1}".format(unity, 1 / unity.width()))
				self.scale(1 / unity.width(), 1 / unity.height())
				
				#viewrect = self.size() 
				viewrect = self.mapToScene(self.viewport().geometry()).boundingRect()
				scenerect = self.transform().mapRect(rect) # IMAGE SIZE
				factor = min(viewrect.width() / scenerect.width(),
							 viewrect.height() / scenerect.height())
							 
				#print("PhotoViewer::fitInView 'view rect' = {0} ; 'scene rect' = {1} ; 'factor' = {2}".format(viewrect, scenerect, factor))
				self.scale(factor, factor)
				
			self._zoom = 0

	def setPixmap(self, pixmap=None):
		self._zoom = 0
		if pixmap and not pixmap.isNull():			
			if self._photo.pixmap() is None \
				or (self._photo.pixmap().height() != pixmap.height() or self._photo.pixmap().width() != pixmap.width()):
				self.just_updated = True
				#pass
		
			self._empty = False
			self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
			self._photo.setPixmap(pixmap)
		else:
			self._empty = True
			self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
			self._photo.setPixmap(QtGui.QPixmap())
			
	def showEvent(self, event):
		super(PhotoViewer, self).showEvent(event)
		if self.just_updated:
			self.fitInView()
			self.just_updated = False

	def wheelEvent(self, event):
		if self.hasPhoto():
			if event.angleDelta().y() > 0:
				factor = 1.25
				self._zoom += 1
			else:
				factor = 0.8
				self._zoom -= 1
			if self._zoom > 0:
				self.scale(factor, factor)
			elif self._zoom == 0:
				self.fitInView()
			else:
				self._zoom = 0

	def toggleDragMode(self):
		if self.dragMode() == QtWidgets.QGraphicsView.ScrollHandDrag:
			self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
		elif not self._photo.pixmap().isNull():
			self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)

	def mousePressEvent(self, event):
		if self._photo.isUnderMouse():
			point_on_image = self.mapToScene(event.pos()).toPoint()
			self.photoClicked.emit(point_on_image)
		#print('Mouse Press Event: {0}, {1}'.format(event.pos().x(), event.pos().y()))
		super(PhotoViewer, self).mousePressEvent(event)


class Window(QtWidgets.QWidget):
	def __init__(self):
		super(Window, self).__init__()
		self.viewer = PhotoViewer(self)
		# 'Load image' button
		self.btnLoad = QtWidgets.QToolButton(self)
		self.btnLoad.setText('Load image')
		self.btnLoad.clicked.connect(self.loadImage)
		# Button to change from drag/pan to getting pixel info
		self.btnPixInfo = QtWidgets.QToolButton(self)
		self.btnPixInfo.setText('Enter pixel info mode')
		self.btnPixInfo.clicked.connect(self.pixInfo)
		self.editPixInfo = QtWidgets.QLineEdit(self)
		self.editPixInfo.setReadOnly(True)
		self.viewer.photoClicked.connect(self.photoClicked)
		# Arrange layout
		VBlayout = QtWidgets.QVBoxLayout(self)
		VBlayout.addWidget(self.viewer)
		HBlayout = QtWidgets.QHBoxLayout()
		HBlayout.setAlignment(QtCore.Qt.AlignLeft)
		HBlayout.addWidget(self.btnLoad)
		HBlayout.addWidget(self.btnPixInfo)
		HBlayout.addWidget(self.editPixInfo)
		VBlayout.addLayout(HBlayout)

	def loadImage(self):
		self.viewer.setPixmap(QtGui.QPixmap('face.PNG'))

	def pixInfo(self):
		self.viewer.toggleDragMode()

	def photoClicked(self, pos):
		if self.viewer.dragMode()  == QtWidgets.QGraphicsView.NoDrag:
			self.editPixInfo.setText('%d, %d' % (pos.x(), pos.y()))


if __name__ == '__main__':
	import sys
	app = QtWidgets.QApplication(sys.argv)
	window = Window()
	window.setGeometry(500, 300, 800, 600)
	window.show()
	sys.exit(app.exec_())

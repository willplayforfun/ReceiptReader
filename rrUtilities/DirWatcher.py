
import os
import threading
from PyQt5.QtCore import QThread
from PyQt5.QtCore import pyqtSignal as Signal

import win32file
import win32event
import win32con


ACTIONS = {
	1 : "Created",
	2 : "Deleted",
	3 : "Updated",
	4 : "Renamed to something",
	5 : "Renamed from something"
}

def watch_path (path_to_watch, include_subdirectories=False):
	FILE_LIST_DIRECTORY = 0x0001
	hDir = win32file.CreateFile (
		path_to_watch,
		FILE_LIST_DIRECTORY,
		win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
		None,
		win32con.OPEN_EXISTING,
		win32con.FILE_FLAG_BACKUP_SEMANTICS,
		None
	)
	while True:
		results = win32file.ReadDirectoryChangesW (
			hDir,
			1024,
			include_subdirectories,
			win32con.FILE_NOTIFY_CHANGE_FILE_NAME | 
			 win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
			 win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
			 win32con.FILE_NOTIFY_CHANGE_SIZE |
			 win32con.FILE_NOTIFY_CHANGE_LAST_WRITE |
			 win32con.FILE_NOTIFY_CHANGE_SECURITY,
			None,
			None
		)
		for action, file in results:
			full_filename = os.path.join (path_to_watch, file)
			if not os.path.exists (full_filename):
				file_type = "<deleted>"
			elif os.path.isdir (full_filename):
				file_type = 'folder'
			else:
				file_type = 'file'
			yield (file_type, full_filename, ACTIONS.get (action, "Unknown"))


#class DirWatcher (threading.Thread):
class DirWatcher (QThread):

	onDirUpdate = Signal()
	
	def __init__(self, path_to_watch, results_queue):
		QThread.__init__(self)
		self.path_to_watch = path_to_watch
		self.results_queue = results_queue

		self.start()

	def __del__(self):
		self.wait()

	"""
	def __init__ (self, path_to_watch, results_queue, **kwds):
		threading.Thread.__init__ (self, **kwds)
		self.setDaemon (1)
		self.path_to_watch = path_to_watch
		self.results_queue = results_queue
		self.start ()
	"""

	def run (self):
		for result in watch_path (self.path_to_watch):
			self.results_queue.put (result)
			self.onDirUpdate.emit()

"""
	path_to_watch = os.path.abspath (".")

	#
	# FindFirstChangeNotification sets up a handle for watching
	#  file changes. The first parameter is the path to be
	#  watched; the second is a boolean indicating whether the
	#  directories underneath the one specified are to be watched;
	#  the third is a list of flags as to what kind of changes to
	#  watch for. We're just looking at file additions / deletions.
	#
	change_handle = win32file.FindFirstChangeNotification (
	  path_to_watch,
	  0,
	  win32con.FILE_NOTIFY_CHANGE_FILE_NAME
	)

	#
	# Loop forever, listing any file changes. The WaitFor... will
	#  time out every half a second allowing for keyboard interrupts
	#  to terminate the loop.
	#
	try:

	  old_path_contents = dict ([(f, None) for f in os.listdir (path_to_watch)])
	  while 1:
		result = win32event.WaitForSingleObject (change_handle, 500)

		#
		# If the WaitFor... returned because of a notification (as
		#  opposed to timing out or some error) then look for the
		#  changes in the directory contents.
		#
		if result == win32con.WAIT_OBJECT_0:
		  new_path_contents = dict ([(f, None) for f in os.listdir (path_to_watch)])
		  added = [f for f in new_path_contents if not f in old_path_contents]
		  deleted = [f for f in old_path_contents if not f in new_path_contents]
		  if added: print "Added: ", ", ".join (added)
		  if deleted: print "Deleted: ", ", ".join (deleted)

		  old_path_contents = new_path_contents
		  win32file.FindNextChangeNotification (change_handle)

	finally:
	  win32file.FindCloseChangeNotification (change_handle)
"""


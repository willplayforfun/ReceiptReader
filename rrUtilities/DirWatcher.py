import os

# we use Qt's threading so we can emit signals from the thread
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
WIN32_ACTION_CREATED = ACTIONS[1]
WIN32_ACTION_DELETED = ACTIONS[2]
WIN32_ACTION_UPDATED = ACTIONS[3]
WIN32_ACTION_RENAMED_TO = ACTIONS[4]
WIN32_ACTION_RENAMED_FROM = ACTIONS[5]


class DirWatcher (QThread):

	onDirUpdate = Signal()
	
	def __init__(self, path_to_watch, results_queue):
		QThread.__init__(self)
		self.path_to_watch = path_to_watch
		self.results_queue = results_queue

		self.start()

	def __del__(self):
		self.wait()

	def run (self):
		for result in self.watch_path (self.path_to_watch):
			self.results_queue.put (result)
			self.onDirUpdate.emit()
			
	
	def watch_path (self, path_to_watch, include_subdirectories=False):
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


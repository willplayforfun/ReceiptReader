import os
import subprocess

PKGS = ["pillow", "numpy", "opencv-python", "PyYaml", "pywin32", "PyQt5", "pytesseract"]

if __name__ == "__main__":

	os.system("python -m venv venv/")
	
	for pkg in PKGS:
		subprocess.call([r"venv/Scripts/pip", "install", pkg])

#EOF
@ECHO ON
cd /D %~dp0
CALL venv\Scripts\activate
@ECHO ON
StackEditor.py resources/debug_imgs/face.PNG
@ECHO OFF 
CALL deactivate
@ECHO ON
pause
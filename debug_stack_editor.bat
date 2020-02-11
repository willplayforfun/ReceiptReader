@ECHO ON
cd /D %~dp0
CALL venv\Scripts\activate
@ECHO ON
StackEditor.py
@ECHO OFF 
CALL deactivate
@ECHO ON
pause
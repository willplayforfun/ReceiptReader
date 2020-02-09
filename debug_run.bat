set "result=%~dp0"
cd /d %result%

python main.py -c config.yaml
pause
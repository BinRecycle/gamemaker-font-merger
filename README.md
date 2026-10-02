# gamemaker-font-merger
GameMaker 엔진 폰트 파일을 병합해주는 도구

## 빌드 방법
클론 후 아래 명령어 입력
```sh
pyinstaller --noconsole --onefile --icon=app_icon.ico --add-data "font_merger.ui;." --add-data "app_icon.ico;." main.py
```

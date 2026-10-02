import sys
import os
import re
import threading
import ctypes
from PIL import Image

from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QIcon


class LogSignal(QObject):
    log_msg = pyqtSignal(str)


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class FontMergerApp(QMainWindow):
    merge_finished = pyqtSignal()

    @property
    def old_png(self):
        return self.entry_old_png.text().strip()
    
    @property
    def old_csv(self):
        return self.entry_old_csv.text().strip()

    @property
    def new_png(self):
        return self.entry_new_png.text().strip()

    @property
    def new_yy(self):
        return self.entry_new_yy.text().strip()

    def update_merge_button_state(self):
        all_files_exist = (
            os.path.isfile(self.old_png) and
            os.path.isfile(self.old_csv) and
            os.path.isfile(self.new_png) and
            os.path.isfile(self.new_yy)
        )
        self.btn_merge.setEnabled(all_files_exist)

    def update_auto_spinboxes(self):
        if os.path.isfile(self.old_png) and os.path.isfile(self.new_png):
            try:
                with Image.open(self.old_png) as img_old, Image.open(self.new_png) as img_new:
                    if self.ckbx_y_auto.isChecked():
                        self.entry_shift_y.setValue(img_old.height)

                    shift_x = self.entry_shift_x.value()
                    shift_y = self.entry_shift_y.value()

                    req_w = max(img_old.width, shift_x + img_new.width)
                    req_h = max(img_old.height, shift_y + img_new.height)

                    if self.ckbx_w_auto.isChecked():
                        self.entry_out_w.setValue(req_w)
                    if self.ckbx_h_auto.isChecked():
                        self.entry_out_h.setValue(req_h)
            except Exception:
                pass

    def update_auto_name(self):
        if self.ckbx_name_auto.isChecked():
            if self.old_png:
                base_name = os.path.splitext(os.path.basename(self.old_png))[0]
                self.entry_name.setText(base_name)
            else:
                self.entry_name.setText("")
            self.entry_name.setReadOnly(True)
        else:
            self.entry_name.setReadOnly(False)

    def __init__(self):
        super().__init__()

        uic.loadUi(resource_path("font_merger.ui"), self)
        self.setWindowIcon(QIcon(resource_path("app_icon.ico")))

        self.logger = LogSignal()
        self.logger.log_msg.connect(self.log)
        self.merge_finished.connect(self.update_merge_button_state)

        # 파일 선택 버튼 이벤트 연결
        self.btn_select_old_png.clicked.connect(lambda: self.select_file(self.entry_old_png, "PNG 파일 (*.png)"))
        self.btn_select_old_csv.clicked.connect(lambda: self.select_file(self.entry_old_csv, "CSV 파일 (*.csv)"))
        self.btn_select_new_png.clicked.connect(lambda: self.select_file(self.entry_new_png, "PNG 파일 (*.png)"))
        self.btn_select_new_yy.clicked.connect(lambda: self.select_file(self.entry_new_yy, "YY 파일 (*.yy)"))
        self.btn_select_out_dir.clicked.connect(self.select_out_dir)

        # 파일 입력 변경 시 병합 버튼 활성화 상태 업데이트
        self.entry_old_png.textChanged.connect(self.update_merge_button_state)
        self.entry_old_csv.textChanged.connect(self.update_merge_button_state)
        self.entry_new_png.textChanged.connect(self.update_merge_button_state)
        self.entry_new_yy.textChanged.connect(self.update_merge_button_state)
        self.update_merge_button_state()
        
        # 체크박스 토글 이벤트 연결
        self.ckbx_y_auto.toggled.connect(lambda checked: (self.entry_shift_y.setReadOnly(checked), self.update_auto_spinboxes()))
        self.ckbx_w_auto.toggled.connect(lambda checked: (self.entry_out_w.setReadOnly(checked), self.update_auto_spinboxes()))
        self.ckbx_h_auto.toggled.connect(lambda checked: (self.entry_out_h.setReadOnly(checked), self.update_auto_spinboxes()))

        self.entry_old_png.textChanged.connect(self.update_auto_spinboxes)
        self.entry_new_png.textChanged.connect(self.update_auto_spinboxes)

        # 초기 ReadOnly 상태 적용
        self.entry_shift_y.setReadOnly(self.ckbx_y_auto.isChecked())
        self.entry_out_w.setReadOnly(self.ckbx_w_auto.isChecked())
        self.entry_out_h.setReadOnly(self.ckbx_h_auto.isChecked())

        # 이름 자동 지정 설정
        self.ckbx_name_auto.setChecked(True)
        self.ckbx_name_auto.toggled.connect(self.update_auto_name)
        self.entry_old_png.textChanged.connect(self.update_auto_name)
        self.update_auto_name()

        self.btn_merge.clicked.connect(self.start_merge)

        self.log("GameMaker 폰트 병합기 by BinRecycle with Google Gemini\nv20261002")

    def select_file(self, line_edit, file_filter):
        filepath, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", file_filter)
        if filepath:
            line_edit.setText(filepath)

    def select_out_dir(self):
        dirpath = QFileDialog.getExistingDirectory(self, "저장 폴더 선택")
        if dirpath:
            self.entry_out_dir.setText(dirpath)

    def log(self, message):
        self.log_text.append(message)

    def start_merge(self):
        # 메인 스레드에서 UI 인자값 안전하게 추출
        params = {
            "old_png": self.old_png,
            "old_csv": self.old_csv,
            "new_png": self.new_png,
            "new_yy": self.new_yy,
            "shift_x": self.entry_shift_x.value(),
            "shift_y": self.entry_shift_y.value(),
            "out_w": self.entry_out_w.value(),
            "out_h": self.entry_out_h.value(),
            "is_w_auto": self.ckbx_w_auto.isChecked(),
            "is_h_auto": self.ckbx_h_auto.isChecked(),
            "font_name": self.entry_name.text().strip() or "merged_font",
            "out_dir": self.entry_out_dir.text().strip(),
            "keep_old": self.radio_dup_old.isChecked()
        }

        self.btn_merge.setEnabled(False)
        threading.Thread(target=self.run_merge, kwargs=params, daemon=True).start()

    def run_merge(self, old_png, old_csv, new_png, new_yy, shift_x, shift_y, 
                  out_w, out_h, is_w_auto, is_h_auto, font_name, out_dir, keep_old):
        self.logger.log_msg.emit("\n====================================")
        self.logger.log_msg.emit("🚀 병합 작업을 시작합니다...")

        try:
            # --- A. 이미지 병합 처리 ---
            self.logger.log_msg.emit("이미지 데이터를 불러오는 중...")
            with Image.open(old_png) as img_old_raw, Image.open(new_png) as img_new_raw:
                img_old = img_old_raw.convert("RGBA")
                img_new = img_new_raw.convert("RGBA")

                req_w = max(img_old.width, shift_x + img_new.width)
                req_h = max(img_old.height, shift_y + img_new.height)

                final_w = req_w if is_w_auto else out_w
                final_h = req_h if is_h_auto else out_h

                out_img = Image.new("RGBA", (final_w, final_h), (0, 0, 0, 0))
                out_img.paste(img_old, (0, 0))
                out_img.paste(img_new, (shift_x, shift_y))

            dir_name = out_dir if out_dir else os.path.dirname(old_png)
            out_png_path = os.path.join(dir_name, f"{font_name}.png")
            out_yy_path = os.path.join(dir_name, f"{font_name}.yy")

            out_img.save(out_png_path)
            self.logger.log_msg.emit(f"✅ 이미지 병합 완료: {final_w}x{final_h}")

            # --- B. CSV 처리 ---
            old_glyphs = {}
            with open(old_csv, "r", encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(";")
                    if len(parts) >= 7:
                        try:
                            char = int(parts[0])
                            x, y, w, h, shift, offset = map(int, parts[1:7])
                            old_glyphs[char] = (f'    "{char}": {{"x":{x},"y":{y},"w":{w},"h":{h},"character":{char},"shift":{shift},"offset":{offset},}},')
                        except ValueError:
                            pass

            # --- C. YY 처리 ---
            with open(new_yy, "r", encoding="utf-8") as f:
                content = f.read()

            start_idx = content.find('"glyphs"')
            brace_start = content.find("{", start_idx)
            brace_count = 0
            end_idx = -1
            for i in range(brace_start, len(content)):
                if content[i] == "{":
                    brace_count += 1
                elif content[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break

            before_glyphs = content[: brace_start + 1]
            glyphs_content = content[brace_start + 1 : end_idx]
            tail_content = content[end_idx:]

            if shift_x != 0:
                glyphs_content = re.sub(r'("x"\s*:\s*)([+-]?\d+)', lambda m: f"{m.group(1)}{int(m.group(2)) + shift_x}", glyphs_content)
            if shift_y != 0:
                glyphs_content = re.sub(r'("y"\s*:\s*)([+-]?\d+)', lambda m: f"{m.group(1)}{int(m.group(2)) + shift_y}", glyphs_content)

            existing_keys = set()
            for match in re.finditer(r'"(\d+)"\s*:\s*\{', glyphs_content):
                existing_keys.add(int(match.group(1)))

            lines_to_add = []
            for char, line_str in old_glyphs.items():
                if char in existing_keys:
                    if keep_old:
                        pattern = r'"' + str(char) + r'"\s*:\s*\{[^}]+\},?'
                        glyphs_content = re.sub(pattern, "", glyphs_content)
                        lines_to_add.append(line_str)
                else:
                    lines_to_add.append(line_str)

            if lines_to_add:
                insert_str = "\n" + "\n".join(lines_to_add) + "\n"
                glyphs_content = insert_str + glyphs_content

            with open(out_yy_path, "w", encoding="utf-8") as f:
                f.write(before_glyphs + glyphs_content + tail_content)

            self.logger.log_msg.emit("✅ YY 파일 병합 완료")
            self.logger.log_msg.emit("🎉 모든 작업이 성공적으로 완료되었습니다!")

        except Exception as e:
            self.logger.log_msg.emit(f"\n[오류 발생] {str(e)}")
        finally:
            # 안전하게 메인 스레드를 통해 버튼 상태 복원
            self.merge_finished.emit()


if __name__ == "__main__":
    if sys.platform == "win32":
        myappid = "binrecycle.fontmerger.app.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    window = FontMergerApp()
    window.show()
    sys.exit(app.exec())
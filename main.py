import sys
import os
import re
import threading
from PIL import Image

from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QIcon


# 1. 스레드에서 로그 창을 안전하게 업데이트하기 위한 시그널 클래스
class LogSignal(QObject):
    log_msg = pyqtSignal(str)


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class FontMergerApp(QMainWindow):
    def update_auto_spinboxes(self):

        old_path = self.entry_old_png.text().strip()
        new_path = self.entry_new_png.text().strip()

        if os.path.exists(old_path) and os.path.exists(new_path):
            try:
                with Image.open(old_path) as img_old, Image.open(new_path) as img_new:
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
            old_path = self.entry_old_png.text().strip()
            if old_path:
                base_name = os.path.splitext(os.path.basename(old_path))[0]
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

        self.btn_select_old_png.clicked.connect(lambda: self.select_file(self.entry_old_png, "PNG 파일 (*.png)"))
        self.btn_select_old_csv.clicked.connect(lambda: self.select_file(self.entry_old_csv, "CSV 파일 (*.csv)"))
        self.btn_select_new_png.clicked.connect(lambda: self.select_file(self.entry_new_png, "PNG 파일 (*.png)"))
        self.btn_select_new_yy.clicked.connect(lambda: self.select_file(self.entry_new_yy, "YY 파일 (*.yy)"))
        self.btn_select_out_dir.clicked.connect(self.select_out_dir)

        self.ckbx_y_auto.toggled.connect(lambda checked: (self.entry_shift_y.setReadOnly(checked),self.update_auto_spinboxes()))
        self.ckbx_w_auto.toggled.connect(lambda checked: (self.entry_out_w.setReadOnly(checked),self.update_auto_spinboxes()))
        self.ckbx_h_auto.toggled.connect(lambda checked: (self.entry_out_h.setReadOnly(checked),self.update_auto_spinboxes()))

        self.entry_old_png.textChanged.connect(self.update_auto_spinboxes)
        self.entry_new_png.textChanged.connect(self.update_auto_spinboxes)

        self.entry_shift_y.setDisabled(self.ckbx_y_auto.isChecked())
        self.entry_out_w.setDisabled(self.ckbx_w_auto.isChecked())
        self.entry_out_h.setDisabled(self.ckbx_h_auto.isChecked())

        self.ckbx_name_auto.setChecked(True)
        self.ckbx_name_auto.toggled.connect(self.update_auto_name)
        self.entry_old_png.textChanged.connect(self.update_auto_name)
        self.update_auto_name()

        self.btn_merge.clicked.connect(self.start_merge)

        self.log("GameMaker 폰트 병합기 by BinRecycle with Google Gemini\nv20261002")

    # 파일 선택
    def select_file(self, line_edit, file_filter):
        filepath, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", file_filter)
        if filepath:
            line_edit.setText(filepath)

    # 저장 폴더 선택
    def select_out_dir(self):
        dirpath = QFileDialog.getExistingDirectory(self, "저장 폴더 선택")
        if dirpath:
            self.entry_out_dir.setText(dirpath)

    # 로그 출력
    def log(self, message):
        self.log_text.append(message)  # PyQt에서는 text.append()로 간단히 로그를 추가합니다.

    def start_merge(self):
        old_png = self.entry_old_png.text().strip()
        old_csv = self.entry_old_csv.text().strip()
        new_png = self.entry_new_png.text().strip()
        new_yy = self.entry_new_yy.text().strip()

        if not all([old_png, old_csv, new_png, new_yy]):
            self.log("[오류] 모든 파일을 선택해주세요.")
            QMessageBox.warning(self, "입력 오류", "모든 파일을 선택해야 합니다.")
            return

        # 2. 검증을 통과했을 때만 별도 쓰레드 시작
        threading.Thread(target=self.run_merge, daemon=True).start()

    def run_merge(self):
        # PyQt에서 입력창 값 가져오기: .text()
        old_png = self.entry_old_png.text().strip()
        old_csv = self.entry_old_csv.text().strip()
        new_png = self.entry_new_png.text().strip()
        new_yy = self.entry_new_yy.text().strip()

        self.btn_merge.setEnabled(False)  # 버튼 비활성화
        self.logger.log_msg.emit("\n====================================")
        self.logger.log_msg.emit("🚀 병합 작업을 시작합니다...")

        try:
            # --- A. 이미지 병합 처리 ---
            self.logger.log_msg.emit("이미지 데이터를 불러오는 중...")
            img_old = Image.open(old_png).convert("RGBA")
            img_new = Image.open(new_png).convert("RGBA")

            shift_x = self.entry_shift_x.value()
            shift_y = self.entry_shift_y.value()

            req_w = max(img_old.width, shift_x + img_new.width)
            req_h = max(img_old.height, shift_y + img_new.height)

            out_w = self.entry_out_w.value()
            out_h = self.entry_out_h.value()

            final_w = (req_w if self.ckbx_w_auto.isChecked() else self.entry_out_w.value())
            final_h = (req_h if self.ckbx_h_auto.isChecked() else self.entry_out_h.value())

            out_img = Image.new("RGBA", (final_w, final_h), (0, 0, 0, 0))
            out_img.paste(img_old, (0, 0))
            out_img.paste(img_new, (shift_x, shift_y))

            font_name = self.entry_name.text().strip()
            if not font_name:
                font_name = "merged_font"

            custom_dir = self.entry_out_dir.text().strip()
            dir_name = custom_dir if custom_dir else os.path.dirname(old_png)

            out_png = os.path.join(dir_name, f"{font_name}.png")
            out_yy = os.path.join(dir_name, f"{font_name}.yy")

            out_img.save(out_png)
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
                glyphs_content = re.sub(r'("x"\s*:\s*)([+-]?\d+)',lambda m: f"{m.group(1)}{int(m.group(2)) + shift_x}",glyphs_content)
            if shift_y != 0:
                glyphs_content = re.sub(r'("y"\s*:\s*)([+-]?\d+)',lambda m: f"{m.group(1)}{int(m.group(2)) + shift_y}",glyphs_content)

            existing_keys = set()
            for match in re.finditer(r'"(\d+)"\s*:\s*\{', glyphs_content):
                existing_keys.add(int(match.group(1)))

            lines_to_add = []
            # 라디오 버튼 체크 확인
            keep_old = self.radio_dup_old.isChecked()

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

            with open(out_yy, "w", encoding="utf-8") as f:
                f.write(before_glyphs + glyphs_content + tail_content)

            self.logger.log_msg.emit("✅ YY 파일 병합 완료")
            self.logger.log_msg.emit("🎉 모든 작업이 성공적으로 완료되었습니다!")

        except Exception as e:
            self.logger.log_msg.emit(f"\n[오류 발생] {str(e)}")
        finally:
            self.btn_merge.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FontMergerApp()
    window.show()
    sys.exit(app.exec())

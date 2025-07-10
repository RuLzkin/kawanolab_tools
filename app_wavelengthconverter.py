# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QGroupBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QDoubleValidator


class FrequencyWavelengthConverter(QMainWindow):
    def __init__(self, debug=False):
        super().__init__()
        self.debug = debug
        self.c0 = 299792458  # 真空中の光速 [m/s]
        self.updating = False  # 更新中フラグ（無限ループ防止）

        # 内部状態保持用（SI単位系）
        self.current_freq_hz = None  # 周波数 [Hz]
        self.current_wave_m = None  # 波長 [m]
        self.current_wavenum_m_inv = None  # 波数 [m⁻¹]

        self.print("初期化開始")
        self.initUI()
        self.print("初期化完了")

    def print(self, arg):
        if self.debug:
            print(arg)

    def initUI(self):
        self.setWindowTitle('周波数・波長・波数変換器')
        # self.setFixedSize(550, 500)
        self.setFixedSize(350, 320)

        # メインウィジェット
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # タイトル
        title = QLabel('周波数・波長・波数 相互変換')
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # 屈折率グループ
        refr_group = QGroupBox('媒質')
        refr_layout = QHBoxLayout()
        refr_layout.addWidget(QLabel('屈折率 n ='))
        self.refr_input = QLineEdit('1.0')
        self.refr_input.setMaximumWidth(100)
        # 数値のみ入力可能にする
        validator = QDoubleValidator(0.1, 10.0, 6)
        self.refr_input.setValidator(validator)
        refr_layout.addWidget(self.refr_input)
        refr_layout.addWidget(QLabel('（真空: 1.0, 水: 1.33, ガラス: 1.5）'))
        refr_layout.addStretch()
        refr_group.setLayout(refr_layout)

        # 周波数グループ
        freq_group = QGroupBox('周波数')
        freq_layout = QHBoxLayout()
        self.freq_input = QLineEdit()
        self.freq_input.setPlaceholderText('数値を入力')
        self.freq_unit = QComboBox()
        self.freq_unit.addItems(['Hz', 'kHz', 'MHz', 'GHz', 'THz'])
        self.freq_unit.setCurrentIndex(3)  # デフォルトはGHz
        freq_layout.addWidget(self.freq_input)
        freq_layout.addWidget(self.freq_unit)
        freq_group.setLayout(freq_layout)

        # 波長グループ
        wave_group = QGroupBox('波長')
        wave_layout = QHBoxLayout()
        self.wave_input = QLineEdit()
        self.wave_input.setPlaceholderText('数値を入力')
        self.wave_unit = QComboBox()
        self.wave_unit.addItems(['m', 'mm', 'μm', 'nm'])
        self.wave_unit.setCurrentIndex(1)  # デフォルトはmm
        wave_layout.addWidget(self.wave_input)
        wave_layout.addWidget(self.wave_unit)
        wave_group.setLayout(wave_layout)

        # 波数グループ
        wavenum_group = QGroupBox('波数')
        wavenum_layout = QHBoxLayout()
        self.wavenum_input = QLineEdit()
        self.wavenum_input.setPlaceholderText('数値を入力')
        self.wavenum_unit = QComboBox()
        self.wavenum_unit.addItems(['m⁻¹', 'cm⁻¹'])
        self.wavenum_unit.setCurrentIndex(1)  # デフォルトはcm⁻¹
        wavenum_layout.addWidget(self.wavenum_input)
        wavenum_layout.addWidget(self.wavenum_unit)
        wavenum_group.setLayout(wavenum_layout)

        # メインレイアウトに追加
        main_layout.addWidget(refr_group)
        main_layout.addWidget(freq_group)
        main_layout.addWidget(wave_group)
        main_layout.addWidget(wavenum_group)
        main_layout.addStretch()

        # 関係式の表示
        formula_label = QLabel('関係式: c = c₀/n, λ = c/ν, k = 1/λ = ν/c')
        formula_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(formula_label)

        # シグナル接続
        self.print("シグナル接続開始")

        # テキスト変更時に即座に計算（より直感的な動作）
        self.freq_input.textChanged.connect(self.on_freq_text_changed)
        self.wave_input.textChanged.connect(self.on_wave_text_changed)
        self.wavenum_input.textChanged.connect(self.on_wavenum_text_changed)

        # 単位変更時は再表示のみ（再計算はしない）
        self.freq_unit.currentIndexChanged.connect(self.on_freq_unit_changed)
        self.wave_unit.currentIndexChanged.connect(self.on_wave_unit_changed)
        self.wavenum_unit.currentIndexChanged.connect(self.on_wavenum_unit_changed)

        # 屈折率変更時の再計算
        self.refr_input.textChanged.connect(self.on_refr_changed)

        self.print("シグナル接続完了")

        # 初期値を設定（1 GHz）
        self.print("初期値設定: 1 GHz")
        self.freq_input.setText('1')

    def get_refractive_index(self):
        """屈折率を取得"""
        try:
            n = float(self.refr_input.text())
            if n <= 0:
                self.print(f"屈折率が不正: {n}")
                return 1.0
            self.print(f"屈折率: {n}")
            return n
        except Exception as e:
            self.print(f"屈折率取得エラー: {e}")
            return 1.0

    def get_light_speed(self):
        """媒質中の光速を取得"""
        n = self.get_refractive_index()
        c = self.c0 / n
        self.print(f"光速: {c:.3e} m/s (n={n})")
        return c

    def get_frequency_in_hz(self):
        """周波数をHz単位で取得"""
        try:
            text = self.freq_input.text()
            if not text:
                return None
            value = float(text)
            unit = self.freq_unit.currentText()
            multipliers = {'Hz': 1, 'kHz': 1e3, 'MHz': 1e6, 'GHz': 1e9, 'THz': 1e12}
            result = value * multipliers[unit]
            self.print(f"周波数入力: {value} {unit} = {result:.3e} Hz")
            return result
        except Exception as e:
            self.print(f"周波数取得エラー: {e}")
            return None

    def get_wavelength_in_m(self):
        """波長をm単位で取得"""
        try:
            text = self.wave_input.text()
            if not text:
                return None
            value = float(text)
            unit = self.wave_unit.currentText()
            multipliers = {'m': 1, 'mm': 1e-3, 'μm': 1e-6, 'nm': 1e-9}
            result = value * multipliers[unit]
            self.print(f"波長入力: {value} {unit} = {result:.3e} m")
            return result
        except Exception as e:
            self.print(f"波長取得エラー: {e}")
            return None

    def get_wavenumber_in_m_inv(self):
        """波数をm⁻¹単位で取得"""
        try:
            text = self.wavenum_input.text()
            if not text:
                return None
            value = float(text)
            unit = self.wavenum_unit.currentText()
            multipliers = {'m⁻¹': 1, 'cm⁻¹': 1e2}
            result = value * multipliers[unit]
            self.print(f"波数入力: {value} {unit} = {result:.3e} m⁻¹")
            return result
        except Exception as e:
            self.print(f"波数取得エラー: {e}")
            return None

    def set_frequency(self, freq_hz):
        """周波数を適切な単位で設定"""
        if freq_hz is None:
            return
        unit = self.freq_unit.currentText()
        divisors = {'Hz': 1, 'kHz': 1e3, 'MHz': 1e6, 'GHz': 1e9, 'THz': 1e12}
        value = freq_hz / divisors[unit]
        text = f'{value:.6g}'
        self.print(f"周波数設定: {freq_hz:.3e} Hz = {text} {unit}")
        # 一時的にシグナルを切断して設定
        self.freq_input.blockSignals(True)
        self.freq_input.setText(text)
        self.freq_input.blockSignals(False)

    def set_wavelength(self, wave_m):
        """波長を適切な単位で設定"""
        if wave_m is None:
            return
        unit = self.wave_unit.currentText()
        divisors = {'m': 1, 'mm': 1e-3, 'μm': 1e-6, 'nm': 1e-9}
        value = wave_m / divisors[unit]
        text = f'{value:.6g}'
        self.print(f"波長設定: {wave_m:.3e} m = {text} {unit}")
        # 一時的にシグナルを切断して設定
        self.wave_input.blockSignals(True)
        self.wave_input.setText(text)
        self.wave_input.blockSignals(False)

    def set_wavenumber(self, wavenum_m_inv):
        """波数を適切な単位で設定"""
        if wavenum_m_inv is None:
            return
        unit = self.wavenum_unit.currentText()
        divisors = {'m⁻¹': 1, 'cm⁻¹': 1e2}
        value = wavenum_m_inv / divisors[unit]
        text = f'{value:.6g}'
        self.print(f"波数設定: {wavenum_m_inv:.3e} m⁻¹ = {text} {unit}")
        # 一時的にシグナルを切断して設定
        self.wavenum_input.blockSignals(True)
        self.wavenum_input.setText(text)
        self.wavenum_input.blockSignals(False)

    def calculate_from_frequency(self):
        """周波数から波長と波数を計算"""
        self.print("\n=== 周波数からの計算開始 ===")
        if self.updating:
            self.print("更新中のためスキップ")
            return
        freq_hz = self.get_frequency_in_hz()
        if freq_hz is None or freq_hz <= 0:
            self.print(f"無効な周波数: {freq_hz}")
            return

        self.updating = True
        try:
            c = self.get_light_speed()
            # 波長の計算: λ = c/ν
            wave_m = c / freq_hz
            self.print(f"計算: 波長 = {c:.3e} / {freq_hz:.3e} = {wave_m:.3e} m")

            # 波数の計算: k = ν/c = 1/λ
            wavenum_m_inv = freq_hz / c
            self.print(f"計算: 波数 = {freq_hz:.3e} / {c:.3e} = {wavenum_m_inv:.3e} m⁻¹")

            # 内部状態を更新
            self.current_freq_hz = freq_hz
            self.current_wave_m = wave_m
            self.current_wavenum_m_inv = wavenum_m_inv

            # updatingフラグを一旦解除して値を設定
            self.updating = False
            self.set_wavelength(wave_m)
            self.set_wavenumber(wavenum_m_inv)

        except Exception as e:
            self.print(f"計算エラー: {e}")
            self.updating = False
        finally:
            self.print("=== 計算完了 ===\n")

    def calculate_from_wavelength(self):
        """波長から周波数と波数を計算"""
        self.print("\n=== 波長からの計算開始 ===")
        if self.updating:
            self.print("更新中のためスキップ")
            return
        wave_m = self.get_wavelength_in_m()
        if wave_m is None or wave_m <= 0:
            self.print(f"無効な波長: {wave_m}")
            return

        self.updating = True
        try:
            c = self.get_light_speed()
            # 周波数の計算: ν = c/λ
            freq_hz = c / wave_m
            self.print(f"計算: 周波数 = {c:.3e} / {wave_m:.3e} = {freq_hz:.3e} Hz")

            # 波数の計算: k = 1/λ
            wavenum_m_inv = 1 / wave_m
            self.print(f"計算: 波数 = 1 / {wave_m:.3e} = {wavenum_m_inv:.3e} m⁻¹")

            # 内部状態を更新
            self.current_freq_hz = freq_hz
            self.current_wave_m = wave_m
            self.current_wavenum_m_inv = wavenum_m_inv

            # updatingフラグを一旦解除して値を設定
            self.updating = False
            self.set_frequency(freq_hz)
            self.set_wavenumber(wavenum_m_inv)

        except Exception as e:
            self.print(f"計算エラー: {e}")
            self.updating = False
        finally:
            self.print("=== 計算完了 ===\n")

    def calculate_from_wavenumber(self):
        """波数から周波数と波長を計算"""
        self.print("\n=== 波数からの計算開始 ===")
        if self.updating:
            self.print("更新中のためスキップ")
            return
        wavenum_m_inv = self.get_wavenumber_in_m_inv()
        if wavenum_m_inv is None or wavenum_m_inv <= 0:
            self.print(f"無効な波数: {wavenum_m_inv}")
            return

        self.updating = True
        try:
            c = self.get_light_speed()
            # 波長の計算: λ = 1/k
            wave_m = 1 / wavenum_m_inv
            self.print(f"計算: 波長 = 1 / {wavenum_m_inv:.3e} = {wave_m:.3e} m")

            # 周波数の計算: ν = c*k
            freq_hz = c * wavenum_m_inv
            self.print(f"計算: 周波数 = {c:.3e} * {wavenum_m_inv:.3e} = {freq_hz:.3e} Hz")

            # 内部状態を更新
            self.current_freq_hz = freq_hz
            self.current_wave_m = wave_m
            self.current_wavenum_m_inv = wavenum_m_inv

            # updatingフラグを一旦解除して値を設定
            self.updating = False
            self.set_wavelength(wave_m)
            self.set_frequency(freq_hz)

        except Exception as e:
            self.print(f"計算エラー: {e}")
            self.updating = False
        finally:
            self.print("=== 計算完了 ===\n")

    def recalculate_all(self):
        """全ての値を再計算（屈折率変更時に使用）"""
        self.print("\n=== 全体再計算開始 ===")
        if self.updating:
            self.print("更新中のためスキップ")
            return

        # 最後に有効だった値から再計算
        if self.current_freq_hz is not None:
            self.print("周波数から再計算")
            self.calculate_from_frequency()
        elif self.current_wave_m is not None:
            self.print("波長から再計算")
            self.calculate_from_wavelength()
        elif self.current_wavenum_m_inv is not None:
            self.print("波数から再計算")
            self.calculate_from_wavenumber()
        self.print("=== 全体再計算完了 ===\n")

    # イベントハンドラ
    def on_freq_text_changed(self):
        self.print(f"周波数テキスト変更: '{self.freq_input.text()}'")
        if not self.updating and self.freq_input.text():
            self.calculate_from_frequency()

    def on_wave_text_changed(self):
        self.print(f"波長テキスト変更: '{self.wave_input.text()}'")
        if not self.updating and self.wave_input.text():
            self.calculate_from_wavelength()

    def on_wavenum_text_changed(self):
        self.print(f"波数テキスト変更: '{self.wavenum_input.text()}'")
        if not self.updating and self.wavenum_input.text():
            self.calculate_from_wavenumber()

    def on_freq_unit_changed(self):
        """周波数単位変更時：再計算せず、現在の値を新しい単位で表示"""
        self.print(f"周波数単位変更: {self.freq_unit.currentText()}")
        if self.current_freq_hz is not None and not self.updating:
            self.set_frequency(self.current_freq_hz)

    def on_wave_unit_changed(self):
        """波長単位変更時：再計算せず、現在の値を新しい単位で表示"""
        self.print(f"波長単位変更: {self.wave_unit.currentText()}")
        if self.current_wave_m is not None and not self.updating:
            self.set_wavelength(self.current_wave_m)

    def on_wavenum_unit_changed(self):
        """波数単位変更時：再計算せず、現在の値を新しい単位で表示"""
        self.print(f"波数単位変更: {self.wavenum_unit.currentText()}")
        if self.current_wavenum_m_inv is not None and not self.updating:
            self.set_wavenumber(self.current_wavenum_m_inv)

    def on_refr_changed(self):
        """屈折率が変更された時、保存されている値から再計算"""
        self.print(f"屈折率変更: {self.refr_input.text()}")
        if self.updating:
            return
        self.recalculate_all()


def main():
    debug = False
    if debug:
        print("アプリケーション起動")
    app = QApplication(sys.argv)
    converter = FrequencyWavelengthConverter(debug=debug)
    converter.show()
    if debug:
        print("ウィンドウ表示完了")
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Working USBTMC Class for Keysight Instruments
Ubuntu24で動作確認済み - PyVISA互換インターフェース
"""

import os
import glob
import time
from typing import List, Optional, Dict, Union
import serial
import serial.tools.list_ports

# PyVISA定数のインポート（あればインポート、なければ自作）
try:
    from pyvisa.constants import (
        StopBits as PyVISAStopBits,  # type: ignore
        Parity as PyVISAParity,  # type: ignore
        VI_ASRL_FLOW_NONE,
        VI_ASRL_FLOW_XON_XOFF,
        VI_ASRL_FLOW_RTS_CTS,
        VI_ASRL_FLOW_DTR_DSR
    )
    PYVISA_AVAILABLE = True
except ImportError:
    PYVISA_AVAILABLE = False
    # ダミー定義（後で自作クラスで上書き）
    class PyVISAParity:
        pass
    class PyVISAStopBits:
        pass

# 自作の定数クラス（PyVISAがない環境用）
class Parity:
    none = serial.PARITY_NONE
    odd = serial.PARITY_ODD
    even = serial.PARITY_EVEN
    mark = serial.PARITY_MARK
    space = serial.PARITY_SPACE

class StopBits:
    one = serial.STOPBITS_ONE
    one_point_five = serial.STOPBITS_ONE_POINT_FIVE
    two = serial.STOPBITS_TWO

class FlowControl:
    none = 0
    xon_xoff = 1
    rts_cts = 2
    dtr_dsr = 3

# PyVISAがない場合のフォールバック定数
if not PYVISA_AVAILABLE:
    VI_ASRL_FLOW_NONE = FlowControl.none
    VI_ASRL_FLOW_XON_XOFF = FlowControl.xon_xoff
    VI_ASRL_FLOW_RTS_CTS = FlowControl.rts_cts
    VI_ASRL_FLOW_DTR_DSR = FlowControl.dtr_dsr

# PyVISA定数 → pyserial定数の変換マッピング
if PYVISA_AVAILABLE:
    PARITY_MAP = {
        PyVISAParity.none: serial.PARITY_NONE,  # type: ignore
        PyVISAParity.odd: serial.PARITY_ODD,  # type: ignore
        PyVISAParity.even: serial.PARITY_EVEN,  # type: ignore
        PyVISAParity.mark: serial.PARITY_MARK,  # type: ignore
        PyVISAParity.space: serial.PARITY_SPACE,  # type: ignore
    }

    STOPBITS_MAP = {
        PyVISAStopBits.one: serial.STOPBITS_ONE,  # type: ignore
        PyVISAStopBits.two: serial.STOPBITS_TWO,  # type: ignore
    }

# 変換ヘルパー関数
def _to_serial_parity(value):
    """PyVISAまたは自作のParity定数をpyserial形式に変換"""
    if PYVISA_AVAILABLE and value in PARITY_MAP:
        return PARITY_MAP[value]
    return value  # すでにpyserial形式

def _to_serial_stopbits(value):
    """PyVISAまたは自作のStopBits定数をpyserial形式に変換"""
    if PYVISA_AVAILABLE and value in STOPBITS_MAP:
        return STOPBITS_MAP[value]
    return value  # すでにpyserial形式


class USBTMCResourceManager:
    """PyVISA互換のResourceManager"""

    def __init__(self):
        self._opened_resources = []  # 開いたリソースを追跡

    def list_resources(self) -> List[str]:
        """利用可能なリソースを一覧表示（PyVISA互換）"""
        resources = []

        # USBTMCデバイスを検索
        for device_path in glob.glob('/dev/usbtmc*'):
            if os.access(device_path, os.R_OK | os.W_OK):
                # 簡単な通信テストでデバイスを確認
                try:
                    idn = self._test_idn(device_path)
                    if idn:
                        # PyVISA風のリソース名を生成
                        visa_name = self._generate_visa_resource_name(device_path, idn)
                        resources.append(visa_name)
                except:
                    continue

        # シリアルデバイスを検索
        for _port in serial.tools.list_ports.comports():
            if _port.vid in [0x0403]:
                resources.append(f"ASRL{_port.device}::INSTR")

        return resources

    def _test_idn(self, device_path: str) -> Optional[str]:
        """デバイスでIDNテスト"""
        try:
            with open(device_path, 'wb', 0) as dev:
                dev.write(b'*IDN?\n')
                dev.flush()

            time.sleep(0.5)

            with open(device_path, 'rb', 0) as dev:
                response = dev.read(1024)
                if response:
                    return response.decode('utf-8', errors='ignore').strip()
        except:
            pass
        return None

    def _generate_visa_resource_name(self, device_path: str, idn: str) -> str:
        """IDN情報からVISAリソース名を生成"""
        try:
            parts = idn.split(',')
            if len(parts) >= 3:
                manufacturer = parts[0].strip()
                model = parts[1].strip()
                serial = parts[2].strip()

                # Keysight装置のVID/PIDマッピング
                device_map = {
                    'DAQ970A': 'USB0::0x2A8D::0x5001',
                    'E5071C': 'USB0::0x0957::0x0007',
                    'E36313A': 'USB0::0x0957::0x2818'
                }

                vid_pid = device_map.get(model, 'USB0::0x2A8D::0x5001')
                return f"{vid_pid}::{serial}::INSTR"
            else:
                # フォールバック
                return f"USB0::0x2A8D::0x5001::UNKNOWN::INSTR"
        except:
            return f"USB0::0x2A8D::0x5001::UNKNOWN::INSTR"

    def open_resource(self, resource_name: str, **kwargs) -> Union['USBTMCInstrument', 'SerialInstrument']:
        """リソースを開く（PyVISA互換）"""
        # シリアルデバイスの判定
        if resource_name.startswith('ASRL'):
            # ASRL/dev/ttyUSB0::INSTR から /dev/ttyUSB0 を抽出
            port = resource_name.split('::')[0].replace('ASRL', '')
            baudrate = kwargs.get('baud_rate', 9600)

            instrument = SerialInstrument(port, baudrate)
            if instrument.connect():
                instrument._resource_manager = self
                self._opened_resources.append(instrument)
                return instrument
            else:
                raise Exception(f"Failed to connect to {resource_name}")

        # リソース名から実際のデバイスパスを特定
        device_path = self._find_device_path_by_resource(resource_name)

        if device_path:
            instrument = USBTMCInstrument(device_path)
            if instrument.connect():
                # 開いたリソースを追跡
                instrument._resource_manager = self  # 親の参照を設定
                self._opened_resources.append(instrument)
                return instrument
            else:
                raise Exception(f"Failed to connect to {resource_name}")
        else:
            raise Exception(f"Resource {resource_name} not found")

    def _find_device_path_by_resource(self, resource_name: str) -> Optional[str]:
        """リソース名から実際のデバイスパスを検索"""
        # シリアル番号を抽出
        try:
            parts = resource_name.split('::')
            if len(parts) >= 4:
                target_serial = parts[3]

                # 全デバイスをチェック
                for device_path in glob.glob('/dev/usbtmc*'):
                    if os.access(device_path, os.R_OK | os.W_OK):
                        idn = self._test_idn(device_path)
                        if idn:
                            idn_parts = idn.split(',')
                            if len(idn_parts) >= 3:
                                serial = idn_parts[2].strip()
                                if serial == target_serial:
                                    return device_path
        except:
            pass

        # フォールバック: 最初に見つかったデバイスを返す
        for device_path in glob.glob('/dev/usbtmc*'):
            if os.access(device_path, os.R_OK | os.W_OK):
                return device_path

        return None

    def close(self):
        """ResourceManagerを閉じ、開いている全てのリソースを閉じる（PyVISA互換）"""
        # 開いている全てのリソースを閉じる
        for resource in self._opened_resources[:]:  # コピーを作成してイテレート
            try:
                resource.close()
            except:
                pass  # エラーが発生しても続行

        # リストをクリア
        self._opened_resources.clear()

        print(f"ResourceManager closed. All resources have been closed.")

    def __enter__(self):
        """コンテキストマネージャーサポート"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー終了時に自動クローズ"""
        self.close()

    def __del__(self):
        """デストラクタでリソースをクリーンアップ"""
        try:
            self.close()
        except:
            pass


class USBTMCInstrument:
    """PyVISA互換のInstrumentクラス"""

    def __init__(self, device_path: Optional[str] = None):
        self.device_path = device_path
        self.is_connected = False
        self._resource_manager: Optional[USBTMCResourceManager] = None  # 親のResourceManagerを追跡

        # PyVISA互換属性
        self.timeout = 5000  # ms
        self.read_termination = '\n'
        self.write_termination = '\n'

    def connect(self) -> bool:
        """デバイスに接続"""
        if self.device_path is None:
            # 自動検索
            devices = self._find_devices()
            if not devices:
                return False
            self.device_path = devices[0]

        if not os.path.exists(self.device_path):
            return False

        if not os.access(self.device_path, os.R_OK | os.W_OK):
            return False

        # 接続テスト
        idn = self._test_idn()
        if idn:
            self.is_connected = True
            return True
        return False

    def _find_devices(self) -> List[str]:
        """利用可能なデバイスパスを検索"""
        devices = []
        for device_path in glob.glob('/dev/usbtmc*'):
            if os.access(device_path, os.R_OK | os.W_OK):
                devices.append(device_path)
        return devices

    def _test_idn(self) -> Optional[str]:
        """IDNテスト"""
        assert self.device_path is not None
        try:
            with open(self.device_path, 'wb', 0) as dev:
                dev.write(b'*IDN?\n')
                dev.flush()

            time.sleep(0.5)

            with open(self.device_path, 'rb', 0) as dev:
                response = dev.read(1024)
                if response:
                    return response.decode('utf-8', errors='ignore').strip()
        except:
            pass
        return None

    # PyVISA互換メソッド
    def write(self, command: str) -> int:
        """コマンド送信（PyVISA互換）"""
        if not self.is_connected:
            raise Exception("Not connected to any device")
        assert self.device_path is not None

        try:
            if not command.endswith(self.write_termination):
                command += self.write_termination

            with open(self.device_path, 'wb', 0) as dev:
                data = command.encode('utf-8')
                dev.write(data)
                dev.flush()
            return len(data)
        except Exception as e:
            raise Exception(f"Write error: {e}")

    def read(self, max_bytes: int = 1024) -> str:
        """応答読み取り（PyVISA互換）"""
        if not self.is_connected:
            raise Exception("Not connected to any device")
        assert self.device_path is not None

        try:
            with open(self.device_path, 'rb', 0) as dev:
                response = dev.read(max_bytes)
                if response:
                    decoded = response.decode('utf-8', errors='ignore').strip()
                    # read_terminationを除去
                    if self.read_termination and decoded.endswith(self.read_termination):
                        decoded = decoded[:-len(self.read_termination)]
                    return decoded
        except Exception as e:
            raise Exception(f"Read error: {e}")
        return ""

    def query(self, command: str, delay: float = 0.1) -> str:
        """コマンド送信して応答を読み取り（PyVISA互換）"""
        self.write(command)
        time.sleep(delay)
        return self.read()

    def close(self):
        """接続を閉じる（PyVISA互換）"""
        if self.is_connected:
            self.is_connected = False

            # ResourceManagerから自分を削除
            if self._resource_manager and self in self._resource_manager._opened_resources:
                self._resource_manager._opened_resources.remove(self)

            print(f"Closed connection to {self.device_path}")

    # コンテキストマネージャーサポート
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # 便利メソッド（元のUSBTMCクラス互換）
    def get_idn(self) -> str:
        """デバイス識別情報を取得"""
        return self.query("*IDN?")

    def get_error(self) -> str:
        """システムエラーを取得"""
        return self.query(":SYST:ERR?")

    def reset(self) -> int:
        """デバイスリセット"""
        return self.write("*RST")

    def clear(self) -> int:
        """エラーキューをクリア"""
        return self.write("*CLS")


class SerialInstrument:
    """PyVISA互換のシリアル通信クラス"""

    def __init__(self, port: str, baudrate: int = 9600):
        self.port = port
        self._baudrate = baudrate
        self._data_bits = 8
        self._parity = Parity.none
        self._stop_bits = StopBits.one
        self._flow_control = FlowControl.none
        self._timeout = 5000

        self.ser = None
        self.is_connected = False
        self._resource_manager: Optional["USBTMCResourceManager"] = None

        self.read_termination = '\n'
        self.write_termination = '\n'

    # PyVISA互換プロパティ（すべて実装）
    @property
    def baud_rate(self):
        return self._baudrate

    @baud_rate.setter
    def baud_rate(self, value):
        self._baudrate = value
        if self.ser:
            self.ser.baudrate = value

    @property
    def data_bits(self):
        return self._data_bits

    @data_bits.setter
    def data_bits(self, value):
        self._data_bits = value
        if self.ser:
            self.ser.bytesize = value

    @property
    def parity(self):
        return self._parity

    @parity.setter
    def parity(self, value):
        self._parity = value
        if self.ser:
            self.ser.parity = _to_serial_parity(value)

    @property
    def stop_bits(self):
        return self._stop_bits

    @stop_bits.setter
    def stop_bits(self, value):
        self._stop_bits = value
        if self.ser:
            self.ser.stopbits = _to_serial_stopbits(value)

    @property
    def flow_control(self):
        return self._flow_control

    @flow_control.setter
    def flow_control(self, value):
        self._flow_control = value
        if self.ser:
            if value == FlowControl.rts_cts or value == VI_ASRL_FLOW_RTS_CTS:
                self.ser.rtscts = True
                self.ser.dsrdtr = False
                self.ser.xonxoff = False
            elif value == FlowControl.dtr_dsr or value == VI_ASRL_FLOW_DTR_DSR:
                self.ser.dsrdtr = True
                self.ser.rtscts = False
                self.ser.xonxoff = False
            elif value == FlowControl.xon_xoff or value == VI_ASRL_FLOW_XON_XOFF:
                self.ser.xonxoff = True
                self.ser.rtscts = False
                self.ser.dsrdtr = False
            else:  # none
                self.ser.rtscts = False
                self.ser.dsrdtr = False
                self.ser.xonxoff = False

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        self._timeout = value
        if self.ser:
            self.ser.timeout = value / 1000.0  # ms → sec

    def connect(self) -> bool:
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self._baudrate,
                timeout=self._timeout / 1000.0,
                bytesize=self._data_bits,
                parity=_to_serial_parity(self._parity),  # ← 変換
                stopbits=_to_serial_stopbits(self._stop_bits)  # ← 変換
            )
            self.flow_control = self._flow_control
            self.is_connected = True
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def write(self, command: str) -> int:
        if not self.ser:
            raise Exception("Serial port not initialized")
        if not self.is_connected:
            raise Exception("Not connected")
        if not command.endswith(self.write_termination):
            command += self.write_termination
        data = command.encode('utf-8')
        self.ser.write(data)
        return len(data)

    def read(self, max_bytes: int = 1024) -> str:
        if not self.ser:
            raise Exception("Serial port not initialized")
        if not self.is_connected:
            raise Exception("Not connected")

        try:
            if self.read_termination:
                # ターミネーター文字まで読む（これが速い！）
                response = self.ser.read_until(
                    expected=self.read_termination.encode('utf-8'),
                    size=max_bytes
                ).decode('utf-8', errors='ignore').strip()

                # ターミネーター文字を除去
                if response.endswith(self.read_termination):
                    response = response[:-len(self.read_termination)]
                return response
            else:
                # ターミネーター指定なしの場合は従来通り
                response = self.ser.read(max_bytes).decode('utf-8', errors='ignore').strip()
                return response
        except Exception as e:
            raise Exception(f"Read error: {e}")

    def query(self, command: str, delay: float = 0.1) -> str:
        self.write(command)
        time.sleep(delay)
        return self.read()

    def close(self):
        if self.is_connected and self.ser:
            self.ser.close()
            self.is_connected = False
            if self._resource_manager and self in self._resource_manager._opened_resources:
                self._resource_manager._opened_resources.remove(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# PyVISA互換のファクトリ関数
def ResourceManager() -> USBTMCResourceManager:
    """PyVISA互換のResourceManager作成"""
    return USBTMCResourceManager()


# 使用例とテスト
def test_serial():
    # PyVISA風の使用方法 - with文でResourceManagerも自動クローズ
    with ResourceManager() as rm:

        # リソース一覧
        resources = rm.list_resources()
        print(f"Available resources: {resources}")

        if resources:
            # 最初のリソースに接続
            resource_name = resources[0]
            print(f"Connecting to: {resource_name}")

            # with文での使用（PyVISA互換）
            with rm.open_resource(resource_name) as instrument:
                if isinstance(instrument, USBTMCInstrument):
                    return  # USBTMCInstrumentなら終了

                # PyVISA風に属性で設定
                instrument.baud_rate = 38400
                instrument.data_bits = 8
                instrument.parity = Parity.none
                instrument.stop_bits = StopBits.one
                instrument.flow_control = VI_ASRL_FLOW_RTS_CTS
                instrument.timeout = 5000  # ms
                instrument.read_termination = '\r\n'
                instrument.write_termination = '\r\n'

                print("IDN:", instrument.query("?:N"))


def test_usbtmc():
    print("=== PyVISA Compatible USBTMC Test ===")

    # PyVISA風の使用方法 - with文でResourceManagerも自動クローズ
    with ResourceManager() as rm:

        # リソース一覧
        resources = rm.list_resources()
        print(f"Available resources: {resources}")

        if resources:
            # 最初のリソースに接続
            resource_name = resources[0]
            print(f"Connecting to: {resource_name}")

            # with文での使用（PyVISA互換）
            with rm.open_resource(resource_name) as instrument:

                # 基本情報取得
                idn = instrument.query("*IDN?")
                print(f"Device Info: {idn}")

                # DAQ970A用コマンド例
                print("\n=== DAQ970A Commands ===")

                # チャンネル設定
                instrument.write("CONF:VOLT:DC 10,0.001,(@101)")
                print("Configured channel 101 for DC voltage")

                # 測定実行
                measurement = instrument.query("READ?")
                print(f"Measurement: {measurement}")

                # エラーチェック
                error = instrument.query(":SYST:ERR?")
                print(f"System Error: {error}")

            # instrumentは自動的に閉じられる
            print("Instrument automatically closed")

        else:
            print("No resources found")
            print("\nTroubleshooting:")
            print("1. Check device connection")
            print("2. Fix permissions: sudo chmod 666 /dev/usbtmc*")

    # ResourceManagerも自動的に閉じられ、全てのリソースがクリーンアップされる
    print("ResourceManager automatically closed")

# 使用例とテスト
if __name__ == "__main__":
    test_serial()
    # test_usbtmc()

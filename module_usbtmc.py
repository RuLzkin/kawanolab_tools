#!/usr/bin/env python3
"""
Working USBTMC Class for Keysight Instruments
Ubuntu24で動作確認済み - PyVISA互換インターフェース
"""

import os
import glob
import time
from typing import List, Optional, Dict


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
    
    def open_resource(self, resource_name: str, **kwargs) -> 'USBTMCInstrument':
        """リソースを開く（PyVISA互換）"""
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


# PyVISA互換のファクトリ関数
def ResourceManager() -> USBTMCResourceManager:
    """PyVISA互換のResourceManager作成"""
    return USBTMCResourceManager()


# 使用例とテスト
if __name__ == "__main__":
    """PyVISA互換の使用例"""
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
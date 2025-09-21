import os
import sys
from typing import Optional, List
from abc import ABC, abstractmethod

current_file_path = os.path.abspath(__file__)
current_file_dir = os.path.dirname(current_file_path)

sys.path.append(current_file_dir)

class I2CDevice(ABC):
    """i2c通讯芯片抽象类"""
    @abstractmethod
    def __init__(self, dll_path: str, baudrate: int = 100000):
        """
        初始化i2c设备

        Args:
            dll_path: dll文件路径
            baudrate: i2c通讯速率，默认100000Hz
        """
        pass

    @abstractmethod
    def __del__(self):
        """
        析构函数，关闭设备
        """
        pass

    @abstractmethod
    def is_open(self) -> bool:
        """检查设备是否已打开"""
        pass

    @abstractmethod
    def scan_devices(self) -> List[int]:
        """扫描i2c总线上的设备地址"""
        pass

    @abstractmethod
    def write(self, address: int, register: int, data: List[int]) -> bool:
        """
        多字节写入

        Args:
            address: 设备地址
            register: 寄存器地址
            data: 要写入的数据列表

        Returns:
            是否写入成功
        """
        pass

    @abstractmethod
    def read(self, address: int, register: int, length: int, fast_read: bool = False) -> Optional[List[int]]:
        """
        多字节读取

        Args:
            address: 设备地址
            register: 寄存器地址
            length: 要读取的数据长度
            fast_read: 是否使用快速读取模式，默认False

        Returns:
            读取的数据列表，失败返回None
        """
        pass

    @property
    @abstractmethod
    def supported_gpios(self) -> List[str]:
        """获取支持的GPIO口列表"""
        pass

    @abstractmethod
    def init_gpio(self, gpio_name: str, direction: str, mode: Optional[str] = None, pull: Optional[str] = None) -> bool:
        """
        初始化GPIO口

        Args:
            gpio_name: GPIO口名称
            direction: 方向，'in'或'out'
            mode: 推挽/开漏，'pp'、'od'或None
            pull: 上拉/下拉，'up'、'down'或None

        Returns:
            是否初始化成功
        """
        pass

    @abstractmethod
    def set_gpio_output(self, gpio_name: str, state: bool) -> bool:
        """
        设置GPIO口输出状态

        Args:
            gpio_name: GPIO口名称
            state: 输出状态，True为高电平，False为低电平

        Returns:
            是否设置成功
        """
        pass

    @abstractmethod
    def get_gpio_input(self, gpio_name: str) -> Optional[bool]:
        """
        获取GPIO口输入状态

        Args:
            gpio_name: GPIO口名称

        Returns:
            输入状态，True为高电平，False为低电平，失败返回None
        """
        pass


class I2CAdapter:
    """i2c通讯芯片适配工厂类"""

    @staticmethod
    def get_supported_chips() -> list:
        """
        获取支持的i2c通讯芯片列表

        Returns:
            支持的芯片名称列表
        """
        return ['ch341', 'cp2112']

    @staticmethod
    def create_device(chip_name: str, baudrate: int = 100000) -> Optional[I2CDevice]:
        """
        根据芯片名称创建对应的i2c_device

        Args:
            chip_name: 芯片名称
            baudrate: i2c通讯速率，默认100000Hz

        Returns:
            创建的i2c_device实例，不支持的芯片返回None
        """
        # 转换为小写以实现大小写不敏感
        chip_name = chip_name.lower()

        # 检查芯片是否支持
        if chip_name not in I2CAdapter.get_supported_chips():
            return None

        # 根据不同芯片实现不同的子类
        if chip_name == 'ch341':
            # 假设存在CH341Device类
            try:
                from src.i2c_tools.ch341_device import CH341Device
                return CH341Device(baudrate)
            except ImportError:
                print("CH341Device类未找到，请确保已实现该类。")
                return None
        elif chip_name == 'cp2112':
            # 假设存在CP2112Device类
            try:
                from cp2112_device import CP2112Device
                return CP2112Device(baudrate)
            except ImportError:
                print("CP2112Device类未找到，请确保已实现该类。")
                return None

        return None

if __name__ == '__main__':
    # 测试代码
    device = I2CAdapter.create_device('ch341', 1000000)
    if device.is_open():
        print("i2c设备初始化成功")
    else:
        print("i2c设备初始化失败")

from abc import ABC, abstractmethod
from typing import List, Optional
import ctypes
from ctypes import wintypes, Structure, Union, POINTER, byref, c_uint8, c_uint16, c_uint32, c_ulong, c_char_p, c_void_p
import time
import sys
import os

current_file_path = os.path.abspath(__file__)
current_file_dir = os.path.dirname(current_file_path)

sys.path.append(current_file_dir)
from i2c_adapter import I2CDevice


"""
提示词：
请根据i2c_device.py文件中的I2CDevice类，实现CH341Device类。

更新提示词：
增加测试代码，测试CH341Device类的功能。
"""


class CH341Device(I2CDevice):
    """CH341系列i2c通讯芯片的实现类"""

    IC_VER_CH341 = 0x10
    IC_VER_CH341T = 0x18
    IC_VER_CH341A = 0x20
    IC_VER_CH341B = 0x32

    # I2C速度
    I2C_LOW_SPEED = 0x00        # 20KHz
    I2C_STANDARD_SPEED = 0x01   # 100KHz
    I2C_FAST_SPEED = 0x02       # 400KHz
    I2C_HIGH_SPEED = 0x03       # 750KHz

    # 状态位定义
    STATE_BIT_ERR = 0x00000100      # ERR#引脚
    STATE_BIT_PEMP = 0x00000200     # PEMP引脚
    STATE_BIT_INT = 0x00000400      # INT#引脚
    STATE_BIT_SLCT = 0x00000800     # SLCT引脚
    STATE_BIT_WAIT = 0x00002000     # WAIT#引脚
    STATE_BIT_DATAS = 0x00004000    # DATAS#引脚
    STATE_BIT_ADDRS = 0x00008000    # ADDRS#引脚
    STATE_BIT_RESET = 0x00010000    # RESET#引脚
    STATE_BIT_WRITE = 0x00020000    # WRITE#引脚
    STATE_BIT_SCL = 0x00400000      # SCL引脚
    STATE_BIT_SDA = 0x00800000      # SDA引脚

    def __init__(self, baudrate: int = 100000):
        """
        初始化CH341设备

        Args:
            i2c_address: i2c设备地址
            baudrate: i2c通讯速率，默认100000Hz
        """
        self.baudrate = baudrate
        self.device_handle = None
        self._supported_gpios = {'GPIO0': 8, 'GPIO1': 9}
        self.gpio_dir_mask = 0x000FC000 # default direction mask
        self.gpio_data_mask = None # default data mask
        self.reg_pointer = None

        # 加载dll文件
        try:
            self._dll = ctypes.WinDLL(os.path.join(current_file_dir, "CH341DLLA64.DLL"))
            # self._dll = ctypes.windll.LoadLibrary("CH341DLLA64.DLL")

            # 基础设备操作
            self._dll.CH341OpenDevice.argtypes = [c_uint32]
            self._dll.CH341OpenDevice.restype = wintypes.HANDLE

            self._dll.CH341CloseDevice.argtypes = [c_uint32]
            self._dll.CH341CloseDevice.restype = None

            self._dll.CH341GetVersion.argtypes = []
            self._dll.CH341GetVersion.restype = c_uint32

            self._dll.CH341GetDrvVersion.argtypes = []
            self._dll.CH341GetDrvVersion.restype = c_uint32

            self._dll.CH341ResetDevice.argtypes = [c_uint32]
            self._dll.CH341ResetDevice.restype = wintypes.BOOL

            self._dll.CH341GetVerIC.argtypes = [c_uint32]
            self._dll.CH341GetVerIC.restype = c_uint32

            self._dll.CH341GetDeviceName.argtypes = [c_uint32]
            self._dll.CH341GetDeviceName.restype = c_char_p

            self._dll.CH341FlushBuffer.argtypes = [c_uint32]
            self._dll.CH341FlushBuffer.restype = wintypes.BOOL

            # I2C操作
            self._dll.CH341ReadI2C.argtypes = [c_uint32, c_uint8, c_uint8, POINTER(c_uint8)]
            self._dll.CH341ReadI2C.restype = wintypes.BOOL

            self._dll.CH341WriteI2C.argtypes = [c_uint32, c_uint8, c_uint8, c_uint8]
            self._dll.CH341WriteI2C.restype = wintypes.BOOL

            self._dll.CH341SetStream.argtypes = [c_uint32, c_uint32]
            self._dll.CH341SetStream.restype = wintypes.BOOL

            self._dll.CH341StreamI2C.argtypes = [c_uint32, c_uint32, c_void_p, c_uint32, c_void_p]
            self._dll.CH341StreamI2C.restype = wintypes.BOOL

            self._dll.CH341SetDelaymS.argtypes = [c_uint32, c_uint32]
            self._dll.CH341SetDelaymS.restype = wintypes.BOOL
        except Exception as e:
            print(f"加载dll文件失败: {e}")
            raise

        self._init_device()

    def is_open(self) -> bool:
        """检查设备是否已打开"""
        return self.device_handle is not None

    def __del__(self):
        """析构函数，关闭设备"""
        if self.is_open():
            self._dll.CH341CloseDevice(self.device_handle)
            self.device_handle = None

    def _init_device(self, device_index = 0, skip_scan = True):
        """初始化CH341设备"""
        try:
            # 打开设备
            self.device_handle = self._dll.CH341OpenDevice(device_index)
            if not self._dll.CH341ResetDevice(self.device_handle):
                self.device_handle = None
                raise Exception("打开CH341设备失败")

            print("Device opened successfully")

            # 获取芯片版本
            version = self._dll.CH341GetVerIC(device_index)
            print(f"Chip Version: 0x{version:X}")
            
            if version == self.IC_VER_CH341B:
                self._supported_gpios['GPIO2'] = 0
                self._supported_gpios['GPIO3'] = 1
                self._supported_gpios['GPIO4'] = 2
                self._supported_gpios['GPIO5'] = 3
                self._supported_gpios['GPIO6'] = 5
                self._supported_gpios['GPIO7'] = 7

            # 获取设备名称
            device_name = "Unkown"
            name_ptr = self._dll.CH341GetDeviceName(device_index)
            if name_ptr:
                device_name = name_ptr.decode('gbk', errors='ignore')
                # device_name = name_ptr.decode('utf-8', errors='ignore')
            print(f"Device Name: {device_name}")

            # 设置I2C模式
            if bool(self._dll.CH341SetStream(device_index, self.I2C_STANDARD_SPEED)):
                print("I2C mode set successfully")

                # 扫描I2C设备
                if not skip_scan:
                    print("Scanning I2C devices...")
                    devices = self.scan_devices()
                    if devices:
                        print(f"Found I2C devices: {[f'0x{addr:02X}' for addr in devices]}")
                    else:
                        print("No I2C devices found")

            # 使能 P8/P9 引脚为输出状态并配置默认输出低电平
            # if self._set_output(0x2, 0xC3 << 8, 0x0):
            #     UtilLog.i("Config P8/P9 output mode fail")
            self.gpio_data_mask = self._get_input()
            print(f"GPIO data mask: {self.gpio_data_mask:X}")

            # 获取设备状态
            status = self.get_status(device_index)
            if status:
                print(f"Device Status: {status}")

        except Exception as e:
            print(f"Error: {e}")

    def scan_devices(self) -> List[int]:
        """扫描i2c总线上的设备地址"""
        found: List[int] = []
        # Skip reserved addresses: 0x00-0x02 and 0x78-0x7F
        start_addr, end_addr = 0x03, 0x77
        for addr in range(start_addr, end_addr + 1):
            try:
                # Prefer a pure address read probe: START + (addr|R) + 1 byte + NACK + STOP
                # We require a non-None response of expected length.
                resp = self._stream(bytes([(addr << 1) | 0x01]), 1)
                # print(resp.hex())
                if resp.hex() != 'ff' and len(resp) == 1:
                    # Optional quick retry to reduce noise
                    resp2 = self._stream(bytes([(addr << 1) | 0x01]), 1)
                    if resp2 is not None and len(resp2) == 1:
                        found.append(addr)
            except Exception:
                # Ignore and continue scanning
                pass
            # Small inter-address delay can improve reliability on some buses
            time.sleep(0.001)

        return found

    def scan_eeproms(self) -> List[int]:
        """扫描i2c总线上的eeprom设备地址"""
        found: List[int] = []
        # 扫描i2c总线上的eeprom设备地址
        for addr in range(0x50, 0x58):
            try:
                # Prefer a pure address read probe: START + (addr|R) + 1 byte + NACK + STOP
                # We require a non-None response of expected length.
                resp = self._stream(bytes([(addr << 1) | 0x01]), 1)
                # print(resp.hex())
                if resp.hex() != 'ff' and len(resp) == 1:
                    # Optional quick retry to reduce noise
                    resp2 = self._stream(bytes([(addr << 1) | 0x01]), 1)
                    if resp2 is not None and len(resp2) == 1:
                        found.append(addr)
                else:
                    # 写入单字节数据
                    self._write_byte(addr, 0x00, 0xAA)
                    # 读取单字节数据
                    data = self._read_byte(addr, 0x00)
                    # print(data)
                    if data == 0xAA:
                        found.append(addr)
            except Exception:
                # Ignore and continue scanning
                pass
            # Small inter-address delay can improve reliability on some buses
            time.sleep(0.001)

        return found

    def get_status(self, device_index: int) -> int:
        """
        获取设备状态
        """
        status = ctypes.c_uint32()
        if self._dll.CH341GetStatus(device_index, byref(status)):
            return self._parse_status(status.value)
        return None

    def _parse_status(self, status: int) -> dict:
        """解析状态值"""
        return {
            'raw': status,
            'data_lines': status & 0xFF,
            'err_pin': bool(status & self.STATE_BIT_ERR),
            'pemp_pin': bool(status & self.STATE_BIT_PEMP),
            'int_pin': bool(status & self.STATE_BIT_INT),
            'slct_pin': bool(status & self.STATE_BIT_SLCT),
            'wait_pin': bool(status & self.STATE_BIT_WAIT),
            'datas_pin': bool(status & self.STATE_BIT_DATAS),
            'addrs_pin': bool(status & self.STATE_BIT_ADDRS),
            'reset_pin': bool(status & self.STATE_BIT_RESET),
            'write_pin': bool(status & self.STATE_BIT_WRITE),
            'scl_pin': bool(status & self.STATE_BIT_SCL),
            'sda_pin': bool(status & self.STATE_BIT_SDA),
        }

    def _write_byte(self, device_addr: int, reg_addr: int, value: int, device_index: int = 0) -> bool:
        """
        向I2C设备写入一个字节

        Args:
            device_addr: I2C设备地址
            reg_addr: 寄存器地址
            value: 要写入的值
            device_index: 设备序号

        Returns:
            bool: 成功返回True
        """
        return bool(self._dll.CH341WriteI2C(device_index, device_addr, reg_addr, value))

    def _read_byte(self, device_addr: int, reg_addr: int, device_index: int = 0) -> Optional[int]:
        """
        从I2C设备读取一个字节

        Args:
            device_addr: I2C设备地址
            reg_addr: 寄存器地址
            device_index: 设备序号

        Returns:
            Optional[int]: 读取的字节值，失败返回None
        """
        byte_value = c_uint8()
        if self._dll.CH341ReadI2C(device_index, device_addr, reg_addr, byref(byte_value)):
            return byte_value.value
        return None

    def _stream(self, write_data: bytes, read_length: int = 0, device_index: int = 0) -> Optional[bytes]:
        """
        I2C流操作

        Args:
            write_data: 要写入的数据
            read_length: 要读取的长度
            device_index: 设备序号

        Returns:
            Optional[bytes]: 读取的数据，失败返回None
        """
        write_length = len(write_data)
        write_buffer = (c_uint8 * write_length)(*write_data)

        if read_length > 0:
            read_buffer = (c_uint8 * read_length)()
        else:
            read_buffer = None

        if self._dll.CH341StreamI2C(device_index, write_length, write_buffer, read_length, read_buffer):
            if read_length > 0 and read_buffer:
                return bytes(read_buffer)
            return b''
        return None

    def _set_output(self, enable_mask: int, direction_mask: int, data_mask: int, device_index: int = 0) -> bool:
        """
        设置输出引脚

        Args:
            enable_mask: 使能掩码（bit0/bit1: b8-b15(data/dir) bit2/bit3: b0-b7(data/dir) bit4: b16-b23(data only)）
            direction_mask: 方向掩码（1=输出 0=输入）
            data_mask: 数据掩码（1=高 0=低）

        Returns:
            bool: 成功返回true
        """
        return bool(self._dll.CH341SetOutput(device_index, enable_mask, direction_mask, data_mask))

    def _get_input(self, device_index: int = 0) -> Optional[int]:
        """
        获取输入引脚状态

        Args:
            device_index: 设备序号

        Returns:
            Optional[int]: 状态掩码，失败返回None
        """
        status = c_uint32()
        if self._dll.CH341GetInput(device_index, byref(status)):
            return status.value
        return None

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
        try:
            write_buffer = bytes([(address << 1) | 0, register]) + bytes(data)
            status = self._stream(write_buffer, 0)
            # print(f"Write bytes to 0x{register:X}: [{','.join([f'0x{byte:02X}' for byte in data])}] ret: {status is b''}")
            self.reg_pointer = register
            return bool(status == b'')
        except Exception as e:
            print(f"多字节写入失败: {e}")
            return False

    def read(self, address: int, register: int, length: int, fast_read: bool = False) -> Optional[List[int]]:
        """
        多字节读取

        Args:
            address: 设备地址
            register: 寄存器地址
            length: 要读取的数据长度

        Returns:
            读取的数据列表，失败返回None
        """
        try:
            read_data = None
            write_buffer = bytes([(address << 1) | 1])

            if fast_read and register == self.reg_pointer:
                read_data = self._stream(write_buffer, length)
            else:
                if not self.write(address, register, []) is None:
                    read_data = self._stream(write_buffer, length)
                else:
                    self.reg_pointer = None
                    print(f"寄存器0x{register:X}写入失败")

            return list(read_data) if read_data else None
        except Exception as e:
            print(f"多字节读取失败: {e}")
            return None

    @property
    def supported_gpios(self) -> List[str]:
        """获取支持的GPIO口列表"""
        return list(self._supported_gpios.keys())

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
        # 获取GPIO索引
        if gpio_name not in self._supported_gpios:
            print(f"不支持的GPIO口: {gpio_name}")
            return False
        gpio_index = self._supported_gpios[gpio_name]

        if direction not in ['in', 'out']:
            print(f"无效的方向: {direction}")
            return False

        # CH341的GPIO没有内置推挽/开漏功能，这里忽略mode参数
        if mode is not None:
            print(f"警告: CH341的GPIO不支持推挽/开漏切换，忽略'{mode}'")

        # CH341的GPIO没有内置上拉/下拉功能，这里忽略pull参数
        if pull is not None:
            print(f"警告: CH341的GPIO不支持上拉/下拉切换，忽略'{pull}'")

        try:
            if gpio_index > 15:
                print(f"不支持修改 {gpio_name} 的方向")
                return False
            elif gpio_index > 7:
                enable_mask = 0x2
            else:
                enable_mask = 0x8

            direction_mask = self.gpio_dir_mask
            if direction == 'out':
                direction_mask |= (0x1 << gpio_index)
            elif direction == 'in':
                direction_mask &= ~(0x1 << gpio_index)

            if direction_mask == self.gpio_dir_mask:
                return True

            if not self._set_output(enable_mask, direction_mask, 0x0):
                print("Config P8/P9 output mode fail")
                return False

            self.gpio_dir_mask = direction_mask
            return True
        except Exception as e:
            print(f"初始化GPIO失败: {e}")
            return False

    def set_gpio_output(self, gpio_name: str, value: bool) -> bool:
        """
        设置GPIO输出值

        Args:
            gpio_name: GPIO口名称
            value: 输出值，True为高电平，False为低电平

        Returns:
            是否设置成功
        """
        # 获取GPIO索引
        if gpio_name not in self._supported_gpios:
            print(f"不支持的GPIO口: {gpio_name}")
            return False
        gpio_index = self._supported_gpios[gpio_name]

        if not self.gpio_dir_mask & (0x1 << gpio_index):
            print(f"GPIO口 {gpio_name} 未初始化为输出模式")

        try:
            if gpio_index > 23:
                print(f"未定义的GPIO口: {gpio_name}")
                return False
            elif gpio_index > 15:
                enable_mask = 0x10
            elif gpio_index > 7:
                enable_mask = 0x1
            else:
                enable_mask = 0x4

            data_mask = self._get_input()
            if value:
                data_mask |= (0x1 << gpio_index)
            else:
                data_mask &= ~(0x1 << gpio_index)

            # if data_mask == self.gpio_data_mask:
            #     print(f"GPIO{gpio_name} 未改变")
            #     return True

            # 设置GPIO输出
            if self._set_output(enable_mask, 0x0, data_mask):
                time.sleep(0.5)
                if self._get_input() == data_mask:
                    self.gpio_data_mask = data_mask
                    print(f"GPIO口 {gpio_name} 设置成功")
                    return True
            print(f"GPIO口 {gpio_name} 设置失败")
            return False
        except Exception as e:
            print(f"设置GPIO口 {gpio_name} 输出值失败: {e}")
            return False

    def get_gpio_input(self, gpio_name: str) -> Optional[bool]:
        """
        获取GPIO输入值

        Args:
            gpio_name: GPIO口名称

        Returns:
            输入值，True为高电平，False为低电平，失败返回None
        """
        if gpio_name not in self._supported_gpios:
            print(f"不支持的GPIO口: {gpio_name}")
            return None
        gpio_index = self._supported_gpios[gpio_name]

        # skip input check
        # if not self.gpio_dir_mask & (0x1 << gpio_index) == 0x0:
        #     print(f"GPIO口 {gpio_name} 未初始化为输入模式")
        #     return None

        try:
            # 读取GPIO输入
            input_value = self._get_input()
            if input_value is None:
                return None
            return (input_value & (0x1 << gpio_index)) != 0
        except Exception as e:
            print(f"读取GPIO输入值失败: {e}")
            return None

def gpio_ctrl_loop(device: I2CDevice):
    """GPIO控制循环"""
    states = {}
    gpios = device.supported_gpios

    for gpio in gpios:
        print(f"初始化 {gpio} 为输出")
        if not device.init_gpio(gpio, 'out'):
            print(f"初始化 {gpio} 失败")
            return
        states[gpio] = False

    def set_low():
        for gpio in gpios:
            device.set_gpio_output(gpio, False)
            states[gpio] = False
        print("GPIO0=0, GPIO1=0")

    def toggle(pin):
        id = gpios[pin]
        new_val = 0 if states[id] else 1
        states[id] = new_val
        device.set_gpio_output(f"GPIO{pin}", new_val)
        print(f"GPIO{pin}={new_val}")

    set_low()
    while True:
        try:
            cmd = input(f"输入指令 (0:init low, 1:toggle GPIO0, ... , {len(gpios)+1}:exit): ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd == '0':
            set_low()
        elif 1 <= int(cmd) <= len(gpios):
            toggle(int(cmd) - 1)
        elif cmd == f'{len(gpios) + 1}':
            print("退出")
            break
        else:
            print("无效指令")
        time.sleep(0.1)

def eeprom_test(device: I2CDevice):
    """EEPROM测试"""
    dev_addr = 0x50

    # # 写入单字节数据
    # device._write_byte(dev_addr, 0x10, 0xAA)
    # # 读取单字节数据
    # data = device._read_byte(dev_addr, 0x10)
    # print(f"读取到的数据: {hex(data)}") 

    # # 写入多字节数据
    # resp = device._stream(bytes([(dev_addr << 1) | 0x00, 0x10, 0xAA, 0xBB, 0xCC, 0xDD]), 0)
    # print(f"读取到的数据: {resp}")
    # time.sleep(0.01)
    # resp = device._stream(bytes([(dev_addr << 1) | 0x00, 0x10]), 4)
    # print(f"读取到的数据: {resp}")
    
    # 测试
    device.write(dev_addr, 0x10, [0xAA, 0xBB, 0xCC, 0xDD])
    time.sleep(0.01)
    data = device.read(dev_addr, 0x10, 4)
    print(f"读取到的数据: {[hex(n) for n in data]}")


if __name__ == '__main__':
    try:
        write_test = False
        loop_test = True

        dev_addr = 0x40
        # 初始化CH341Device
        device = CH341Device(baudrate=1000000)
        if not device.is_open():
            raise Exception("CH341设备初始化失败")

        print("CH341设备初始化成功")

        # 扫描设备
        print("扫描i2c设备...")
        devices = device.scan_devices()
        print(f"发现设备地址: {[hex(addr) for addr in devices]}")

        eeproms = device.scan_eeproms()
        print(f"发现rom地址: {[hex(addr) for addr in eeproms]}")

        # 测试I2C读写
        if write_test and dev_addr in devices:
            reg_addr = 0x00
            print(f"测试向地址 {hex(reg_addr)} 写入数据...")
            # 写入一个字节
            result = device.write(dev_addr, reg_addr, [0x39, 0x9F])
            print(f"写入结果: {result}")

            # 读取一个字节
            print("读取数据...")
            data = device.read(dev_addr, reg_addr, 2)
            print(f"读取结果: 0x{bytes(data).hex()} ({data})")
        else:
            print(f"设备 {hex(dev_addr)} 未找到，或设置为跳过读写测试")

        # 测试GPIO
        print("测试GPIO...")
        if loop_test:
            gpio_ctrl_loop(device)
        else:
            # 初始化GPIO0为输出
            result = device.init_gpio('GPIO0', 'out')
            print(f"初始化GPIO0为输出: {result}")

            # 设置GPIO0输出高电平
            result = device.set_gpio_output('GPIO0', True)
            print(f"设置GPIO0为高电平: {result}")
            time.sleep(1)

            # 设置GPIO0输出低电平
            result = device.set_gpio_output('GPIO0', False)
            print(f"设置GPIO0为低电平: {result}")

            # 初始化GPIO1为输入
            result = device.init_gpio('GPIO1', 'in')
            print(f"初始化GPIO1为输入: {result}")

            # 读取GPIO1输入值
            value = device.get_gpio_input('GPIO1')
            print(f"GPIO1输入值: {value}")

        del device
    except Exception as e:
        print(f"测试失败: {e}")
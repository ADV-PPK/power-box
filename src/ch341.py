"""
CH341 USB转I2C通信模块

该模块提供了与CH341芯片进行USB转I2C通信的接口，
支持I2C读写操作和GPIO控制功能。
"""

import ctypes
import os
import platform
import logging
import time
from typing import Optional, List, Union
from ctypes import wintypes, Structure, Union, POINTER, byref, c_uint8, c_uint16, c_uint32, c_ulong, c_char_p, c_void_p

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CH341Exception(Exception):
    """CH341相关异常"""
    pass


class CH341Device:
    """CH341设备控制类"""
    
    # CH341版本定义
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
    
    def __init__(self, device_index: int = 0):
        """
        初始化CH341设备
        
        Args:
            device_index: 设备索引，默认为0
        """
        self.device_index = device_index
        self._dll = None
        self.device_handle = None
        self.is_opened = False
        self._supported_gpios = {'GPIO0': 8, 'GPIO1': 9}
        self.gpio_dir_mask = 0x000FC000  # default direction mask
        self.gpio_data_mask = 0x00000000  # default data mask
        self.reg_pointer = None
        
        self._load_dll()
        # 不在初始化时自动打开设备，让调用者决定何时打开
        
    def _load_dll(self):
        """加载CH341 DLL库"""
        try:
            # 根据系统架构选择DLL
            if platform.architecture()[0] == '64bit':
                dll_name = "CH341DLLA64.DLL"
            else:
                dll_name = "CH341DLL.DLL"
            
            # 尝试从当前目录加载DLL
            current_dir = os.path.dirname(os.path.abspath(__file__))
            dll_path = os.path.join(current_dir, dll_name)
            
            if os.path.exists(dll_path):
                self._dll = ctypes.WinDLL(dll_path)
            else:
                # 尝试从系统PATH加载
                self._dll = ctypes.windll.LoadLibrary(dll_name)
                
            # 设置函数原型
            self._setup_dll_functions()
            logger.info(f"成功加载 {dll_name}")
            
        except Exception as e:
            logger.error(f"无法加载CH341 DLL库: {e}")
            raise CH341Exception(f"无法加载CH341 DLL库: {e}")
    
    def _setup_dll_functions(self):
        """设置DLL函数原型"""
        if not self._dll:
            return
            
        try:
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

            # GPIO操作 - 使用更精确的函数名
            try:
                self._dll.CH341SetOutput.argtypes = [c_uint32, c_uint32, c_uint32, c_uint32]
                self._dll.CH341SetOutput.restype = wintypes.BOOL

                self._dll.CH341GetInput.argtypes = [c_uint32, POINTER(c_uint32)]
                self._dll.CH341GetInput.restype = wintypes.BOOL

                self._dll.CH341GetStatus.argtypes = [c_uint32, POINTER(c_uint32)]
                self._dll.CH341GetStatus.restype = wintypes.BOOL
            except:
                # 某些版本的DLL可能没有这些函数
                pass
        except Exception as e:
            logger.warning(f"设置DLL函数原型时出现警告: {e}")
            
    def is_open(self) -> bool:
        """检查设备是否已打开"""
        return self.device_handle is not None
            
    def open(self, skip_scan: bool = True, silent: bool = False) -> bool:
        """
        打开CH341设备
        
        Args:
            skip_scan: 是否跳过I2C设备扫描
            silent: 静默模式，失败时不打印错误信息
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            if self.is_opened:
                return True
                
            if not self._dll:
                if not silent:
                    logger.error("CH341 DLL未正确加载")
                return False
                
            # 打开设备
            self.device_handle = self._dll.CH341OpenDevice(self.device_index)
            if not self._dll.CH341ResetDevice(self.device_handle):
                self.device_handle = None
                if not silent:
                    logger.error(f"无法打开CH341设备 {self.device_index}")
                return False
                
            logger.info("Device opened successfully")

            # 获取芯片版本
            version = self._dll.CH341GetVerIC(self.device_index)
            logger.info(f"Chip Version: 0x{version:X}")
            
            if version == self.IC_VER_CH341B:
                self._supported_gpios['GPIO2'] = 0
                self._supported_gpios['GPIO3'] = 1
                self._supported_gpios['GPIO4'] = 2
                self._supported_gpios['GPIO5'] = 3
                self._supported_gpios['GPIO6'] = 5
                self._supported_gpios['GPIO7'] = 7

            # 获取设备名称
            device_name = "Unknown"
            try:
                name_ptr = self._dll.CH341GetDeviceName(self.device_index)
                if name_ptr:
                    device_name = name_ptr.decode('gbk', errors='ignore')
                logger.info(f"Device Name: {device_name}")
            except:
                pass

            # 设置I2C模式
            if bool(self._dll.CH341SetStream(self.device_index, self.I2C_STANDARD_SPEED)):
                logger.info("I2C mode set successfully")
                
                # 扫描I2C设备
                if not skip_scan:
                    logger.info("Scanning I2C devices...")
                    devices = self.scan_i2c_devices()
                    if devices:
                        logger.info(f"Found I2C devices: {[f'0x{addr:02X}' for addr in devices]}")
                    else:
                        logger.info("No I2C devices found")
            else:
                logger.warning("设置I2C模式失败，但继续运行")

            # 获取GPIO初始状态
            self.gpio_data_mask = self._get_input() or 0x00000000
            logger.info(f"GPIO data mask: {self.gpio_data_mask:X}")

            # 获取设备状态
            status = self.get_status()
            if status:
                logger.info(f"Device Status: {status}")

            self.is_opened = True
            logger.info(f"成功打开CH341设备 {self.device_index}")
            return True
            
        except Exception as e:
            logger.error(f"打开设备失败: {e}")
            return False
            
    def _init_device(self):
        """初始化设备"""
        if not self.open():
            raise CH341Exception(f"无法打开CH341设备 {self.device_index}")
    
    def _get_input(self, device_index: Optional[int] = None) -> Optional[int]:
        """
        获取输入引脚状态

        Args:
            device_index: 设备序号

        Returns:
            Optional[int]: 状态掩码，失败返回None
        """
        if device_index is None:
            device_index = self.device_index
            
        if not self._dll:
            return None
            
        status = c_uint32()
        if self._dll.CH341GetInput(device_index, byref(status)):
            return status.value
        return None

    def _set_output(self, enable_mask: int, direction_mask: int, data_mask: int, device_index: Optional[int] = None) -> bool:
        """
        设置输出/方向寄存器封装，参数语义与 ch341_device.py 对齐

        Args:
            enable_mask: 使能掩码（bit0/bit1: b8-b15(data/dir) bit2/bit3: b0-b7(data/dir) bit4: b16-b23(data only)）
            direction_mask: 方向掩码（1=输出 0=输入）
            data_mask: 数据掩码（1=高 0=低）
            device_index: 设备序号

        Returns:
            bool: 设置成功
        """
        if device_index is None:
            device_index = self.device_index
        if not self._dll:
            return False
        return bool(self._dll.CH341SetOutput(device_index, enable_mask, direction_mask, data_mask))

    def get_status(self, device_index: Optional[int] = None) -> Optional[dict]:
        """
        获取设备状态
        """
        if device_index is None:
            device_index = self.device_index
            
        if not self._dll:
            return None
            
        status = c_uint32()
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
    
    def _stream(self, write_data: bytes, read_length: int = 0) -> Optional[bytes]:
        """
        I2C流操作

        Args:
            write_data: 要写入的数据
            read_length: 要读取的长度

        Returns:
            Optional[bytes]: 读取的数据，失败返回None
        """
        if not self._dll:
            return None
            
        write_length = len(write_data)
        write_buffer = (c_uint8 * write_length)(*write_data)

        if read_length > 0:
            read_buffer = (c_uint8 * read_length)()
        else:
            read_buffer = None

        if self._dll.CH341StreamI2C(self.device_index, write_length, write_buffer, read_length, read_buffer):
            if read_length > 0 and read_buffer:
                return bytes(read_buffer)
            return b''
        return None
    
    def close(self):
        """关闭CH341设备"""
        if self.is_opened and self._dll:
            try:
                self._dll.CH341CloseDevice(self.device_index)
                self.is_opened = False
                self.device_handle = None
                logger.info(f"已关闭CH341设备 {self.device_index}")
            except Exception as e:
                logger.error(f"关闭设备失败: {e}")
    
    def reset(self) -> bool:
        """
        重置设备
        
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            if not self.is_opened or not self._dll:
                return False
            return bool(self._dll.CH341ResetDevice(self.device_index))
        except Exception as e:
            logger.error(f"重置设备失败: {e}")
            return False
    
    def get_version(self) -> int:
        """
        获取驱动版本
        
        Returns:
            int: 版本号
        """
        try:
            if not self._dll:
                return 0
            return self._dll.CH341GetVersion()
        except Exception as e:
            logger.error(f"获取版本失败: {e}")
            return 0
    
    def scan_i2c_devices(self) -> List[int]:
        """
        扫描I2C设备
        
        Returns:
            List[int]: 发现的设备地址列表
        """
        if not self.is_opened or not self._dll:
            logger.error("设备未打开或DLL未加载")
            return []
        
        devices = []
        logger.info("开始扫描I2C设备...")
        
        # 使用工作的扫描方法
        start_addr, end_addr = 0x03, 0x77
        for addr in range(start_addr, end_addr + 1):
            try:
                # 使用流操作进行设备检测
                resp = self._stream(bytes([(addr << 1) | 0x01]), 1)
                if resp and resp.hex() != 'ff' and len(resp) == 1:
                    # 二次确认
                    resp2 = self._stream(bytes([(addr << 1) | 0x01]), 1)
                    if resp2 is not None and len(resp2) == 1:
                        devices.append(addr)
                        logger.info(f"发现I2C设备: 0x{addr:02X}")
            except:
                pass  # 忽略错误，继续扫描
        
        logger.info(f"扫描完成，共发现 {len(devices)} 个设备")
        return devices
    
    def i2c_read_register(self, device_addr: int, register_addr: int) -> int:
        """
        读取I2C设备寄存器
        
        Args:
            device_addr: 设备地址
            register_addr: 寄存器地址
            
        Returns:
            int: 读取的数据
        """
        if not self.is_opened or not self._dll:
            raise CH341Exception("设备未打开或DLL未加载")
        
        try:
            data = c_uint8()
            if self._dll.CH341ReadI2C(self.device_index, device_addr, register_addr, byref(data)):
                return data.value
            else:
                raise CH341Exception(f"读取寄存器失败: 设备=0x{device_addr:02X}, 寄存器=0x{register_addr:02X}")
        except Exception as e:
            raise CH341Exception(f"I2C读取错误: {e}")
    
    def i2c_write_register(self, device_addr: int, register_addr: int, data: int) -> bool:
        """
        写入I2C设备寄存器
        
        Args:
            device_addr: 设备地址
            register_addr: 寄存器地址
            data: 要写入的数据
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        if not self.is_opened or not self._dll:
            raise CH341Exception("设备未打开或DLL未加载")
        
        try:
            success = self._dll.CH341WriteI2C(self.device_index, device_addr, register_addr, data)
            if not success:
                raise CH341Exception(f"写入寄存器失败: 设备=0x{device_addr:02X}, 寄存器=0x{register_addr:02X}, 数据=0x{data:02X}")
            return True
        except Exception as e:
            raise CH341Exception(f"I2C写入错误: {e}")
    
    def i2c_read_bytes(self, device_addr: int, register_addr: int, length: int) -> List[int]:
        """
        读取多个字节
        
        Args:
            device_addr: 设备地址
            register_addr: 寄存器地址
            length: 读取长度
            
        Returns:
            List[int]: 读取的数据列表
        """
        if not self.is_opened or not self._dll:
            raise CH341Exception("设备未打开或DLL未加载")
        
        try:
            # 构建命令缓冲区
            write_buf = (c_uint8 * 32)()
            read_buf = (c_uint8 * 32)()
            
            # 写入命令：开始 + 设备地址(写) + 寄存器地址
            write_buf[0] = 0x74  # I2C start
            write_buf[1] = (device_addr << 1) & 0xFE  # 写地址
            write_buf[2] = register_addr
            write_buf[3] = 0x74  # I2C restart
            write_buf[4] = ((device_addr << 1) | 0x01) & 0xFF  # 读地址
            
            # 读取数据命令
            for i in range(length - 1):
                write_buf[5 + i] = 0x80  # 读取并ACK
            write_buf[5 + length - 1] = 0x81  # 读取并NACK（最后一个字节）
            write_buf[5 + length] = 0x75  # I2C stop
            
            write_len = 6 + length
            
            if self._dll.CH341StreamI2C(self.device_index, write_len, write_buf, length, read_buf):
                return [read_buf[i] for i in range(length)]
            else:
                raise CH341Exception(f"批量读取失败: 设备=0x{device_addr:02X}, 寄存器=0x{register_addr:02X}")
                
        except Exception as e:
            raise CH341Exception(f"I2C批量读取错误: {e}")
    
    def i2c_write_bytes(self, device_addr: int, register_addr: int, data: List[int]) -> bool:
        """
        写入多个字节
        
        Args:
            device_addr: 设备地址
            register_addr: 寄存器地址
            data: 要写入的数据列表
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        if not self.is_opened or not self._dll:
            raise CH341Exception("设备未打开或DLL未加载")
        
        try:
            # 构建命令缓冲区
            write_buf = (c_uint8 * 32)()
            
            # 写入命令：开始 + 设备地址(写) + 寄存器地址 + 数据
            write_buf[0] = 0x74  # I2C start
            write_buf[1] = (device_addr << 1) & 0xFE  # 写地址
            write_buf[2] = register_addr
            
            # 写入数据
            for i, byte_data in enumerate(data):
                write_buf[3 + i] = byte_data
            
            write_buf[3 + len(data)] = 0x75  # I2C stop
            write_len = 4 + len(data)
            
            success = self._dll.CH341StreamI2C(self.device_index, write_len, write_buf, 0, None)
            if not success:
                raise CH341Exception(f"批量写入失败: 设备=0x{device_addr:02X}, 寄存器=0x{register_addr:02X}")
            return True
            
        except Exception as e:
            raise CH341Exception(f"I2C批量写入错误: {e}")
    
    @property
    def supported_gpios(self) -> List[str]:
        """获取支持的GPIO口列表"""
        return list(self._supported_gpios.keys())

    def init_gpio(self, gpio_name: str, direction: str, mode: Optional[str] = None, pull: Optional[str] = None) -> bool:
        """
        初始化GPIO方向，接口与 ch341_device.py 对齐

        Args:
            gpio_name: GPIO名称（如 'GPIO0'）
            direction: 'in' 或 'out'
            mode: 推挽/开漏（CH341不支持，忽略，仅兼容）
            pull: 上拉/下拉（CH341不支持，忽略，仅兼容）
        """
        if gpio_name not in self._supported_gpios:
            logger.error(f"不支持的GPIO口: {gpio_name}")
            return False
        if direction not in ['in', 'out']:
            logger.error(f"无效的方向: {direction}")
            return False

        if mode is not None:
            logger.warning("CH341的GPIO不支持推挽/开漏切换，忽略mode参数")
        if pull is not None:
            logger.warning("CH341的GPIO不支持上拉/下拉切换，忽略pull参数")

        gpio_index = self._supported_gpios[gpio_name]
        try:
            if gpio_index > 15:
                logger.error(f"不支持修改 {gpio_name} 的方向")
                return False
            elif gpio_index > 7:
                enable_mask = 0x2
            else:
                enable_mask = 0x8

            direction_mask = self.gpio_dir_mask
            if direction == 'out':
                direction_mask |= (0x1 << gpio_index)
            else:  # 'in'
                direction_mask &= ~(0x1 << gpio_index)

            if direction_mask == self.gpio_dir_mask:
                return True

            if not self._set_output(enable_mask, direction_mask, 0x0):
                logger.error("设置GPIO方向失败")
                return False

            self.gpio_dir_mask = direction_mask
            return True
        except Exception as e:
            logger.error(f"初始化GPIO失败: {e}")
            return False

    def set_gpio_output(self, gpio_name: str, value: bool) -> bool:
        """
        设置GPIO输出电平，接口与 ch341_device.py 对齐
        """
        if gpio_name not in self._supported_gpios:
            logger.error(f"不支持的GPIO口: {gpio_name}")
            return False
        gpio_index = self._supported_gpios[gpio_name]

        if (self.gpio_dir_mask & (0x1 << gpio_index)) == 0:
            logger.warning(f"GPIO口 {gpio_name} 未初始化为输出模式")
            # 尝试自动初始化为输出
            if not self.init_gpio(gpio_name, 'out'):
                logger.error(f"自动初始化 {gpio_name} 为输出失败")
                # 继续尝试设置，但可能失败

        try:
            if gpio_index > 23:
                logger.error(f"未定义的GPIO口: {gpio_name}")
                return False
            elif gpio_index > 15:
                enable_mask = 0x10
            elif gpio_index > 7:
                enable_mask = 0x1
            else:
                enable_mask = 0x4

            data_mask = self._get_input()
            if data_mask is None:
                data_mask = self.gpio_data_mask

            if value:
                data_mask |= (0x1 << gpio_index)
            else:
                data_mask &= ~(0x1 << gpio_index)

            if self._set_output(enable_mask, 0x0, data_mask):
                # 等待更长时间以确保硬件状态稳定（与 ch341_device.py 保持一致）
                time.sleep(0.5)
                confirm = self._get_input()
                if confirm is None or confirm != data_mask:
                    logger.warning(f"GPIO口 {gpio_name} 设置后读取不一致")
                else:
                    self.gpio_data_mask = data_mask
                return True
            logger.error(f"GPIO口 {gpio_name} 设置失败")
            return False
        except Exception as e:
            logger.error(f"设置GPIO口 {gpio_name} 输出值失败: {e}")
            return False

    def get_gpio_input(self, gpio_name: str) -> Optional[bool]:
        """
        获取GPIO输入电平，接口与 ch341_device.py 对齐
        """
        if gpio_name not in self._supported_gpios:
            logger.error(f"不支持的GPIO口: {gpio_name}")
            return None
        gpio_index = self._supported_gpios[gpio_name]

        try:
            input_value = self._get_input()
            if input_value is None:
                return None
            return (input_value & (0x1 << gpio_index)) != 0
        except Exception as e:
            logger.error(f"读取GPIO输入值失败: {e}")
            return None

    def set_gpio(self, pin: str, value: bool) -> bool:
        """
        设置GPIO输出
        
        Args:
            pin: GPIO引脚名称 ('GPIO0', 'GPIO1' 等)
            value: 输出值 (True=高电平, False=低电平)
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        if not self.is_opened or not self._dll:
            raise CH341Exception("设备未打开或DLL未加载")
        if pin not in self._supported_gpios:
            raise CH341Exception(f"不支持的GPIO引脚: {pin}")
        try:
            ok = self.set_gpio_output(pin, value)
            if not ok:
                raise CH341Exception(f"设置GPIO失败: {pin}={value}")
            return True
        except Exception as e:
            raise CH341Exception(f"GPIO操作错误: {e}")
    
    def get_gpio(self, pin: str) -> bool:
        """
        读取GPIO输入
        
        Args:
            pin: GPIO引脚名称
            
        Returns:
            bool: 引脚状态 (True=高电平, False=低电平)
        """
        if not self.is_opened or not self._dll:
            raise CH341Exception("设备未打开或DLL未加载")
        if pin not in self._supported_gpios:
            raise CH341Exception(f"不支持的GPIO引脚: {pin}")
        try:
            val = self.get_gpio_input(pin)
            if val is None:
                raise CH341Exception(f"读取GPIO失败: {pin}")
            return bool(val)
        except Exception as e:
            raise CH341Exception(f"GPIO读取错误: {e}")
    
    def get_device_status(self) -> dict:
        """
        获取设备状态
        
        Returns:
            dict: 设备状态信息
        """
        if not self.is_opened or not self._dll:
            return {"error": "设备未打开或DLL未加载"}
        
        try:
            status = c_uint32()
            if self._dll.CH341GetStatus(self.device_index, byref(status)):
                status_val = status.value
                return {
                    "raw_status": f"0x{status_val:08X}",
                    "ERR": bool(status_val & self.STATE_BIT_ERR),
                    "PEMP": bool(status_val & self.STATE_BIT_PEMP),
                    "INT": bool(status_val & self.STATE_BIT_INT),
                    "SLCT": bool(status_val & self.STATE_BIT_SLCT),
                    "WAIT": bool(status_val & self.STATE_BIT_WAIT),
                    "DATAS": bool(status_val & self.STATE_BIT_DATAS),
                    "ADDRS": bool(status_val & self.STATE_BIT_ADDRS),
                    "RESET": bool(status_val & self.STATE_BIT_RESET),
                    "WRITE": bool(status_val & self.STATE_BIT_WRITE),
                    "SCL": bool(status_val & self.STATE_BIT_SCL),
                    "SDA": bool(status_val & self.STATE_BIT_SDA),
                }
            else:
                return {"error": "无法读取设备状态"}
        except Exception as e:
            return {"error": f"状态读取错误: {e}"}
    
    def __enter__(self):
        """上下文管理器入口"""
        if not self.is_opened:
            self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
    
    def __del__(self):
        """析构函数"""
        self.close()
    
    # 兼容性方法别名
    def gpio_set(self, pin, value: bool) -> bool:
        """GPIO设置方法别名，保持向后兼容"""
        # 支持数字引脚和字符串引脚名
        if isinstance(pin, int):
            pin_name = f"GPIO{pin}"
        else:
            pin_name = pin
        return self.set_gpio(pin_name, value)
    
    def i2c_write_read(self, device_addr: int, write_data: List[int], read_length: int) -> Optional[bytes]:
        """I2C写读方法别名，保持向后兼容"""
        if not write_data:
            return None
        
        try:
            # 使用流操作进行写读
            write_buffer = bytes([(device_addr << 1) | 1])
            
            # 如果需要先写寄存器地址
            if len(write_data) > 0:
                register_addr = write_data[0]
                # 写寄存器地址
                if not self.write(device_addr, register_addr, []):
                    return None
                    
            # 读取数据
            read_data = self._stream(write_buffer, read_length)
            return read_data if read_data else None
        except:
            return None
    
    def i2c_read(self, device_addr: int, length: int) -> Optional[bytes]:
        """I2C读取方法别名，保持向后兼容"""
        try:
            # 直接读取
            write_buffer = bytes([(device_addr << 1) | 1])
            read_data = self._stream(write_buffer, length)
            return read_data if read_data else None
        except:
            return None
    
    def i2c_write(self, device_addr: int, data: List[int]) -> bool:
        """
        I2C写入方法，兼容性方法
        
        Args:
            device_addr: 设备地址
            data: 要写入的数据列表，第一个字节是寄存器地址，后续是数据
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        if not data:
            return False
        
        try:
            register_addr = data[0]
            write_data = data[1:] if len(data) > 1 else []
            return self.i2c_write_bytes(device_addr, register_addr, write_data)
        except Exception as e:
            logger.error(f"I2C写入失败: {e}")
            return False
    
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
            self.reg_pointer = register
            return bool(status == b'')
        except Exception as e:
            logger.error(f"多字节写入失败: {e}")
            return False

    def read(self, address: int, register: int, length: int, fast_read: bool = False) -> Optional[List[int]]:
        """
        多字节读取

        Args:
            address: 设备地址
            register: 寄存器地址
            length: 要读取的数据长度
            fast_read: 是否快速读取

        Returns:
            读取的数据列表，失败返回None
        """
        try:
            read_data = None
            write_buffer = bytes([(address << 1) | 1])

            if fast_read and register == self.reg_pointer:
                read_data = self._stream(write_buffer, length)
            else:
                if self.write(address, register, []):
                    read_data = self._stream(write_buffer, length)
                else:
                    self.reg_pointer = None
                    logger.error(f"寄存器0x{register:X}写入失败")

            return list(read_data) if read_data else None
        except Exception as e:
            logger.error(f"多字节读取失败: {e}")
            return None


def get_device_count() -> int:
    """
    获取系统中CH341设备的数量
    
    Returns:
        int: 设备数量
    """
    try:
        # 创建临时设备实例来检测设备
        count = 0
        for i in range(16):  # 最多检查16个设备
            try:
                device = CH341Device(i)
                if device.open(silent=True):  # 使用静默模式
                    count += 1
                    device.close()
                else:
                    break
            except:
                break
        return count
    except Exception as e:
        logger.error(f"获取设备数量异常: {e}")
        return 0
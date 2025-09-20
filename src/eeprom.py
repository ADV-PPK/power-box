"""
EEPROM访问模块

通过CH341访问I2C EEPROM，用于读取板卡的唯一识别码。
支持常见的EEPROM芯片如24C02, 24C04, 24C08, 24C16等。
"""

import time
import logging
from typing import Optional, List, Union, cast

# 导入CH341模块
try:
    from .ch341 import CH341Device, CH341Exception
except ImportError:
    from ch341 import CH341Device, CH341Exception

# 配置日志
logger = logging.getLogger(__name__)


class EEPROMException(Exception):
    """EEPROM相关异常"""
    pass


class EEPROM:
    """I2C EEPROM访问类"""
    
    # 常见EEPROM型号的参数
    EEPROM_TYPES = {
        '24C02': {'size': 256, 'page_size': 8, 'address_bytes': 1},
        '24C04': {'size': 512, 'page_size': 16, 'address_bytes': 1},
        '24C08': {'size': 1024, 'page_size': 16, 'address_bytes': 1},
        '24C16': {'size': 2048, 'page_size': 16, 'address_bytes': 1},
        '24C32': {'size': 4096, 'page_size': 32, 'address_bytes': 2},
        '24C64': {'size': 8192, 'page_size': 32, 'address_bytes': 2},
        '24C128': {'size': 16384, 'page_size': 64, 'address_bytes': 2},
        '24C256': {'size': 32768, 'page_size': 64, 'address_bytes': 2},
    }
    
    def __init__(self, ch341_device: CH341Device, address: int = 0x50, 
                 eeprom_type: str = '24C32'):
        """
        初始化EEPROM访问
        
        Args:
            ch341_device: CH341设备实例
            address: EEPROM的I2C地址，默认0x50
            eeprom_type: EEPROM型号，默认24C32
        """
        self.ch341 = ch341_device
        self.address = address
        self.eeprom_type = eeprom_type.upper()
        
        if self.eeprom_type not in self.EEPROM_TYPES:
            raise EEPROMException(f"不支持的EEPROM型号: {eeprom_type}")
        
        self.params = self.EEPROM_TYPES[self.eeprom_type]
        self.size = self.params['size']
        self.page_size = self.params['page_size']
        self.address_bytes = self.params['address_bytes']
        
        logger.info(f"初始化{self.eeprom_type} EEPROM: "
                   f"地址=0x{self.address:02X}, 大小={self.size}字节")
    
    def _check_address(self, address: int, length: int = 1) -> bool:
        """
        检查地址范围是否有效
        
        Args:
            address: 起始地址
            length: 长度
            
        Returns:
            bool: 有效返回True
        """
        if address < 0 or address >= self.size:
            logger.error(f"地址超出范围: {address} (最大{self.size-1})")
            return False
        
        if address + length > self.size:
            logger.error(f"读取长度超出范围: {address}+{length} > {self.size}")
            return False
        
        return True
    
    def _wait_write_complete(self, timeout: float = 0.1, probe_addr: Optional[int] = None, expected: Optional[int] = None) -> bool:
        """
        等待写操作完成
        
        Args:
            timeout: 超时时间（秒）
            probe_addr: 可选，轮询读取的地址（用于无ACK轮询时回退）
            expected: 可选，预期写入的字节（用于回读比较）
            
        Returns:
            bool: 成功返回True
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 优先：通过ACK轮询检查写操作是否完成
            try:
                if self.ch341.i2c_write(self.address, []):
                    return True
            except Exception:
                pass

            # 回退：通过对 probe_addr 执行最小读操作来判断是否就绪
            if probe_addr is not None:
                try:
                    # 组装地址字节
                    if self.address_bytes == 1:
                        addr_data = [probe_addr & 0xFF]
                    else:
                        addr_data = [(probe_addr >> 8) & 0xFF, probe_addr & 0xFF]
                    rb = self.ch341.i2c_write_read(self.address, addr_data, 1)
                    if rb and len(rb) == 1:
                        if expected is None:
                            return True
                        if rb[0] == (expected & 0xFF):
                            return True
                except Exception:
                    pass
            time.sleep(0.001)  # 等待1ms
        
        logger.warning("写操作完成等待超时")
        return False
    
    def read_byte(self, address: int) -> Optional[int]:
        """
        读取单个字节
        
        Args:
            address: 要读取的地址
            
        Returns:
            int: 读取的字节值，失败返回None
        """
        if not self._check_address(address):
            return None
        
        try:
            # 准备地址数据
            if self.address_bytes == 1:
                addr_data = [address & 0xFF]
            else:  # 2字节地址
                addr_data = [(address >> 8) & 0xFF, address & 0xFF]
            
            # 写地址后读数据
            data = self.ch341.i2c_write_read(self.address, addr_data, 1)
            if data and len(data) == 1:
                return data[0]
            else:
                logger.error(f"读取字节失败: 地址0x{address:04X}")
                return None
                
        except Exception as e:
            logger.error(f"读取字节异常: {e}")
            return None
    
    def write_byte(self, address: int, value: int) -> bool:
        """
        写入单个字节
        
        Args:
            address: 要写入的地址
            value: 要写入的字节值
            
        Returns:
            bool: 成功返回True
        """
        if not self._check_address(address):
            return False
        
        if value < 0 or value > 255:
            logger.error(f"字节值超出范围: {value}")
            return False
        
        try:
            # 准备写入数据
            if self.address_bytes == 1:
                write_data = [address & 0xFF, value]
            else:  # 2字节地址
                write_data = [(address >> 8) & 0xFF, address & 0xFF, value]
            
            # 写入数据
            if self.ch341.i2c_write(self.address, write_data):
                # 等待写操作完成（使用读回退/期望值）
                return self._wait_write_complete(probe_addr=address, expected=value)
            else:
                logger.error(f"写入字节失败: 地址0x{address:04X}")
                return False
                
        except Exception as e:
            logger.error(f"写入字节异常: {e}")
            return False
    
    def read_bytes(self, address: int, length: int) -> Optional[bytes]:
        """
        读取多个字节
        
        Args:
            address: 起始地址
            length: 要读取的字节数
            
        Returns:
            bytes: 读取的数据，失败返回None
        """
        if not self._check_address(address, length):
            return None
        
        try:
            # 准备地址数据
            if self.address_bytes == 1:
                addr_data = [address & 0xFF]
            else:  # 2字节地址
                addr_data = [(address >> 8) & 0xFF, address & 0xFF]
            
            # 写地址后读数据
            data = self.ch341.i2c_write_read(self.address, addr_data, length)
            if data and len(data) == length:
                logger.debug(f"成功读取{length}字节: 地址0x{address:04X}")
                return data
            else:
                logger.error(f"读取数据失败: 地址0x{address:04X}, 长度{length}")
                return None
                
        except Exception as e:
            logger.error(f"读取数据异常: {e}")
            return None
    
    def write_bytes(self, address: int, data: Union[List[int], bytes]) -> bool:
        """
        写入多个字节（支持页写入优化）
        
        Args:
            address: 起始地址
            data: 要写入的数据
            
        Returns:
            bool: 成功返回True
        """
        if isinstance(data, list):
            data = bytes(data)
        
        if not self._check_address(address, len(data)):
            return False
        
        try:
            offset = 0
            total_length = len(data)
            # 对于1字节地址的器件（如24C02系列），使用单字节写+轮询校验以提升可靠性
            if self.address_bytes == 1:
                buf: bytes = data if isinstance(data, (bytes, bytearray)) else bytes(data)
                for i in range(total_length):
                    cur_addr = address + i
                    byte_val: int = buf[i] & 0xFF
                    if not self.ch341.i2c_write_register(self.address, cur_addr & 0xFF, byte_val):
                        logger.error(f"字节写入失败: 地址0x{cur_addr:04X}")
                        return False
                    if not self._wait_write_complete(probe_addr=cur_addr, expected=byte_val):
                        logger.error(f"字节写入完成等待超时: 地址0x{cur_addr:04X}")
                        return False
                    # 适度延时，增加兼容性
                    time.sleep(0.001)
                logger.info(f"成功写入{total_length}字节: 地址0x{address:04X}")
                return True
            
            while offset < total_length:
                # 计算当前页的起始地址
                current_addr = address + offset
                
                # 计算当前页剩余空间
                page_start = (current_addr // self.page_size) * self.page_size
                page_remaining = self.page_size - (current_addr - page_start)
                
                # 计算本次写入的长度
                write_length = min(page_remaining, total_length - offset)
                
                # 准备写入数据
                if self.address_bytes == 1:
                    write_data = [current_addr & 0xFF]
                else:  # 2字节地址
                    write_data = [(current_addr >> 8) & 0xFF, current_addr & 0xFF]
                
                write_data.extend(data[offset:offset + write_length])
                
                # 执行页写入
                if not self.ch341.i2c_write(self.address, write_data):
                    logger.error(f"页写入失败: 地址0x{current_addr:04X}")
                    return False
                
                # 等待写操作完成（使用读回退/期望值：最后一个字节）
                probe_addr = current_addr + write_length - 1
                expected = cast(int, data[offset + write_length - 1])
                if not self._wait_write_complete(probe_addr=probe_addr, expected=expected):
                    logger.error(f"页写入完成等待超时: 地址0x{current_addr:04X}")
                    return False
                # 额外固定延时，增加兼容性
                time.sleep(0.005)
                
                offset += write_length
                logger.debug(f"页写入成功: 地址0x{current_addr:04X}, 长度{write_length}")
            
            logger.info(f"成功写入{total_length}字节: 地址0x{address:04X}")
            return True
            
        except Exception as e:
            logger.error(f"写入数据异常: {e}")
            return False
    
    def read_string(self, address: int, max_length: int = 64) -> Optional[str]:
        """
        读取以NULL结尾的字符串
        
        Args:
            address: 起始地址
            max_length: 最大读取长度
            
        Returns:
            str: 读取的字符串，失败返回None
        """
        try:
            data = self.read_bytes(address, max_length)
            if data:
                # 诊断：记录前16字节
                logger.debug("读取字符串原始数据(前16字节): " + ' '.join(f"{b:02X}" for b in data[:16]))
                # 若全为0xFF或0x00，视为未设置
                if all(b == 0xFF for b in data) or all(b == 0x00 for b in data):
                    return ""
                # 查找NULL终止符
                null_pos = data.find(0)
                if null_pos >= 0:
                    data = data[:null_pos]
                # 转换为字符串
                return data.decode('utf-8', errors='ignore')
            else:
                return None
                
        except Exception as e:
            logger.error(f"读取字符串异常: {e}")
            return None
    
    def write_string(self, address: int, text: str) -> bool:
        """
        写入以NULL结尾的字符串
        
        Args:
            address: 起始地址
            text: 要写入的字符串
            
        Returns:
            bool: 成功返回True
        """
        try:
            # 转换为字节并添加NULL终止符
            data = text.encode('utf-8') + b'\x00'
            if not self.write_bytes(address, data):
                return False
            # 额外固定延时，确保写周期完全结束
            time.sleep(0.005)
            # 写入后回读校验
            verify = self.read_bytes(address, len(data))
            if verify is None:
                logger.error("写入后读取校验失败: 读取为空")
                return False
            if bytes(verify) != data:
                logger.error("写入校验不一致，可能写保护(WP)已使能或地址不正确")
                logger.debug(f"期望: {data.hex(' ')} 实际: {bytes(verify).hex(' ')}")
                return False
            return True
            
        except Exception as e:
            logger.error(f"写入字符串异常: {e}")
            return False
    
    def read_board_id(self, address: int = 0x00) -> Optional[str]:
        """
        读取板卡唯一识别码
        
        Args:
            address: 识别码存储地址，默认0x00
            
        Returns:
            str: 板卡识别码，失败返回None
        """
        logger.info(f"读取板卡识别码: 地址0x{address:04X}")
        return self.read_string(address, 32)  # 假设识别码最长32字符
    
    def write_board_id(self, board_id: str, address: int = 0x00) -> bool:
        """
        写入板卡唯一识别码
        
        Args:
            board_id: 板卡识别码
            address: 识别码存储地址，默认0x00
            
        Returns:
            bool: 成功返回True
        """
        logger.info(f"写入板卡识别码: {board_id}")
        return self.write_string(address, board_id)
    
    def dump_hex(self, start_addr: int = 0, length: Optional[int] = None) -> str:
        """
        以十六进制格式转储EEPROM内容
        
        Args:
            start_addr: 起始地址
            length: 转储长度，默认为整个EEPROM
            
        Returns:
            str: 十六进制格式的数据
        """
        if length is None:
            length = self.size - start_addr
        
        if not self._check_address(start_addr, length):
            return ""
        
        data = self.read_bytes(start_addr, length)
        if not data:
            return ""
        
        result = []
        for i in range(0, len(data), 16):
            # 地址
            addr = start_addr + i
            line = f"{addr:04X}: "
            
            # 十六进制数据
            hex_part = ""
            ascii_part = ""
            for j in range(16):
                if i + j < len(data):
                    byte_val = data[i + j]
                    hex_part += f"{byte_val:02X} "
                    # ASCII部分
                    if 32 <= byte_val <= 126:
                        ascii_part += chr(byte_val)
                    else:
                        ascii_part += "."
                else:
                    hex_part += "   "
                    ascii_part += " "
            
            line += hex_part + " |" + ascii_part + "|"
            result.append(line)

        return "\n".join(result)
    
    def test_device(self, silent: bool = False) -> bool:
        """
        测试EEPROM设备是否可访问
        
        Args:
            silent: 静默模式，失败时不打印错误信息
        
        Returns:
            bool: 可访问返回True
        """
        try:
            # 尝试读取第一个字节
            test_byte = self.read_byte(0)
            if test_byte is not None:
                if not silent:
                    logger.info(f"EEPROM设备测试成功: 地址0x{self.address:02X}")
                return True
            else:
                if not silent:
                    logger.error(f"EEPROM设备测试失败: 地址0x{self.address:02X}")
                return False
                
        except Exception as e:
            if not silent:
                logger.error(f"EEPROM设备测试异常: {e}")
            return False
    
    def get_info(self) -> dict:
        """
        获取EEPROM信息
        
        Returns:
            dict: EEPROM信息
        """
        return {
            'type': self.eeprom_type,
            'address': f"0x{self.address:02X}",
            'size': f"{self.size} bytes",
            'page_size': f"{self.page_size} bytes",
            'address_bytes': self.address_bytes
        }


def scan_eeprom_devices(ch341_device: CH341Device, method: str = 'read_probe') -> List[int]:
    """
    扫描I2C总线上的EEPROM设备
    
    Args:
        ch341_device: CH341设备实例
        method: 扫描方法，可选值：
               'read_probe' - 纯读取探测（推荐，非破坏性）
               'write_test' - 写入测试验证（较可靠，但会修改EEPROM内容）
               'class_test' - 使用EEPROM类测试（兼容性最好）
        
    Returns:
        list: 发现的EEPROM设备地址列表
    """
    devices = []
    
    # EEPROM常见地址范围
    possible_addresses = [0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57]
    
    logger.info(f"扫描EEPROM设备(方法: {method})...")
    
    for addr in possible_addresses:
        found = False
        try:
            if method == 'read_probe':
                # 方法1: 使用i2c_write_read进行读取探测（非破坏性）
                try:
                    # 尝试从地址0读取1字节
                    data = ch341_device.i2c_write_read(addr, [0x00], 1)
                    if data and len(data) == 1 and data[0] != 0xFF:
                        # 二次确认减少噪声
                        data2 = ch341_device.i2c_write_read(addr, [0x00], 1)
                        if data2 and len(data2) == 1 and data2[0] == data[0]:
                            found = True
                            logger.info(f"发现EEPROM设备(读取探测): 0x{addr:02X}")
                except:
                    pass
                    
            elif method == 'write_test':
                # 方法2: 使用写入测试验证（会修改EEPROM内容）
                try:
                    # 先读取原始值
                    original_value = None
                    try:
                        orig_data = ch341_device.i2c_write_read(addr, [0x00], 1)
                        if orig_data and len(orig_data) == 1:
                            original_value = orig_data[0]
                    except:
                        pass
                    
                    # 写入测试值0xAA到地址0x00
                    test_value = 0xAA
                    if ch341_device.i2c_write_register(addr, 0x00, test_value):
                        # 等待写入完成
                        time.sleep(0.005)
                        # 读取验证
                        verify_data = ch341_device.i2c_write_read(addr, [0x00], 1)
                        if verify_data and len(verify_data) == 1 and verify_data[0] == test_value:
                            found = True
                            logger.info(f"发现EEPROM设备(写入测试): 0x{addr:02X}")
                            
                            # 恢复原始值
                            if original_value is not None:
                                try:
                                    ch341_device.i2c_write_register(addr, 0x00, original_value)
                                    time.sleep(0.005)
                                except:
                                    pass
                except:
                    pass
                    
            elif method == 'class_test':
                # 方法3: 使用EEPROM类的test_device方法（兼容性回退）
                try:
                    eeprom = EEPROM(ch341_device, addr)
                    if eeprom.test_device(silent=True):  # 使用静默模式
                        found = True
                        logger.info(f"发现EEPROM设备(类测试): 0x{addr:02X}")
                except Exception as e:
                    logger.debug(f"地址0x{addr:02X}检查失败: {e}")
            else:
                logger.error(f"未知的扫描方法: {method}")
                break
            
            if found:
                devices.append(addr)
            
        except Exception:
            # 忽略异常，继续扫描
            pass
        
        # 添加小延迟提高总线可靠性
        time.sleep(0.001)
    
    logger.info(f"扫描完成，发现{len(devices)}个EEPROM设备")
    return devices


if __name__ == "__main__":
    # 测试代码
    try:
        from ch341 import CH341Device
    except ImportError:
        from .ch341 import CH341Device
    
    try:
        with CH341Device(0) as ch341:
            print("开始测试EEPROM...")
            
            # 扫描EEPROM设备
            devices = scan_eeprom_devices(ch341, method='read_probe')
            if not devices:
                print("未发现EEPROM设备")
                exit(1)
            
            # 使用第一个发现的设备
            eeprom = EEPROM(ch341, devices[0], '24C02')
            
            # 显示设备信息
            info = eeprom.get_info()
            print("EEPROM信息:")
            for key, value in info.items():
                print(f"  {key}: {value}")
            
            # 转储前64字节内容
            print("\nEEPROM内容 (前64字节):")
            hex_dump = eeprom.dump_hex(0, 64)
            print(hex_dump)
            
            # 设置板卡ID
            new_id = "Power Box S0"
            print("\n写入板卡ID:", new_id)
            if eeprom.write_board_id(new_id):
                print("写入成功")
            else:
                print("写入失败")
            
            # 读取板卡ID
            print("\n读取板卡ID:")
            board_id = eeprom.read_board_id()
            if board_id:
                print(f"\n当前板卡ID: {board_id}")
            else:
                print("\n未找到板卡ID")
            
            
    except Exception as e:
        print(f"测试异常: {e}")
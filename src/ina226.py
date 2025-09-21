"""
INA226 电流/电压监测芯片驱动

INA226是一款高精度数字电流传感器，支持：
- 双向电流测量
- 总线电压测量
- 分流电压测量  
- 功率计算
- 可编程报警功能
"""

import time
import logging
from typing import Optional, Tuple, Dict, Any

# 导入CH341模块
try:
    from .ch341 import CH341Device, CH341Exception
except ImportError:
    from ch341 import CH341Device, CH341Exception

# 配置日志
logger = logging.getLogger(__name__)


class INA226Exception(Exception):
    """INA226相关异常"""
    pass


class INA226:
    """INA226电流监测芯片驱动类"""
    
    # INA226默认I2C地址
    DEFAULT_ADDRESS = 0x40
    
    # 寄存器地址定义
    REG_CONFIGURATION = 0x00
    REG_SHUNT_VOLTAGE = 0x01
    REG_BUS_VOLTAGE = 0x02
    REG_POWER = 0x03
    REG_CURRENT = 0x04
    REG_CALIBRATION = 0x05
    REG_MASK_ENABLE = 0x06
    REG_ALERT_LIMIT = 0x07
    REG_MANUFACTURER_ID = 0xFE
    REG_DIE_ID = 0xFF
    
    # 配置寄存器位定义
    CONFIG_RESET = 0x8000
    CONFIG_AVG_1 = 0x0000
    CONFIG_AVG_4 = 0x0200
    CONFIG_AVG_16 = 0x0400
    CONFIG_AVG_64 = 0x0600
    CONFIG_AVG_128 = 0x0800
    CONFIG_AVG_256 = 0x0A00
    CONFIG_AVG_512 = 0x0C00
    CONFIG_AVG_1024 = 0x0E00
    
    CONFIG_VBUSCT_140US = 0x0000
    CONFIG_VBUSCT_204US = 0x0040
    CONFIG_VBUSCT_332US = 0x0080
    CONFIG_VBUSCT_588US = 0x00C0
    CONFIG_VBUSCT_1100US = 0x0100
    CONFIG_VBUSCT_2116US = 0x0140
    CONFIG_VBUSCT_4156US = 0x0180
    CONFIG_VBUSCT_8244US = 0x01C0
    
    CONFIG_VSHCT_140US = 0x0000
    CONFIG_VSHCT_204US = 0x0008
    CONFIG_VSHCT_332US = 0x0010
    CONFIG_VSHCT_588US = 0x0018
    CONFIG_VSHCT_1100US = 0x0020
    CONFIG_VSHCT_2116US = 0x0028
    CONFIG_VSHCT_4156US = 0x0030
    CONFIG_VSHCT_8244US = 0x0038
    
    CONFIG_MODE_POWER_DOWN = 0x0000
    CONFIG_MODE_SHUNT_TRIG = 0x0001
    CONFIG_MODE_BUS_TRIG = 0x0002
    CONFIG_MODE_SHUNT_BUS_TRIG = 0x0003
    CONFIG_MODE_ADC_OFF = 0x0004
    CONFIG_MODE_SHUNT_CONT = 0x0005
    CONFIG_MODE_BUS_CONT = 0x0006
    CONFIG_MODE_SHUNT_BUS_CONT = 0x0007
    
    # 默认配置
    DEFAULT_CONFIG = 0x4000 | (CONFIG_AVG_16 | CONFIG_VBUSCT_1100US | 
                     CONFIG_VSHCT_1100US | CONFIG_MODE_SHUNT_BUS_CONT)
    
    # 制造商ID和器件ID
    MANUFACTURER_ID = 0x5449  # "TI"
    DIE_ID = 0x2260  # INA226
    
    def __init__(self, ch341_device: CH341Device, address: int = DEFAULT_ADDRESS, 
                 shunt_resistance: float = 0.1):
        """
        初始化INA226
        
        Args:
            ch341_device: CH341设备实例
            address: I2C地址
            shunt_resistance: 分流电阻阻值（欧姆），默认0.1欧
        """
        self.ch341 = ch341_device
        self.address = address
        self.shunt_resistance = shunt_resistance
        self.current_lsb = 0.0
        self.power_lsb = 0.0
        self.calibration_value = 0
        
    def _write_register(self, reg: int, value: int) -> bool:
        """
        写寄存器
        
        Args:
            reg: 寄存器地址
            value: 16位值
            
        Returns:
            bool: 成功返回True
        """
        try:
            # INA226使用大端字节序
            data = [(value >> 8) & 0xFF, value & 0xFF]
            return self.ch341.write(self.address, reg, data)
        except Exception as e:
            logger.error(f"写寄存器异常: {e}")
            return False
    
    def _read_register(self, reg: int) -> Optional[int]:
        """
        读寄存器
        
        Args:
            reg: 寄存器地址
            
        Returns:
            int: 16位寄存器值，失败返回None
        """
        try:
            # 写寄存器地址
            data = self.ch341.read(self.address, reg, 2, fast_read=True)
            logger.debug(f"读寄存器0x{reg:02X}数据: {data}")
            if data and len(data) == 2:
                # 大端字节序转换
                value = (data[0] << 8) | data[1]
                return value
            else:
                return None
        except Exception as e:
            logger.error(f"读寄存器异常: {e}")
            return None
    
    def reset(self) -> bool:
        """
        软件复位INA226
        
        Returns:
            bool: 成功返回True
        """
        logger.info("复位INA226...")
        if self._write_register(self.REG_CONFIGURATION, self.CONFIG_RESET):
            # 等待复位完成
            time.sleep(0.01)  # 10ms
            return True
        return False
    
    def check_device(self, silent: bool = False) -> bool:
        """
        检查设备是否为INA226
        
        Args:
            silent: 静默模式，失败时不打印错误信息
        
        Returns:
            bool: 是INA226返回True
        """
        try:
            # 读取制造商ID
            manufacturer_id = self._read_register(self.REG_MANUFACTURER_ID)
            if manufacturer_id != self.MANUFACTURER_ID:
                if not silent:
                    logger.error(f"制造商ID不匹配: 期望0x{self.MANUFACTURER_ID:04X}, "
                               f"实际0x{manufacturer_id:04X}")
                return False
            
            # 读取器件ID
            die_id = self._read_register(self.REG_DIE_ID)
            if die_id != self.DIE_ID:
                if not silent:
                    logger.error(f"器件ID不匹配: 期望0x{self.DIE_ID:04X}, "
                               f"实际0x{die_id:04X}")
                return False
            
            if not silent:
                logger.info("成功识别INA226器件")
            return True
            
        except Exception as e:
            if not silent:
                logger.error(f"设备检查异常: {e}")
            return False
    
    def configure(self, config: int = DEFAULT_CONFIG) -> bool:
        """
        配置INA226
        
        Args:
            config: 配置值
            
        Returns:
            bool: 成功返回True
        """
        logger.info(f"配置INA226: 0x{config:04X}")
        return self._write_register(self.REG_CONFIGURATION, config)
    
    def calibrate(self, max_current: float) -> bool:
        """
        校准INA226
        
        Args:
            max_current: 最大预期电流（安培）
            
        Returns:
            bool: 成功返回True
        """
        try:
            # 计算Current LSB = max_current / 32768
            self.current_lsb = max_current / 32768.0
            
            # 计算校准寄存器值
            # Cal = 0.00512 / (Current_LSB * R_shunt)
            self.calibration_value = int(0.00512 / (self.current_lsb * self.shunt_resistance))
            
            # Power LSB = 25 * Current LSB
            self.power_lsb = 25 * self.current_lsb
            
            logger.info(f"校准参数: Current LSB={self.current_lsb:.6f}A, "
                       f"Power LSB={self.power_lsb:.6f}W, "
                       f"Cal=0x{self.calibration_value:04X}")
            
            # 写入校准寄存器
            return self._write_register(self.REG_CALIBRATION, self.calibration_value)
            
        except Exception as e:
            logger.error(f"校准异常: {e}")
            return False
    
    def read_shunt_voltage(self) -> Optional[float]:
        """
        读取分流电压
        
        Returns:
            float: 分流电压（伏特），失败返回None
        """
        raw_value = self._read_register(self.REG_SHUNT_VOLTAGE)
        if raw_value is not None:
            # 转换为有符号16位数
            if raw_value > 32767:
                raw_value -= 65536
            # LSB = 2.5μV
            voltage = raw_value * 2.5e-6
            return voltage
        return None
    
    def read_bus_voltage(self) -> Optional[float]:
        """
        读取总线电压
        
        Returns:
            float: 总线电压（伏特），失败返回None
        """
        raw_value = self._read_register(self.REG_BUS_VOLTAGE)
        if raw_value is not None:
            # LSB = 1.25mV
            voltage = raw_value * 1.25e-3
            return voltage
        return None
    
    def read_current(self) -> Optional[float]:
        """
        读取电流
        
        Returns:
            float: 电流（安培），失败返回None
        """
        if self.current_lsb == 0:
            logger.error("未进行校准，无法读取电流")
            return None
            
        raw_value = self._read_register(self.REG_CURRENT)
        logger.debug(f"读取电流原始值: {raw_value}")
        if raw_value is not None:
            # 转换为有符号16位数
            if raw_value > 32767:
                raw_value -= 65536
            current = raw_value * self.current_lsb
            return current
        return None
    
    def read_power(self) -> Optional[float]:
        """
        读取功率
        
        Returns:
            float: 功率（瓦特），失败返回None
        """
        if self.power_lsb == 0:
            logger.error("未进行校准，无法读取功率")
            return None
            
        raw_value = self._read_register(self.REG_POWER)
        if raw_value is not None:
            power = raw_value * self.power_lsb
            return power
        return None
    
    def read_all(self) -> Optional[Dict[str, float]]:
        """
        读取所有测量值
        
        Returns:
            dict: 包含所有测量值的字典，失败返回None
        """
        try:
            shunt_voltage = self.read_shunt_voltage()
            bus_voltage = self.read_bus_voltage()
            current = self.read_current()
            power = self.read_power()
            
            if all(v is not None for v in [shunt_voltage, bus_voltage, current, power]):
                return {
                    'shunt_voltage': shunt_voltage,
                    'bus_voltage': bus_voltage,
                    'current': current,
                    'power': power,
                    'load_voltage': bus_voltage + shunt_voltage # type: ignore
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"读取所有数据异常: {e}")
            return None
    
    def initialize(self, max_current: float = 0.8192) -> bool:
        """
        初始化INA226（完整初始化流程）
        
        Args:
            max_current: 最大预期电流（安培），默认0.8192A
            
        Returns:
            bool: 成功返回True
        """
        # 清空I2C缓冲区
        self.ch341.flush()

        logger.info("开始初始化INA226...")
        
        # 1. 检查设备
        if not self.check_device():
            return False
        
        # 2. 复位设备
        if not self.reset():
            return False
        
        # 3. 配置设备
        if not self.configure():
            return False
        
        # 4. 校准设备
        if not self.calibrate(max_current):
            return False
        
        logger.info("INA226初始化完成")
        return True
    
    def get_info(self) -> Dict[str, Any]:
        """
        获取设备信息
        
        Returns:
            dict: 设备信息
        """
        config = self._read_register(self.REG_CONFIGURATION)
        manufacturer_id = self._read_register(self.REG_MANUFACTURER_ID)
        die_id = self._read_register(self.REG_DIE_ID)
        
        return {
            'address': f"0x{self.address:02X}",
            'shunt_resistance': f"{self.shunt_resistance}Ω",
            'current_lsb': f"{self.current_lsb:.6f}A",
            'power_lsb': f"{self.power_lsb:.6f}W",
            'calibration': f"0x{self.calibration_value:04X}",
            'configuration': f"0x{config:04X}" if config else "N/A",
            'manufacturer_id': f"0x{manufacturer_id:04X}" if manufacturer_id else "N/A",
            'die_id': f"0x{die_id:04X}" if die_id else "N/A"
        }


def scan_ina226_devices(ch341_device: CH341Device) -> list:
    """
    扫描I2C总线上的INA226设备
    
    Args:
        ch341_device: CH341设备实例
        
    Returns:
        list: 发现的INA226设备地址列表
    """
    devices = []
    
    # INA226可能的地址范围 (根据A0, A1引脚配置)
    possible_addresses = [
        0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47,
        0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F
    ]
    
    logger.info("扫描INA226设备...")
    
    for addr in possible_addresses:
        try:
            ina226 = INA226(ch341_device, addr)
            if ina226.check_device(silent=True):  # 使用静默模式
                devices.append(addr)
                logger.info(f"发现INA226设备: 0x{addr:02X}")
        except Exception as e:
            logger.debug(f"地址0x{addr:02X}检查失败: {e}")
    
    logger.info(f"扫描完成，发现{len(devices)}个INA226设备")
    return devices


if __name__ == "__main__":
    # 测试代码
    try:
        from ch341 import CH341Device
    except ImportError:
        from .ch341 import CH341Device
    
    try:
        with CH341Device(0) as ch341:
            print("开始测试INA226...")
            
            # 扫描INA226设备
            devices = scan_ina226_devices(ch341)
            if not devices:
                print("未发现INA226设备")
                exit(1)
            
            # 使用第一个发现的设备
            ina226 = INA226(ch341, devices[0], shunt_resistance=0.1)
            
            ch341.init_gpio('GPIO1', 'out')
            ch341.set_gpio('GPIO1', True)  # 使能电源
            
            # 初始化
            if ina226.initialize(max_current=3.2):
                print("INA226初始化成功")
                
                # 显示设备信息
                info = ina226.get_info()
                print("设备信息:")
                for key, value in info.items():
                    print(f"  {key}: {value}")
                
                # 连续测量
                print("\n开始连续测量（按Ctrl+C停止）：")
                try:
                    while True:
                        data = ina226.read_all()
                        if data:
                            print(f"总线电压: {data['bus_voltage']:.3f}V, "
                                  f"电流: {data['current']*1000:.3f}mA, "
                                  f"功率: {data['power']*1000:.3f}mW")
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\n测量结束")
            else:
                print("INA226初始化失败")
                
    except Exception as e:
        print(f"测试异常: {e}")
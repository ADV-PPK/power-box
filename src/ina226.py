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
        # 量程与PMOS自定义参数
        self.measurement_mode: str = 'fixed'  # 'fixed' | 'auto-range'
        self.alert_threshold_mv: float = 40.0
        self.vbus_nominal: float = 3.3
        # PMOS导通内阻按Vbus映射，默认3.3V时0.1Ω，可通过校准更新
        self.pmos_r_on_map: Dict[float, float] = {3.3: 0.1}
        # 上一次判定的量程状态（仅用于估计）: 'low' 使用R_shunt, 'high' 使用并联R
        self._last_range_state: Optional[str] = None
        # 首次读取前等待一次转换就绪，避免第一次读到0
        self._first_read_done = False

    # INA226 Mask/Enable 寄存器常量（近似，供配置ALERT使用）
    MASK_SOL_ENABLE = 0x8000  # 使能分流电压过压告警（Shunt Over-Voltage）
    MASK_ALERT_LATCH = 0x0004  # Latch 使能（实际位可能不同，按需调整）
        
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

    def _mv_to_shunt_counts(self, threshold_mv: float) -> int:
        """将mV阈值转换为INA226的分流电压寄存器计数（LSB=2.5µV）"""
        counts = int((threshold_mv * 1e-3) / 2.5e-6)
        # 限制在16位有符号范围
        if counts > 0x7FFF:
            counts = 0x7FFF
        if counts < -0x8000:
            counts = -0x8000
        return counts & 0xFFFF

    def _wait_conversion_ready(self, timeout: float = 0.05) -> bool:
        """等待一次转换完成（CNVR=1），超时返回False"""
        end_t = time.time() + max(0.0, timeout)
        CNVR_BIT = 0x0008
        while time.time() < end_t:
            val = self._read_register(self.REG_MASK_ENABLE)
            if val is not None and (val & CNVR_BIT):
                return True
            time.sleep(0.001)
        return False

    def _configure_alert_shunt_overvoltage(self, threshold_mv: float, latch: bool = True) -> bool:
        """配置ALERT在分流电压超过阈值时触发，用于PMOS导通控制"""
        try:
            mask = self.MASK_SOL_ENABLE
            if latch:
                mask |= self.MASK_ALERT_LATCH
            ok = self._write_register(self.REG_MASK_ENABLE, mask)
            ok2 = self._write_register(self.REG_ALERT_LIMIT, self._mv_to_shunt_counts(threshold_mv))
            return bool(ok and ok2)
        except Exception as e:
            logger.error(f"配置ALERT异常: {e}")
            return False

    def set_measurement_mode(self, mode: str, *, threshold_mv: Optional[float] = None, vbus_nominal: Optional[float] = None, latch: bool = True) -> bool:
        """
        设置工作模式

        Args:
            mode: 'fixed' 固定10Ω量程 | 'auto-range' 基于ALERT切换量程
            threshold_mv: 在auto-range下的分流电压阈值（mV），超过则ALERT低拉使PMOS导通
            vbus_nominal: 名义Vbus（用于选择PMOS R_on映射的key）
            latch: 是否使能告警锁存
        """
        mode = mode.lower()
        if mode not in ('fixed', 'auto-range'):
            logger.error("mode 需为 'fixed' 或 'auto-range'")
            return False
        if vbus_nominal is not None:
            self.vbus_nominal = float(vbus_nominal)
        if threshold_mv is not None:
            self.alert_threshold_mv = float(threshold_mv)
        self.measurement_mode = mode
        if mode == 'auto-range':
            return self._configure_alert_shunt_overvoltage(self.alert_threshold_mv, latch=latch)
        else:
            # 固定模式：关闭SOL功能（将掩码写0）
            try:
                return self._write_register(self.REG_MASK_ENABLE, 0x0000)
            except Exception:
                return True

    def set_pmos_r_on(self, vbus: float, r_on_ohm: float) -> None:
        """设置/更新指定Vbus下的PMOS导通内阻映射"""
        if r_on_ohm <= 0:
            raise INA226Exception("PMOS导通内阻必须为正数")
        self.pmos_r_on_map[float(vbus)] = float(r_on_ohm)

    def get_effective_shunt(self, vbus: Optional[float] = None, assume_high: Optional[bool] = None) -> float:
        """
        获取当前有效的分流电阻
        在auto-range下，若assume_high为True则返回并联后的等效电阻；否则返回基础分流电阻。
        这里不读取ALERT引脚状态，留作后续扩展（可通过GPIO或寄存器标志判定）。
        """
        if self.measurement_mode != 'auto-range':
            return self.shunt_resistance
        vkey = float(self.vbus_nominal if vbus is None else vbus)
        r_pmos = self.pmos_r_on_map.get(vkey, self.pmos_r_on_map.get(3.3, 0.1))
        if not assume_high:
            return self.shunt_resistance
        # 并联等效
        r_low = self.shunt_resistance
        r_eff = (r_low * r_pmos) / (r_low + r_pmos)
        return r_eff

    def calibrate_pmos_r_on(self, known_load_ohms: float, *, vbus_nominal: Optional[float] = None, force_threshold_mv: float = 0.5, settle_time: float = 0.2) -> Optional[float]:
        """
        通过已知负载校准PMOS导通内阻（在指定Vbus下）

        步骤：
        1) 将ALERT阈值设置得很低（force_threshold_mv），确保PMOS导通
        2) 等待稳定后，读取总线电压Vbus与分流电压Vshunt
        3) 由 I = Vbus / R_load 得到电流，计算等效分流电阻 R_eff = Vshunt / I
        4) 由 R_eff 与 R_shunt 反求 PMOS内阻 R_on
        5) 存入映射表（key为vbus_nominal）
        """
        if known_load_ohms <= 0:
            raise INA226Exception("已知负载阻值必须为正数")
        vkey = float(self.vbus_nominal if vbus_nominal is None else vbus_nominal)
        prev_mode = self.measurement_mode
        prev_threshold = self.alert_threshold_mv
        try:
            # 强制进入auto-range并设置极低阈值，让PMOS导通
            self.set_measurement_mode('auto-range', threshold_mv=force_threshold_mv, vbus_nominal=vkey, latch=True)
            time.sleep(settle_time)
            vbus = self.read_bus_voltage()
            vshunt = self.read_shunt_voltage()
            if vbus is None or vshunt is None:
                logger.error("校准读取失败：Vbus或Vshunt为空")
                return None
            i_load = vbus / known_load_ohms
            if i_load <= 0:
                logger.error("校准失败：电流为零或负")
                return None
            r_eff = vshunt / i_load
            r_shunt = self.shunt_resistance
            if r_eff >= r_shunt:
                logger.error("校准失败：等效电阻应小于基准分流电阻")
                return None
            r_on = (r_eff * r_shunt) / (r_shunt - r_eff)
            # 保存映射
            self.pmos_r_on_map[vkey] = r_on
            logger.info(f"校准完成：Vbus={vkey}V, PMOS R_on≈{r_on:.6f}Ω (R_eff≈{r_eff:.6f}Ω)")
            return r_on
        finally:
            # 恢复原模式/阈值
            if prev_mode == 'auto-range':
                self.set_measurement_mode('auto-range', threshold_mv=prev_threshold, vbus_nominal=vkey)
            else:
                self.set_measurement_mode('fixed')
    
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
            if not self._first_read_done:
                # 等待一次转换完成，避免初始化后第一次读到0
                self._wait_conversion_ready(timeout=0.06)
            shunt_voltage = self.read_shunt_voltage()
            bus_voltage = self.read_bus_voltage()
            if shunt_voltage is None or bus_voltage is None:
                return None
            # 在auto-range下，基于等效分流电阻计算电流与功率；否则沿用芯片寄存器换算
            if self.measurement_mode == 'auto-range':
                # 估计是否处于高量程：简单策略，若设定阈值存在，则以阈值为界近似判断
                # 因为PMOS导通后Vshunt会显著降低，这里使用“低于阈值的较小比例”作为高量程的迹象
                assume_high = shunt_voltage < (self.alert_threshold_mv * 1e-3 * 0.6)
                r_eff = self.get_effective_shunt(vbus=self.vbus_nominal, assume_high=assume_high)
                current = shunt_voltage / r_eff
                power = current * bus_voltage
                self._last_range_state = 'high' if assume_high else 'low'
            else:
                current = self.read_current()
                power = self.read_power()
                if current is None or power is None:
                    return None
            
            return {
                'shunt_voltage': shunt_voltage,
                'bus_voltage': bus_voltage,
                'current': current,
                'power': power,
                'load_voltage': bus_voltage + shunt_voltage # type: ignore
            }
            
            # 标记首次读取已完成
            self._first_read_done = True
                
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
        
        # 5. 若启用了 auto-range，重新配置ALERT阈值
        try:
            if getattr(self, 'measurement_mode', 'fixed') == 'auto-range':
                self._configure_alert_shunt_overvoltage(getattr(self, 'alert_threshold_mv', 40.0), latch=True)
        except Exception:
            # 忽略告警配置失败，不影响基本测量
            pass
        
        # 首次读取前的预热等待一次转换完成
        try:
            self._first_read_done = False
            self._wait_conversion_ready(timeout=0.06)
        except Exception:
            pass
        
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
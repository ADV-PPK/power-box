"""
继电器控制模块

通过CH341控制继电器，用于控制被测电源的开关。
支持多种继电器控制方式：GPIO直接控制、I2C IO扩展器控制等。
"""

import time
import logging
from enum import Enum
from typing import Optional, Dict, Any

# 导入CH341模块
try:
    from .ch341 import CH341Device, CH341Exception
except ImportError:
    from ch341 import CH341Device, CH341Exception

# 配置日志
logger = logging.getLogger(__name__)


class RelayException(Exception):
    """继电器相关异常"""
    pass


class RelayState(Enum):
    """继电器状态枚举"""
    OFF = 0
    ON = 1


class RelayControlMode(Enum):
    """继电器控制模式"""
    GPIO_DIRECT = "gpio_direct"  # GPIO直接控制
    I2C_PCF8574 = "i2c_pcf8574"  # PCF8574 I2C IO扩展器
    I2C_MCP23008 = "i2c_mcp23008"  # MCP23008 I2C IO扩展器


class RelayController:
    """继电器控制器基类"""
    
    def __init__(self, ch341_device: CH341Device):
        self.ch341 = ch341_device
        self.relays = {}  # 继电器状态记录
    
    def set_relay(self, relay_id: int, state: RelayState) -> bool:
        """设置继电器状态"""
        raise NotImplementedError
    
    def get_relay(self, relay_id: int) -> Optional[RelayState]:
        """获取继电器状态"""
        return self.relays.get(relay_id)
    
    def toggle_relay(self, relay_id: int) -> bool:
        """切换继电器状态"""
        current_state = self.get_relay(relay_id)
        if current_state == RelayState.ON:
            return self.set_relay(relay_id, RelayState.OFF)
        else:
            return self.set_relay(relay_id, RelayState.ON)


class GPIORelayController(RelayController):
    """GPIO直接控制继电器"""
    
    def __init__(self, ch341_device: CH341Device, pin_mapping: Dict[int, int]):
        """
        初始化GPIO继电器控制器
        
        Args:
            ch341_device: CH341设备实例
            pin_mapping: 继电器ID到GPIO引脚的映射 {relay_id: gpio_pin}
        """
        super().__init__(ch341_device)
        self.pin_mapping = pin_mapping
        
        # 初始化所有继电器为OFF状态
        for relay_id in pin_mapping.keys():
            self.relays[relay_id] = RelayState.OFF
        
        logger.info(f"初始化GPIO继电器控制器: {pin_mapping}")
    
    def set_relay(self, relay_id: int, state: RelayState) -> bool:
        """
        设置继电器状态
        
        Args:
            relay_id: 继电器ID
            state: 继电器状态
            
        Returns:
            bool: 成功返回True
        """
        if relay_id not in self.pin_mapping:
            logger.error(f"未知的继电器ID: {relay_id}")
            return False
        
        gpio_pin = self.pin_mapping[relay_id]
        
        try:
            # 设置GPIO引脚状态
            # 注意：继电器的高低电平逻辑可能需要根据硬件设计调整
            success = self.ch341.gpio_set(gpio_pin, state == RelayState.ON)
            
            if success:
                self.relays[relay_id] = state
                logger.info(f"继电器{relay_id}设置为{state.name}: GPIO{gpio_pin}")
                return True
            else:
                logger.error(f"设置继电器{relay_id}失败: GPIO{gpio_pin}")
                return False
                
        except Exception as e:
            logger.error(f"设置继电器异常: {e}")
            return False


class PCF8574RelayController(RelayController):
    """基于PCF8574 I2C IO扩展器的继电器控制"""
    
    DEFAULT_ADDRESS = 0x20
    
    def __init__(self, ch341_device: CH341Device, address: int = DEFAULT_ADDRESS,
                 pin_mapping: Dict[int, int] = None):
        """
        初始化PCF8574继电器控制器
        
        Args:
            ch341_device: CH341设备实例
            address: PCF8574的I2C地址
            pin_mapping: 继电器ID到PCF8574引脚的映射
        """
        super().__init__(ch341_device)
        self.address = address
        
        # 默认引脚映射
        if pin_mapping is None:
            pin_mapping = {0: 0, 1: 1, 2: 2, 3: 3}  # 最多4个继电器
        
        self.pin_mapping = pin_mapping
        self.output_state = 0xFF  # PCF8574初始状态（所有引脚高电平）
        
        # 初始化所有继电器为OFF状态
        for relay_id in pin_mapping.keys():
            self.relays[relay_id] = RelayState.OFF
        
        logger.info(f"初始化PCF8574继电器控制器: 地址0x{address:02X}, 映射{pin_mapping}")
    
    def _update_output(self) -> bool:
        """更新PCF8574输出状态"""
        try:
            return self.ch341.i2c_write(self.address, [self.output_state])
        except Exception as e:
            logger.error(f"更新PCF8574输出异常: {e}")
            return False
    
    def set_relay(self, relay_id: int, state: RelayState) -> bool:
        """
        设置继电器状态
        
        Args:
            relay_id: 继电器ID
            state: 继电器状态
            
        Returns:
            bool: 成功返回True
        """
        if relay_id not in self.pin_mapping:
            logger.error(f"未知的继电器ID: {relay_id}")
            return False
        
        pin = self.pin_mapping[relay_id]
        
        try:
            # 更新输出状态
            if state == RelayState.ON:
                # 清除对应位（低电平激活继电器）
                self.output_state &= ~(1 << pin)
            else:
                # 设置对应位（高电平关闭继电器）
                self.output_state |= (1 << pin)
            
            # 写入PCF8574
            if self._update_output():
                self.relays[relay_id] = state
                logger.info(f"继电器{relay_id}设置为{state.name}: PCF8574引脚{pin}")
                return True
            else:
                logger.error(f"设置继电器{relay_id}失败: PCF8574引脚{pin}")
                return False
                
        except Exception as e:
            logger.error(f"设置继电器异常: {e}")
            return False
    
    def read_inputs(self) -> Optional[int]:
        """
        读取PCF8574输入状态
        
        Returns:
            int: 输入状态字节，失败返回None
        """
        try:
            data = self.ch341.i2c_read(self.address, 1)
            if data and len(data) == 1:
                return data[0]
            else:
                return None
        except Exception as e:
            logger.error(f"读取PCF8574输入异常: {e}")
            return None
    
    def test_device(self) -> bool:
        """
        测试PCF8574设备是否可访问
        
        Returns:
            bool: 可访问返回True
        """
        try:
            # 尝试读取设备状态
            return self.read_inputs() is not None
        except Exception as e:
            logger.error(f"PCF8574设备测试异常: {e}")
            return False


class PowerRelay:
    """电源继电器控制类（高级封装）"""
    
    def __init__(self, controller: RelayController, relay_id: int = 0):
        """
        初始化电源继电器
        
        Args:
            controller: 继电器控制器实例
            relay_id: 继电器ID
        """
        self.controller = controller
        self.relay_id = relay_id
        self.is_enabled = False
        
        # 确保继电器初始状态为关闭
        self.disable()
        
        logger.info(f"初始化电源继电器: ID={relay_id}")
    
    def enable(self) -> bool:
        """
        打开电源（继电器导通）
        
        Returns:
            bool: 成功返回True
        """
        if self.controller.set_relay(self.relay_id, RelayState.ON):
            self.is_enabled = True
            logger.info(f"电源已打开: 继电器{self.relay_id}")
            return True
        else:
            logger.error(f"电源打开失败: 继电器{self.relay_id}")
            return False
    
    def disable(self) -> bool:
        """
        关闭电源（继电器断开）
        
        Returns:
            bool: 成功返回True
        """
        if self.controller.set_relay(self.relay_id, RelayState.OFF):
            self.is_enabled = False
            logger.info(f"电源已关闭: 继电器{self.relay_id}")
            return True
        else:
            logger.error(f"电源关闭失败: 继电器{self.relay_id}")
            return False
    
    def toggle(self) -> bool:
        """
        切换电源状态
        
        Returns:
            bool: 成功返回True
        """
        if self.is_enabled:
            return self.disable()
        else:
            return self.enable()
    
    def get_state(self) -> RelayState:
        """
        获取当前电源状态
        
        Returns:
            RelayState: 当前状态
        """
        state = self.controller.get_relay(self.relay_id)
        return state if state is not None else RelayState.OFF
    
    def pulse(self, duration: float = 0.1) -> bool:
        """
        脉冲控制（短暂打开后关闭）
        
        Args:
            duration: 脉冲持续时间（秒）
            
        Returns:
            bool: 成功返回True
        """
        try:
            if self.enable():
                time.sleep(duration)
                return self.disable()
            else:
                return False
        except Exception as e:
            logger.error(f"脉冲控制异常: {e}")
            return False


def create_relay_controller(ch341_device: CH341Device, 
                          mode: RelayControlMode = RelayControlMode.GPIO_DIRECT,
                          **kwargs) -> RelayController:
    """
    创建继电器控制器
    
    Args:
        ch341_device: CH341设备实例
        mode: 控制模式
        **kwargs: 额外参数
        
    Returns:
        RelayController: 继电器控制器实例
    """
    if mode == RelayControlMode.GPIO_DIRECT:
        pin_mapping = kwargs.get('pin_mapping', {0: 0})  # 默认继电器0映射到GPIO0
        return GPIORelayController(ch341_device, pin_mapping)
    
    elif mode == RelayControlMode.I2C_PCF8574:
        address = kwargs.get('address', PCF8574RelayController.DEFAULT_ADDRESS)
        pin_mapping = kwargs.get('pin_mapping', {0: 0})
        return PCF8574RelayController(ch341_device, address, pin_mapping)
    
    else:
        raise RelayException(f"不支持的继电器控制模式: {mode}")


def scan_pcf8574_devices(ch341_device: CH341Device) -> list:
    """
    扫描I2C总线上的PCF8574设备
    
    Args:
        ch341_device: CH341设备实例
        
    Returns:
        list: 发现的PCF8574设备地址列表
    """
    devices = []
    
    # PCF8574可能的地址范围
    possible_addresses = [0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
                         0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F]
    
    logger.info("扫描PCF8574设备...")
    
    for addr in possible_addresses:
        try:
            controller = PCF8574RelayController(ch341_device, addr)
            if controller.test_device():
                devices.append(addr)
                logger.info(f"发现PCF8574设备: 0x{addr:02X}")
        except Exception as e:
            logger.debug(f"地址0x{addr:02X}检查失败: {e}")
    
    logger.info(f"扫描完成，发现{len(devices)}个PCF8574设备")
    return devices


if __name__ == "__main__":
    # 测试代码
    try:
        from ch341 import CH341Device
    except ImportError:
        from .ch341 import CH341Device
    
    try:
        with CH341Device(0) as ch341:
            print("开始测试继电器控制...")
            
            # 尝试不同的控制模式
            controllers = []
            
            # 1. GPIO直接控制
            try:
                gpio_controller = create_relay_controller(
                    ch341, RelayControlMode.GPIO_DIRECT,
                    pin_mapping={0: 0, 1: 1}
                )
                controllers.append(("GPIO", gpio_controller))
                print("创建GPIO继电器控制器成功")
            except Exception as e:
                print(f"创建GPIO继电器控制器失败: {e}")
            
            # 2. PCF8574控制
            pcf8574_devices = scan_pcf8574_devices(ch341)
            if pcf8574_devices:
                try:
                    pcf8574_controller = create_relay_controller(
                        ch341, RelayControlMode.I2C_PCF8574,
                        address=pcf8574_devices[0],
                        pin_mapping={0: 0, 1: 1}
                    )
                    controllers.append(("PCF8574", pcf8574_controller))
                    print(f"创建PCF8574继电器控制器成功: 0x{pcf8574_devices[0]:02X}")
                except Exception as e:
                    print(f"创建PCF8574继电器控制器失败: {e}")
            
            # 测试每个控制器
            for name, controller in controllers:
                print(f"\\n测试{name}继电器控制器:")
                
                # 创建电源继电器
                power_relay = PowerRelay(controller, 0)
                
                print("  - 打开电源")
                power_relay.enable()
                time.sleep(1)
                
                print("  - 关闭电源")
                power_relay.disable()
                time.sleep(1)
                
                print("  - 脉冲控制")
                power_relay.pulse(0.5)
                
                print(f"  - 当前状态: {power_relay.get_state().name}")
            
            print("\\n继电器控制测试完成")
            
    except Exception as e:
        print(f"测试异常: {e}")
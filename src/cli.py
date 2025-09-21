"""
命令行接口模块

提供完整的命令行参数解析和功能调用接口，支持：
- 设备扫描和信息查询
- 电流/电压测量
- EEPROM读写操作
- 连续监测模式
"""

import argparse
import sys
import time
import json
import logging
import shlex
from typing import Optional, Dict, Any
from colorama import init, Fore, Style

# 初始化colorama（Windows颜色支持）
init(autoreset=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CommandLineInterface:
    """命令行接口类"""
    
    def __init__(self):
        self.parser: Any = None
        self.ch341: Any = None
        self.ina226: Any = None
        self.eeprom: Any = None
        self._interactive_active = False
        
        self._setup_parser()
    
    def _setup_parser(self):
        """设置命令行参数解析器"""
        self.parser = argparse.ArgumentParser(
            description='电流测试板卡上位机控制软件',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog='''
示例用法:
  %(prog)s scan                          # 扫描设备
  %(prog)s info                          # 显示设备信息
  %(prog)s measure                       # 单次测量
  %(prog)s monitor -t 5                  # 连续监测5秒
  %(prog)s monitor -s 1000 -f data.json # 监测1000次，保存到文件
  %(prog)s board-id                      # 读取板卡ID
  %(prog)s board-id -w "PWR-BOX-001"     # 写入板卡ID
  %(prog)s power on                      # 打开电源
  %(prog)s power off                     # 关闭电源
  %(prog)s power status                  # 查看电源状态
    %(prog)s mode --set auto --vbus 3.3   # 设置自动量程与名义Vbus
    %(prog)s calib --input-ohms 10        # 计算等效阻值(基于Vshunt/Vbus)
            '''
        )

        # 全局选项
        self.parser.add_argument('-v', '--verbose', action='store_true', help='详细输出模式')
        self.parser.add_argument('--device-index', type=int, default=0, help='CH341设备索引 (默认: 0)')
        self.parser.add_argument('--ina226-addr', type=str, default='0x40', help='INA226 I2C地址 (默认: 0x40)')
        self.parser.add_argument('--eeprom-addr', type=str, default='0x50', help='EEPROM I2C地址 (默认: 0x50)')
        self.parser.add_argument('--eeprom-type', type=str, default='24C02', help='EEPROM型号 (默认: 24C02)')
        self.parser.add_argument('--shunt-resistance', type=float, default=10, help='分流电阻阻值/欧姆 (默认: 10)')
        self.parser.add_argument('--max-current', type=float, default=0.8192, help='最大预期电流/安培 (默认: 0.8192)')
        self.parser.add_argument('-I', '--interactive', action='store_true', help='交互式模式：进入交互式命令行，可连续执行命令')

        # 子命令
        subparsers = self.parser.add_subparsers(dest='command', help='可用命令')

        # scan命令
        scan_parser = subparsers.add_parser('scan', help='扫描设备')
        scan_parser.add_argument('--type', choices=['all', 'ch341', 'ina226', 'eeprom'], default='all', help='扫描设备类型')
        scan_parser.add_argument('--eeprom-method', choices=['read_probe', 'write_test', 'class_test'], default='write_test', help='EEPROM扫描方法 (默认: read_probe)')

        # info命令
        subparsers.add_parser('info', help='显示设备信息')

        # measure命令
        measure_parser = subparsers.add_parser('measure', help='单次测量')
        measure_parser.add_argument('--format', choices=['table', 'json', 'csv'], default='table', help='输出格式')
        measure_parser.add_argument('--mode', choices=['fixed', 'auto'], help='测量量程模式：fixed 或 auto-range')
        measure_parser.add_argument('--vbus', type=float, help='名义Vbus电压，用于PMOS内阻映射')

        # monitor命令
        monitor_parser = subparsers.add_parser('monitor', help='连续监测')
        monitor_parser.add_argument('-t', '--time', type=float, help='监测时间/秒')
        monitor_parser.add_argument('-s', '--samples', type=int, help='监测次数')
        monitor_parser.add_argument('-i', '--interval', type=float, default=1.0, help='监测间隔/秒 (默认: 1.0)')
        monitor_parser.add_argument('-f', '--file', type=str, help='保存数据到文件')
        monitor_parser.add_argument('--format', choices=['table', 'json', 'csv'], default='table', help='输出格式')
        monitor_parser.add_argument('--mode', choices=['fixed', 'auto'], help='测量量程模式：fixed 或 auto-range')
        monitor_parser.add_argument('--vbus', type=float, help='名义Vbus电压，用于PMOS内阻映射')

        # board-id命令
        board_id_parser = subparsers.add_parser('board-id', help='板卡ID操作')
        board_id_parser.add_argument('-w', '--write', type=str, help='写入板卡ID')
        board_id_parser.add_argument('-a', '--address', type=str, default='0x00', help='EEPROM存储地址 (默认: 0x00)')

        # eeprom命令
        eeprom_parser = subparsers.add_parser('eeprom', help='EEPROM操作')
        eeprom_subparsers = eeprom_parser.add_subparsers(dest='eeprom_action')

        # eeprom read
        read_parser = eeprom_subparsers.add_parser('read', help='读取EEPROM')
        read_parser.add_argument('address', type=str, help='起始地址 (十六进制)')
        read_parser.add_argument('length', type=int, help='读取长度')
        read_parser.add_argument('--format', choices=['hex', 'ascii', 'raw'], default='hex', help='输出格式')

        # eeprom write
        write_parser = eeprom_subparsers.add_parser('write', help='写入EEPROM')
        write_parser.add_argument('address', type=str, help='起始地址 (十六进制)')
        write_parser.add_argument('data', type=str, help='要写入的数据')
        write_parser.add_argument('--format', choices=['hex', 'ascii'], default='ascii', help='数据格式')

        # eeprom dump
        dump_parser = eeprom_subparsers.add_parser('dump', help='转储EEPROM')
        dump_parser.add_argument('--start', type=str, default='0x00', help='起始地址 (默认: 0x00)')
        dump_parser.add_argument('--length', type=int, help='转储长度 (默认: 全部)')

        # power命令
        power_parser = subparsers.add_parser('power', help='电源控制')
        power_parser.add_argument('--pin', type=str, default='GPIO1', help='用于电源控制的GPIO引脚，示例: GPIO1 或 1 (默认: GPIO1)')
        power_subparsers = power_parser.add_subparsers(dest='power_action')
        power_subparsers.add_parser('on', help='打开电源')
        power_subparsers.add_parser('off', help='关闭电源')
        power_subparsers.add_parser('status', help='查看电源状态')

        # gpio命令
        gpio_parser = subparsers.add_parser('gpio', help='GPIO控制与查询')
        gpio_subparsers = gpio_parser.add_subparsers(dest='gpio_action')

        # gpio list
        gpio_subparsers.add_parser('list', help='列出支持的GPIO引脚')

        # gpio get
        gpio_get = gpio_subparsers.add_parser('get', help='读取GPIO电平')
        gpio_get.add_argument('--pin', required=True, help='GPIO引脚，如 GPIO1 或 1')

        # gpio set
        gpio_set = gpio_subparsers.add_parser('set', help='设置GPIO电平')
        gpio_set.add_argument('--pin', required=True, help='GPIO引脚，如 GPIO1 或 1')
        gpio_set.add_argument('--value', required=True, choices=['0', '1', 'low', 'high', 'false', 'true'], help='目标电平')
        gpio_set.add_argument('--direction', choices=['in', 'out'], default='out', help='方向（默认: out）')

        # gpio toggle
        gpio_toggle = gpio_subparsers.add_parser('toggle', help='翻转GPIO电平')
        gpio_toggle.add_argument('--pin', required=True, help='GPIO引脚，如 GPIO1 或 1')

        # gpio dir set
        gpio_dir = gpio_subparsers.add_parser('dir', help='设置GPIO方向')
        gpio_dir_sub = gpio_dir.add_subparsers(dest='dir_action')
        gpio_dir_set = gpio_dir_sub.add_parser('set', help='设置方向')
        gpio_dir_set.add_argument('--pin', required=True, help='GPIO引脚，如 GPIO1 或 1')
        gpio_dir_set.add_argument('--value', required=True, choices=['in', 'out'], help='方向 in/out')

        # gpio watch
        gpio_watch = gpio_subparsers.add_parser('watch', help='持续监视GPIO电平变化')
        gpio_watch.add_argument('--pin', required=True, help='GPIO引脚，如 GPIO1 或 1')
        gpio_watch.add_argument('-i', '--interval', type=float, default=0.5, help='轮询间隔秒 (默认: 0.5)')
        gpio_watch.add_argument('-t', '--time', type=float, help='持续时间秒')
        gpio_watch.add_argument('-n', '--samples', type=int, help='采样次数')
        gpio_watch.add_argument('--changes-only', action='store_true', help='仅在电平变化时输出')

        # 顶层 mode 命令（等同 ina226 mode）
        mode_parser = subparsers.add_parser('mode', help='设置/查询量程模式（简写）')
        mode_parser.add_argument('--set', choices=['fixed', 'auto'], help='设置模式：fixed 或 auto')
        mode_parser.add_argument('--vbus', type=float, help='名义Vbus电压')

        # 顶层 calib 命令（统一计算等效阻值）
        calib_parser = subparsers.add_parser('calib', help='根据 Vshunt/Vbus 与已知输入电阻计算等效阻值')
        calib_parser.add_argument('--input-ohms', type=float, required=True, help='输入/负载电阻(Ω)，用于比例计算')
        calib_parser.add_argument('--samples', type=int, default=8, help='采样次数用于平均 (默认: 8)')
        calib_parser.add_argument('--interval', type=float, default=0.05, help='采样间隔秒 (默认: 0.05)')
        calib_parser.add_argument('--alert-pin', type=str, default='GPIO0', help='用于读取ALERT状态的GPIO引脚 (默认: GPIO0)')
        calib_parser.add_argument('--read-alert', action='store_true', help='读取ALERT状态用于解释结果（默认不读取，以免干扰调试）')
    
    def _parse_address(self, addr_str: str) -> int:
        """解析地址字符串（支持十六进制）"""
        if addr_str.startswith('0x') or addr_str.startswith('0X'):
            return int(addr_str, 16)
        else:
            return int(addr_str)
    
    def _print_error(self, message: str):
        """打印错误信息"""
        print(f"{Fore.RED}错误: {message}{Style.RESET_ALL}")
    
    def _print_success(self, message: str):
        """打印成功信息"""
        print(f"{Fore.GREEN}成功: {message}{Style.RESET_ALL}")
    
    def _print_info(self, message: str):
        """打印信息"""
        print(f"{Fore.CYAN}信息: {message}{Style.RESET_ALL}")
    
    def _print_warning(self, message: str):
        """打印警告"""
        print(f"{Fore.YELLOW}警告: {message}{Style.RESET_ALL}")

    def _normalize_gpio_pin(self, pin: str) -> str:
        """规范化GPIO引脚名称: '1' -> 'GPIO1', 'gpio2' -> 'GPIO2'"""
        s = str(pin).strip()
        if s.upper().startswith('GPIO'):
            num = s[4:]
            return f"GPIO{num}"
        if s.isdigit():
            return f"GPIO{s}"
        return s
    
    def _init_devices(self, args) -> bool:
        """初始化设备"""
        try:
            import ch341
            import ina226
            import eeprom
        except ImportError:
            # 如果直接导入失败，尝试相对导入（当作为包导入时）
            try:
                from . import ch341  # type: ignore
                from . import ina226  # type: ignore
                from . import eeprom  # type: ignore
            except ImportError:
                # 最后尝试添加当前目录到路径
                import sys
                import os
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                import ch341
                import ina226
                import eeprom

        try:
            # 交互模式下若设备已打开，则复用并补齐从属对象
            if self.ch341 and getattr(self.ch341, 'is_opened', False):
                try:
                    if self.ina226 is None:
                        ina226_addr = self._parse_address(args.ina226_addr)
                        self.ina226 = ina226.INA226(self.ch341, ina226_addr, args.shunt_resistance)
                    if self.eeprom is None:
                        eeprom_addr = self._parse_address(args.eeprom_addr)
                        self.eeprom = eeprom.EEPROM(self.ch341, eeprom_addr, args.eeprom_type)
                except Exception:
                    pass
                return True

            # 检查CH341设备
            device_count = ch341.get_device_count()
            if device_count == 0:
                self._print_error("未检测到CH341设备")
                return False
            
            if args.device_index >= device_count:
                self._print_error(f"设备索引超出范围: {args.device_index} (最大: {device_count-1})")
                return False
            
            # 打开CH341设备
            self.ch341 = ch341.CH341Device(args.device_index)
            if not self.ch341.open():
                self._print_error(f"无法打开CH341设备 {args.device_index}")
                return False
            
            # 初始化INA226
            ina226_addr = self._parse_address(args.ina226_addr)
            self.ina226 = ina226.INA226(self.ch341, ina226_addr, args.shunt_resistance)
            
            # 初始化EEPROM
            eeprom_addr = self._parse_address(args.eeprom_addr)
            self.eeprom = eeprom.EEPROM(self.ch341, eeprom_addr, args.eeprom_type)
            
            return True
            
        except Exception as e:
            self._print_error(f"设备初始化失败: {e}")
            return False
    
    def _cleanup_devices(self):
        """清理设备资源"""
        # 交互模式中不在每个命令后关闭，等待REPL结束统一清理
        if self._interactive_active:
            return
        if self.ch341:
            try:
                self.ch341.close()
            except Exception:
                pass
    
    def cmd_scan(self, args) -> int:
        """扫描设备命令"""
        try:
            import ch341
            import ina226
            import eeprom
        except ImportError:
            # 如果直接导入失败，尝试相对导入
            try:
                from . import ch341  # type: ignore
                from . import ina226  # type: ignore
                from . import eeprom  # type: ignore
            except ImportError:
                # 最后尝试添加当前目录到路径
                import sys
                import os
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                import ch341
                import ina226
                import eeprom
        
        if not self._init_devices(args):
            return 1
        
        try:
            print(f"{Fore.BLUE}=== 设备扫描结果 ==={Style.RESET_ALL}")
            
            if args.type in ['all', 'ina226']:
                devices = ina226.scan_ina226_devices(self.ch341)
                print(f"INA226设备数量: {len(devices)}")
                for addr in devices:
                    print(f"  地址 0x{addr:02X}: INA226")
            
            if args.type in ['all', 'eeprom']:
                devices = eeprom.scan_eeprom_devices(self.ch341, args.eeprom_method)
                print(f"EEPROM设备数量: {len(devices)} (方法: {args.eeprom_method})")
                for addr in devices:
                    print(f"  地址 0x{addr:02X}: EEPROM")
            
            if args.type in ['all', 'ch341']:
                device_count = ch341.get_device_count()
                print(f"CH341设备数量: {device_count}")
                for i in range(device_count):
                    print(f"  设备 {i}: 可用")
            
            return 0
            
        except Exception as e:
            self._print_error(f"扫描失败: {e}")
            return 1
        finally:
            self._cleanup_devices()
    
    def cmd_info(self, args) -> int:
        """显示设备信息命令"""
        if not self._init_devices(args):
            return 1
        
        try:
            print(f"{Fore.BLUE}=== 设备信息 ==={Style.RESET_ALL}")
            
            # CH341信息
            print("CH341设备:")
            print(f"  设备索引: {args.device_index}")
            print(f"  状态: {'已连接' if self.ch341.is_opened else '未连接'}")
            
            # INA226信息
            if self.ina226.check_device():
                self.ina226.initialize(args.max_current)
                info = self.ina226.get_info()
                print("INA226设备:")
                for key, value in info.items():
                    print(f"  {key}: {value}")
            else:
                print("INA226设备: 未检测到")
            
            # EEPROM信息
            if self.eeprom.test_device():
                info = self.eeprom.get_info()
                print("EEPROM设备:")
                for key, value in info.items():
                    print(f"  {key}: {value}")
            else:
                print("EEPROM设备: 未检测到")

            return 0
            
        except Exception as e:
            self._print_error(f"获取信息失败: {e}")
            return 1
        finally:
            self._cleanup_devices()
    
    def cmd_measure(self, args) -> int:
        """单次测量命令"""
        if not self._init_devices(args):
            return 1
        
        try:
            if not self.ina226.check_device():
                self._print_error("INA226设备未检测到")
                return 1
            
            if not self.ina226.initialize(args.max_current):
                self._print_error("INA226初始化失败")
                return 1
            # 可选的量程模式设置（不再涉及阈值）
            try:
                if getattr(args, 'mode', None):
                    mode = 'auto-range' if args.mode == 'auto' else 'fixed'
                    vbus = getattr(args, 'vbus', None)
                    self.ina226.set_measurement_mode(mode, vbus_nominal=vbus)
            except Exception as e:
                self._print_warning(f"设置量程模式失败: {e}")
            
            data = self.ina226.read_all()
            if not data:
                self._print_error("测量失败")
                return 1
            
            # 格式化输出
            if args.format == 'json':
                print(json.dumps(data, indent=2))
            elif args.format == 'csv':
                print("shunt_voltage,bus_voltage,current,power,load_voltage")
                print(f"{data['shunt_voltage']},{data['bus_voltage']},{data['current']},{data['power']},{data['load_voltage']}")
            else:  # table
                print(f"{Fore.BLUE}=== 测量结果 ==={Style.RESET_ALL}")
                print(f"分流电压: {data['shunt_voltage']:.6f} V")
                print(f"总线电压: {data['bus_voltage']:8.3f} V")
                print(f"负载电压: {data['load_voltage']:8.3f} V")
                print(f"电流:     {data['current']:.6f} A")
                print(f"功率:     {data['power']:.6f} W")
            
            return 0
            
        except Exception as e:
            self._print_error(f"测量失败: {e}")
            return 1
        finally:
            self._cleanup_devices()
    
    def cmd_monitor(self, args) -> int:
        """连续监测命令"""
        if not self._init_devices(args):
            return 1
        
        try:
            if not self.ina226.check_device():
                self._print_error("INA226设备未检测到")
                return 1
            
            if not self.ina226.initialize(args.max_current):
                self._print_error("INA226初始化失败")
                return 1
            # 可选的量程模式设置（不再涉及阈值）
            try:
                if getattr(args, 'mode', None):
                    mode = 'auto-range' if args.mode == 'auto' else 'fixed'
                    vbus = getattr(args, 'vbus', None)
                    self.ina226.set_measurement_mode(mode, vbus_nominal=vbus)
            except Exception as e:
                self._print_warning(f"设置量程模式失败: {e}")
            
            # 确定监测参数
            if args.time and args.samples:
                self._print_error("不能同时指定时间和次数")
                return 1
            
            if args.time:
                max_samples = int(args.time / args.interval)
                duration_mode = True
            elif args.samples:
                max_samples = args.samples
                duration_mode = False
            else:
                # 无限监测
                max_samples = float('inf')
                duration_mode = False
            
            # 数据存储
            measurements = []
            
            # 开始监测
            print(f"{Fore.BLUE}=== 开始连续监测 ==={Style.RESET_ALL}")
            if duration_mode:
                print(f"监测时间: {args.time} 秒, 间隔: {args.interval} 秒")
            elif args.samples:
                print(f"监测次数: {args.samples}, 间隔: {args.interval} 秒")
            else:
                print(f"连续监测, 间隔: {args.interval} 秒 (按Ctrl+C停止)")
            
            if args.format == 'table':
                print(f"{'时间':<20} {'总线电压(V)':<12} {'电流(A)':<10} {'功率(W)':<10}")
                print("-" * 60)
            
            start_time = time.time()
            sample_count = 0
            
            try:
                while sample_count < max_samples:
                    current_time = time.time()
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    data = self.ina226.read_all()
                    if not data:
                        self._print_warning("测量失败，跳过此次")
                        continue
                    
                    # 添加时间戳
                    data['timestamp'] = timestamp
                    data['elapsed'] = current_time - start_time
                    measurements.append(data)
                    
                    # 输出数据
                    if args.format == 'json':
                        print(json.dumps(data))
                    elif args.format == 'csv':
                        if sample_count == 0:
                            print("timestamp,elapsed,shunt_voltage,bus_voltage,current,power,load_voltage")
                        print(f"{timestamp},{data['elapsed']:.3f},{data['shunt_voltage']},{data['bus_voltage']},{data['current']},{data['power']},{data['load_voltage']}")
                    else:  # table
                        print(f"{timestamp} {data['bus_voltage']:>10.3f} {data['current']:>8.3f} {data['power']:>8.3f}")
                    
                    sample_count += 1
                    
                    if sample_count < max_samples:
                        time.sleep(args.interval)
                        
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}监测被用户中断{Style.RESET_ALL}")
            
            # 保存数据到文件
            if args.file and measurements:
                try:
                    with open(args.file, 'w', encoding='utf-8') as f:
                        json.dump(measurements, f, indent=2, ensure_ascii=False)
                    self._print_success(f"数据已保存到 {args.file}")
                except Exception as e:
                    self._print_error(f"保存文件失败: {e}")
            
            print(f"\n监测完成，共采集 {len(measurements)} 个数据点")
            return 0
            
        except Exception as e:
            self._print_error(f"监测失败: {e}")
            return 1
        finally:
            self._cleanup_devices()
    
    def cmd_board_id(self, args) -> int:
        """板卡ID操作命令"""
        if not self._init_devices(args):
            return 1
        
        try:
            if not self.eeprom.test_device():
                self._print_error("EEPROM设备未检测到")
                return 1
            
            address = self._parse_address(args.address)
            
            if args.write:
                # 写入板卡ID
                if self.eeprom.write_board_id(args.write, address):
                    self._print_success(f"板卡ID已写入: {args.write}")
                    return 0
                else:
                    self._print_error("写入板卡ID失败")
                    return 1
            else:
                # 读取板卡ID
                board_id = self.eeprom.read_board_id(address)
                if board_id is None:
                    self._print_error("读取板卡ID失败")
                    return 1
                if board_id == "":
                    print("板卡ID: (未设置)")
                    return 0
                print(f"板卡ID: {board_id}")
                return 0
            
        except Exception as e:
            self._print_error(f"板卡ID操作失败: {e}")
            return 1
        finally:
            self._cleanup_devices()
    
    def cmd_eeprom(self, args) -> int:
        """EEPROM操作命令"""
        if not self._init_devices(args):
            return 1
        
        try:
            if not self.eeprom.test_device():
                self._print_error("EEPROM设备未检测到")
                return 1
            
            if args.eeprom_action == 'read':
                address = self._parse_address(args.address)
                data = self.eeprom.read_bytes(address, args.length)
                if data:
                    if args.format == 'hex':
                        hex_str = ' '.join(f'{b:02X}' for b in data)
                        print(hex_str)
                    elif args.format == 'ascii':
                        ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data)
                        print(ascii_str)
                    else:  # raw
                        sys.stdout.buffer.write(data)
                    return 0
                else:
                    self._print_error("读取EEPROM失败")
                    return 1
            
            elif args.eeprom_action == 'write':
                address = self._parse_address(args.address)
                if args.format == 'hex':
                    # 解析十六进制数据
                    hex_str = args.data.replace(' ', '').replace('0x', '')
                    if len(hex_str) % 2 != 0:
                        self._print_error("十六进制数据长度必须为偶数")
                        return 1
                    data = bytes.fromhex(hex_str)
                else:  # ascii
                    data = args.data.encode('utf-8')
                
                if self.eeprom.write_bytes(address, data):
                    self._print_success(f"已写入{len(data)}字节到地址0x{address:04X}")
                    return 0
                else:
                    self._print_error("写入EEPROM失败")
                    return 1
            
            elif args.eeprom_action == 'dump':
                start_addr = self._parse_address(args.start)
                length = args.length if args.length else None
                hex_dump = self.eeprom.dump_hex(start_addr, length)
                if hex_dump:
                    print(hex_dump)
                    return 0
                else:
                    self._print_error("转储EEPROM失败")
                    return 1
            
            else:
                self._print_error("未知的EEPROM操作")
                return 1
            
        except Exception as e:
            self._print_error(f"EEPROM操作失败: {e}")
            return 1
        finally:
            self._cleanup_devices()
    
    def cmd_gpio(self, args) -> int:
        """GPIO 控制与查询命令"""
        if not self._init_devices(args):
            return 1
        try:
            action = getattr(args, 'gpio_action', None)
            if not action:
                self._print_error('未指定GPIO操作 (list|get|set|toggle|dir|watch)')
                return 1

            # 获取支持的GPIO列表
            try:
                gpios = list(getattr(self.ch341, 'supported_gpios', []) or [])
            except Exception:
                gpios = []

            if action == 'list':
                if gpios:
                    print('可用GPIO: ' + ', '.join(gpios))
                else:
                    print('未获取到GPIO列表')
                return 0

            # 对 get/set 操作进行引脚规范化与校验
            pin_raw = getattr(args, 'pin', None)
            if not pin_raw:
                self._print_error('必须提供 --pin')
                return 1
            pin = self._normalize_gpio_pin(pin_raw)
            if gpios and pin not in gpios:
                self._print_error(f"不支持的GPIO引脚: {pin}. 可用: {', '.join(gpios)}")
                return 1

            if action == 'get':
                try:
                    val = self.ch341.get_gpio(pin)
                    state = '高(1)' if val else '低(0)'
                    print(f"{pin}: {state}")
                    return 0
                except Exception as e:
                    self._print_error(f"读取失败: {e}")
                    return 1

            if action == 'set':
                v = str(getattr(args, 'value', '')).lower()
                high_values = {'1', 'high', 'true'}
                low_values = {'0', 'low', 'false'}
                if v not in high_values | low_values:
                    self._print_error('无效的 --value, 需为 0/1/low/high/false/true')
                    return 1
                target = v in high_values
                direction = getattr(args, 'direction', 'out')
                try:
                    if direction and hasattr(self.ch341, 'init_gpio'):
                        self.ch341.init_gpio(pin, direction)
                except Exception:
                    # 忽略方向设置失败，仍尝试设置电平
                    pass
                try:
                    self.ch341.set_gpio(pin, target)
                    # 读回确认
                    try:
                        rb = self.ch341.get_gpio(pin)
                        state = '高(1)' if rb else '低(0)'
                        print(f"{pin} 已设置为 {state}")
                    except Exception:
                        print(f"{pin} 已设置为 {'高(1)' if target else '低(0)'}")
                    return 0
                except Exception as e:
                    self._print_error(f"设置失败: {e}")
                    return 1

            if action == 'toggle':
                try:
                    cur = self.ch341.get_gpio(pin)
                except Exception as e:
                    self._print_error(f"读取当前电平失败: {e}")
                    return 1
                target = not bool(cur)
                try:
                    # 确保为输出
                    try:
                        if hasattr(self.ch341, 'init_gpio'):
                            self.ch341.init_gpio(pin, 'out')
                    except Exception:
                        pass
                    self.ch341.set_gpio(pin, target)
                    rb = self.ch341.get_gpio(pin)
                    state = '高(1)' if rb else '低(0)'
                    print(f"{pin} 翻转 -> {state}")
                    return 0
                except Exception as e:
                    self._print_error(f"翻转失败: {e}")
                    return 1

            if action == 'dir':
                dir_action = getattr(args, 'dir_action', None)
                if dir_action != 'set':
                    self._print_error('需指定 dir set --pin ... --value in|out')
                    return 1
                val = str(getattr(args, 'value', '')).lower()
                if val not in {'in', 'out'}:
                    self._print_error('方向必须为 in 或 out')
                    return 1
                try:
                    if hasattr(self.ch341, 'init_gpio'):
                        ok = self.ch341.init_gpio(pin, val)
                    else:
                        ok = False
                    if not ok:
                        self._print_error('设置方向失败')
                        return 1
                    print(f"{pin} 方向已设置为 {val}")
                    return 0
                except Exception as e:
                    self._print_error(f"设置方向异常: {e}")
                    return 1

            if action == 'watch':
                interval = float(getattr(args, 'interval', 0.5) or 0.5)
                max_time = getattr(args, 'time', None)
                max_samples = getattr(args, 'samples', None)
                changes_only = bool(getattr(args, 'changes_only', False))
                if max_time and max_samples:
                    self._print_error('不能同时指定 --time 与 --samples')
                    return 1
                count = 0
                start = time.time()
                last = None
                try:
                    print(f"开始监视 {pin} (间隔 {interval}s){'，仅变化输出' if changes_only else ''}")
                    while True:
                        try:
                            val = self.ch341.get_gpio(pin)
                        except Exception as e:
                            self._print_error(f"读取失败: {e}")
                            return 1
                        if last is None or (not changes_only) or (val != last):
                            ts = time.strftime('%H:%M:%S')
                            state = '高(1)' if val else '低(0)'
                            print(f"{ts} {pin}={state}")
                            last = val
                        count += 1
                        if max_samples and count >= max_samples:
                            break
                        if max_time and (time.time() - start) >= max_time:
                            break
                        time.sleep(interval)
                    return 0
                except KeyboardInterrupt:
                    print("\n已停止监视")
                    return 0

            self._print_error('未知的GPIO操作')
            return 1
        finally:
            self._cleanup_devices()

    def cmd_power(self, args) -> int:
        """电源控制命令"""
        if not self._init_devices(args):
            return 1
        
        try:
            # 解析并规范化引脚名称
            pin_arg = getattr(args, 'pin', 'GPIO1')
            pin = f"GPIO{pin_arg}" if isinstance(pin_arg, str) and pin_arg.isdigit() else (pin_arg if str(pin_arg).upper().startswith('GPIO') else f"GPIO{pin_arg}")

            # 校验引脚是否受支持
            try:
                gpios = getattr(self.ch341, 'supported_gpios', None)
                if isinstance(gpios, list):
                    if pin not in gpios:
                        self._print_error(f"不支持的GPIO引脚: {pin}. 可用: {', '.join(gpios)}")
                        return 1
            except Exception:
                pass

            if args.power_action == 'on':
                # 通过选定GPIO打开电源 (高电平)
                try:
                    if hasattr(self.ch341, 'init_gpio'):
                        self.ch341.init_gpio(pin, 'out')
                except Exception:
                    pass
                self.ch341.set_gpio(pin, True)
                self._print_success("电源已打开")
                return 0
            
            elif args.power_action == 'off':
                # 通过选定GPIO关闭电源 (低电平)
                try:
                    if hasattr(self.ch341, 'init_gpio'):
                        self.ch341.init_gpio(pin, 'out')
                except Exception:
                    pass
                self.ch341.set_gpio(pin, False)
                self._print_success("电源已关闭")
                return 0
            
            elif args.power_action == 'status':
                # 读取选定GPIO状态
                try:
                    status = self.ch341.get_gpio(pin)
                    state_str = "开启" if status else "关闭"
                    print(f"电源状态: {state_str}")
                    return 0
                except Exception as e:
                    self._print_error(f"读取电源状态失败: {e}")
                    return 1
            
            else:
                self._print_error("未知的电源操作")
                return 1
                
        except Exception as e:
            self._print_error(f"电源控制失败: {e}")
            return 1
        finally:
            self._cleanup_devices()


    def cmd_mode(self, args) -> int:
        """顶层模式设置命令，等同于 `ina226 mode`"""
        if not self._init_devices(args):
            return 1
        try:
            if not self.ina226.check_device():
                self._print_error("INA226设备未检测到")
                return 1
            if not self.ina226.initialize(getattr(args, 'max_current', 0.8192)):
                self._print_error("INA226初始化失败")
                return 1
            set_mode = getattr(args, 'set', None)
            vbus = getattr(args, 'vbus', None)
            if set_mode:
                mode = 'auto-range' if set_mode == 'auto' else 'fixed'
                ok = self.ina226.set_measurement_mode(mode, vbus_nominal=vbus)
                if not ok:
                    self._print_error('设置量程模式失败')
                    return 1
                self._print_success(f"已设置模式: {mode}, Vbus: {vbus if vbus is not None else self.ina226.vbus_nominal}V")
            # 显示当前状态
            mode_cur = getattr(self.ina226, 'measurement_mode', 'fixed')
            print(f"当前模式: {mode_cur}")
            print(f"名义Vbus(V): {self.ina226.vbus_nominal}")
            try:
                rmap = getattr(self.ina226, 'pmos_r_on_map', {})
                print(f"PMOS内阻映射: {json.dumps(rmap, ensure_ascii=False)}")
            except Exception:
                pass
            lrs = getattr(self.ina226, '_last_range_state', None)
            if lrs:
                print(f"最近量程判定: {lrs}")
            return 0
        finally:
            self._cleanup_devices()

    def cmd_calib(self, args) -> int:
        """统一校准：计算等效阻值 R_eq。
        - ALERT=高: R_eq 即为 Rshunt
        - ALERT=低: R_eq 为 Rpmos||Rshunt
        """
        if not self._init_devices(args):
            return 1
        try:
            if not self.ina226.check_device():
                self._print_error("INA226设备未检测到")
                return 1
            if not self.ina226.initialize(getattr(args, 'max_current', 0.8192)):
                self._print_error("INA226初始化失败")
                return 1

            rin = float(getattr(args, 'input_ohms'))
            samples = int(getattr(args, 'samples', 8) or 8)
            interval = float(getattr(args, 'interval', 0.05) or 0.05)
            alert_pin = self._normalize_gpio_pin(getattr(args, 'alert_pin', 'GPIO0'))

            # 切换为固定量程以避免量程切换影响测量稳定性
            prev_mode = getattr(self.ina226, 'measurement_mode', 'fixed')
            prev_vbus = getattr(self.ina226, 'vbus_nominal', None)
            try:
                if prev_mode != 'fixed':
                    try:
                        self.ina226.set_measurement_mode('fixed')
                    except Exception:
                        pass

                vs_sum = 0.0
                vb_sum = 0.0
                taken = 0
                for i in range(max(1, samples)):
                    data = self.ina226.read_all()
                    if not data:
                        continue
                    vs_sum += float(data.get('shunt_voltage', 0.0))
                    vb_sum += float(data.get('bus_voltage', 0.0))
                    taken += 1
                    if i < samples - 1:
                        time.sleep(interval)
                if taken == 0:
                    self._print_error('未能获得有效测量值')
                    return 1
                vshunt = vs_sum / taken
                vbus = vb_sum / taken
                if vbus == 0 or abs(vbus) < 1e-6:
                    self._print_error('Vbus测得为0，无法计算')
                    return 1
                req = rin * (vshunt / vbus)

                # 可选：读取 ALERT 状态（高=1，低=0）；默认不读取以避免干扰外部拉低调试
                alert_state = None
                if bool(getattr(args, 'read_alert', False)):
                    try:
                        if hasattr(self.ch341, 'get_gpio'):
                            alert_state = bool(self.ch341.get_gpio(alert_pin))
                    except Exception:
                        alert_state = None

                print(f"采样次数: {taken}")
                print(f"平均 Vshunt: {vshunt:.9f} V, 平均 Vbus: {vbus:.6f} V")
                self._print_success(f"计算得到 等效阻值 R_eq ≈ {req:.9f} Ω (Rin={rin}Ω)")

                if alert_state is True:
                    print('ALERT=高 -> R_eq 代表 Rshunt')
                elif alert_state is False:
                    print('ALERT=低 -> R_eq 代表 Rpmos 与 Rshunt 的并联值')

                return 0
            finally:
                try:
                    if prev_mode != 'fixed':
                        self.ina226.set_measurement_mode(prev_mode, vbus_nominal=prev_vbus)
                except Exception:
                    pass
        finally:
            self._cleanup_devices()

    def _repl(self, base_args) -> int:
        """交互式命令行：复用全局参数，连续执行子命令"""
        # 启动交互模式并初始化一次设备
        self._interactive_active = True
        if not self._init_devices(base_args):
            self._interactive_active = False
            return 1
        # 构造基础全局参数（优先放在前面，后续输入覆盖）
        base_argv = []
        try:
            if getattr(base_args, 'verbose', False):
                base_argv.append('--verbose')
            if getattr(base_args, 'device_index', None) is not None:
                base_argv += ['--device-index', str(base_args.device_index)]
            if getattr(base_args, 'ina226_addr', None):
                base_argv += ['--ina226-addr', str(base_args.ina226_addr)]
            if getattr(base_args, 'eeprom_addr', None):
                base_argv += ['--eeprom-addr', str(base_args.eeprom_addr)]
            if getattr(base_args, 'eeprom_type', None):
                base_argv += ['--eeprom-type', str(base_args.eeprom_type)]
            if getattr(base_args, 'shunt_resistance', None) is not None:
                base_argv += ['--shunt-resistance', str(base_args.shunt_resistance)]
            if getattr(base_args, 'max_current', None) is not None:
                base_argv += ['--max-current', str(base_args.max_current)]
        except Exception:
            pass

        print(f"{Fore.BLUE}进入交互式模式 (输入 help 查看帮助, exit/quit 退出){Style.RESET_ALL}")
        while True:
            try:
                line = input('power-box> ').strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not line:
                continue
            if line.lower() in ('exit', 'quit', 'q'):
                break
            if line.lower() in ('help', 'h', '?'):
                print('示例:')
                print('  scan')
                print('  info')
                print('  measure --format json')
                print('  monitor -t 5 -i 0.5')
                print('  eeprom read 0x00 16 --format hex')
                print('  power --pin GPIO1 on')
                print('  power status')
                print('  gpio list')
                print('  gpio get --pin GPIO1')
                print('  gpio set --pin GPIO1 --value 1 --direction out')
                print('  gpio toggle --pin GPIO1')
                print('  gpio dir set --pin GPIO1 --value out')
                print('  gpio watch --pin GPIO1 -i 0.5 --changes-only')
                print('  mode --set auto --vbus 3.3')
                print('  calib --input-ohms 10 --samples 16')
                continue

            try:
                tokens = shlex.split(line)
            except ValueError as e:
                self._print_error(f"解析命令失败: {e}")
                continue

            try:
                # 组合基础参数 + 本次命令；不带 --interactive
                argv = [*base_argv, *tokens]
                args = self.parser.parse_args(argv)

                # 设置日志级别（允许在 REPL 中切换 -v 时生效）
                if getattr(args, 'verbose', False):
                    logging.getLogger().setLevel(logging.DEBUG)
                else:
                    logging.getLogger().setLevel(logging.WARNING)

                if not args.command:
                    self.parser.print_help()
                    continue

                command_map = {
                    'scan': self.cmd_scan,
                    'info': self.cmd_info,
                    'measure': self.cmd_measure,
                    'monitor': self.cmd_monitor,
                    'board-id': self.cmd_board_id,
                    'eeprom': self.cmd_eeprom,
                    'power': self.cmd_power,
                    'gpio': self.cmd_gpio,
                    'mode': self.cmd_mode,
                    'calib': self.cmd_calib,
                }

                if args.command in command_map:
                    rc = command_map[args.command](args)
                    if rc not in (0, None):
                        print(f"退出码: {rc}")
                else:
                    self._print_error(f"未知命令: {args.command}")
            except SystemExit:
                # argparse 在错误时会调用 sys.exit；在 REPL 中捕获并继续
                continue
            except Exception as e:
                self._print_error(f"执行失败: {e}")

        # 退出与清理
        print(f"{Fore.BLUE}退出交互式模式{Style.RESET_ALL}")
        self._interactive_active = False
        try:
            self._cleanup_devices()
        except Exception:
            pass
        return 0
    
    def run(self, argv=None) -> int:
        """运行命令行接口"""
        args = None
        try:
            args = self.parser.parse_args(argv)
            
            # 设置日志级别
            if args.verbose:
                logging.getLogger().setLevel(logging.DEBUG)
            else:
                logging.getLogger().setLevel(logging.WARNING)
            
            # 交互式模式
            if getattr(args, 'interactive', False):
                return self._repl(args)

            # 检查命令
            if not args.command:
                self.parser.print_help()
                return 1
            
            # 执行对应命令
            command_map = {
                'scan': self.cmd_scan,
                'info': self.cmd_info,
                'measure': self.cmd_measure,
                'monitor': self.cmd_monitor,
                'board-id': self.cmd_board_id,
                'eeprom': self.cmd_eeprom,
                'power': self.cmd_power,
                'gpio': self.cmd_gpio,
                'mode': self.cmd_mode,
                'calib': self.cmd_calib,
            }
            
            if args.command in command_map:
                return command_map[args.command](args)
            else:
                self._print_error(f"未知命令: {args.command}")
                return 1
                
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}操作被用户中断{Style.RESET_ALL}")
            return 1
        except Exception as e:
            self._print_error(f"程序异常: {e}")
            if args is not None and getattr(args, 'verbose', False):
                import traceback
                traceback.print_exc()
            return 1


def main():
    """主函数"""
    cli = CommandLineInterface()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
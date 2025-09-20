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
        self.parser = None
        self.ch341 = None
        self.ina226 = None
        self.eeprom = None
        
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
            '''
        )
        
        # 全局选项
        self.parser.add_argument('-v', '--verbose', action='store_true',
                               help='详细输出模式')
        self.parser.add_argument('--device-index', type=int, default=0,
                               help='CH341设备索引 (默认: 0)')
        self.parser.add_argument('--ina226-addr', type=str, default='0x40',
                               help='INA226 I2C地址 (默认: 0x40)')
        self.parser.add_argument('--eeprom-addr', type=str, default='0x50',
                               help='EEPROM I2C地址 (默认: 0x50)')
        self.parser.add_argument('--eeprom-type', type=str, default='24C02',
                               help='EEPROM型号 (默认: 24C02)')
        self.parser.add_argument('--shunt-resistance', type=float, default=10,
                               help='分流电阻阻值/欧姆 (默认: 10)')
        self.parser.add_argument('--max-current', type=float, default=0.8192,
                               help='最大预期电流/安培 (默认: 0.8192)')
        
        # 子命令
        subparsers = self.parser.add_subparsers(dest='command', help='可用命令')
        
        # scan命令
        scan_parser = subparsers.add_parser('scan', help='扫描设备')
        scan_parser.add_argument('--type', choices=['all', 'ch341', 'ina226', 'eeprom'],
                               default='all', help='扫描设备类型')
        scan_parser.add_argument('--eeprom-method', choices=['read_probe', 'write_test', 'class_test'],
                               default='write_test', help='EEPROM扫描方法 (默认: read_probe)')
        
        # info命令
        info_parser = subparsers.add_parser('info', help='显示设备信息')
        
        # measure命令
        measure_parser = subparsers.add_parser('measure', help='单次测量')
        measure_parser.add_argument('--format', choices=['table', 'json', 'csv'],
                                  default='table', help='输出格式')
        
        # monitor命令
        monitor_parser = subparsers.add_parser('monitor', help='连续监测')
        monitor_parser.add_argument('-t', '--time', type=float,
                                  help='监测时间/秒')
        monitor_parser.add_argument('-s', '--samples', type=int,
                                  help='监测次数')
        monitor_parser.add_argument('-i', '--interval', type=float, default=1.0,
                                  help='监测间隔/秒 (默认: 1.0)')
        monitor_parser.add_argument('-f', '--file', type=str,
                                  help='保存数据到文件')
        monitor_parser.add_argument('--format', choices=['table', 'json', 'csv'],
                                  default='table', help='输出格式')
        
        # board-id命令
        board_id_parser = subparsers.add_parser('board-id', help='板卡ID操作')
        board_id_parser.add_argument('-w', '--write', type=str,
                                   help='写入板卡ID')
        board_id_parser.add_argument('-a', '--address', type=str, default='0x00',
                                   help='EEPROM存储地址 (默认: 0x00)')
        
        # eeprom命令
        eeprom_parser = subparsers.add_parser('eeprom', help='EEPROM操作')
        eeprom_subparsers = eeprom_parser.add_subparsers(dest='eeprom_action')
        
        # eeprom read
        read_parser = eeprom_subparsers.add_parser('read', help='读取EEPROM')
        read_parser.add_argument('address', type=str, help='起始地址 (十六进制)')
        read_parser.add_argument('length', type=int, help='读取长度')
        read_parser.add_argument('--format', choices=['hex', 'ascii', 'raw'],
                               default='hex', help='输出格式')
        
        # eeprom write
        write_parser = eeprom_subparsers.add_parser('write', help='写入EEPROM')
        write_parser.add_argument('address', type=str, help='起始地址 (十六进制)')
        write_parser.add_argument('data', type=str, help='要写入的数据')
        write_parser.add_argument('--format', choices=['hex', 'ascii'],
                                default='ascii', help='数据格式')
        
        # eeprom dump
        dump_parser = eeprom_subparsers.add_parser('dump', help='转储EEPROM')
        dump_parser.add_argument('--start', type=str, default='0x00',
                               help='起始地址 (默认: 0x00)')
        dump_parser.add_argument('--length', type=int,
                               help='转储长度 (默认: 全部)')
        
        # power命令
        power_parser = subparsers.add_parser('power', help='电源控制')
        power_parser.add_argument('--pin', type=str, default='GPIO1', help='用于电源控制的GPIO引脚，示例: GPIO1 或 1 (默认: GPIO1)')
        power_subparsers = power_parser.add_subparsers(dest='power_action')
        
        # power on
        on_parser = power_subparsers.add_parser('on', help='打开电源')
        
        # power off
        off_parser = power_subparsers.add_parser('off', help='关闭电源')
        
        # power status
        status_parser = power_subparsers.add_parser('status', help='查看电源状态')
    
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
    
    def _init_devices(self, args) -> bool:
        """初始化设备"""
        try:
            import ch341
            import ina226
            import eeprom 
        except ImportError:
            # 如果直接导入失败，尝试相对导入
            try:
                from . import ch341
                from . import ina226
                from . import eeprom
            except ImportError:
                # 最后尝试添加当前目录到路径
                import sys
                import os
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                import ch341
                import ina226
                import eeprom

        try:
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
        if self.ch341:
            self.ch341.close()
    
    def cmd_scan(self, args) -> int:
        """扫描设备命令"""
        try:
            import ch341
            import ina226
            import eeprom
        except ImportError:
            # 如果直接导入失败，尝试相对导入
            try:
                from . import ch341
                from . import ina226
                from . import eeprom
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
                print(f"总线电压: {data['bus_voltage']:.3f} V")
                print(f"负载电压: {data['load_voltage']:.3f} V")
                print(f"电流:     {data['current']:.3f} A")
                print(f"功率:     {data['power']:.3f} W")
            
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
    
    def run(self, argv=None) -> int:
        """运行命令行接口"""
        try:
            args = self.parser.parse_args(argv)
            
            # 设置日志级别
            if args.verbose:
                logging.getLogger().setLevel(logging.DEBUG)
            else:
                logging.getLogger().setLevel(logging.WARNING)
            
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
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1


def main():
    """主函数"""
    cli = CommandLineInterface()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
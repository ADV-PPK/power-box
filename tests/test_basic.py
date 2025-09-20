"""
测试用例模块

包含对各个模块的基本测试用例。
"""

import unittest
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestImports(unittest.TestCase):
    """测试模块导入"""
    
    def test_import_ch341(self):
        """测试CH341模块导入"""
        try:
            from ch341 import CH341Device, CH341Exception
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"CH341模块导入失败: {e}")
    
    def test_import_ina226(self):
        """测试INA226模块导入"""
        try:
            from ina226 import INA226, INA226Exception
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"INA226模块导入失败: {e}")
    
    def test_import_eeprom(self):
        """测试EEPROM模块导入"""
        try:
            from eeprom import EEPROM, EEPROMException
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"EEPROM模块导入失败: {e}")
    
    def test_import_cli(self):
        """测试CLI模块导入"""
        try:
            from cli import CommandLineInterface
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"CLI模块导入失败: {e}")


class TestCLI(unittest.TestCase):
    """测试命令行接口"""
    
    def setUp(self):
        from cli import CommandLineInterface
        self.cli = CommandLineInterface()
    
    def test_parser_creation(self):
        """测试解析器创建"""
        self.assertIsNotNone(self.cli.parser)
    
    def test_help_command(self):
        """测试帮助命令"""
        try:
            args = self.cli.parser.parse_args(['--help'])
        except SystemExit:
            # argparse在--help时会调用sys.exit()，这是正常行为
            pass
    
    def test_scan_command_parsing(self):
        """测试scan命令解析"""
        args = self.cli.parser.parse_args(['scan'])
        self.assertEqual(args.command, 'scan')
        self.assertEqual(args.type, 'all')
    
    def test_measure_command_parsing(self):
        """测试measure命令解析"""
        args = self.cli.parser.parse_args(['measure', '--format', 'json'])
        self.assertEqual(args.command, 'measure')
        self.assertEqual(args.format, 'json')
    
    def test_monitor_command_parsing(self):
        """测试monitor命令解析"""
        args = self.cli.parser.parse_args(['monitor', '-t', '10', '-i', '0.5'])
        self.assertEqual(args.command, 'monitor')
        self.assertEqual(args.time, 10.0)
        self.assertEqual(args.interval, 0.5)


if __name__ == '__main__':
    # 运行测试
    unittest.main()
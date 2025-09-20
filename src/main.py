"""
电流测试板卡上位机主程序

这是一个基于CH341 + INA226的电流测试板卡上位机软件。
主要功能包括：
- CH341 USB转I2C通信
- INA226电流/电压测量
- EEPROM访问板卡唯一识别码
- 继电器控制被测电源
- 完整的命令行接口

使用示例：
    python main.py scan                      # 扫描设备
    python main.py info                      # 显示设备信息
    python main.py measure                   # 单次测量
    python main.py monitor -t 10             # 监测10秒
    python main.py board-id                  # 读取板卡ID
"""

import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli import main


if __name__ == "__main__":
    sys.exit(main())
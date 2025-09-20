#!/usr/bin/env python3
"""
电流测试板卡上位机启动脚本
解决模块导入问题
"""

import sys
import os

# 将src目录添加到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

if __name__ == "__main__":
    # 导入并运行主程序
    from cli import main
    sys.exit(main())
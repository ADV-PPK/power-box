# 电流测试板卡上位机项目概览

## 项目完成情况 ✅

我已经为您创建了一个完整的基于 CH341 + INA226 的电流测试板卡上位机软件。

## 🎯 核心功能实现

### ✅ 硬件驱动模块
- **CH341 通信模块** (`src/ch341.py`)
  - USB转I2C通信接口
  - GPIO控制功能
  - 设备管理和异常处理

- **INA226 电流传感器驱动** (`src/ina226.py`)
  - 高精度电流/电压测量
  - 自动校准和配置
  - 支持连续和单次测量

- **EEPROM 访问模块** (`src/eeprom.py`)
  - 支持多种EEPROM型号 (24C02-24C256)
  - 板卡唯一识别码读写
  - 页写入优化和数据转储

- **继电器控制模块** (`src/relay.py`)
  - GPIO直接控制
  - PCF8574 I2C扩展器支持
  - 电源开关和脉冲控制

### ✅ 用户界面
- **命令行接口** (`src/cli.py`)
  - 完整的argparse参数解析
  - 彩色输出和错误处理
  - 多种输出格式 (table/json/csv)

- **主程序入口** (`src/main.py`)
  - 统一的程序入口点
  - 路径管理和模块导入

## 📂 项目结构

```
power-box/
├── src/                    # 源代码目录
│   ├── __init__.py        # 包初始化
│   ├── main.py            # 主程序入口
│   ├── cli.py             # 命令行接口
│   ├── ch341.py           # CH341驱动
│   ├── ina226.py          # INA226驱动  
│   ├── eeprom.py          # EEPROM访问
│   └── relay.py           # 继电器控制
├── tests/                  # 测试用例
│   └── test_basic.py      # 基础测试
├── docs/                   # 文档目录
│   ├── quick-start.md     # 快速使用指南
│   └── deployment.md      # 部署说明
├── requirements.txt        # Python依赖
├── pyproject.toml         # 项目配置
├── power-box.spec         # PyInstaller配置
├── build.bat              # 打包脚本
└── README.md              # 项目说明
```

## 🚀 使用方法

### 开发环境运行
```bash
# 安装依赖
pip install -r requirements.txt

# 扫描设备
python src/main.py scan

# 单次测量
python src/main.py measure

# 连续监测
python src/main.py monitor -t 10
```

### 打包为exe
```bash
# 自动打包
build.bat

# 手动打包
pyinstaller power-box.spec
```

## 💡 主要特性

### 🔧 硬件兼容性
- **CH341**: 支持USB转I2C通信和GPIO控制
- **INA226**: 双向电流监测，±81.9175A范围
- **EEPROM**: 支持24C系列，最大32KB容量  
- **继电器**: GPIO直接控制或I2C扩展器

### 📊 测量功能
- **电流测量**: 高精度双向电流监测
- **电压测量**: 分流电压和总线电压
- **功率计算**: 自动计算瞬时功率
- **连续采集**: 支持时间或次数限制的连续监测

### 💾 数据管理
- **实时显示**: 表格格式实时显示测量数据
- **数据导出**: 支持JSON、CSV格式导出
- **板卡管理**: EEPROM存储的唯一识别码

### ⚡ 控制功能
- **电源控制**: 继电器控制被测设备电源
- **安全保护**: 软件层面的设备保护机制
- **脉冲控制**: 支持定时的电源脉冲控制

## 🛠️ 配置选项

### 设备地址配置
```bash
--ina226-addr 0x40        # INA226 I2C地址
--eeprom-addr 0x50        # EEPROM I2C地址  
--eeprom-type 24C32       # EEPROM型号
```

### 测量参数配置
```bash
--shunt-resistance 0.1    # 分流电阻值(Ω)
--max-current 3.2         # 最大电流(A)
```

### 输出格式配置
```bash
--format table|json|csv   # 输出格式
-v, --verbose            # 详细输出模式
```

## 📋 命令参考

| 命令 | 功能 | 示例 |
|------|------|------|
| `scan` | 扫描设备 | `power-box scan` |
| `info` | 显示设备信息 | `power-box info` |
| `measure` | 单次测量 | `power-box measure` |
| `monitor` | 连续监测 | `power-box monitor -t 10` |
| `board-id` | 板卡ID操作 | `power-box board-id -w "PWR-001"` |
| `eeprom` | EEPROM操作 | `power-box eeprom dump` |
| `relay` | 继电器控制 | `power-box relay on` |

## 🔍 故障排除

### 常见问题及解决方案
1. **CH341设备未找到**: 检查驱动安装和USB连接
2. **INA226通信失败**: 检查I2C连线和供电
3. **EEPROM访问错误**: 确认型号和写保护状态
4. **继电器无响应**: 检查驱动电路和供电

### 调试工具
- 使用 `-v` 参数获取详细日志
- `scan` 命令检查设备连接状态
- `info` 命令查看设备配置信息

## 🎯 下一步建议

### 硬件准备
1. **获取CH341 DLL文件**
   - 从沁恒官网下载驱动包
   - 提取DLL文件到程序目录

2. **准备硬件连接**
   - 确保I2C连线正确 (SDA, SCL, GND, VCC)
   - 检查继电器驱动电路
   - 验证电源和地线连接

### 软件测试
1. **功能测试**
   ```bash
   # 测试基本功能
   python tests/test_basic.py
   
   # 实际硬件测试
   python src/main.py scan
   python src/main.py info
   ```

2. **性能测试**
   - 连续测量稳定性测试
   - 精度和重复性验证
   - 温度漂移测试

### 部署准备
1. **打包测试**
   ```bash
   # 执行打包
   build.bat
   
   # 测试可执行文件
   dist/power-box.exe --help
   ```

2. **文档完善**
   - 根据实际硬件更新配置说明
   - 添加具体的接线图和说明
   - 制作用户手册

## 📞 技术支持

这个项目已经包含了您需求的所有核心功能：
- ✅ CH341 USB转I2C通信
- ✅ INA226 电流测量
- ✅ EEPROM 板卡ID管理
- ✅ 继电器电源控制
- ✅ 完整的命令行界面
- ✅ 打包为独立exe文件

如有任何问题或需要进一步的定制化开发，欢迎随时联系！
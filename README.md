# 电流测试板卡上位机软件

这是一个基于 CH341 + INA226 的电流测试板卡上位机软件，支持 Windows 平台。

## 主要功能

- **电流/电压测量**: 使用 INA226 高精度电流传感器进行测量
- **EEPROM 访问**: 读取/写入板卡唯一识别码
- **继电器控制**: 控制被测电源的开关
- **命令行接口**: 提供完整的命令行操作界面
- **数据记录**: 支持连续监测和数据保存

## 硬件要求

- CH341 USB转I2C适配器
- INA226 电流监测芯片
- I2C EEPROM (24C02/24C04/24C08/24C16/24C32/24C64等)
- 继电器控制电路 (GPIO直接控制或PCF8574扩展)

## 软件依赖

- Python 3.8+
- pyusb
- pyserial
- colorama
- CH341 DLL库 (Windows)

## 安装说明

1. 安装Python依赖:
```bash
pip install -r requirements.txt
```

2. 安装CH341驱动程序并将DLL文件放在程序目录

3. 连接硬件设备

## 使用方法

### 扫描设备
```bash
python src/main.py scan
```

### 查看设备信息
```bash
python src/main.py info
```

### 单次测量
```bash
python src/main.py measure
```

### 连续监测
```bash
# 监测10秒
python src/main.py monitor -t 10

# 监测100次，每秒一次
python src/main.py monitor -s 100 -i 1

# 监测并保存数据
python src/main.py monitor -t 60 -f measurement_data.json
```

### 板卡ID操作
```bash
# 读取板卡ID
python src/main.py board-id

# 写入板卡ID
python src/main.py board-id -w "PWR-BOX-001"
```

### EEPROM操作
```bash
# 转储EEPROM内容
python src/main.py eeprom dump

# 读取指定地址
python src/main.py eeprom read 0x10 16

# 写入数据
python src/main.py eeprom write 0x20 "Hello World"
```

### 继电器控制
```bash
# 打开继电器
python src/main.py relay on

# 关闭继电器
python src/main.py relay off

# 脉冲控制(2秒)
python src/main.py relay pulse -d 2.0

# 查看状态
python src/main.py relay status
```

### 高级选项
```bash
# 指定设备参数
python src/main.py measure --ina226-addr 0x41 --shunt-resistance 0.05 --max-current 5.0

# 详细输出模式
python src/main.py -v info

# 使用不同的EEPROM类型
python src/main.py --eeprom-type 24C64 board-id
```

## 输出格式

支持多种输出格式：
- **table**: 表格格式 (默认)
- **json**: JSON格式
- **csv**: CSV格式

```bash
python src/main.py measure --format json
python src/main.py monitor -t 10 --format csv -f data.csv
```

## 打包为可执行文件

使用 PyInstaller 打包：
```bash
pip install pyinstaller
pyinstaller --onefile --console src/main.py -n power-box
```

## 配置说明

### INA226配置
- 默认I2C地址: 0x40
- 默认分流电阻: 0.1Ω
- 默认最大电流: 3.2A

### EEPROM配置  
- 默认I2C地址: 0x50
- 默认型号: 24C32
- 板卡ID存储地址: 0x00

### 继电器配置
- 默认控制模式: GPIO直接控制
- 默认继电器ID: 0
- 支持PCF8574 I2C扩展

## 故障排除

### 常见问题

1. **找不到CH341设备**
   - 检查CH341驱动是否正确安装
   - 确认设备已连接且工作正常
   - 尝试使用不同的USB端口

2. **INA226通信失败**
   - 检查I2C连线是否正确
   - 确认INA226地址设置
   - 检查供电是否正常

3. **EEPROM访问失败**
   - 检查EEPROM型号和地址
   - 确认写保护引脚状态
   - 检查I2C时钟频率

4. **继电器控制无响应**
   - 检查继电器驱动电路
   - 确认GPIO配置
   - 检查继电器供电

### 调试模式

使用 `-v` 参数启用详细输出：
```bash
python src/main.py -v scan
python src/main.py -v measure
```

## 技术支持

如有问题请联系：
- 邮箱: dev@adv-ppk.com  
- 项目主页: https://github.com/ADV-PPK/power-box

## 许可证

MIT License - 详见 LICENSE 文件

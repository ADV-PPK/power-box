# 电流测试板卡上位机软件

这是一个基于 CH341 + INA226 的电流测试板卡上位机软件，支持 Windows 平台。

## 主要功能

- **电流/电压测量**: 使用 INA226 高精度电流传感器进行测量
- **EEPROM 访问**: 读取/写入板卡唯一识别码
- **数据记录**: 支持连续监测和数据保存

## 硬件要求

- CH341 USB转I2C适配器
### 校准
在稳定接线与恒定负载条件下执行统一校准：
```bash
python src/main.py calib --input-ohms 10 --samples 16 --interval 0.05
# 可选：读取 ALERT 进行结果解释（默认不读取以避免干扰调试）
python src/main.py calib --input-ohms 10 --read-alert
```
- 基于比例关系 R_eq/Rin = Vshunt/Vbus 计算等效阻值 R_eq。
- 若能读取 CH341 `P0`(或指定引脚) 与 INA226 `ALERT` 的连线状态：
   - ALERT=高: R_eq 即 Rshunt
   - ALERT=低: R_eq 为 Rpmos 与 Rshunt 的并联
- `--read-alert`: 可选，读取 `ALERT` 状态用于解释结果；默认不读取以避免将用于调试的输出引脚切换为输入。
- `--alert-pin`: 可选，指定 `ALERT` 读取引脚（默认 `GPIO0`）。

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

### 电源控制（通过GPIO）
```bash
# 打开/关闭电源（默认GPIO1）
python src/main.py power on
python src/main.py power off

# 指定用于控制电源的GPIO引脚
python src/main.py power --pin GPIO1 on
python src/main.py power --pin 1 off

# 查看电源状态
python src/main.py power status
```

### GPIO 命令
```bash
# 列出支持的GPIO
python src/main.py gpio list

# 读取/设置电平
python src/main.py gpio get --pin GPIO1
python src/main.py gpio set --pin GPIO1 --value 1 --direction out

# 翻转电平
python src/main.py gpio toggle --pin GPIO1

# 设置方向
python src/main.py gpio dir set --pin GPIO1 --value out

# 监视电平变化
python src/main.py gpio watch --pin GPIO1 -i 0.5 --changes-only
```

### 量程模式（INA226）
```bash
# 查看当前模式与名义Vbus
python src/main.py mode

# 设置为自动量程，并指定名义Vbus（用于PMOS内阻映射）
python src/main.py mode --set auto --vbus 3.3

# 固定量程
python src/main.py mode --set fixed

```
```

测量命令也可直接带模式/名义Vbus参数：
```bash
python src/main.py measure --mode auto --vbus 3.3
python src/main.py monitor -t 10 --mode fixed
```

提示：硬件连接中 CH341 的 `P0` 建议与 INA226 的 `ALERT` 相连。
- 调试阶段：可通过外部拉低 `P0` 强制触发量程切换并观测行为。
- 量产阶段：将 `P0` 作为输入用于检测 `ALERT` 状态；CLI 不再提供阈值相关参数。


### 交互式模式
```bash
# 进入交互式命令行，可连续执行命令
python src/main.py -I

# 在提示符下直接输入子命令
scan
info
power on
gpio list
gpio set --pin GPIO1 --value 1
gpio watch --pin GPIO1 -i 0.2 --changes-only
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

### GPIO/电源配置
- 默认用于电源控制的GPIO: GPIO1（可通过 `--pin` 指定）
- 支持的GPIO列表视硬件型号而定，使用 `gpio list` 查看

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

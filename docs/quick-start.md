# 快速使用指南

## 系统要求

- **操作系统**: Windows 7/8/10/11 (32位或64位)
- **Python**: 3.8或更高版本 (仅开发环境需要)
- **硬件**: CH341 + INA226 电流测试板卡

## 快速开始

### 1. 准备工作

1. **安装CH341驱动程序**
   - 从南京沁恒官网下载CH341驱动
   - 或使用Windows自动识别的驱动

2. **连接硬件**
   - 将CH341适配器插入USB端口
   - 确认设备管理器中显示CH341设备

### 2. 使用预编译版本（推荐）

1. **下载可执行文件**
   - 下载 `power-box.exe`
   - 下载对应的CH341 DLL文件

2. **放置DLL文件**
   ```
   power-box.exe 同目录下需要有：
   - CH341DLL.DLL (32位系统)
   - CH341DLLA64.DLL (64位系统)
   ```

3. **测试连接**
   ```cmd
   power-box.exe scan
   ```

### 3. 使用Python源码版本

1. **安装依赖**
   ```cmd
   pip install -r requirements.txt
   ```

2. **运行程序**
   ```cmd
   python src/main.py scan
   ```

## 基本操作

### 扫描设备
```cmd
# 扫描所有设备
power-box.exe scan

# 只扫描特定类型设备
power-box.exe scan --type ina226
```

### 查看设备信息
```cmd
power-box.exe info
```

### 电流测量
```cmd
# 单次测量
power-box.exe measure

# 连续监测10秒
power-box.exe monitor -t 10

# 监测100次，每0.5秒一次
power-box.exe monitor -s 100 -i 0.5

# 保存数据到文件
power-box.exe monitor -t 60 -f data.json
```

### 板卡ID管理
```cmd
# 读取板卡ID
power-box.exe board-id

# 写入板卡ID
power-box.exe board-id -w "PWR-BOX-001"
```

### 电源控制（通过GPIO）
```cmd
# 使用默认引脚(GPIO1)打开电源
power-box.exe power on

# 关闭电源
power-box.exe power off

# 指定用于控制电源的GPIO引脚
power-box.exe power --pin GPIO1 on
power-box.exe power --pin 1 off

# 查看当前电源状态
power-box.exe power status
```

### GPIO 控制
```cmd
# 列出支持的GPIO
power-box.exe gpio list

# 读取GPIO电平
power-box.exe gpio get --pin GPIO1

# 设置GPIO电平（并可指定方向）
power-box.exe gpio set --pin GPIO1 --value 1 --direction out
power-box.exe gpio set --pin 1 --value low

# 翻转GPIO电平
power-box.exe gpio toggle --pin GPIO1

# 设置GPIO方向
power-box.exe gpio dir set --pin GPIO1 --value out

# 监视GPIO电平变化
power-box.exe gpio watch --pin GPIO1 -i 0.5 --changes-only
power-box.exe gpio watch --pin 1 -n 20
```

### 交互式模式
```cmd
# 进入交互式命令行
power-box.exe -I

# 交互模式中可直接输入子命令，例如：
scan
info
power on
gpio list
gpio set --pin GPIO1 --value 1
gpio watch --pin GPIO1 -i 0.2 --changes-only
```

### 量程模式与校准

设置/查询量程模式（INA226）：
```cmd
power-box.exe mode                 
power-box.exe mode --set auto --vbus 3.3
power-box.exe mode --set fixed
```

测量命令也支持带入模式/名义Vbus：
```cmd
power-box.exe measure --mode auto --vbus 3.3
power-box.exe monitor -t 5 --mode fixed
```

统一校准命令：
```cmd
power-box.exe calib --input-ohms 10 --samples 16 --interval 0.05
# 可选：读取 ALERT 解释结果（默认不读取）
power-box.exe calib --input-ohms 10 --read-alert
```
若能读取 ALERT：ALERT=高 => Rshunt；ALERT=低 => Rpmos||Rshunt。

提示：如果将 CH341 的 `P0` 与 INA226 的 `ALERT` 相连，则：
- 调试时可通过外部拉低 `P0` 来模拟阈值切换；
- 量产时将 `P0` 作为输入用于检测 `ALERT`，CLI 不提供阈值调节参数。

## 常见问题

### Q: 提示"未检测到CH341设备"
**解决方案:**
1. 检查USB连接
2. 确认CH341驱动已安装
3. 尝试不同的USB端口
4. 检查设备管理器中是否有未知设备

### Q: INA226通信失败
**解决方案:**
1. 检查I2C连线 (SDA、SCL、GND、VCC)
2. 确认INA226供电正常 (3.3V或5V)
3. 检查I2C地址设置 (默认0x40)
4. 使用万用表测试连线

### Q: EEPROM访问失败
**解决方案:**
1. 确认EEPROM型号和地址
2. 检查写保护引脚 (WP) 是否接地
3. 确认EEPROM供电正常
4. 尝试不同的EEPROM型号参数

### Q: 电源/GPIO 控制不工作
**解决方案:**
1. 检查继电器供电
2. 确认继电器驱动电路或被控电路连接正确
3. 使用 `gpio list/get/set` 测试GPIO状态
4. 使用 `power status` 查看电源控制GPIO电平

## 高级配置

### 自定义设备地址
```cmd
# 使用不同的INA226地址
power-box.exe --ina226-addr 0x41 measure

# 使用不同的EEPROM地址和型号
power-box.exe --eeprom-addr 0x51 --eeprom-type 24C64 board-id
```

### 自定义电流参数
```cmd
# 设置分流电阻和最大电流
power-box.exe --shunt-resistance 0.05 --max-current 5.0 measure
```

### 输出格式
```cmd
# JSON格式输出
power-box.exe measure --format json

# CSV格式输出
power-box.exe monitor -t 10 --format csv -f data.csv
```

### 详细调试信息
```cmd
# 启用详细输出
power-box.exe -v info
power-box.exe -v scan
```

## 数据分析

### 使用Excel分析CSV数据
1. 使用CSV格式保存数据
2. 在Excel中打开CSV文件
3. 创建图表分析电流变化趋势

### 使用Python分析JSON数据
```python
import json
import matplotlib.pyplot as plt

# 读取数据
with open('data.json', 'r') as f:
    data = json.load(f)

# 提取时间和电流数据
times = [d['elapsed'] for d in data]
currents = [d['current'] for d in data]

# 绘制图表
plt.plot(times, currents)
plt.xlabel('Time (s)')
plt.ylabel('Current (A)')
plt.title('Current vs Time')
plt.show()
```

## 批处理自动化

### 创建测试脚本
```batch
@echo off
echo 开始电流测试...

rem 读取板卡ID
for /f "tokens=*" %%i in ('power-box.exe board-id') do set BOARD_ID=%%i
echo 板卡ID: %BOARD_ID%

rem 打开电源
power-box.exe power on
echo 电源已打开

rem 等待稳定
timeout /t 2 /nobreak

rem 测量电流
power-box.exe monitor -t 10 -f test_data.json
echo 测量完成

rem 关闭电源
power-box.exe power off
echo 电源已关闭

echo 测试结束
pause
```

## 技术支持

- 📧 邮箱: dev@adv-ppk.com
- 🌐 项目主页: https://github.com/ADV-PPK/power-box
- 📖 完整文档: 查看 README.md
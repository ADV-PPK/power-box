# 部署说明

## 打包为可执行文件

### 方法1: 使用批处理脚本（推荐）

直接运行 `build.bat` 脚本：
```cmd
build.bat
```

这个脚本会自动：
1. 检查并安装PyInstaller
2. 安装项目依赖
3. 清理之前的构建文件
4. 使用spec配置文件打包
5. 测试生成的可执行文件

### 方法2: 手动打包

1. 安装PyInstaller:
```cmd
pip install pyinstaller
```

2. 安装项目依赖:
```cmd
pip install -r requirements.txt
```

3. 使用spec文件打包:
```cmd
pyinstaller power-box.spec
```

4. 或者使用命令行参数打包:
```cmd
pyinstaller --onefile --console --name power-box src/main.py
```

### 方法3: 简单打包

最简单的打包方式：
```cmd
pyinstaller --onefile src/main.py
```

## 依赖文件

打包时需要确保以下文件在正确位置：

### CH341 DLL文件
根据系统架构复制对应的DLL文件到打包目录：
- `CH341DLL.DLL` (32位系统)
- `CH341DLLA64.DLL` (64位系统)

可从以下位置获取：
- CH341官方驱动包
- Windows系统目录
- 项目libs目录（需要手动下载）

### 运行时依赖
确保目标系统已安装：
- Microsoft Visual C++ Redistributable
- CH341驱动程序

## 部署结构

推荐的部署目录结构：
```
power-box/
├── power-box.exe           # 主程序
├── CH341DLL.DLL           # CH341驱动库(32位)
├── CH341DLLA64.DLL        # CH341驱动库(64位)
├── README.txt             # 使用说明
└── examples/              # 示例文件夹
    ├── sample_config.json
    └── sample_data.csv
```

## 发布注意事项

1. **版本信息**: 更新 `src/__init__.py` 中的版本号
2. **测试**: 在不同Windows版本上测试可执行文件
3. **文档**: 提供详细的使用说明和故障排除指南
4. **授权**: 确保包含适当的许可证信息

## 安装包制作

可使用以下工具制作安装包：
- NSIS (Nullsoft Scriptable Install System)
- Inno Setup
- WiX Toolset

### NSIS脚本示例
```nsis
; power-box安装脚本
Name "PowerBox电流测试上位机"
OutFile "power-box-installer.exe"
InstallDir "$PROGRAMFILES\PowerBox"

Section
  SetOutPath $INSTDIR
  File "dist\power-box.exe"
  File "CH341DLL.DLL"
  File "CH341DLLA64.DLL"
  File "README.txt"
  
  CreateDirectory "$SMPROGRAMS\PowerBox"
  CreateShortCut "$SMPROGRAMS\PowerBox\PowerBox.lnk" "$INSTDIR\power-box.exe"
  CreateShortCut "$DESKTOP\PowerBox.lnk" "$INSTDIR\power-box.exe"
  
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PowerBox" "DisplayName" "PowerBox电流测试上位机"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PowerBox" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\*.*"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\PowerBox\*.*"
  RMDir "$SMPROGRAMS\PowerBox"
  Delete "$DESKTOP\PowerBox.lnk"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PowerBox"
SectionEnd
```

## 数字签名

为了提高软件的可信度，建议对可执行文件进行数字签名：

1. 获取代码签名证书
2. 使用signtool.exe进行签名：
```cmd
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com power-box.exe
```

## 自动化构建

可以使用GitHub Actions等CI/CD服务自动化构建和发布过程：

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: windows-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pyinstaller
    - name: Build executable
      run: pyinstaller power-box.spec
    - name: Upload artifact
      uses: actions/upload-artifact@v2
      with:
        name: power-box-exe
        path: dist/power-box.exe
```
@echo off
rem 电流测试板卡上位机打包脚本
rem 使用PyInstaller将Python程序打包成独立的exe文件

echo 开始打包电流测试板卡上位机...

rem 检查是否安装了PyInstaller
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo 正在安装PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo PyInstaller安装失败！
        pause
        exit /b 1
    )
)

rem 检查是否安装了依赖包
echo 检查依赖包...
pip install -r requirements.txt
if errorlevel 1 (
    echo 依赖包安装失败！
    pause
    exit /b 1
)

rem 清理之前的构建
echo 清理之前的构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__

rem 使用spec文件打包
echo 开始打包...
pyinstaller power-box.spec
if errorlevel 1 (
    echo 打包失败！
    pause
    exit /b 1
)

rem 检查打包结果
if exist dist\power-box.exe (
    echo 打包成功！
    echo 可执行文件位置: dist\power-box.exe
    echo 文件大小:
    dir dist\power-box.exe
) else (
    echo 打包失败，未找到可执行文件！
    pause
    exit /b 1
)

rem 测试可执行文件
echo 测试可执行文件...
dist\power-box.exe --help
if errorlevel 1 (
    echo 可执行文件测试失败！
) else (
    echo 可执行文件测试成功！
)

echo 打包完成！
pause
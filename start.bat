@echo off
chcp 65001 >nul
cd /d %~dp0
echo ============================================================
echo   企业知识产权管理系统 IPMS
echo ============================================================
echo.
where python >nul 2>nul
if %errorlevel%==0 (
  python server.py 8770
) else (
  echo 未检测到 python，请先安装 Python 3.8 及以上版本
  pause
)

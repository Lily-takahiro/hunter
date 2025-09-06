@echo off
echo コンピューターのIPアドレスを確認中...
echo.
ipconfig | findstr "IPv4"
echo.
echo 上記のIPアドレスのいずれかを使用してスマホからアクセスしてください
echo 例: http://192.168.1.100:5000
echo.
pause

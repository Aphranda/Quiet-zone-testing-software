# LCD_LINK

LCD74000F 链路箱独立控制包，已从主程序中拆出，可单独安装和运行。

## 包含内容

- `lcd_link.controller`：LCD74000F TCP/IP 和串口通信控制器。
- `lcd_link.routing`：S 参数到 `CONFigure:LINK ...` 命令的路由，以及常用链路命令列表。
- `lcd_link.service`：简单链路服务封装。
- `lcd_link.window`：独立 PySide6 控制窗口。

## 运行控制窗口

在本目录执行：

```powershell
python -m pip install -e .
python -m lcd_link
```

或安装后执行：

```powershell
lcd-link-control
```

也可以从项目根目录直接运行源码入口：

```powershell
python LCD_LINK/src/lcd_link/app.py
```

默认连接参数：

- TCP/IP：`192.168.1.113:7`
- 串口：`COM3 @ 115200`
- 超时：`2000 ms`

## 代码调用示例

```python
from lcd_link import Lcd74000fSwitchBoxConfig, Lcd74000fSwitchBoxController

controller = Lcd74000fSwitchBoxController(
    Lcd74000fSwitchBoxConfig(ip_address="192.168.1.113", tcp_port=7)
)
info = controller.connect()
print(info)
controller.send_command("CONFigure:LINK H, VNA1")
controller.disconnect()
```

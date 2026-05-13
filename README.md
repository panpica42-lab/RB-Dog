# Quadruped Dev SDK

四足机器人二次开发版本 C++ SDK。

本项目根据官方《四足机器人二次开发版本开发手册 V1.0》整理，SDK 运行在控制板内，通过 UDP 与机器狗扩展网口通信，提供状态查询、运动控制、动作命令和 IMU 数据读取能力。

## 1. 环境要求

官方测试环境：

- 控制板：香橙派 5Pro
- 操作系统：Ubuntu 20.04
- SDK 语言：C++
- JSON 依赖：jsoncpp

安装依赖：

```bash
sudo apt install libjsoncpp-dev
```

## 2. 网络连接

推荐将控制链路和调试链路分成两个网络：

- 控制板有线网口连接机器狗扩展网口，只负责 SDK 与机器狗之间的 UDP 通信。
- 控制板 Wi-Fi 连接现场网络，电脑也连接同一个现场网络；SSH、网页控制台和网页推流都通过这个 Wi-Fi 地址访问控制板。
- 掌机遥控器继续连接机器狗自带 Wi-Fi，作为机器狗原厂遥控链路。

调试阶段可以临时查看控制板 Wi-Fi IP；正式部署到客户现场时，建议在现场路由器或 DHCP 服务器中给控制板 Wi-Fi MAC 绑定固定 IP。这样 SSH、VS Code Remote-SSH、网页控制台和网页推流地址都保持稳定。客户现场更换 Wi-Fi、路由器或 IP 段时，只需要重新确认或重新绑定控制板 Wi-Fi IP；机器狗有线控制网段仍保持 `192.168.96.x`。

机器狗有线控制网络默认配置：

| 设备 | IP 地址 |
| --- | --- |
| 机器狗 | `192.168.96.2` |
| 控制板有线网口 | `192.168.96.3` |
| UDP 端口 | `8080` |

硬件连接步骤：

1. 用网线连接控制板与机器狗扩展网口。
2. 确保电脑与控制板连接到同一个 Wi-Fi，例如公司 Wi-Fi 或客户现场 Wi-Fi。
3. 长按机器狗背部电源按键 3 秒以上开机。
4. 等待机器狗和控制板启动完成。
5. 听到“机器狗启动已完成”后，通过控制板 Wi-Fi IP SSH 登录控制板。
6. 登录控制板后，再运行 SDK 程序或 WS 网关。

在控制板上查看 Wi-Fi IP：

```bash
hostname -I
```

也可以查看具体无线网卡：

```bash
ip addr show wlan0
```

部署时可记录 `wlan0` 的 `link/ether` 地址，并在路由器中做 DHCP 固定地址绑定。例如：

```text
link/ether 28:2d:06:39:a0:16
```

上面的 MAC 地址只是当前调试设备示例，客户现场应以实际控制板 `wlan0` 显示为准。

SSH 示例：

```bash
ssh orangepi@192.168.110.82
```

其中 `192.168.110.82` 是示例 Wi-Fi 地址，实际地址以控制板当前连接的 Wi-Fi 网络为准。不要把办公室调试 IP 写死到客户现场配置中。

VS Code Remote-SSH 可在电脑本机的 SSH 配置中同时保留 Wi-Fi 和网线两个入口：

```sshconfig
Host orangepi-wifi
  HostName 10.0.50.236
  User orangepi

Host orangepi-lan
  HostName 192.168.97.2
  User orangepi
```

- `orangepi-wifi`：走控制板 Wi-Fi，推荐用于 SSH、VS Code、网页控制台和网页推流。
- `orangepi-lan`：走电脑直连控制板的网线，用于没有 Wi-Fi 或现场网络不可用时调试。

如果客户现场给控制板 Wi-Fi 绑定了新的固定 IP，只需要修改 `orangepi-wifi` 的 `HostName`。

## 3. 编译 SDK

进入 SDK 目录：

```bash
cd <sdk目录>
```

清理旧产物：

```bash
make clean
```

编译 SDK 和示例程序：

```bash
make
```

编译完成后会生成：

```text
lib/libquadruped_sdk.a
bin/example
bin/keyboard_test
bin/imu_client_example
```

## 4. 运行示例

运行示例前，请确保机器狗 3 米范围内无障碍物，并且不要打开遥控器。

### 4.1 自动动作示例

```bash
./bin/example
```

该程序会依次执行复位回零、前进、后退、左移、右移、左转、右转、趴下等动作。

### 4.2 键盘控制示例

```bash
./bin/keyboard_test
```

常用按键：

| 按键 | 功能 |
| --- | --- |
| `r` | 复位回零 |
| `w` / `s` | 前进 / 后退 |
| `a` / `d` | 左移 / 右移 |
| `q` / `e` | 左转 / 右转 |
| `t` | 急停 |
| `y` | 站起 |
| `u` | 趴下 |
| `i` | 切换模型 |
| `o` | 打开/关闭停障 |
| `+` / `-` | 增加 / 减少速度 |
| `x` | 停止所有运动 |
| `h` | 显示帮助 |
| `ESC` | 退出程序 |

### 4.3 IMU 数据示例

```bash
./bin/imu_client_example
```

该程序会注册 IMU 数据流，并显示当前 IMU 信息。

### 4.4 WebSocket/UDP 网页控制网关

启动网关：

```bash
make run_ws_gateway
```

无机器狗模拟模式：

```bash
make run_ws_mock
```

模拟模式不会等待 `192.168.96.2:8080`，会直接启动网页和 WebSocket 服务，并返回模拟状态、模拟 IMU 和模拟命令响应，适合客户在没有机械狗时先开发网页项目和 WS 控制逻辑。

默认监听：

```text
HTTP/WebSocket: 0.0.0.0:9001
UDP 控制入口: 0.0.0.0:9001
机器狗 UDP: 192.168.96.2:8080
```

浏览器访问控制台：

```text
http://<控制板 Wi-Fi IP>:9001
```

WebSocket 地址：

```text
ws://<控制板 Wi-Fi IP>:9001/ws
```

网页端和 WebSocket 都通过控制板 Wi-Fi IP 访问；网关在控制板内部再把控制消息通过有线网口转发到机器狗 `192.168.96.2:8080`。如果客户现场 Wi-Fi IP 变化，只需要替换浏览器和 WebSocket 地址中的 `<控制板 Wi-Fi IP>`。

网页控制台当前包含：

| 区域 | 功能 |
| --- | --- |
| 状态 | 电量、运动模式、运动模型、硬件故障 |
| 基础控制 | 复位、站起、趴下、急停、停止、停障、视频、动作下拉 |
| IMU | Roll、Pitch、Yaw 和 Frame |
| RealSense RGB | 控制板直连 RealSense 的 RGB 画面 |
| RealSense 点云 | 手动开启后展示 RGB-D 点云，支持拖动旋转和滚轮缩放 |
| 摇杆 | 前后、左右、转向三轴速度控制 |

网页发送控制消息示例：

```json
{"type":"reset"}
{"type":"stand"}
{"type":"lie"}
{"type":"emergency"}
{"type":"stop"}
{"type":"move","frontback":0.3,"leftright":0,"turn":0}
{"type":"pointcloud","enabled":true}
{"type":"pointcloud","enabled":false}
```

UDP `9001` 也接受同样的 `type` 控制消息；如果发送原始机器狗协议 JSON，网关会直接转发到机器狗。

RealSense 默认会自动尝试启动 RGB/depth 流；点云计算默认关闭，只有网页或 App 手动发送 `{"type":"pointcloud","enabled":true}` 后才会生成和广播点云数据，关闭页面、切后台或发送 `enabled:false` 会暂停点云计算。没有接相机或依赖缺失时只影响 RGB/点云显示，不影响基础控制。需要关闭相机时可直接运行：

```bash
python3 tools/ws_gateway.py --no-camera
```

## 5. 基础用法

### 5.1 创建 UDP 客户端

```cpp
#include "quadruped_sdk/udp_client.h"

std::string server_ip = "192.168.96.2";
int server_port = 8080;

quadruped_sdk::UDPClient client(server_ip, server_port);

if (!client.initialize()) {
    // 初始化失败
}
```

### 5.2 建立连接

机器狗和控制板上电后系统加载需要一定时间，可使用 `testConnection()` 等待机器狗 UDP 服务就绪。

```cpp
bool is_connect = client.testConnection();
```

`true` 表示已经连接到机器狗服务器。

### 5.3 创建解析器并启动后台线程

```cpp
#include "quadruped_sdk/json_parser.h"

quadruped_sdk::JsonParser parser(std::move(client));
parser.run();
```

使用结束时：

```cpp
parser.stop();
```

## 6. API 说明

### 6.1 获取机器狗状态

```cpp
quadruped_sdk::DogStatus status = parser.getDogStatus();
```

`DogStatus` 主要字段：

| 字段 | 含义 |
| --- | --- |
| `battery_level` | 电池电量 |
| `motion_mode` | 当前运动模式 |
| `velocity_level` | 速度档位 |
| `model` | 运动模型，`0` 越障模式，`1` 高速模式 |
| `hw_failures` | 故障硬件列表 |
| `software_version` | 软件版本 |
| `latest_software_version` | 服务器最新软件版本 |
| `robot_number` | 机器狗编号 |
| `robot_type` | 机器狗型号 |
| `hardware_error` | 总体故障状态，`0` 无故障，`1` 有故障 |

`motion_mode` 取值：

| 值 | 含义 |
| --- | --- |
| `0` | 趴地未回零 |
| `1` | 趴地 |
| `2` | 站立 |
| `3` | 低身位 |
| `4` | 翻倒 |

### 6.2 复位回零

```cpp
parser.handleResetCommand();
```

### 6.3 站立

```cpp
parser.handleStandUpCommand();
```

### 6.4 趴下

```cpp
parser.handleLieDownCommand();
```

### 6.5 急停

```cpp
parser.handleEmergencyCommand();
```

### 6.6 切换模型

```cpp
parser.handleSwitchMnnCommand(1);
```

参数含义：

| 参数 | 含义 |
| --- | --- |
| `0` | 越障模式 |
| `1` | 高速模式 |

### 6.7 设置超声波雷达停障

```cpp
parser.handleLidarObstacleCommand(1);
```

参数含义：

| 参数 | 含义 |
| --- | --- |
| `0` | 关闭停障 |
| `1` | 开启停障 |

### 6.8 单方向运动控制

```cpp
parser.sendDirectionVel(1, 0.5);
```

参数：

| 参数 | 含义 |
| --- | --- |
| `direction` | `1` 前后平移，`2` 左右平移，`3` 左右转向 |
| `velocity` | 速度，范围 `-1` 到 `1` |

方向说明：

| direction | 正数 | 负数 |
| --- | --- | --- |
| `1` | 前进 | 后退 |
| `2` | 左移 | 右移 |
| `3` | 左转 | 右转 |

### 6.9 三轴运动控制

```cpp
parser.sendDirectionVel(0.5, 0.0, 0.0);
```

参数：

| 参数 | 含义 |
| --- | --- |
| `move_frontback` | 正数前进，负数后退 |
| `move_leftright` | 正数左移，负数右移 |
| `turn_leftright` | 正数左转，负数右转 |

参数范围均为 `-1` 到 `1`。

停止运动：

```cpp
parser.sendDirectionVel(0.0, 0.0, 0.0);
```

### 6.10 注册 IMU 数据流

```cpp
parser.setIMUDataCallback(imuDataCallback);
parser.run();

bool result = parser.enableIMUStream();
```

### 6.11 获取 IMU 数据

```cpp
quadruped_sdk::IMUData imu_data = parser.getLatestIMUData();
```

### 6.12 注销 IMU 数据流

```cpp
bool result = parser.disableIMUStream();
```

## 7. 静态 IP 配置参考

如果控制板连接机器狗的有线网口没有 IP，可配置静态 IP 为 `192.168.96.3`。

注意：该有线网口只用于访问机器狗 `192.168.96.2`，不要在这个网口上配置默认网关或 DNS。默认路由应保留给 Wi-Fi，这样 SSH、网页控制台和网页推流才会走现场 Wi-Fi。

在 `/etc/netplan` 下创建或修改网络配置文件，例如 `01-network-manager-all.yaml`：

```yaml
network:
  version: 2
  renderer: NetworkManager
  ethernets:
    enP4p65s0:
      dhcp4: no
      dhcp6: no
      addresses: [192.168.96.3/24]
```

重启控制板：

```bash
sudo reboot
```

网口名称 `enP4p65s0` 可能因系统不同而变化，请以实际设备名为准。

## 8. 安全注意事项

- 运行运动示例前，确保机器狗 3 米范围内无障碍物。
- 不要在遥控器开机的情况下运行 SDK 控制程序。
- 开机前确认四条腿处于官方手册要求的初始摆放姿态。
- 上装设备不要遮挡开机键和充电接口。
- 机器狗可搭载不超过 8 kg 重物，尽量居中放置。
- 电源接口为 XT60，供电范围 22.4 V 到 33.6 V，注意正负极不要接反。
- 请在关机状态下插拔电源端子。

## 9. 目录结构

```text
.
├── Makefile
├── bin/
│   ├── example
│   ├── keyboard_test
│   └── imu_client_example
├── examples/
│   ├── example.cpp
│   ├── keyboard_test.cpp
│   └── imu_client_example.cpp
├── include/quadruped_sdk/
│   ├── imu_data.h
│   ├── json_parser.h
│   └── udp_client.h
├── lib/
│   └── libquadruped_sdk.a
└── src/
    ├── imu_data.cpp
    ├── json_parser.cpp
    └── udp_client.cpp
```

## 10. 后续建议

当前 SDK 已提供底层 UDP 通信和 JSON 协议封装。后续可以在此基础上增加更友好的统一入口类，例如 `QuadrupedClient`，将连接、状态查询、运动控制和 IMU 数据读取进一步封装，降低二次开发使用门槛。

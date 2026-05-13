# 机械狗 App 蓝牙 Wi-Fi 配网通信协议

版本：v1.0  
适用对象：移动端 App、香橙派端配网服务  
通信方式：BLE 蓝牙低功耗  

## 1. 目标

手机 App 通过 BLE 连接香橙派，将用户选择的 Wi-Fi 名称和密码发送给香橙派。香橙派收到后连接 Wi-Fi，并通过 BLE 将连接进度和结果返回给 App。

配网成功后，App 可根据香橙派返回的 IP 地址切换到局域网通信，用于后续控制机械狗。

## 2. 基本流程

1. 香橙派启动 BLE 配网服务并广播设备。
2. App 扫描 BLE 设备，找到机械狗设备。
3. App 连接香橙派 BLE 服务。
4. App 读取设备状态。
5. App 请求香橙派扫描附近 Wi-Fi。
6. 用户在 App 中选择 Wi-Fi 并输入密码。
7. App 下发 Wi-Fi 配置信息。
8. 香橙派尝试连接 Wi-Fi。
9. 香橙派通过 BLE Notify 返回连接进度。
10. 香橙派返回配网成功或失败结果。

## 3. BLE 广播

### 3.1 广播名称

格式：

```text
RoboDog-XXXX
```

说明：

`XXXX` 建议使用设备序列号后四位或 MAC 地址后四位。

示例：

```text
RoboDog-0001
```

### 3.2 广播状态

如平台支持 Manufacturer Data，可携带以下信息：

```json
{
  "type": "robodog",
  "ver": "1.0",
  "sn": "RD202605120001",
  "state": 0
}
```

`state` 说明：

| 值 | 含义 |
|---:|---|
| 0 | 未配网 |
| 1 | 已配网 |
| 2 | 正在配网 |
| 3 | Wi-Fi 连接失败 |

## 4. BLE Service 和 Characteristic

### 4.1 Service UUID

```text
0000a001-0000-1000-8000-00805f9b34fb
```

### 4.2 Characteristic 列表

| 名称 | UUID | 权限 | 用途 |
|---|---|---|---|
| Device Info | `0000a002-0000-1000-8000-00805f9b34fb` | Read | 读取设备基础信息 |
| Command | `0000a003-0000-1000-8000-00805f9b34fb` | Write / Write Without Response | App 向香橙派发送命令 |
| Notify | `0000a004-0000-1000-8000-00805f9b34fb` | Notify | 香橙派向 App 返回响应和状态 |
| Wi-Fi List | `0000a005-0000-1000-8000-00805f9b34fb` | Read / Notify | 返回 Wi-Fi 扫描列表 |

## 5. 数据格式

所有命令统一使用 UTF-8 JSON 字符串。

### 5.1 请求格式

```json
{
  "id": "1",
  "cmd": "get_status",
  "data": {}
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | string | 是 | 请求 ID，由 App 生成，用于匹配响应 |
| cmd | string | 是 | 命令名称 |
| data | object | 是 | 命令参数 |

### 5.2 响应格式

```json
{
  "id": "1",
  "cmd": "get_status_resp",
  "code": 0,
  "msg": "ok",
  "data": {}
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | string | 是 | 对应请求 ID |
| cmd | string | 是 | 响应命令名称 |
| code | number | 是 | 结果码，0 表示成功 |
| msg | string | 是 | 结果说明 |
| data | object | 是 | 响应数据 |

## 6. 错误码

| code | 含义 |
|---:|---|
| 0 | 成功 |
| 1001 | 参数错误 |
| 1002 | 设备忙 |
| 1003 | Wi-Fi 扫描失败 |
| 1004 | Wi-Fi 密码错误 |
| 1005 | Wi-Fi 连接超时 |
| 1006 | Wi-Fi 未找到 |
| 1007 | 系统错误 |
| 1008 | 未授权 |

## 7. 命令定义

### 7.1 获取设备状态

App 写入 Command Characteristic：

```json
{
  "id": "1",
  "cmd": "get_status",
  "data": {}
}
```

香橙派通过 Notify Characteristic 返回：

```json
{
  "id": "1",
  "cmd": "get_status_resp",
  "code": 0,
  "msg": "ok",
  "data": {
    "sn": "RD202605120001",
    "deviceName": "RoboDog-0001",
    "wifiState": 0,
    "connectedSsid": "",
    "ip": "",
    "fwVersion": "1.0.0"
  }
}
```

`wifiState` 说明：

| 值 | 含义 |
|---:|---|
| 0 | 未连接 |
| 1 | 正在连接 |
| 2 | 已连接 |
| 3 | 连接失败 |

### 7.2 扫描 Wi-Fi

App 写入：

```json
{
  "id": "2",
  "cmd": "scan_wifi",
  "data": {}
}
```

香橙派立即返回：

```json
{
  "id": "2",
  "cmd": "scan_wifi_resp",
  "code": 0,
  "msg": "scanning",
  "data": {}
}
```

扫描完成后返回：

```json
{
  "id": "2",
  "cmd": "wifi_list",
  "code": 0,
  "msg": "ok",
  "data": {
    "list": [
      {
        "ssid": "HomeWiFi",
        "rssi": -45,
        "secure": true,
        "freq": 2412
      },
      {
        "ssid": "Office_5G",
        "rssi": -61,
        "secure": true,
        "freq": 5180
      }
    ]
  }
}
```

Wi-Fi 字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| ssid | string | Wi-Fi 名称 |
| rssi | number | 信号强度，数值越接近 0 越强 |
| secure | boolean | 是否需要密码 |
| freq | number | 频率，单位 MHz |

### 7.3 下发 Wi-Fi 配置

App 写入：

```json
{
  "id": "3",
  "cmd": "set_wifi",
  "data": {
    "ssid": "HomeWiFi",
    "password": "12345678",
    "auth": "wpa2",
    "hidden": false
  }
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| ssid | string | 是 | Wi-Fi 名称 |
| password | string | 否 | Wi-Fi 密码，开放网络可为空 |
| auth | string | 否 | 加密方式，可填 `open`、`wpa2`、`wpa3` |
| hidden | boolean | 否 | 是否隐藏 Wi-Fi |

香橙派收到后立即返回：

```json
{
  "id": "3",
  "cmd": "set_wifi_resp",
  "code": 0,
  "msg": "accepted",
  "data": {}
}
```

连接过程中返回进度：

```json
{
  "id": "3",
  "cmd": "wifi_progress",
  "code": 0,
  "msg": "connecting",
  "data": {
    "step": 1,
    "desc": "connecting to ap"
  }
}
```

配网成功返回：

```json
{
  "id": "3",
  "cmd": "wifi_result",
  "code": 0,
  "msg": "connected",
  "data": {
    "ssid": "HomeWiFi",
    "ip": "192.168.1.88",
    "gateway": "192.168.1.1",
    "robotPort": 9000
  }
}
```

配网失败返回：

```json
{
  "id": "3",
  "cmd": "wifi_result",
  "code": 1004,
  "msg": "wrong password",
  "data": {
    "ssid": "HomeWiFi"
  }
}
```

### 7.4 清除 Wi-Fi 配置

App 写入：

```json
{
  "id": "4",
  "cmd": "clear_wifi",
  "data": {}
}
```

香橙派返回：

```json
{
  "id": "4",
  "cmd": "clear_wifi_resp",
  "code": 0,
  "msg": "ok",
  "data": {}
}
```

### 7.5 重启网络

App 写入：

```json
{
  "id": "5",
  "cmd": "restart_network",
  "data": {}
}
```

香橙派返回：

```json
{
  "id": "5",
  "cmd": "restart_network_resp",
  "code": 0,
  "msg": "ok",
  "data": {}
}
```

## 8. App 状态机

App 建议按以下状态流转：

```text
Idle
  -> ScanningBle
  -> BleConnected
  -> GettingDeviceStatus
  -> ScanningWifi
  -> WaitingUserSelectWifi
  -> SendingWifiConfig
  -> WaitingWifiResult
  -> ProvisionSuccess / ProvisionFailed
```

## 9. 超时时间

| 操作 | 建议超时时间 |
|---|---:|
| BLE 扫描 | 10 秒 |
| BLE 连接 | 10 秒 |
| 获取设备状态 | 5 秒 |
| Wi-Fi 扫描 | 15 秒 |
| Wi-Fi 连接 | 45 秒 |

## 10. App 端接入要点

1. App 扫描 BLE 时优先通过 Service UUID 过滤设备。
2. 连接成功后必须开启 Notify Characteristic 订阅。
3. App 写入命令后，通过 `id` 匹配香橙派返回的数据。
4. 下发 Wi-Fi 后，App 不应立即断开 BLE，需要等待 `wifi_result`。
5. 如果收到成功结果，App 使用返回的 `ip` 和 `robotPort` 建立局域网控制连接。
6. 如果超时未收到结果，App 提示用户检查 Wi-Fi 密码、距离和设备状态。

## 11. 香橙派端实现要点

1. 未配网状态下启动 BLE 广播和配网服务。
2. 收到 `scan_wifi` 后调用系统 Wi-Fi 扫描接口。
3. 收到 `set_wifi` 后保存 Wi-Fi 配置并尝试连接。
4. 连接过程中持续通过 Notify 返回进度。
5. 配网成功后返回 IP、网关和控制端口。
6. 配网成功后可关闭配网 BLE 服务，或只保留只读状态服务。

## 12. 安全建议

第一版可以先使用明文 JSON 跑通流程。量产版本建议增加以下限制：

1. BLE 配网服务只在未配网或按下设备配网按键后开启。
2. 配网成功后自动关闭 BLE 配网写入能力。
3. App 与设备建立连接后增加一次 `hello` 握手。
4. 后续版本可将 Wi-Fi 密码改为 AES 加密传输。

简单握手示例：

App 发送：

```json
{
  "id": "10",
  "cmd": "hello",
  "data": {
    "appNonce": "a8f31c92"
  }
}
```

香橙派返回：

```json
{
  "id": "10",
  "cmd": "hello_resp",
  "code": 0,
  "msg": "ok",
  "data": {
    "deviceNonce": "91ab22cd",
    "sessionId": "s202605120001"
  }
}
```

## 13. 最小可用版本

App 第一版至少需要实现以下命令：

| 命令 | 是否必需 | 说明 |
|---|---|---|
| get_status | 是 | 确认设备状态 |
| scan_wifi | 是 | 获取 Wi-Fi 列表 |
| set_wifi | 是 | 下发 Wi-Fi 配置 |
| clear_wifi | 建议 | 重新配网时使用 |

核心闭环：

```text
App -> 香橙派: set_wifi
香橙派 -> App: wifi_result
```

## 14. 联调检查清单

App 侧：

- 能扫描到 `RoboDog-XXXX`。
- 能连接 BLE。
- 能订阅 Notify。
- 能发送 `get_status` 并收到响应。
- 能发送 `scan_wifi` 并展示 Wi-Fi 列表。
- 能发送 `set_wifi`。
- 能正确处理成功、失败和超时。

香橙派侧：

- BLE 广播名称正确。
- Service UUID 和 Characteristic UUID 正确。
- JSON 编码为 UTF-8。
- 每条响应都带原始请求 `id`。
- Wi-Fi 连接成功后能返回 IP。
- Wi-Fi 密码错误时能返回明确错误码。

# App 通信链路与指令说明

本文档说明手机 App `hbuilder_quadruped_controller` 当前的通信方式、指令映射、发送频率和回包处理。

## 结论先说

当前通信逻辑已经拆成三层：

```text
hbuilder_quadruped_controller/services/gateway.js
hbuilder_quadruped_controller/services/commands.js
hbuilder_quadruped_controller/pages/index/index.vue
```

分工如下：

- `services/gateway.js`：只负责 WebSocket 连接、关闭、发送 JSON、接收消息。
- `services/commands.js`：只负责生成机械狗控制 payload。
- `pages/index/index.vue`：负责业务状态、回包分发、摇杆节流、相机/点云采集开关策略。

视觉页的点云绘制逻辑已经迁移到：

```text
hbuilder_quadruped_controller/components/VisionView.vue
```

但“是否请求网关开启点云采集”仍在 `index.vue`，因为这是通信控制逻辑。

## 总体通信链路

```text
手机 App
  ↓ WebSocket: ws://<控制器IP>:9001/ws
Python 网关 tools/ws_gateway.py
  ↓ UDP: 192.168.96.2:8080
机械狗
```

App 不直接和机械狗 UDP 通信。App 只连 Python 网关，网关再把 App 的 JSON 控制消息转成机械狗 UDP 协议。

## App 连接流程

App 默认控制器地址在 `index.vue`：

```js
const DEFAULT_CONTROLLER_ADDRESS = '10.0.50.236:9001'
```

连接时会转成：

```text
ws://10.0.50.236:9001/ws
```

核心方法：

- `normalizeAddress(input)`：整理地址，去掉 `ws://`、`/ws` 等多余部分
- `buildSocketUrl(address)`：生成 WebSocket 地址
- `connect()`：整理地址后调用 `gateway.connect(url)`
- `closeSocket()`：关闭点云采集后调用 `gateway.close()`
- `handleMessage(message)`：处理网关返回消息

底层 WebSocket 在：

```text
hbuilder_quadruped_controller/services/gateway.js
```

其中 `createGatewayClient()` 提供：

- `connect(url)`
- `send(payload, callbacks)`
- `close()`
- `isOpen()`

连接成功后，网关会主动发一条：

```json
{
  "type": "hello",
  "dog": "192.168.96.2:8080",
  "mock": false,
  "camera": true,
  "pointcloud": true,
  "robot_ready": true,
  "status": {},
  "imu": {}
}
```

App 收到 `hello` 后：

- 设置 `connected = true`
- 设置 `connecting = false`
- 切换到控制页 `pageMode = 'control'`
- 更新状态和 IMU

## 是否是一问一答

不是严格的一问一答。

更准确说，它是：

```text
WebSocket 长连接 + 异步消息广播
```

App 发出控制命令后，网关通常会立刻广播一条：

```json
{
  "type": "sent",
  "command": {...}
}
```

这只是“网关已收到/已处理 App 命令”的确认，不代表机械狗已经完成动作。

机械狗如果后续通过 UDP 返回命令结果，网关会再广播：

```json
{
  "type": "command_result",
  "result": {...}
}
```

所以当前不是：

```text
App 问一句 -> 等机械狗回一句 -> 再继续
```

而是：

```text
App 发送命令
网关异步转发
网关异步广播 sent / status / command_result / imu / camera_frame / pointcloud_frame
App 根据 message.type 更新界面
```

## App 发送命令格式

App 通过：

```js
sendCommand(payload)
```

发送 JSON 字符串：

```js
this.gateway.send(payload)
```

payload 由：

```text
hbuilder_quadruped_controller/services/commands.js
```

统一生成。

常见 payload：

```json
{"type":"reset"}
{"type":"stand"}
{"type":"lie"}
{"type":"emergency"}
{"type":"stop"}
{"type":"move","frontback":0.3,"leftright":0,"turn":0}
{"type":"model","value":0}
{"type":"obstacle","enabled":true}
{"type":"video","enabled":true}
{"type":"action","code":11}
{"type":"pointcloud","enabled":true}
```

## App 指令到网关/机械狗指令映射

网关处理入口：

```text
tools/ws_gateway.py -> handle_web_command()
```

### 基础动作

| App 命令 | 网关转发给机械狗 UDP |
| --- | --- |
| `{"type":"reset"}` | `{"msg_type":3,"cmd_code":4}` |
| `{"type":"stand"}` | `{"msg_type":3,"cmd_code":10}` |
| `{"type":"lie"}` | `{"msg_type":3,"cmd_code":11}` |
| `{"type":"emergency"}` | `{"msg_type":3,"cmd_code":6}` |

对应常量：

```text
MSG_COMMAND_REQUEST = 3
CMD_RESET = 4
CMD_EMERGENCY_STOP = 6
CMD_STAND_UP = 10
CMD_LIE_DOWN = 11
```

### 停止/移动

App：

```json
{"type":"stop"}
```

网关转成速度 0：

```json
{
  "vel_move_frontback": 0,
  "vel_move_leftright": 0,
  "vel_turn_leftright": 0
}
```

App：

```json
{"type":"move","frontback":0.3,"leftright":0,"turn":0}
```

网关转成：

```json
{
  "vel_move_frontback": 0.3,
  "vel_move_leftright": 0,
  "vel_turn_leftright": 0
}
```

网关会把速度值限制在 `-1.0` 到 `1.0`。

### 模式切换

App：

```json
{"type":"model","value":0}
{"type":"model","value":1}
```

网关：

```json
{"msg_type":3,"cmd_code":2,"para":0}
{"msg_type":3,"cmd_code":2,"para":1}
```

当前含义：

- `0`：越障模式
- `1`：高速模式

### 停障

App：

```json
{"type":"obstacle","enabled":true}
```

网关：

```json
{"msg_type":3,"cmd_code":5,"para":1}
```

关闭：

```json
{"msg_type":3,"cmd_code":5,"para":0}
```

### 视频

App：

```json
{"type":"video","enabled":true}
```

网关：

```json
{"msg_type":3,"cmd_code":9,"para":1}
```

### 动作库

App：

```json
{"type":"action","code":11}
```

网关：

```json
{"msg_type":3,"cmd_code":3,"para":11}
```

当前按钮对应：

| App 按钮 | App code | 网关 cmd_code | para |
| --- | ---: | ---: | ---: |
| 打招呼 | `11` | `3` | `11` |
| 撒尿 | `5` | `3` | `5` |
| 跳跃 | `2` | `3` | `2` |
| 比心 | `14` | `3` | `14` |
| 拜年 | `15` | `3` | `15` |

### 点云开关

App：

```json
{"type":"pointcloud","enabled":true}
```

这个命令不直接发给机械狗，而是控制网关内部的 RealSense 点云采集。

网关逻辑：

- 如果网关没有启用相机或点云，返回 `pointcloud_status: ok=false`
- 如果可用，把当前 WebSocket client 加入 `pointcloud_clients`
- 只有至少一个 client 需要点云时，网关才开启点云采集
- client 离开或关闭点云后，网关暂停点云采集

## 通信频率

### 普通按钮

普通按钮是事件触发，点一次发一次。

例如：

- 回零
- 站立
- 趴下
- 急停
- 动作库
- 模式切换
- 停障开关
- 视频开关

### 摇杆移动

摇杆是连续控制，有节流。

相关代码：

```js
startMoveLoop()
sendMove(force)
```

频率规则：

- 摇杆开始拖动时，立即发送一次
- 拖动过程中，`moveStick()` 会尝试发送，但 `sendMove(false)` 有 45ms 节流
- 同时 `startMoveLoop()` 会启动一个 `setInterval(..., 80)`，拖动期间每 80ms 强制发送一次当前速度
- 松手时立即发送一次速度归零

所以摇杆移动命令大约是：

```text
最多约 12.5 次/秒的持续保活发送
拖动变化时还有 45ms 节流保护
```

这不是一问一答，而是连续流式控制。

### 状态查询

网关对机械狗每 1 秒查询一次实时状态：

```python
time.sleep(1.0)
```

网关发送：

```json
{"msg_type":1,"query_code":1}
```

并广播：

```json
{"type":"snapshot","status":...,"imu":...}
```

机械狗返回实时状态后，网关广播：

```json
{"type":"status","status":...}
```

### IMU

网关连接机械狗 UDP 服务后会发送：

```json
{"msg_type":3,"cmd_code":20}
```

也就是启用 IMU。

收到机械狗 IMU 响应后，网关广播：

```json
{"type":"imu","imu":...}
```

具体频率取决于机械狗/网关收到数据的频率。mock 模式下大约 1 秒一次。

### RGB 相机

网关默认配置：

```text
camera_publish_fps = 5
```

也就是 RGB 图像最多约 5 FPS 广播给 App。

消息格式：

```json
{
  "type":"camera_frame",
  "format":"jpeg",
  "encoding":"base64",
  "width":640,
  "height":480,
  "data":"..."
}
```

### 点云

网关默认配置：

```text
pointcloud_fps = 1
```

也就是点云默认约 1 FPS。

点云数据格式：

```json
{
  "type":"pointcloud_frame",
  "format":"xyzrgb_flat",
  "count":12345,
  "points":[x,y,z,r,g,b,x,y,z,r,g,b,...]
}
```

## App 如何处理回包

App 回包入口：

```js
handleMessage(message)
```

根据 `message.type` 分发：

| message.type | App 处理 |
| --- | --- |
| `hello` | 握手完成，进入控制页，更新状态和 IMU |
| `status` | 更新电量、运动模式、模型、故障 |
| `snapshot` | 同时更新状态和 IMU |
| `imu` | 更新 IMU 姿态 |
| `camera_frame` | 更新 RGB 图片 |
| `camera_status` | 更新相机在线/离线状态 |
| `pointcloud_frame` | 更新点云数据 |
| `pointcloud_status` | 更新点云在线/不可用状态 |
| `command_result` | 记录机械狗命令响应 |
| `sent` | 记录网关已收到/已转发命令 |
| `error` | 记录错误信息 |

## 网关如何处理机械狗回包

网关 UDP 接收入口：

```text
udp_receive_loop()
```

解析 JSON 后进入：

```text
handle_robot_message()
```

处理规则：

| 机械狗消息 | 网关广播给 App |
| --- | --- |
| 实时状态查询响应 | `{"type":"status","status":...}` |
| 命令响应 | `{"type":"command_result","result":...}` |
| IMU 响应 | `{"type":"imu","imu":...}` |
| 其他消息 | `{"type":"robot","message":...}` |

## 心跳

网关 WebSocket 连接中，如果 30 秒没有读到客户端消息，会向客户端发：

```json
{"type":"heartbeat","time":...}
```

当前 App 的 `handleMessage()` 没有专门处理 `heartbeat`，所以会忽略它。

## 当前已知问题和已修复点

### 已修复：摄像头离线时点云请求堆积

之前点云开关请求缺少状态保护。相机离线或点云不可用时，App 可能反复请求开启点云，造成请求堆积。

现在 App 增加了：

- `cameraStatusKnown`
- `pointCloudCaptureState`
- `pointCloudCapturePending`
- `pointCloudCaptureLastSentAt`
- `pointCloudUnavailable`

现在行为：

- 相机明确离线时，不请求开启点云
- 网关明确返回点云不可用时，不重复请求
- 点云开关状态相同，不重复发送
- 上一次点云开关请求 pending 时，不继续堆新请求
- 500ms 内不重复发送点云开关请求
- 相机恢复在线后，重新同步当前点云采集意图

## 当前代码结构建议

通信拆分已经完成：

```text
services/
├─ gateway.js
└─ commands.js
```

后续如果继续整理，可以考虑把 `index.vue` 里的回包处理拆成：

```text
services/messageHandlers.js
```

但这一步不是必须。当前先保持现状更稳，因为 `handleMessage()` 会直接更新页面状态。

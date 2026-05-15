# App 端控制指令与动作映射

本文档整理 App 端通过 WebSocket 控制机器狗时使用的 JSON 指令，以及当前云卓/G20 遥控器按键映射。

## 1. WebSocket 连接

App 连接控制板 WebSocket 网关：

```text
ws://<控制板IP>:9001/ws
```

示例：

```text
ws://10.0.50.236:9001/ws
```

蓝牙配网返回给 App 的 `robotPort` 应为 `9001`，它对应控制板上的 WebSocket/网页网关端口。

## 2. 基础姿态与安全指令

| 功能 | App 发送 JSON |
| --- | --- |
| 复位/回零 | `{ "type": "reset" }` |
| 站立 | `{ "type": "stand" }` |
| 趴下 | `{ "type": "lie" }` |
| 急停 | `{ "type": "emergency" }` |
| 停止运动 | `{ "type": "stop" }` |

说明：

- `reset` 用于解除异常状态或回零。
- `emergency` 是急停，触发后可能需要再发送 `reset` 和 `stand` 才能恢复动作。
- `stop` 只发送零速度，不等同于急停。

## 3. 移动控制指令

移动控制使用 `move` 指令：

```json
{
  "type": "move",
  "frontback": 0.3,
  "leftright": 0.0,
  "turn": 0.0
}
```

方向定义：

| 参数 | 正数 | 负数 |
| --- | --- | --- |
| `frontback` | 前进 | 后退 |
| `leftright` | 左移 | 右移 |
| `turn` | 左转 | 右转 |

速度范围：

```text
-1.0 ~ 1.0
```

建议 App 端日常遥控先限制在：

```text
0.15 ~ 0.55
```

停止运动：

```json
{ "type": "stop" }
```

或发送零速度：

```json
{
  "type": "move",
  "frontback": 0.0,
  "leftright": 0.0,
  "turn": 0.0
}
```

## 4. 模式与开关指令

| 功能 | App 发送 JSON |
| --- | --- |
| 越障模式 | `{ "type": "model", "value": 0 }` |
| 高速模式 | `{ "type": "model", "value": 1 }` |
| 停障开 | `{ "type": "obstacle", "enabled": true }` |
| 停障关 | `{ "type": "obstacle", "enabled": false }` |
| 视频开 | `{ "type": "video", "enabled": true }` |
| 视频关 | `{ "type": "video", "enabled": false }` |

## 5. 动作库指令

动作库统一使用：

```json
{ "type": "action", "code": 11 }
```

当前动作码：

| 动作 | code | App 发送 JSON |
| --- | ---: | --- |
| 打招呼 | 11 | `{ "type": "action", "code": 11 }` |
| 撒尿 | 5 | `{ "type": "action", "code": 5 }` |
| 跳跃 | 2 | `{ "type": "action", "code": 2 }` |
| 比心 | 14 | `{ "type": "action", "code": 14 }` |
| 拜年 | 15 | `{ "type": "action", "code": 15 }` |
| 原地模式 | 18 | `{ "type": "action", "code": 18 }` |

原地模式退出建议：

1. 先发送停止运动：`{ "type": "stop" }`
2. 如果仍保持原地模式，再发送站立：`{ "type": "stand" }`
3. 必要时发送复位再站立：`{ "type": "reset" }`，然后 `{ "type": "stand" }`

## 6. 视觉与 IMU 指令

| 功能 | App 发送 JSON |
| --- | --- |
| 开 RGB 相机 | `{ "type": "camera", "enabled": true }` |
| 关 RGB 相机 | `{ "type": "camera", "enabled": false }` |
| 开点云 | `{ "type": "pointcloud", "enabled": true }` |
| 关点云 | `{ "type": "pointcloud", "enabled": false }` |
| 重启 IMU | `{ "type": "imu_reset" }` |

## 7. 云卓/G20 遥控器当前映射

当前遥控器桥接服务为直连机器狗 UDP 模式，不依赖 WebSocket 网关：

```text
/dev/g20-sbus -> robot udp://192.168.96.2:8080
```

当前服务参数摘要：

```text
frontback-channel: CH3
leftright-channel: CH4
turn-channel: CH1
turn-invert: enabled
speed-channel: CH14
speed range: 0.15 ~ 0.55
initial speed: 0.40
```

按键映射：

| 遥控器/通道 | 功能 | 内部命令 |
| --- | --- | --- |
| CH5 high | 站立 | `stand` |
| CH5 mid | 停止 | `stop` |
| CH5 low | 趴下 | `lie` |
| CH8 high | 复位/回零 | `reset` |
| CH13 high | 急停 | `emergency` |
| CH6 low | 高速/越障切换 | `model-toggle` |
| CH14 | 调速 | 锁存式加/减速 |
| L1 / CH11 low | 打招呼 | `action:11` |
| L2 / CH7 low | 撒尿 | `action:5` |
| R1 / CH15 low | 跳跃 | `action:2` |
| R2 / CH16 low | 比心 | `action:14` |
| B1 / CH10 low | 拜年 | `action:15` |
| B2 / CH9 low | 原地模式 | `action:18` |

摇杆映射：

| 遥控器输入 | 通道 | 功能 |
| --- | --- | --- |
| 前后拨杆 | CH3 | 前进/后退 |
| 左右横移拨杆 | CH4 | 左移/右移 |
| 转向拨杆 | CH1 | 左转/右转 |

## 8. App 端实现建议

App 端建议封装统一发送函数：

```js
function sendCommand(ws, payload) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  ws.send(JSON.stringify(payload))
}
```

常用封装：

```js
export const resetCommand = () => ({ type: 'reset' })
export const standCommand = () => ({ type: 'stand' })
export const lieCommand = () => ({ type: 'lie' })
export const emergencyCommand = () => ({ type: 'emergency' })
export const stopCommand = () => ({ type: 'stop' })
export const moveCommand = (frontback, leftright, turn) => ({ type: 'move', frontback, leftright, turn })
export const modelCommand = value => ({ type: 'model', value })
export const obstacleCommand = enabled => ({ type: 'obstacle', enabled })
export const videoCommand = enabled => ({ type: 'video', enabled })
export const cameraCommand = enabled => ({ type: 'camera', enabled })
export const pointcloudCommand = enabled => ({ type: 'pointcloud', enabled })
export const actionCommand = code => ({ type: 'action', code })
```

动作按钮建议：

```js
const actions = [
  { label: '打招呼', code: 11 },
  { label: '撒尿', code: 5 },
  { label: '跳跃', code: 2 },
  { label: '比心', code: 14 },
  { label: '拜年', code: 15 },
  { label: '原地模式', code: 18 }
]
```

## 9. 注意事项

- 急停后动作可能不会立即恢复，需要 `reset` 后再 `stand`。
- 动作类指令建议在站立状态下触发。
- 点云较占资源，App 切后台或离开页面时建议发送 `{ "type": "pointcloud", "enabled": false }`。
- RGB 没画面但 WS 显示连接时，优先检查 `quadruped-ws-gateway` 日志和 RealSense 是否被旧进程占用。

# hbuilder_quadruped_controller 文件结构汇报

本文只分析手机端 App 项目：`hbuilder_quadruped_controller/`。它是一个 HBuilderX / uni-app 项目，用来编译运行到手机，作为机械狗移动端上位机。

## 总体结论

当前 App 已经从“所有逻辑集中在 `pages/index/index.vue`”调整为更清晰的分层结构：

```text
pages/index/index.vue        页面编排层：切页面、路由网关消息、写日志
components/                  纯 UI 组件：连接页、控制页、视觉页
features/                    业务逻辑模块：连接、状态、控制、视觉流
services/                    底层服务：WebSocket 封装、命令格式
```

重构后的核心变化是：`index.vue` 不再直接处理所有摄像头、点云、摇杆、机器人状态和 WebSocket 细节，而是通过 mixin 组合 `features/` 里的业务模块。

## 一级结构

```text
hbuilder_quadruped_controller/
├── components/
│   ├── ConnectView.vue
│   ├── ControlView.vue
│   └── VisionView.vue
├── features/
│   ├── gatewayConnection.js
│   ├── robotControl.js
│   ├── robotStatus.js
│   └── visionStream.js
├── pages/
│   └── index/
│       └── index.vue
├── services/
│   ├── commands.js
│   └── gateway.js
├── static/
│   └── icon.svg
├── unpackage/
├── App.vue
├── main.js
├── manifest.json
├── pages.json
└── README.md
```

## 目录说明

### `components/`

放页面 UI 组件，主要负责展示和向父级抛事件，不直接处理 WebSocket 协议。

- `ConnectView.vue`：连接页 UI，输入控制器地址，点击连接。
- `ControlView.vue`：控制页 UI，包括摇杆、状态卡片、动作库、设置抽屉等。
- `VisionView.vue`：视觉页 UI，展示 RGB 画面和点云 canvas，处理点云视角拖动、缩放和复位。

### `features/`

业务逻辑模块目录。当前用 Vue 2 mixin 方式组织，适配当前 uni-app 项目，不引入 Vue 3 Composition API。

- `gatewayConnection.js`
  - 管 WebSocket 生命周期。
  - 管控制器地址存储和规范化。
  - 提供 `connect()`、`closeSocket()`、`sendCommand()`。
  - 默认地址在这里：`DEFAULT_CONTROLLER_ADDRESS = '10.0.50.236:9001'`。

- `robotStatus.js`
  - 管机器人回传状态。
  - 包括电量、运动模式、机器人模型、故障状态、IMU。
  - 提供 `updateStatus()`、`updateImu()`。
  - 提供展示用计算属性：`batteryText`、`motionText`、`faultText`、`activeCommand` 等。

- `robotControl.js`
  - 管控制命令和摇杆逻辑。
  - 包括站立、趴下、回零、急停、动作库、避障开关、视频开关。
  - 包括左右摇杆拖动、移动命令节流、循环发送。
  - 依赖 `services/commands.js` 生成命令对象。

- `visionStream.js`
  - 管视觉数据流。
  - 包括 RGB 相机帧、相机状态、点云状态、点云数据。
  - 处理网关消息：`camera_frame`、`camera_status`、`pointcloud_frame`、`pointcloud_status`。
  - 根据页面状态自动开启/关闭 RGB 相机订阅和点云采集。

### `services/`

偏底层的服务和协议工具。

- `gateway.js`
  - 对 `uni.connectSocket` 做薄封装。
  - 提供 `connect()`、`send()`、`close()`、`isOpen()`。
  - 负责 JSON 解析，但不理解具体业务消息。

- `commands.js`
  - 统一生成发给网关的 JSON 命令。
  - 例如：`standCommand()`、`moveCommand()`、`videoCommand()`、`pointcloudCommand()`。

### `pages/index/index.vue`

现在是页面编排层，职责比之前轻很多。

它主要负责：

- 引入三个 UI 组件。
- 引入四个 `features` mixin。
- 维护页面级状态：`pageMode`、`settingsOpen`、`actionsOpen`、`logs`。
- 控制页面切换：连接页 / 控制页 / 视觉页。
- 网关消息一级路由：视觉消息交给 `visionStream`，状态消息交给 `robotStatus`。
- App 生命周期里停止点云、停止移动、关闭连接。

关键页面模式：

```js
pageMode: 'connect'
pageMode: 'control'
pageMode: 'vision'
```

### `static/`

静态资源目录。当前主要有 `static/icon.svg`。

### `unpackage/`

HBuilderX 构建输出目录，不是手写源码。正常不要手动修改，重新运行或打包可能覆盖。

## 摄像头和点云逻辑现在在哪里

App 端视觉逻辑主要分两层：

```text
features/visionStream.js     接收和管理 RGB / 点云数据
components/VisionView.vue    展示 RGB / 绘制点云
```

RGB 画面链路：

```text
进入视觉页 RGB 标签
  ↓
features/visionStream.js -> setCameraCapture(true)
  ↓
发送 { type: 'camera', enabled: true }
  ↓
网关把当前 App 加入 camera_clients
  ↓
网关 camera_frame
  ↓
features/visionStream.js -> updateCameraFrame()
  ↓
cameraFrame = data:image/jpeg;base64,...
  ↓
VisionView.vue <image :src="cameraFrame">
```

点云链路：

```text
进入视觉页并切到点云
  ↓
features/visionStream.js -> setPointCloudCapture(true)
  ↓
发送 { type: 'pointcloud', enabled: true }
  ↓
网关 pointcloud_frame
  ↓
features/visionStream.js -> updatePointCloudFrame()
  ↓
VisionView.vue -> drawPointCloud()
```

注意：App 端不是直接 RTSP/RTMP/WebRTC 拉流。当前是通过 WebSocket 接收网关推送的数据，RGB 是 JSON 里的 JPEG base64，点云兼容旧版 `xyzrgb_flat` 数组和新版 `xyzrgb_float32` 二进制帧。

最新 SDK 中 RGB 不再无条件广播给所有 WebSocket 客户端。客户端必须先发送：

```json
{"type":"camera","enabled":true}
```

网关才会给这个客户端推 `camera_frame`。离开视觉页、App 退后台或关闭连接时，App 会发送 `enabled:false` 取消订阅。

最新 SDK 的点云也可能使用二进制格式：先发一条 `pointcloud_frame` 元数据 JSON，再发一帧 `Float32Array` 二进制点云。App 已在 `services/gateway.js` 和 `features/visionStream.js` 中做了兼容。

## 控制命令链路

控制命令现在分三层：

```text
ControlView.vue              用户点击/摇杆事件
  ↓
features/robotControl.js     转成业务动作
  ↓
services/commands.js         生成 JSON 命令
  ↓
features/gatewayConnection.js -> sendCommand()
  ↓
services/gateway.js          WebSocket 发送
```

常见命令：

```json
{"type":"reset"}
{"type":"stand"}
{"type":"lie"}
{"type":"emergency"}
{"type":"stop"}
{"type":"move","frontback":0,"leftright":0,"turn":0}
{"type":"model","value":0}
{"type":"obstacle","enabled":true}
{"type":"video","enabled":true}
{"type":"camera","enabled":true}
{"type":"action","code":11}
{"type":"pointcloud","enabled":true}
```

App 本身不直接发 UDP 给机械狗，而是发 WebSocket 给 `tools/ws_gateway.py`，再由网关转成机械狗 UDP 协议。

## 根文件说明

### `App.vue`

全局入口组件。当前主要负责横屏、WebView 行为和全局页面样式，不适合放业务逻辑。

### `main.js`

uni-app / Vue 初始化入口，一般不需要改。

### `manifest.json`

App 打包配置，包含 App 名称、版本、权限、横屏配置等。

### `pages.json`

页面路由和窗口配置。当前只有 `pages/index/index` 一个页面。

### `README.md`

手机 App 使用说明，包括 HBuilderX 导入、启动网关、运行到手机、发布 APK 等。

## 后续修改建议

常改位置：

- 改默认控制器 IP：`features/gatewayConnection.js`
- 改 WebSocket 连接行为：`features/gatewayConnection.js`、`services/gateway.js`
- 改按钮命令：`features/robotControl.js`、`services/commands.js`
- 改机器人状态展示：`features/robotStatus.js`
- 改 RGB / 点云逻辑：`features/visionStream.js`、`components/VisionView.vue`
- 改控制页布局：`components/ControlView.vue` 和 `pages/index/index.vue` 的样式区
- 改 App 名称/权限/版本：`manifest.json`

不建议手改：

- `unpackage/`：构建产物
- `.hbuilderx/`：HBuilderX 工具配置
- `.git/`：仓库元数据

## 当前风险点

- 样式仍集中在 `pages/index/index.vue` 的 `<style>` 中。逻辑已经拆开，但 CSS 后续还可以继续按组件拆分。
- `components/` 里的中文在部分 Windows 终端可能显示乱码，实际文件按 UTF-8 编辑即可。
- App 默认地址仍是固定 IP，现场 Wi-Fi 变化时需要用户手动修改。
- `video` 命令只是发给网关/底层的相机流开关，不等于 App RGB 画面显示开关；App RGB 显示依赖 `camera` 订阅命令和网关持续推送 `camera_frame`。

# 机械狗 SDK Docker 部署指南

本文说明如何将本 SDK 打包为 Docker 镜像，并部署到其他控制板或机械狗项目中。

## 1. 适用场景

Docker 部署适合以下场景：

1. 多台控制板部署同一套 SDK 和 WS 网关。
2. 客户现场快速恢复环境，避免重复安装依赖。
3. 无机械狗时先启动模拟模式，进行网页和 WS 二次开发。
4. 固定交付版本，便于后续升级和回滚。

## 2. 镜像内容

镜像内包含：

| 内容 | 路径 |
| --- | --- |
| C++ SDK 头文件 | `/opt/quadruped_dev_sdk/include` |
| C++ 静态库 | `/opt/quadruped_dev_sdk/lib/libquadruped_sdk.a` |
| 示例程序 | `/opt/quadruped_dev_sdk/bin` |
| WS 网关 | `/opt/quadruped_dev_sdk/tools/ws_gateway.py` |
| 网页控制台 | `/opt/quadruped_dev_sdk/web` |
| 文档 | `/opt/quadruped_dev_sdk/docs` |

## 3. 构建镜像

在 SDK 根目录执行：

```bash
cd /home/orangepi/quadruped_dev_sdk
make docker_build
```

如果当前用户没有 Docker daemon 权限，可以使用：

```bash
make docker_build DOCKER="sudo docker"
```

也可以把当前用户加入 `docker` 用户组，后续就不需要每次加 `sudo`：

```bash
sudo usermod -aG docker $USER
```

执行后退出当前 SSH 或终端，重新登录，再验证：

```bash
docker ps
```

如果不再提示 `/var/run/docker.sock` 权限不足，就可以直接使用 `make docker_build`。

等价命令：

```bash
docker build -t quadruped-sdk:1.0.0 -t quadruped-sdk:latest .
```

镜像基于 `ubuntu:20.04`，构建阶段会安装 `build-essential`、`make`、`libjsoncpp-dev` 和 `python3`，并在镜像内执行 `make` 编译 SDK 和示例程序。

## 4. 真实机器狗模式

真实模式需要容器能访问控制板有线网口和机器狗 `192.168.96.2:8080`。推荐使用 Docker host 网络：

```bash
make docker_run_ws
```

如果需要 sudo：

```bash
make docker_run_ws DOCKER="sudo docker"
```

等价命令：

```bash
docker run --rm -it --network host quadruped-sdk:latest ws
```

启动后浏览器访问：

```text
http://<控制板 Wi-Fi IP>:9001
```

例如：

```text
http://10.0.50.236:9001
```

如果机器狗 IP 或端口不同：

```bash
docker run --rm -it --network host \
  -e DOG_IP=192.168.96.2 \
  -e DOG_PORT=8080 \
  -e LISTEN_PORT=9001 \
  quadruped-sdk:latest ws
```

## 5. 无机械狗模拟模式

模拟模式不连接真实机器狗，适合客户没有硬件时开发网页和 WS 逻辑。

```bash
make docker_run_mock
```

如果需要 sudo：

```bash
make docker_run_mock DOCKER="sudo docker"
```

等价命令：

```bash
docker run --rm -it --network host \
  -e LISTEN_PORT=9101 \
  quadruped-sdk:latest ws-mock
```

访问：

```text
http://<控制板 Wi-Fi IP>:9101
```

模拟模式下网页命令格式与真实模式一致，WebSocket 地址仍然是：

```text
ws://<控制板 Wi-Fi IP>:9101/ws
```

切换到真实机器狗时，客户网页代码不需要修改，只需要改启动命令和访问端口。

## 6. Docker Compose

真实机器狗模式：

```bash
docker compose up --build quadruped-ws
```

模拟模式：

```bash
docker compose --profile mock up --build quadruped-ws-mock
```

`docker-compose.yml` 中同样使用 `network_mode: host`。

## 7. 常用入口命令

容器默认命令是 `ws`，也可以手动指定：

| 命令 | 作用 |
| --- | --- |
| `ws` | 启动真实机器狗 WS 网关 |
| `ws-mock` | 启动模拟 WS 网关 |
| `example` | 运行自动动作示例 |
| `keyboard` | 运行键盘控制示例 |
| `imu` | 运行 IMU 示例 |
| `bash` | 进入容器 shell |

示例：

```bash
docker run --rm -it --network host quadruped-sdk:latest bash
docker run --rm -it --network host quadruped-sdk:latest keyboard
```

## 8. 部署到其他控制板

在新控制板上部署时，确认以下事项：

1. 控制板架构与镜像架构一致。香橙派一般为 ARM64，应在 ARM64 设备上构建，或使用 Docker Buildx 构建 ARM64 镜像。
2. 控制板有线网口配置为 `192.168.96.3/24`。
3. 机器狗地址为 `192.168.96.2:8080`。
4. 控制板 Wi-Fi 能被客户电脑或手机访问。
5. 运行容器时使用 `--network host`。

查看控制板 IP：

```bash
ip -4 addr
```

查看容器是否启动：

```bash
docker ps
```

如果执行 Docker 命令提示 `/var/run/docker.sock` 权限不足，可将当前用户加入 `docker` 用户组后重新登录，或临时使用 `sudo docker`。

临时使用 `sudo docker` 构建和运行：

```bash
make docker_build DOCKER="sudo docker"
make docker_run_ws DOCKER="sudo docker"
make docker_run_mock DOCKER="sudo docker"
```

查看网关日志：

```bash
docker logs <container_id>
```

## 9. 版本打包和导出

构建完成后可导出镜像：

```bash
docker save quadruped-sdk:latest -o quadruped-sdk-latest.tar
```

在另一台控制板导入：

```bash
docker load -i quadruped-sdk-latest.tar
```

导入后运行：

```bash
docker run --rm -it --network host quadruped-sdk:latest ws
```

## 10. 注意事项

1. 真实机器狗模式推荐使用 `--network host`，避免 UDP 路由和端口映射问题。
2. 如果 `9001` 已被占用，可以通过 `LISTEN_PORT` 修改端口。
3. 同一时间不要启动多个真实控制网关同时控制同一台机器狗。
4. 运行真实运动示例前，确保机器狗周围安全。
5. 模拟模式只能验证网页流程，不能验证真实运动效果。

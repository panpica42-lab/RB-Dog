import { createGatewayClient } from '../services/gateway.js'

export const STORAGE_KEY = 'quadruped_controller_address'
export const DEFAULT_CONTROLLER_ADDRESS = '10.0.50.236:9001'

export default {
  data() {
    return {
      gateway: null,
      controllerAddressInput: DEFAULT_CONTROLLER_ADDRESS,
      connected: false,
      connecting: false,
      connectHint: '等待连接',
      target: '--'
    }
  },
  computed: {
    connectLabel() {
      if (this.connected) return '已连接'
      if (this.connecting) return '连接中'
      return '未连接'
    }
  },
  created() {
    this.gateway = createGatewayClient({
      onOpen: this.handleGatewayOpen,
      onClose: this.handleGatewayClose,
      onError: this.handleGatewayError,
      onMessage: this.handleGatewayMessage
    })
  },
  methods: {
    loadStoredAddress() {
      const saved = uni.getStorageSync(STORAGE_KEY)
      this.controllerAddressInput = saved || DEFAULT_CONTROLLER_ADDRESS
    },
    normalizeAddress(input) {
      let address = String(input || '').trim() || DEFAULT_CONTROLLER_ADDRESS
      address = address.replace(/^wss?:\/\//i, '').replace(/\/ws(?:$|\?)?.*$/i, '').replace(/\/$/, '')
      return address || DEFAULT_CONTROLLER_ADDRESS
    },
    buildSocketUrl(address) {
      return `ws://${this.normalizeAddress(address)}/ws`
    },
    saveAndConnect() {
      this.controllerAddressInput = this.normalizeAddress(this.controllerAddressInput)
      uni.setStorageSync(STORAGE_KEY, this.controllerAddressInput)
      this.connect()
    },
    connect() {
      const address = this.normalizeAddress(this.controllerAddressInput)
      const url = this.buildSocketUrl(address)
      this.controllerAddressInput = address
      uni.setStorageSync(STORAGE_KEY, address)
      this.closeSocket()
      this.connected = false
      this.connecting = true
      this.connectHint = '正在连接控制网关'
      this.addLog(`连接 ${address}`)
      this.gateway.connect(url)
      setTimeout(() => {
        if (!this.connected && this.connecting) {
          this.connecting = false
          this.connectHint = '连接超时，正在探测 HTTP 网关'
          this.addLog('WebSocket 连接超时')
          this.probeGatewayHttp()
        }
      }, 5000)
    },
    closeSocket() {
      if (this.stopCameraCapture) this.stopCameraCapture({ force: true })
      if (this.stopPointCloudCapture) this.stopPointCloudCapture({ force: true })
      if (this.gateway) this.gateway.close()
      if (this.resetVisionCaptureState) this.resetVisionCaptureState()
    },
    handleGatewayOpen() {
      this.connectHint = '已建立 WebSocket，等待网关握手'
      this.addLog('WebSocket 已连接')
    },
    handleGatewayClose() {
      this.connected = false
      this.connecting = false
      this.connectHint = '连接已断开，请检查网络后重试'
      if (this.pageMode !== 'connect') this.backToConnect(false)
    },
    handleGatewayError(error) {
      this.connected = false
      this.connecting = false
      this.connectHint = '连接失败，请确认 IP、端口和网关服务'
      this.addLog(`WebSocket 连接错误${error && error.errMsg ? `: ${error.errMsg}` : ''}`)
      this.probeGatewayHttp()
    },
    handleGatewayMessage(message, error) {
      if (error || !message) {
        this.addLog(`收到无效消息${error && error.message ? `: ${error.message}` : ''}`)
        return
      }
      this.routeGatewayMessage(message)
    },
    sendCommand(payload, showLog = true) {
      if (!this.gateway || !this.gateway.isOpen() || !this.connected) {
        if (showLog) this.addLog('未连接，命令未发送')
        return false
      }
      return this.gateway.send(payload, {
        fail: () => {
          this.connected = false
          this.addLog('命令发送失败')
        }
      })
    },
    probeGatewayHttp() {
      const address = this.normalizeAddress(this.controllerAddressInput)
      uni.request({
        url: `http://${address}/`,
        method: 'GET',
        timeout: 2500,
        success: response => {
          const status = Number(response.statusCode || 0)
          if (status >= 200 && status < 500) {
            this.connectHint = 'HTTP 网关可访问，但 WebSocket /ws 握手失败'
            this.addLog(`HTTP 探测成功 ${status}，请检查 /ws 服务`)
          } else {
            this.connectHint = `HTTP 探测异常：${status || '--'}`
            this.addLog(`HTTP 探测异常 ${status || '--'}`)
          }
        },
        fail: error => {
          this.connectHint = '控制网关不可达，请检查 IP、端口、Wi-Fi 或网关进程'
          this.addLog(`HTTP 探测失败${error && error.errMsg ? `: ${error.errMsg}` : ''}`)
        }
      })
    }
  }
}

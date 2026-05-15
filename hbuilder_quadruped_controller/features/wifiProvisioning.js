import { createBleProvisionClient } from '../services/bleProvisioning.js'
import { STORAGE_KEY } from './gatewayConnection.js'

const GATEWAY_PORT = 9001
const WIFI_SCAN_TIMEOUT_MS = 18000
const BLE_INIT_OVERLAY_MS = 500
const STATUS_WAIT_TIMEOUT_MS = 3500

function upsertDevice(devices, device) {
  const next = devices.slice()
  const index = next.findIndex(item => item.deviceId === device.deviceId)
  if (index >= 0) {
    next.splice(index, 1, { ...next[index], ...device })
  } else {
    next.push(device)
  }
  return next.sort((left, right) => Number(right.RSSI || 0) - Number(left.RSSI || 0))
}

export default {
  data() {
    return {
      bleProvision: null,
      bleDevices: [],
      bleScanning: false,
      bleConnected: false,
      bleBusy: false,
      bleAutoConnecting: false,
      bleInitializing: false,
      bleDeviceName: '',
      provisionHint: '可通过蓝牙将 Wi-Fi 配置发送到设备',
      wifiNetworks: [],
      wifiScanning: false,
      selectedWifiSsid: '',
      manualWifiSsid: '',
      wifiPassword: '',
      wifiHidden: false,
      wifiProvisioning: false,
      wifiProvisionResult: null,
      wifiScanTimer: null,
      wifiStatusTimer: null,
      deviceWifiConnected: false,
      deviceWifiSsid: '',
      deviceWifiIp: '',
      deviceGatewayPort: GATEWAY_PORT
    }
  },
  computed: {
    provisionSsid() {
      return String(this.selectedWifiSsid || this.manualWifiSsid || '').trim()
    },
    provisionButtonLabel() {
      if (this.wifiProvisioning) return '配网中'
      if (this.wifiScanning) return '扫描中'
      if (this.bleAutoConnecting) return '连接机器狗中'
      if (this.bleScanning) return '正在寻找机器狗'
      return '扫描机器狗'
    }
  },
  methods: {
    clearWifiScanTimer() {
      if (!this.wifiScanTimer) return
      clearTimeout(this.wifiScanTimer)
      this.wifiScanTimer = null
    },
    clearWifiStatusTimer() {
      if (!this.wifiStatusTimer) return
      clearTimeout(this.wifiStatusTimer)
      this.wifiStatusTimer = null
    },
    startWifiStatusTimer() {
      this.clearWifiStatusTimer()
      this.wifiStatusTimer = setTimeout(() => {
        this.wifiStatusTimer = null
        if (!this.bleConnected || this.deviceWifiConnected || this.wifiScanning) return
        this.provisionHint = '未读取到设备网络状态，继续扫描 Wi-Fi'
        this.scanProvisionWifi()
      }, STATUS_WAIT_TIMEOUT_MS)
    },
    startWifiScanTimer() {
      this.clearWifiScanTimer()
      this.wifiScanTimer = setTimeout(async () => {
        if (!this.wifiScanning || !this.bleProvision) return
        this.addLog('Wi-Fi 扫描等待超时，尝试主动读取列表')
        try {
          await this.bleProvision.sendCommand('scan_wifi')
          this.startWifiScanTimer()
          return
        } catch (error) {}
        this.wifiScanning = false
        this.provisionHint = 'Wi-Fi 扫描超时，请检查香橙派无线网卡或重试'
      }, WIFI_SCAN_TIMEOUT_MS)
    },
    ensureBleProvision() {
      if (this.bleProvision) return this.bleProvision
      this.bleProvision = createBleProvisionClient({
        onDevice: this.handleBleDeviceFound,
        onMessage: this.handleBleProvisionMessage,
        onError: this.handleBleProvisionError,
        onState: message => {
          this.provisionHint = message
        }
      })
      return this.bleProvision
    },
    async startBleProvisioning() {
      const client = this.ensureBleProvision()
      this.bleDevices = []
      this.bleConnected = false
      this.bleDeviceName = ''
      this.wifiProvisionResult = null
      this.bleScanning = true
      this.bleAutoConnecting = false
      this.bleInitializing = false
      this.bleBusy = true
      this.deviceWifiConnected = false
      this.deviceWifiSsid = ''
      this.deviceWifiIp = ''
      this.deviceGatewayPort = GATEWAY_PORT
      try {
        await client.startScan()
        this.provisionHint = '正在扫描蓝牙设备'
        this.addLog('开始扫描 BLE 配网设备')
      } catch (error) {
        this.bleScanning = false
        this.handleBleProvisionError(error && error.errMsg ? error.errMsg : '蓝牙扫描失败', error)
      } finally {
        this.bleBusy = false
      }
    },
    async stopBleProvisioningScan() {
      if (!this.bleProvision) return
      this.bleScanning = false
      await this.bleProvision.stopScan()
      this.provisionHint = '蓝牙扫描已停止'
    },
    handleBleDeviceFound(device) {
      this.bleDevices = upsertDevice(this.bleDevices, device)
      if (this.bleScanning && !this.bleConnected && !this.bleAutoConnecting) {
        this.connectBleProvisionDevice(device)
      }
    },
    async connectBleProvisionDevice(device) {
      const client = this.ensureBleProvision()
      this.bleBusy = true
      this.bleScanning = false
      this.bleAutoConnecting = true
      this.bleInitializing = false
      this.bleDeviceName = device.name || 'RoboDog'
      try {
        await client.connect(device.deviceId)
        this.bleConnected = true
        this.bleInitializing = true
        this.provisionHint = 'BLE 已连接，正在读取设备状态'
        this.addLog(`BLE 已连接 ${this.bleDeviceName}`)
        await new Promise(resolve => setTimeout(resolve, BLE_INIT_OVERLAY_MS))
        await client.sendCommand('get_status')
        this.startWifiStatusTimer()
      } catch (error) {
        this.bleConnected = false
        this.handleBleProvisionError(error && error.errMsg ? error.errMsg : 'BLE 连接失败', error)
      } finally {
        this.bleInitializing = false
        this.bleBusy = false
        this.bleAutoConnecting = false
      }
    },
    async scanProvisionWifi() {
      if (!this.bleConnected || !this.bleProvision) {
        this.provisionHint = '请先连接蓝牙设备'
        return
      }
      this.clearWifiStatusTimer()
      this.deviceWifiConnected = false
      this.clearWifiScanTimer()
      this.wifiNetworks = []
      this.wifiScanning = true
      this.provisionHint = '正在扫描附近 Wi-Fi'
      try {
        await this.bleProvision.sendCommand('scan_wifi')
        this.startWifiScanTimer()
      } catch (error) {
        this.wifiScanning = false
        this.handleBleProvisionError(error && error.errMsg ? error.errMsg : 'Wi-Fi 扫描命令发送失败', error)
      }
    },
    selectProvisionWifi(network) {
      this.selectedWifiSsid = network && network.ssid ? network.ssid : ''
      this.manualWifiSsid = ''
      this.provisionHint = this.selectedWifiSsid ? `已选择 ${this.selectedWifiSsid}` : '请选择 Wi-Fi'
    },
    updateManualWifiSsid(value) {
      this.manualWifiSsid = value
      if (value) this.selectedWifiSsid = ''
    },
    updateWifiPassword(value) {
      this.wifiPassword = value
    },
    toggleWifiHidden() {
      this.wifiHidden = !this.wifiHidden
    },
    async submitWifiProvisioning() {
      if (!this.bleConnected || !this.bleProvision) {
        this.provisionHint = '请先连接蓝牙设备'
        return
      }
      const ssid = this.provisionSsid
      if (!ssid) {
        this.provisionHint = '请选择或输入 Wi-Fi 名称'
        return
      }
      this.wifiProvisioning = true
      this.wifiProvisionResult = null
      this.provisionHint = `正在发送 ${ssid} 的网络配置`
      try {
        await this.bleProvision.sendCommand('set_wifi', {
          ssid,
          password: this.wifiPassword,
          auth: this.wifiPassword ? 'wpa2' : 'open',
          hidden: this.wifiHidden
        })
      } catch (error) {
        this.wifiProvisioning = false
        this.handleBleProvisionError(error && error.errMsg ? error.errMsg : 'Wi-Fi 配置发送失败', error)
      }
    },
    async clearProvisionWifi() {
      if (!this.bleConnected || !this.bleProvision) return
      this.provisionHint = '正在清除设备 Wi-Fi 配置'
      try {
        await this.bleProvision.sendCommand('clear_wifi')
      } catch (error) {
        this.handleBleProvisionError(error && error.errMsg ? error.errMsg : '清除 Wi-Fi 配置失败', error)
      }
    },
    async disconnectBleProvisioning() {
      if (!this.bleProvision) return
      this.clearWifiScanTimer()
      await this.bleProvision.disconnect()
      this.bleConnected = false
      this.bleScanning = false
      this.bleAutoConnecting = false
      this.bleInitializing = false
      this.wifiScanning = false
      this.wifiProvisioning = false
      this.provisionHint = 'BLE 已断开'
      this.clearWifiStatusTimer()
      this.deviceWifiConnected = false
      this.deviceWifiSsid = ''
      this.deviceWifiIp = ''
      this.deviceGatewayPort = GATEWAY_PORT
    },
    handleBleProvisionMessage(message) {
      if (!message || !message.cmd) return
      try {
        console.log('[BLE][message]', message.cmd, message)
      } catch (error) {}
      this.addLog(`BLE ${message.cmd}: ${message.msg || ''}`)
      if (message.cmd === 'get_status_resp') {
        this.handleDeviceWifiStatus(message)
      } else if (message.cmd === 'scan_wifi_resp') {
        if (Number(message.code) !== 0) {
          this.clearWifiScanTimer()
          this.wifiScanning = false
          this.provisionHint = message.msg || '设备 Wi-Fi 扫描失败'
          return
        }
        this.provisionHint = '设备正在扫描 Wi-Fi'
      } else if (message.cmd === 'wifi_list') {
        this.clearWifiScanTimer()
        this.wifiScanning = false
        this.wifiNetworks = ((message.data && message.data.list) || []).filter(item => item && item.ssid)
        this.provisionHint = this.wifiNetworks.length ? '请选择设备可连接的 Wi-Fi' : (message.msg || '未扫描到 Wi-Fi，可手动输入名称')
      } else if (message.cmd === 'set_wifi_resp') {
        if (Number(message.code) !== 0) {
          this.wifiProvisioning = false
          this.provisionHint = message.msg || '设备拒绝该网络配置'
        } else {
          this.provisionHint = '设备已接收配置，正在连接网络'
        }
      } else if (message.cmd === 'wifi_progress') {
        this.provisionHint = message.msg || (message.data && message.data.desc) || '正在连接 Wi-Fi'
      } else if (message.cmd === 'wifi_result') {
        this.handleWifiProvisionResult(message)
      } else if (message.cmd === 'clear_wifi_resp') {
        this.provisionHint = message.msg || 'Wi-Fi 配置已清除'
      }
    },
    handleDeviceWifiStatus(message) {
      this.clearWifiStatusTimer()
      const data = message.data || {}
      const ssid = String(data.connectedSsid || data.ssid || '').trim()
      const ip = String(data.ip || '').trim()
      const wifiState = Number(data.wifiState || 0)
      const port = Number(data.robotPort || data.gatewayPort || GATEWAY_PORT) || GATEWAY_PORT
      if (Number(message.code) === 0 && wifiState === 2 && ssid && ip) {
        this.deviceWifiConnected = true
        this.deviceWifiSsid = ssid
        this.deviceWifiIp = ip
        this.deviceGatewayPort = port
        this.controllerAddressInput = `${ip}:${port}`
        uni.setStorageSync(STORAGE_KEY, this.controllerAddressInput)
        this.wifiNetworks = []
        this.wifiScanning = false
        this.provisionHint = `设备已连接 Wi-Fi：${ssid}`
        this.addLog(`设备已联网 ${ssid} ${this.controllerAddressInput}`)
        return
      }
      this.deviceWifiConnected = false
      this.deviceWifiSsid = ssid
      this.deviceWifiIp = ip
      this.deviceGatewayPort = port
      this.provisionHint = ip ? `设备已联网：${ip}，可重新配网` : '设备未联网，正在扫描 Wi-Fi'
      this.scanProvisionWifi()
    },
    continueWithDeviceWifi() {
      if (!this.deviceWifiIp) {
        this.provisionHint = '设备没有返回 IP，无法连接控制网关'
        return
      }
      const port = this.deviceGatewayPort || GATEWAY_PORT
      this.controllerAddressInput = `${this.deviceWifiIp}:${port}`
      uni.setStorageSync(STORAGE_KEY, this.controllerAddressInput)
      this.provisionHint = `正在连接 ${this.controllerAddressInput}`
      this.addLog(`使用已连接 Wi-Fi 继续 ${this.controllerAddressInput}`)
      this.connect()
    },
    reprovisionDeviceWifi() {
      this.deviceWifiConnected = false
      this.deviceWifiSsid = ''
      this.deviceWifiIp = ''
      this.deviceGatewayPort = GATEWAY_PORT
      this.scanProvisionWifi()
    },
    handleWifiProvisionResult(message) {
      this.wifiProvisioning = false
      this.wifiProvisionResult = message
      if (Number(message.code) !== 0) {
        this.provisionHint = `配网失败：${message.msg || message.code}`
        return
      }
      const data = message.data || {}
      const ip = data.ip
      const port = Number(data.robotPort || data.gatewayPort || GATEWAY_PORT) || GATEWAY_PORT
      if (!ip) {
        this.provisionHint = '配网成功，但设备没有返回 IP'
        return
      }
      this.controllerAddressInput = `${ip}:${port}`
      uni.setStorageSync(STORAGE_KEY, this.controllerAddressInput)
      this.provisionHint = `配网成功，正在连接 ${this.controllerAddressInput}`
      this.addLog(`配网成功 ${this.controllerAddressInput}`)
      this.connect()
    },
    handleBleProvisionError(message, error) {
      this.provisionHint = message || 'BLE 配网失败'
      this.addLog(`BLE 配网错误${message ? `: ${message}` : ''}`)
      if (error && error.errCode === 10001) {
        this.provisionHint = '请打开手机蓝牙后重试'
      }
    }
  }
}

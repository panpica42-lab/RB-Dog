import { createBleProvisionClient } from '../services/bleProvisioning.js'
import { DEFAULT_CONTROLLER_ADDRESS, STORAGE_KEY } from './gatewayConnection.js'

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
      bleDeviceName: '',
      provisionHint: '可通过蓝牙把现场 Wi-Fi 发给二开板',
      wifiNetworks: [],
      wifiScanning: false,
      selectedWifiSsid: '',
      manualWifiSsid: '',
      wifiPassword: '',
      wifiHidden: false,
      wifiProvisioning: false,
      wifiProvisionResult: null
    }
  },
  computed: {
    provisionSsid() {
      return String(this.selectedWifiSsid || this.manualWifiSsid || '').trim()
    },
    provisionButtonLabel() {
      if (this.wifiProvisioning) return '配网中'
      if (this.wifiScanning) return '扫描中'
      if (this.bleScanning) return '扫描蓝牙中'
      return '开始蓝牙配网'
    }
  },
  methods: {
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
      this.bleBusy = true
      try {
        await client.startScan()
        this.provisionHint = '正在扫描 RoboDog 蓝牙设备'
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
    },
    async connectBleProvisionDevice(device) {
      const client = this.ensureBleProvision()
      this.bleBusy = true
      this.bleScanning = false
      this.bleDeviceName = device.name || 'RoboDog'
      try {
        await client.connect(device.deviceId)
        this.bleConnected = true
        this.provisionHint = 'BLE 已连接，正在读取设备状态'
        this.addLog(`BLE 已连接 ${this.bleDeviceName}`)
        await client.sendCommand('get_status')
      } catch (error) {
        this.bleConnected = false
        this.handleBleProvisionError(error && error.errMsg ? error.errMsg : 'BLE 连接失败', error)
      } finally {
        this.bleBusy = false
      }
    },
    async scanProvisionWifi() {
      if (!this.bleConnected || !this.bleProvision) {
        this.provisionHint = '请先连接 RoboDog 蓝牙设备'
        return
      }
      this.wifiNetworks = []
      this.wifiScanning = true
      this.provisionHint = '正在让二开板扫描附近 Wi-Fi'
      try {
        await this.bleProvision.sendCommand('scan_wifi')
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
        this.provisionHint = '请先连接 RoboDog 蓝牙设备'
        return
      }
      const ssid = this.provisionSsid
      if (!ssid) {
        this.provisionHint = '请选择或输入 Wi-Fi 名称'
        return
      }
      this.wifiProvisioning = true
      this.wifiProvisionResult = null
      this.provisionHint = `正在把 ${ssid} 的配置发送给二开板`
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
      this.provisionHint = '正在清除二开板 Wi-Fi 配置'
      try {
        await this.bleProvision.sendCommand('clear_wifi')
      } catch (error) {
        this.handleBleProvisionError(error && error.errMsg ? error.errMsg : '清除 Wi-Fi 配置失败', error)
      }
    },
    async disconnectBleProvisioning() {
      if (!this.bleProvision) return
      await this.bleProvision.disconnect()
      this.bleConnected = false
      this.bleScanning = false
      this.wifiScanning = false
      this.wifiProvisioning = false
      this.provisionHint = 'BLE 已断开'
    },
    handleBleProvisionMessage(message) {
      if (!message || !message.cmd) return
      this.addLog(`BLE ${message.cmd}: ${message.msg || ''}`)
      if (message.cmd === 'get_status_resp') {
        const ip = message.data && message.data.ip
        this.provisionHint = ip ? `设备已联网：${ip}` : '设备未联网，可继续配网'
      } else if (message.cmd === 'scan_wifi_resp') {
        this.provisionHint = '二开板正在扫描 Wi-Fi'
      } else if (message.cmd === 'wifi_list') {
        this.wifiScanning = false
        this.wifiNetworks = ((message.data && message.data.list) || []).filter(item => item && item.ssid)
        this.provisionHint = this.wifiNetworks.length ? '请选择机器狗能看到的 Wi-Fi' : '未扫描到 Wi-Fi，可手动输入名称'
      } else if (message.cmd === 'set_wifi_resp') {
        if (Number(message.code) !== 0) {
          this.wifiProvisioning = false
          this.provisionHint = message.msg || '二开板拒绝 Wi-Fi 配置'
        } else {
          this.provisionHint = '二开板已接收配置，等待连接结果'
        }
      } else if (message.cmd === 'wifi_progress') {
        this.provisionHint = message.msg || (message.data && message.data.desc) || '正在连接 Wi-Fi'
      } else if (message.cmd === 'wifi_result') {
        this.handleWifiProvisionResult(message)
      } else if (message.cmd === 'clear_wifi_resp') {
        this.provisionHint = message.msg || 'Wi-Fi 配置已清除'
      }
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
      const port = Number(data.robotPort || 0) || Number(DEFAULT_CONTROLLER_ADDRESS.split(':')[1]) || 9001
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

export const PROVISION_SERVICE_UUID = '0000a001-0000-1000-8000-00805f9b34fb'
export const DEVICE_INFO_UUID = '0000a002-0000-1000-8000-00805f9b34fb'
export const COMMAND_UUID = '0000a003-0000-1000-8000-00805f9b34fb'
export const NOTIFY_UUID = '0000a004-0000-1000-8000-00805f9b34fb'
export const WIFI_LIST_UUID = '0000a005-0000-1000-8000-00805f9b34fb'

function normalizeUuid(value) {
  return String(value || '').toLowerCase()
}

function textToArrayBuffer(text) {
  const encoded = encodeURIComponent(String(text || ''))
  const bytes = []
  for (let index = 0; index < encoded.length; index += 1) {
    const char = encoded[index]
    if (char === '%') {
      bytes.push(parseInt(encoded.slice(index + 1, index + 3), 16))
      index += 2
    } else {
      bytes.push(char.charCodeAt(0))
    }
  }
  return new Uint8Array(bytes).buffer
}

function arrayBufferToText(buffer) {
  if (typeof buffer === 'string') return buffer
  const bytes = new Uint8Array(buffer || [])
  if (typeof TextDecoder !== 'undefined') {
    return new TextDecoder('utf-8').decode(bytes)
  }
  let encoded = ''
  for (let index = 0; index < bytes.length; index += 1) {
    encoded += `%${bytes[index].toString(16).padStart(2, '0')}`
  }
  return decodeURIComponent(encoded)
}

function promisify(fn, options = {}) {
  return new Promise((resolve, reject) => {
    fn({
      ...options,
      success: resolve,
      fail: reject
    })
  })
}

export function createBleProvisionClient({ onDevice, onMessage, onError, onState } = {}) {
  let deviceId = ''
  let serviceId = PROVISION_SERVICE_UUID
  let commandId = COMMAND_UUID
  let notifyIds = []
  let requestSeq = 0
  let initialized = false
  let discovering = false
  let valueListenerReady = false

  function emitState(message) {
    if (onState) onState(message)
  }

  function emitError(error, fallback = 'BLE 操作失败') {
    const message = error && error.errMsg ? error.errMsg : fallback
    if (onError) onError(message, error)
  }

  function handleFound(result) {
    const devices = result.devices || (result.deviceId ? [result] : [])
    devices.forEach(device => {
      const name = device.name || device.localName || ''
      const serviceIds = (device.advertisServiceUUIDs || []).map(normalizeUuid)
      const matched = name.indexOf('RoboDog') === 0 || serviceIds.includes(PROVISION_SERVICE_UUID)
      if (!matched || !onDevice) return
      onDevice({
        deviceId: device.deviceId,
        name: name || 'RoboDog',
        RSSI: device.RSSI || 0
      })
    })
  }

  async function init() {
    if (initialized) return
    await promisify(uni.openBluetoothAdapter)
    initialized = true
    uni.onBluetoothDeviceFound(handleFound)
  }

  async function startScan() {
    await init()
    await stopScan()
    emitState('正在扫描 RoboDog 蓝牙设备')
    await promisify(uni.startBluetoothDevicesDiscovery, {
      services: [PROVISION_SERVICE_UUID],
      allowDuplicatesKey: false
    })
    discovering = true
  }

  async function stopScan() {
    if (!initialized || !discovering) return
    discovering = false
    try {
      await promisify(uni.stopBluetoothDevicesDiscovery)
    } catch (error) {}
  }

  async function connect(nextDeviceId) {
    await init()
    await stopScan()
    await disconnect()
    deviceId = nextDeviceId
    emitState('正在连接 BLE 设备')
    await promisify(uni.createBLEConnection, { deviceId })
    try {
      await promisify(uni.setBLEMTU, { deviceId, mtu: 512 })
    } catch (error) {}
    await discoverCharacteristics()
    await enableNotify()
    emitState('BLE 已连接')
    return readDeviceInfo()
  }

  async function discoverCharacteristics() {
    const servicesResult = await promisify(uni.getBLEDeviceServices, { deviceId })
    const service = (servicesResult.services || []).find(item => normalizeUuid(item.uuid) === PROVISION_SERVICE_UUID)
    serviceId = service ? service.uuid : PROVISION_SERVICE_UUID

    const charsResult = await promisify(uni.getBLEDeviceCharacteristics, { deviceId, serviceId })
    const chars = charsResult.characteristics || []
    const command = chars.find(item => normalizeUuid(item.uuid) === COMMAND_UUID)
    const notify = chars.find(item => normalizeUuid(item.uuid) === NOTIFY_UUID)
    const wifiList = chars.find(item => normalizeUuid(item.uuid) === WIFI_LIST_UUID)
    commandId = command ? command.uuid : COMMAND_UUID
    notifyIds = [notify, wifiList].filter(Boolean).map(item => item.uuid)
  }

  async function enableNotify() {
    if (!valueListenerReady) {
      valueListenerReady = true
      uni.onBLECharacteristicValueChange(event => {
        const uuid = normalizeUuid(event.characteristicId)
        if (uuid !== NOTIFY_UUID && uuid !== WIFI_LIST_UUID) return
        try {
          const text = arrayBufferToText(event.value)
          if (onMessage) onMessage(JSON.parse(text), uuid)
        } catch (error) {
          emitError(error, 'BLE 消息解析失败')
        }
      })
    }
    for (let index = 0; index < notifyIds.length; index += 1) {
      await promisify(uni.notifyBLECharacteristicValueChange, {
        deviceId,
        serviceId,
        characteristicId: notifyIds[index],
        state: true
      })
    }
  }

  async function readDeviceInfo() {
    try {
      const result = await promisify(uni.readBLECharacteristicValue, {
        deviceId,
        serviceId,
        characteristicId: DEVICE_INFO_UUID
      })
      if (result && result.value) {
        return JSON.parse(arrayBufferToText(result.value))
      }
    } catch (error) {}
    return null
  }

  async function sendCommand(cmd, data = {}, id = '') {
    if (!deviceId) throw new Error('BLE device is not connected')
    requestSeq += 1
    const payload = {
      id: id || String(requestSeq),
      cmd,
      data
    }
    await promisify(uni.writeBLECharacteristicValue, {
      deviceId,
      serviceId,
      characteristicId: commandId,
      value: textToArrayBuffer(JSON.stringify(payload))
    })
    return payload.id
  }

  async function disconnect() {
    if (!deviceId) return
    const closingDeviceId = deviceId
    deviceId = ''
    notifyIds = []
    try {
      await promisify(uni.closeBLEConnection, { deviceId: closingDeviceId })
    } catch (error) {}
  }

  function closeAdapter() {
    stopScan()
    disconnect()
    if (!initialized) return
    initialized = false
    try {
      uni.closeBluetoothAdapter({})
    } catch (error) {}
  }

  return {
    startScan,
    stopScan,
    connect,
    disconnect,
    closeAdapter,
    sendCommand
  }
}

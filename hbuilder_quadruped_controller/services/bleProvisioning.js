export const PROVISION_SERVICE_UUID = '0000a001-0000-1000-8000-00805f9b34fb'
export const DEVICE_INFO_UUID = '0000a002-0000-1000-8000-00805f9b34fb'
export const COMMAND_UUID = '0000a003-0000-1000-8000-00805f9b34fb'
export const NOTIFY_UUID = '0000a004-0000-1000-8000-00805f9b34fb'
export const WIFI_LIST_UUID = '0000a005-0000-1000-8000-00805f9b34fb'

function normalizeUuid(value) {
  return String(value || '').toLowerCase()
}

function hasProperty(characteristic, name) {
  return Boolean(characteristic && characteristic.properties && characteristic.properties[name])
}

function getWriteCandidates(characteristic) {
  const properties = (characteristic && characteristic.properties) || {}
  const candidates = []
  if (properties.write) candidates.push('write')
  if (properties.writeNoResponse || properties.writeWithoutResponse || properties['write-without-response']) {
    candidates.push('writeNoResponse')
  }
  if (!candidates.length) {
    candidates.push('write', 'writeNoResponse')
  }
  candidates.push('default')
  return Array.from(new Set(candidates))
}

function makeError(message, detail) {
  const error = new Error(message)
  error.errMsg = detail ? `${message}: ${detail}` : message
  return error
}

function previewText(text, limit = 72) {
  const value = String(text || '').replace(/\s+/g, ' ').trim()
  return value.length > limit ? `${value.slice(0, limit)}...` : value
}

function debugLog(...args) {
  try {
    console.log('[BLE]', ...args)
  } catch (error) {}
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

function bytesToBase64(bytes) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
  let output = ''
  for (let index = 0; index < bytes.length; index += 3) {
    const first = bytes[index]
    const second = index + 1 < bytes.length ? bytes[index + 1] : 0
    const third = index + 2 < bytes.length ? bytes[index + 2] : 0
    const triplet = (first << 16) | (second << 8) | third
    output += chars[(triplet >> 18) & 63]
    output += chars[(triplet >> 12) & 63]
    output += index + 1 < bytes.length ? chars[(triplet >> 6) & 63] : '='
    output += index + 2 < bytes.length ? chars[triplet & 63] : '='
  }
  return output
}

function base64ToBytes(text) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
  const clean = String(text || '').replace(/[^A-Za-z0-9+/=]/g, '')
  const bytes = []
  for (let index = 0; index < clean.length; index += 4) {
    const chunk = clean.slice(index, index + 4)
    if (chunk.length < 4) break
    const values = chunk.split('').map(char => (char === '=' ? 64 : chars.indexOf(char)))
    if (values.some(value => value < 0)) throw new Error('invalid base64')
    const triplet = ((values[0] & 63) << 18) | ((values[1] & 63) << 12) | ((values[2] & 63) << 6) | (values[3] & 63)
    bytes.push((triplet >> 16) & 255)
    if (chunk[2] !== '=') bytes.push((triplet >> 8) & 255)
    if (chunk[3] !== '=') bytes.push(triplet & 255)
  }
  return new Uint8Array(bytes)
}

function encodeFrameNumber(value, width = 2) {
  const chars = '0123456789abcdefghijklmnopqrstuvwxyz'
  if (value < 0) throw new Error('frame number must be positive')
  let encoded = ''
  let current = value
  do {
    encoded = chars[current % 36] + encoded
    current = Math.floor(current / 36)
  } while (current > 0)
  if (encoded.length > width) throw new Error('frame number exceeds width')
  return encoded.padStart(width, '0')
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
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
  let commandWriteType = 'write'
  let commandWriteCandidates = ['write', 'writeNoResponse', 'default']
  let notifyIds = []
  let requestSeq = 0
  let frameSeq = 0
  let initialized = false
  let discovering = false
  let valueListenerReady = false
  let lastWifiListMessage = null
  const notifyFrameBuffers = {}

  function emitState(message) {
    debugLog('state', message)
    if (onState) onState(message)
  }

  function emitError(error, fallback = 'BLE 操作失败') {
    const message = error && error.errMsg ? error.errMsg : fallback
    debugLog('error', message, error)
    if (onError) onError(message, error)
  }

  function parseFrameDigit(char) {
    const code = String(char || '').toLowerCase().charCodeAt(0)
    if (code >= 48 && code <= 57) return code - 48
    if (code >= 97 && code <= 122) return code - 97 + 10
    throw new Error('bad frame digit')
  }

  function parseFrameNumber(text) {
    let value = 0
    for (let index = 0; index < text.length; index += 1) {
      value = value * 36 + parseFrameDigit(text[index])
    }
    return value
  }

  function decodeIncomingText(text, uuid) {
    if (!text || text[0] !== '~') return text
    const splitIndex = text.indexOf(':')
    if (splitIndex !== 6) throw new Error('bad frame header')
    const frameId = text[1]
    const seq = parseFrameNumber(text.slice(2, 4))
    const total = parseFrameNumber(text.slice(4, 6))
    if (total <= 0 || seq >= total) throw new Error('bad frame index')
    const key = `${uuid}:${frameId}`
    const buffer = notifyFrameBuffers[key] || { total, parts: {}, time: Date.now() }
    if (buffer.total !== total) {
      buffer.total = total
      buffer.parts = {}
    }
    buffer.parts[seq] = text.slice(splitIndex + 1)
    buffer.time = Date.now()
    notifyFrameBuffers[key] = buffer

    Object.keys(notifyFrameBuffers).forEach(item => {
      if (Date.now() - notifyFrameBuffers[item].time > 8000) delete notifyFrameBuffers[item]
    })

    if (Object.keys(buffer.parts).length < total) return null
    delete notifyFrameBuffers[key]
    const encoded = Array.from({ length: total }, (_, index) => buffer.parts[index] || '').join('')
    return arrayBufferToText(base64ToBytes(encoded).buffer)
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
        name: name || '设备',
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
    emitState('正在扫描蓝牙设备')
    // Some phones do not surface 128-bit service UUIDs from scan response
    // reliably, so scan broadly and filter RoboDog/a001 in handleFound.
    await promisify(uni.startBluetoothDevicesDiscovery, {
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
    debugLog('connect:start', { deviceId })
    emitState('正在连接 BLE 设备')
    await promisify(uni.createBLEConnection, { deviceId })
    await sleep(200)
    try {
      await promisify(uni.setBLEMTU, { deviceId, mtu: 512 })
    } catch (error) {}
    await discoverCharacteristics()
    await enableNotify()
    await sleep(120)
    emitState('BLE 已连接')
    return readDeviceInfo()
  }

  async function discoverCharacteristics() {
    const servicesResult = await promisify(uni.getBLEDeviceServices, { deviceId })
    debugLog('services', (servicesResult.services || []).map(item => item.uuid))
    const service = (servicesResult.services || []).find(item => normalizeUuid(item.uuid) === PROVISION_SERVICE_UUID)
    if (!service) throw makeError('未发现设备配网服务')
    serviceId = service.uuid

    const charsResult = await promisify(uni.getBLEDeviceCharacteristics, { deviceId, serviceId })
    const chars = charsResult.characteristics || []
    debugLog('characteristics', chars.map(item => ({ uuid: item.uuid, properties: item.properties || {} })))
    const command = chars.find(
      item =>
        normalizeUuid(item.uuid) === COMMAND_UUID &&
        (hasProperty(item, 'write') ||
          hasProperty(item, 'writeNoResponse') ||
          hasProperty(item, 'writeWithoutResponse') ||
          hasProperty(item, 'write-without-response'))
    )
    const notify = chars.find(item => normalizeUuid(item.uuid) === NOTIFY_UUID && hasProperty(item, 'notify'))
    const wifiList = chars.find(item => normalizeUuid(item.uuid) === WIFI_LIST_UUID && hasProperty(item, 'notify'))
    if (!command) {
      const found = chars.map(item => `${item.uuid} ${JSON.stringify(item.properties || {})}`).join('; ')
      throw makeError('未发现可写入的 Command characteristic', found)
    }
    if (!notify && !wifiList) throw makeError('未发现可订阅的 Notify characteristic')
    commandId = command.uuid
    commandWriteCandidates = getWriteCandidates(command)
    commandWriteType = commandWriteCandidates[0] === 'default' ? 'write' : commandWriteCandidates[0]
    notifyIds = [notify, wifiList].filter(Boolean).map(item => item.uuid)
    emitState(`BLE 特征已确认：a003 ${commandWriteType}`)
  }

  async function enableNotify() {
    if (!valueListenerReady) {
      valueListenerReady = true
      uni.onBLECharacteristicValueChange(event => {
        const uuid = normalizeUuid(event.characteristicId)
        if (uuid !== NOTIFY_UUID && uuid !== WIFI_LIST_UUID) return
        try {
          const rawText = arrayBufferToText(event.value)
          debugLog('notify:raw', { uuid, len: rawText.length, preview: previewText(rawText) })
          const decoded = decodeIncomingText(rawText, uuid)
          if (!decoded) return
          const text = decoded
          debugLog('notify:decoded', { uuid, len: text.length, preview: previewText(text) })
          const message = JSON.parse(text)
          if (message && message.cmd === 'wifi_list') {
            lastWifiListMessage = message
          }
          if (onMessage) onMessage(message, uuid)
        } catch (error) {
          const rawText = arrayBufferToText(event.value)
          emitError(
            makeError(
              'BLE 消息解析失败',
              `uuid=${uuid} len=${rawText.length} preview=${previewText(rawText)} detail=${error && error.message ? error.message : error}`
            ),
            'BLE 消息解析失败'
          )
        }
      })
    }
    for (let index = 0; index < notifyIds.length; index += 1) {
      debugLog('notify:enable:start', { characteristicId: notifyIds[index] })
      await promisify(uni.notifyBLECharacteristicValueChange, {
        deviceId,
        serviceId,
        characteristicId: notifyIds[index],
        state: true
      })
      debugLog('notify:enable:ok', { characteristicId: notifyIds[index] })
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

  async function readWifiList() {
    debugLog('readWifiList:skip', 'wifi_list uses notify only; skip direct read fallback')
    return lastWifiListMessage
  }

  async function writeValue(value) {
    const options = {
      deviceId,
      serviceId,
      characteristicId: commandId,
      writeType: commandWriteType,
      value
    }
    try {
      await promisify(uni.writeBLECharacteristicValue, options)
      return
    } catch (error) {
      const message = error && error.errMsg ? error.errMsg : ''
      const alternative = commandWriteType === 'write' ? 'writeNoResponse' : 'write'
      if (message.indexOf('property not support') >= 0) {
        try {
          await promisify(uni.writeBLECharacteristicValue, {
            ...options,
            writeType: alternative
          })
          commandWriteType = alternative
          emitState(`BLE 写入模式已切换：a003 ${commandWriteType}`)
          return
        } catch (retryError) {
          throw makeError(
            'BLE 写入失败',
            `${retryError.errMsg || retryError} service=${serviceId} characteristic=${commandId} tried=${commandWriteType},${alternative}`
          )
        }
      }
      throw makeError(
        'BLE 写入失败',
        `${message || error} service=${serviceId} characteristic=${commandId} writeType=${commandWriteType}`
      )
    }
  }

  async function writeValueRobust(value) {
    const tried = []
    let lastError = null
    for (let index = 0; index < commandWriteCandidates.length; index += 1) {
      const candidate = commandWriteCandidates[index]
      const options = {
        deviceId,
        serviceId,
        characteristicId: commandId,
        value
      }
      if (candidate !== 'default') {
        options.writeType = candidate
      }
      tried.push(candidate)
      try {
        await promisify(uni.writeBLECharacteristicValue, options)
        if (candidate !== 'default') {
          commandWriteType = candidate
        }
        if (index > 0) {
          emitState(`BLE 写入模式已切换：a003 ${candidate}`)
        }
        return
      } catch (error) {
        lastError = error
        const message = error && error.errMsg ? error.errMsg : String(error || '')
        debugLog('write:retry', { candidate, message })
        if (message.indexOf('property not support') < 0) {
          break
        }
        await sleep(60)
      }
    }
    throw makeError(
      'BLE 写入失败',
      `${(lastError && lastError.errMsg) || lastError || 'unknown error'} service=${serviceId} characteristic=${commandId} tried=${tried.join(',')}`
    )
  }

  async function writeJsonPayload(payload) {
    const json = JSON.stringify(payload)
    debugLog('write:json', { cmd: payload && payload.cmd, len: json.length, preview: previewText(json) })
    const bytes = new Uint8Array(textToArrayBuffer(json))
    const encoded = bytesToBase64(bytes)
    const chunkSize = 15
    const total = Math.ceil(encoded.length / chunkSize)
    if (total > 36 * 36) throw makeError('BLE 数据过长，无法通过 BLE 分片发送')
    frameSeq = (frameSeq + 1) % 36
    const frameId = frameSeq.toString(36)
    debugLog('write:frames', { frameId, total })
    for (let index = 0; index < total; index += 1) {
      const frame = `~${frameId}${encodeFrameNumber(index)}${encodeFrameNumber(total)}:${encoded.slice(index * chunkSize, (index + 1) * chunkSize)}`
      debugLog('write:frame', { index, total, preview: previewText(frame) })
      await writeValueRobust(textToArrayBuffer(frame))
      await sleep(18)
    }
  }

  async function sendCommand(cmd, data = {}, id = '') {
    if (!deviceId) throw new Error('BLE device is not connected')
    requestSeq += 1
    const payload = {
      id: id || String(requestSeq),
      cmd,
      data
    }
    await writeJsonPayload(payload)
    return payload.id
  }

  async function disconnect() {
    if (!deviceId) return
    const closingDeviceId = deviceId
    deviceId = ''
    notifyIds = []
    commandId = COMMAND_UUID
    commandWriteType = 'write'
    commandWriteCandidates = ['write', 'writeNoResponse', 'default']
    lastWifiListMessage = null
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
    sendCommand,
    readWifiList
  }
}

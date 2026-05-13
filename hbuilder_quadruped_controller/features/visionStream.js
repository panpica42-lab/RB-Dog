import { cameraCommand, pointcloudCommand } from '../services/commands.js'

export default {
  data() {
    return {
      cameraFrame: '',
      cameraOnline: false,
      cameraStatus: '等待相机画面',
      pointCloudOnline: false,
      pointCloudStatus: '等待点云',
      pointCloudCount: 0,
      pointCloudPoints: [],
      cameraStatusKnown: false,
      pointCloudCaptureState: false,
      pointCloudCapturePending: false,
      pointCloudCaptureLastSentAt: 0,
      pointCloudUnavailable: false,
      cameraCaptureState: false,
      cameraCapturePending: false,
      cameraCaptureLastSentAt: 0,
      cameraFrameCount: 0,
      cameraFrameLastSize: 0,
      cameraDebugLoggedTypes: {},
      pendingPointCloudBinary: null,
      visionMode: 'rgb'
    }
  },
  methods: {
    handleVisionMessage(message) {
      if (message.type === 'binary') {
        this.updatePointCloudBinary(message.data)
        return true
      }
      if (this.isCameraFrameMessage(message)) {
        this.updateCameraFrame(message)
        return true
      }
      if (message.type === 'camera_status') {
        this.updateCameraStatus(message.ok, message.message)
        return true
      }
      if (message.type === 'pointcloud_frame') {
        this.updatePointCloudFrame(message)
        return true
      }
      if (message.type === 'pointcloud_status') {
        this.updatePointCloudStatus(message.ok, message.message)
        return true
      }
      return false
    },
    isCameraFrameMessage(message) {
      const type = String(message.type || '').toLowerCase()
      if ([
        'camera_frame',
        'rgb_frame',
        'color_frame',
        'video_frame',
        'image_frame',
        'frame'
      ].indexOf(type) >= 0) return true
      if (type.indexOf('status') >= 0 || type === 'hello' || type === 'snapshot') return false
      return Boolean(this.extractCameraFrame(message).data)
    },
    setVisionMode(mode) {
      this.visionMode = mode
      this.syncVisionCapture()
    },
    syncVisionCapture() {
      this.syncCameraCapture()
      this.syncPointCloudCapture()
    },
    syncCameraCapture() {
      const shouldCapture = this.pageMode === 'vision' && this.visionMode === 'rgb'
      this.setCameraCapture(shouldCapture)
    },
    syncPointCloudCapture() {
      const shouldCapture = this.pageMode === 'vision' && this.visionMode === 'pointcloud'
      this.setPointCloudCapture(shouldCapture)
    },
    stopCameraCapture(options = {}) {
      this.setCameraCapture(false, options)
    },
    stopPointCloudCapture(options = {}) {
      this.setPointCloudCapture(false, options)
    },
    resetVisionCaptureState() {
      this.pointCloudCaptureState = false
      this.pointCloudCapturePending = false
      this.cameraCaptureState = false
      this.cameraCapturePending = false
      this.pendingPointCloudBinary = null
    },
    updateCameraStatus(ok, message) {
      this.cameraOnline = Boolean(ok)
      this.cameraStatusKnown = true
      this.cameraStatus = message || (ok ? '相机在线' : '相机不可用')
      if (this.cameraOnline) {
        this.pointCloudUnavailable = false
        this.syncVisionCapture()
      }
      if (!this.cameraOnline) {
        this.pointCloudOnline = false
        this.pointCloudStatus = '相机不可用，点云已暂停'
        if (this.pointCloudCaptureState || this.pointCloudCapturePending) {
          this.setPointCloudCapture(false, { force: true })
        }
      }
    },
    updateCameraFrame(message) {
      const frame = this.extractCameraFrame(message)
      if (!frame.data) {
        this.logCameraDebug(message)
        return
      }
      this.cameraFrame = frame.src
      this.cameraOnline = true
      this.cameraStatusKnown = true
      this.pointCloudUnavailable = false
      this.cameraFrameCount += 1
      this.cameraFrameLastSize = frame.size
      this.cameraStatus = `RGB ${frame.width || '--'}x${frame.height || '--'} #${this.cameraFrameCount}`
    },
    extractCameraFrame(message) {
      const sources = this.compactObjects([
        message,
        message.frame,
        message.image,
        message.camera,
        message.rgb,
        message.color
      ])
      const data = this.findStringFrameField(sources, ['data', 'image', 'frame', 'jpeg', 'jpg', 'base64', 'payload', 'bytes'])
      const source = sources.find(item => this.findFrameField([item], ['width', 'w', 'height', 'h', 'format', 'encoding']) || '')
      const src = this.normalizeCameraSource(data, source && source.format, source && source.encoding)
      return {
        data,
        src,
        size: data ? data.length : 0,
        width: (source && (source.width || source.w)) || message.width || message.w,
        height: (source && (source.height || source.h)) || message.height || message.h
      }
    },
    normalizeCameraSource(data, format, encoding) {
      if (!data) return ''
      if (/^data:image\//i.test(data)) return data
      const type = String(format || '').toLowerCase().indexOf('png') >= 0 ? 'png' : 'jpeg'
      const isBase64 = !encoding || String(encoding).toLowerCase() === 'base64'
      return isBase64 ? `data:image/${type};base64,${data}` : data
    },
    compactObjects(items) {
      const objects = []
      for (const item of items) {
        if (item && typeof item === 'object' && !Array.isArray(item)) objects.push(item)
      }
      return objects
    },
    findFrameField(sources, fields) {
      for (const source of sources) {
        for (const field of fields) {
          const value = source && source[field]
          if (typeof value === 'string' && value.length) return value
          if (typeof value === 'number' && Number.isFinite(value)) return value
        }
      }
      return ''
    },
    findStringFrameField(sources, fields) {
      for (const source of sources) {
        for (const field of fields) {
          const value = source && source[field]
          if (typeof value === 'string' && value.length) return value
        }
      }
      return ''
    },
    logCameraDebug(message) {
      const type = String(message.type || 'unknown')
      if (this.cameraDebugLoggedTypes[type]) return
      this.cameraDebugLoggedTypes = Object.assign({}, this.cameraDebugLoggedTypes, { [type]: true })
      const keys = Object.keys(message || {}).join(',')
      this.cameraStatus = `收到 ${type}，但未找到图像字段`
      if (this.addLog) this.addLog(`视觉帧缺少图像字段: ${type} keys=${keys}`)
    },
    updatePointCloudStatus(ok, message) {
      this.pointCloudOnline = Boolean(ok)
      this.pointCloudStatus = message || (ok ? '点云在线' : '点云不可用')
      if (ok) {
        this.pointCloudUnavailable = false
      } else {
        this.pointCloudUnavailable = true
        this.pointCloudCaptureState = false
        this.pointCloudCapturePending = false
      }
    },
    updatePointCloudFrame(message) {
      if (message.format === 'xyzrgb_float32' && message.encoding === 'binary') {
        this.pendingPointCloudBinary = message
        this.pointCloudOnline = true
        this.pointCloudStatus = `等待点云二进制 ${message.count || '--'} 点`
        return
      }
      const points = message.points || []
      if (points.length) {
        this.pointCloudPoints = points
      }
      this.pointCloudCount = Number(message.count || 0)
      this.pointCloudOnline = true
      this.pointCloudUnavailable = false
      this.pointCloudStatus = `点云 ${this.pointCloudCount || Math.floor(points.length / 6)} 点`
    },
    updatePointCloudBinary(buffer) {
      const metadata = this.pendingPointCloudBinary
      this.pendingPointCloudBinary = null
      if (!metadata || !buffer) return
      const points = new Float32Array(buffer)
      if (!points.length) return
      this.pointCloudPoints = points
      this.pointCloudCount = Number(metadata.count || Math.floor(points.length / 6))
      this.pointCloudOnline = true
      this.pointCloudUnavailable = false
      this.pointCloudStatus = `点云 ${this.pointCloudCount} 点`
    },
    setCameraCapture(enabled, options = {}) {
      if (!this.gateway || !this.gateway.isOpen() || !this.connected) return
      const nextEnabled = Boolean(enabled)
      const now = Date.now()
      if (!options.force) {
        if (this.cameraCapturePending) return
        if (this.cameraCaptureState === nextEnabled) return
        if (now - this.cameraCaptureLastSentAt < 500) return
      }
      this.cameraCapturePending = true
      this.cameraCaptureLastSentAt = now
      this.gateway.send(cameraCommand(nextEnabled), {
        success: () => {
          this.cameraCaptureState = nextEnabled
          this.cameraCapturePending = false
        },
        fail: () => {
          this.cameraCapturePending = false
          this.connected = false
          this.addLog('RGB 相机订阅开关发送失败')
        },
        complete: () => {
          this.cameraCapturePending = false
        }
      })
    },
    setPointCloudCapture(enabled, options = {}) {
      if (!this.gateway || !this.gateway.isOpen() || !this.connected) return
      const nextEnabled = Boolean(enabled)
      if (nextEnabled && this.cameraStatusKnown && !this.cameraOnline) {
        this.pointCloudStatus = '相机不可用，未请求点云'
        return
      }
      if (nextEnabled && this.pointCloudUnavailable) {
        this.pointCloudStatus = '点云不可用，未重复请求'
        return
      }
      const now = Date.now()
      if (!options.force) {
        if (this.pointCloudCapturePending) return
        if (this.pointCloudCaptureState === nextEnabled) return
        if (now - this.pointCloudCaptureLastSentAt < 500) return
      }
      this.pointCloudCapturePending = true
      this.pointCloudCaptureLastSentAt = now
      this.gateway.send(pointcloudCommand(nextEnabled), {
        success: () => {
          this.pointCloudCaptureState = nextEnabled
          this.pointCloudCapturePending = false
        },
        fail: () => {
          this.pointCloudCapturePending = false
          this.connected = false
          this.addLog('点云采集开关发送失败')
        },
        complete: () => {
          this.pointCloudCapturePending = false
        }
      })
    }
  }
}

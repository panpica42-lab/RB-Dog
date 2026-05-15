<template>
  <view class="vision-page">
  <view class="topbar vision-topbar">
    <view class="status-left">
      <button class="icon-button" @tap="backToControl">返回</button>
      <view :class="['pill', connected ? 'ok' : 'bad']">{{ connected ? '已连接' : '未连接' }}</view>
    </view>

    <view class="title">
      <text class="title-main">视觉查看</text>
      <text class="title-sub">{{ visionMode === 'rgb' ? cameraStatus : pointCloudStatus }}</text>
    </view>

    <view class="top-actions">
      <button :class="['tab-button', visionMode === 'rgb' ? 'active' : '']" @tap="setVisionMode('rgb')">RGB</button>
      <button :class="['tab-button', visionMode === 'pointcloud' ? 'active' : '']" @tap="setVisionMode('pointcloud')">点云</button>
    </view>
  </view>

  <view class="vision-main">
    <view v-if="visionMode === 'rgb'" class="vision-stage">
      <image v-if="cameraFrame" class="vision-rgb" :src="cameraFrame" mode="aspectFit"></image>
      <view v-else class="vision-empty"><text>{{ cameraStatus }}</text></view>
      <view :class="['vision-badge', cameraOnline ? 'ok' : 'bad']"><text>{{ cameraStatus }}</text></view>
    </view>

    <view v-else class="vision-stage">
      <canvas
        id="pointCloudCanvas"
        canvas-id="pointCloudCanvas"
        class="pointcloud-canvas"
        @touchstart.stop.prevent="startPointCloudDrag"
        @touchmove.stop="movePointCloudDrag"
        @touchend.stop.prevent="endPointCloudDrag"
        @touchcancel.stop.prevent="endPointCloudDrag"
      ></canvas>
      <view v-if="!pointCloudPoints.length" class="vision-empty"><text>{{ pointCloudStatus }}</text></view>
      <view :class="['vision-badge', pointCloudOnline ? 'ok' : 'bad']"><text>{{ pointCloudStatus }}</text></view>
      <view class="pointcloud-tools">
        <button @tap="zoomPointCloud(1.18)">放大</button>
        <button @tap="zoomPointCloud(0.85)">缩小</button>
        <button @tap="resetPointCloudView">复位</button>
      </view>
    </view>
  </view>
</view>
</template>

<script>
export default {
  name: 'VisionView',
  props: {
    connected: Boolean,
    visionMode: String,
    cameraStatus: String,
    pointCloudStatus: String,
    cameraFrame: String,
    cameraOnline: Boolean,
    pointCloudPoints: Array,
    pointCloudOnline: Boolean
  },
  data() {
    return {
      pointCloudYaw: -0.2,
      pointCloudPitch: -0.28,
      pointCloudZoom: 1,
      pointCloudDragging: false,
      pointCloudTouch: null
    }
  },
  watch: {
    pointCloudPoints() {
      if (this.visionMode === 'pointcloud') {
        this.$nextTick(() => this.drawPointCloud())
      }
    },
    visionMode(mode) {
      if (mode === 'pointcloud') {
        this.$nextTick(() => this.drawPointCloud())
      }
    }
  },
  methods: {
    backToControl() { this.$emit('back-to-control') },
    setVisionMode(mode) { this.$emit('set-vision-mode', mode) },
    startPointCloudDrag(event) {
      const touch = this.getTouch(event)
      if (!touch) return
      this.pointCloudDragging = true
      this.pointCloudTouch = touch
    },
    movePointCloudDrag(event) {
      if (!this.pointCloudDragging || !this.pointCloudTouch) return
      const touch = this.getTouch(event)
      if (!touch) return
      const dx = touch.clientX - this.pointCloudTouch.clientX
      const dy = touch.clientY - this.pointCloudTouch.clientY
      this.pointCloudTouch = touch
      this.pointCloudYaw += dx * 0.008
      this.pointCloudPitch = Math.max(-1.35, Math.min(1.1, this.pointCloudPitch + dy * 0.008))
      this.drawPointCloud()
    },
    endPointCloudDrag() {
      this.pointCloudDragging = false
      this.pointCloudTouch = null
    },
    zoomPointCloud(factor) {
      this.pointCloudZoom = Math.max(0.45, Math.min(3, this.pointCloudZoom * factor))
      this.drawPointCloud()
    },
    resetPointCloudView() {
      this.pointCloudYaw = -0.2
      this.pointCloudPitch = -0.28
      this.pointCloudZoom = 1
      this.drawPointCloud()
    },
    getTouch(event) {
      const touch = event.touches && event.touches[0]
      if (!touch) return null
      return { clientX: touch.clientX, clientY: touch.clientY }
    },
    getCanvasRect(callback) {
      uni.createSelectorQuery()
        .in(this)
        .select('#pointCloudCanvas')
        .boundingClientRect(rect => {
          if (rect && callback) callback(rect)
        })
        .exec()
    },
    createPointCloudContext() {
      return uni.createCanvasContext('pointCloudCanvas', this)
    },
    drawPointCloud() {
      if (this.visionMode !== 'pointcloud') return
      this.getCanvasRect(rect => {
        const width = Math.max(1, rect.width || 1)
        const height = Math.max(1, rect.height || 1)
        const ctx = this.createPointCloudContext()
        ctx.setFillStyle('#071017')
        ctx.fillRect(0, 0, width, height)
        this.drawPointCloudGrid(ctx, width, height)

        const points = this.pointCloudPoints || []
        if (points.length) {
          const centerX = width / 2
          const centerY = height * 0.52
          const focal = Math.min(width, height) * 0.72 * this.pointCloudZoom
          const dotSize = points.length / 6 < 5000 ? 2.4 : 1.6
          const cosY = Math.cos(this.pointCloudYaw)
          const sinY = Math.sin(this.pointCloudYaw)
          const cosP = Math.cos(this.pointCloudPitch)
          const sinP = Math.sin(this.pointCloudPitch)
          const projected = []

          for (let i = 0; i < points.length; i += 6) {
            const x = Number(points[i])
            const y = Number(points[i + 1])
            const z = Number(points[i + 2])
            if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z) || z <= 0) continue

            const zx = x * cosY - z * sinY
            const zz = x * sinY + z * cosY
            const yy = y * cosP - zz * sinP
            const depth = y * sinP + zz * cosP + 2.4
            if (depth <= 0.08) continue

            const perspective = focal / depth
            const px = centerX + zx * perspective
            const py = centerY + yy * perspective
            if (px < 0 || px >= width || py < 0 || py >= height) continue
            projected.push({
              x: px,
              y: py,
              depth,
              color: `rgb(${points[i + 3] || 0},${points[i + 4] || 0},${points[i + 5] || 0})`
            })
          }

          projected.sort((a, b) => b.depth - a.depth)
          ctx.setGlobalAlpha(0.92)
          for (const point of projected) {
            ctx.setFillStyle(point.color)
            ctx.fillRect(point.x, point.y, dotSize, dotSize)
          }
          ctx.setGlobalAlpha(1)
        }
        ctx.draw()
      })
    },
    drawPointCloudGrid(ctx, width, height) {
      const cx = width / 2
      const cy = height * 0.72
      const gap = Math.min(width, height) / 10
      ctx.setStrokeStyle('rgba(54, 241, 244, 0.16)')
      ctx.setLineWidth(1)
      for (let i = -5; i <= 5; i += 1) {
        ctx.beginPath()
        ctx.moveTo(cx + i * gap, cy - 5 * gap * 0.36)
        ctx.lineTo(cx + i * gap, cy + 5 * gap * 0.36)
        ctx.stroke()
        ctx.beginPath()
        ctx.moveTo(cx - 5 * gap, cy + i * gap * 0.36)
        ctx.lineTo(cx + 5 * gap, cy + i * gap * 0.36)
        ctx.stroke()
      }
    }
  }
}
</script>

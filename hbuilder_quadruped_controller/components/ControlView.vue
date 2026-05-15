<template>
  <view class="control-page">
  <view class="topbar">
    <view class="status-left">
      <view class="battery">
        <view class="battery-fill" :style="{ width: batteryWidth, background: batteryColor }"></view>
      </view>
      <view class="wifi">
        <view class="arc arc1"></view>
        <view class="arc arc2"></view>
        <view class="arc arc3"></view>
      </view>
      <view :class="['pill', connected ? 'ok' : 'bad']">{{ connected ? '已连接' : '未连接' }}</view>
    </view>

    <view class="title">
      <text class="title-main">四足控制器</text>
      <text class="title-sub">移动端遥控</text>
    </view>

    <view class="top-actions">
      <button class="icon-button" @tap="openVision">视觉</button>
      <button class="danger" @tap="emitCommand('emergency')">紧急停止</button>
      <button class="icon-button" @tap="toggleSettings">设置</button>
    </view>
  </view>

  <view class="main">
    <view class="sidebar">
      <button :class="['mode-button', robotModel === 0 ? 'active' : '']" @tap="emitCommand('model', 0)">
        <text class="mode-icon">△</text><text>越障</text>
      </button>
      <button :class="['mode-button', robotModel === 1 ? 'active' : '']" @tap="emitCommand('model', 1)">
        <text class="mode-icon">◷</text><text>高速</text>
      </button>
      <view class="slider-card">
        <text>速度 {{ speedPercent }}</text>
        <slider :value="speedSlider" min="10" max="100" step="5" activeColor="#36f1f4" block-color="#ecfbfb" @change="setSpeed" @changing="setSpeed" />
      </view>
      <view class="slider-card">
        <text>转向 {{ turnPercent }}</text>
        <slider :value="turnSlider" min="10" max="100" step="5" activeColor="#36f1f4" block-color="#ecfbfb" @change="setTurnSpeed" @changing="setTurnSpeed" />
      </view>
    </view>

    <view class="center-status">
      <view class="status-card primary-status">
        <text class="status-kicker">当前状态</text>
        <text class="status-title">{{ motionText }}</text>
      </view>
      <view class="mini-row">
        <view class="mini-card"><text>电量</text><text>{{ batteryText }}</text></view>
        <view class="mini-card"><text>模型</text><text>{{ robotModel === 1 ? '高速' : '越障' }}</text></view>
        <view class="mini-card"><text>故障</text><text>{{ faultText }}</text></view>
      </view>
    </view>

    <view
      id="movePad"
      class="stick-area left"
      @touchstart.stop.prevent="startStick('move', $event)"
      @touchmove.stop="moveStick('move', $event)"
      @touchend.stop.prevent="endStick('move')"
      @touchcancel.stop.prevent="endStick('move')"
    >
      <text class="arrow up">⌃</text>
      <text class="arrow down">⌄</text>
      <text class="arrow left-a">‹</text>
      <text class="arrow right-a">›</text>
      <view class="knob" :style="{ transform: moveKnobTransform }"></view>
    </view>

    <view
      id="turnPad"
      class="stick-area right"
      @touchstart.stop.prevent="startStick('turn', $event)"
      @touchmove.stop="moveStick('turn', $event)"
      @touchend.stop.prevent="endStick('turn')"
      @touchcancel.stop.prevent="endStick('turn')"
    >
      <text class="arrow left-a">‹</text>
      <text class="arrow right-a">›</text>
      <view class="knob" :style="{ transform: turnKnobTransform }"></view>
    </view>

    <view class="action-strip">
      <button
        v-for="action in actionLibrary"
        :key="action.code"
        hover-class="button-press"
        class="action-strip-button"
        @tap="emitCommand('action', action.code)"
      >
        {{ action.label }}
      </button>
    </view>

    <view class="rail command-rail">
      <button hover-class="button-press" :class="['command-button', activeCommand === 'reset' ? 'active' : '']" @tap="emitCommand('reset')">回零</button>
      <button hover-class="button-press" :class="['command-button', activeCommand === 'lie' ? 'active' : '']" @tap="emitCommand('lie')">趴下</button>
      <button hover-class="button-press" :class="['command-button', activeCommand === 'stand' ? 'active' : '']" @tap="emitCommand('stand')">站立</button>
      <button hover-class="button-press" :class="['command-button', activeCommand === 'actions' ? 'active' : '']" @tap="toggleActions">动作库</button>
    </view>
  </view>

  <view :class="['drawer', settingsOpen || actionsOpen ? 'open' : '']">
    <view v-if="settingsOpen" class="panel">
      <text class="panel-title">连接设置</text>
      <text class="field-label">控制器地址</text>
      <input class="input" :value="controllerAddressInput" @input="updateControllerAddress" placeholder="10.0.50.236:9001" />
      <view class="panel-actions">
        <button @tap="saveAndConnect">保存并重连</button>
        <button @tap="backToConnect">返回连接页</button>
      </view>
    </view>

    <view class="panel">
      <text class="panel-title">状态</text>
      <view class="metrics">
        <view class="metric"><text>电量</text><text class="metric-value">{{ batteryText }}</text></view>
        <view class="metric"><text>姿态</text><text class="metric-value">{{ motionText }}</text></view>
        <view class="metric"><text>模型</text><text class="metric-value">{{ robotModel === 1 ? '高速' : '越障' }}</text></view>
        <view class="metric"><text>故障</text><text class="metric-value">{{ faultText }}</text></view>
      </view>
    </view>

    <view v-if="actionsOpen" class="panel">
      <text class="panel-title">动作库</text>
      <view class="action-grid">
        <button v-for="action in actionLibrary" :key="action.code" @tap="emitCommand('action', action.code)">{{ action.label }}</button>
        <button @tap="toggleObstacle">{{ obstacle ? '停障开' : '停障关' }}</button>
        <button @tap="toggleVideo">{{ video ? '视频开' : '视频关' }}</button>
        <button @tap="emitCommand('stop')">停止运动</button>
      </view>
    </view>

    <scroll-view scroll-y class="log">
      <text>{{ logs.join('\n') }}</text>
    </scroll-view>
  </view>
</view>

</template>

<script>
export default {
  name: 'ControlView',
  props: {
    connected: Boolean,
    batteryWidth: String,
    batteryColor: String,
    robotModel: Number,
    speedPercent: String,
    speedSlider: Number,
    turnPercent: String,
    turnSlider: Number,
    motionText: String,
    batteryText: String,
    faultText: String,
    moveKnobTransform: String,
    turnKnobTransform: String,
    activeCommand: String,
    settingsOpen: Boolean,
    actionsOpen: Boolean,
    controllerAddressInput: String,
    obstacle: Boolean,
    video: Boolean,
    logs: Array
  },
  data() {
    return {
      actionLibrary: [
        { label: '打招呼', code: 11 },
        { label: '撒尿', code: 5 },
        { label: '跳跃', code: 2 },
        { label: '比心', code: 14 },
        { label: '拜年', code: 15 },
        { label: '原地模式', code: 18 }
      ]
    }
  },
  methods: {
    openVision() { this.$emit('open-vision') },
    emitCommand(name, value) { this.$emit('command', { name, value }) },
    toggleSettings() { this.$emit('toggle-settings') },
    setSpeed(event) { this.$emit('set-speed', event) },
    setTurnSpeed(event) { this.$emit('set-turn-speed', event) },
    startStick(kind, event) { this.$emit('stick-start', kind, event) },
    moveStick(kind, event) { this.$emit('stick-move', kind, event) },
    endStick(kind) { this.$emit('stick-end', kind) },
    toggleActions() { this.$emit('toggle-actions') },
    updateControllerAddress(event) { this.$emit('update-controller-address', event.detail.value) },
    saveAndConnect() { this.$emit('save-and-connect') },
    backToConnect() { this.$emit('back-to-connect') },
    toggleObstacle() { this.$emit('toggle-obstacle') },
    toggleVideo() { this.$emit('toggle-video') },
    getStickRect(kind, callback) {
      const selector = kind === 'move' ? '#movePad' : '#turnPad'
      uni.createSelectorQuery()
        .in(this)
        .select(selector)
        .boundingClientRect(rect => {
          if (rect && callback) callback(rect)
        })
        .exec()
    }
  }
}
</script>

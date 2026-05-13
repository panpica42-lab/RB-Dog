<template>
  <view class="connect-page">
  <view class="connect-header">
    <view class="brand-block">
      <text class="brand-title">四足控制器</text>
      <text class="brand-subtitle">移动端遥控</text>
    </view>
    <view :class="['pill', connected ? 'ok' : connecting ? 'wait' : 'bad']">{{ connectLabel }}</view>
  </view>

  <view class="connect-center">
    <view class="connect-panel">
      <view class="panel-glow"></view>
      <view class="connect-layout">
        <view class="connect-copy">
          <text class="connect-title">连接控制网关</text>
          <text class="connect-desc">手机连接香橙派所在 Wi-Fi 后，点击连接完成通讯握手。</text>

          <view class="field">
            <text class="field-label">控制器地址</text>
            <input class="input" :value="controllerAddressInput" @input="updateControllerAddress" placeholder="10.0.50.236:9001" />
          </view>

          <button :class="['connect-button', connecting ? 'active' : '']" :disabled="connecting" @tap="connect">
            {{ connecting ? '连接中' : '连接' }}
          </button>
        </view>

        <view class="connect-visual">
          <view class="signal-ring ring-a"></view>
          <view class="signal-ring ring-b"></view>
          <view class="signal-core">
            <text>{{ connecting ? '握手中' : connected ? '在线' : '待连接' }}</text>
          </view>
          <view class="node node-phone"><text>手机</text></view>
          <view class="node node-board"><text>控制器</text></view>
        </view>
      </view>

      <view class="connect-steps">
        <view :class="['step', connecting || connected ? 'active' : '']"><text>1</text><text>发送连接</text></view>
        <view :class="['step', connected ? 'active' : '']"><text>2</text><text>握手完成</text></view>
        <view :class="['step', pageMode === 'control' ? 'active' : '']"><text>3</text><text>进入控制</text></view>
      </view>

      <text class="hint">{{ connectHint }}</text>
    </view>
  </view>
</view>

</template>

<script>
export default {
  name: 'ConnectView',
  props: {
    pageMode: String,
    connected: Boolean,
    connecting: Boolean,
    connectLabel: String,
    controllerAddressInput: String,
    connectHint: String
  },
  methods: {
    updateControllerAddress(event) {
      this.$emit('update-controller-address', event.detail.value)
    },
    connect() {
      this.$emit('connect')
    }
  }
}
</script>

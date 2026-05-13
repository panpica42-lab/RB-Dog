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

          <view class="provision-box">
            <view class="provision-head">
              <text class="panel-title">蓝牙配网</text>
              <view :class="['pill', bleConnected ? 'ok' : bleScanning ? 'wait' : 'bad']">
                {{ bleConnected ? 'BLE 已连接' : bleScanning ? '扫描中' : '待配网' }}
              </view>
            </view>

            <view class="provision-actions">
              <button :class="['mini-button', bleScanning ? 'active' : '']" :disabled="bleBusy || wifiProvisioning" @tap="startBleProvisioning">
                {{ provisionButtonLabel }}
              </button>
              <button class="mini-button" :disabled="!bleScanning" @tap="stopBleProvisioningScan">停止扫描</button>
              <button class="mini-button" :disabled="!bleConnected" @tap="disconnectBleProvisioning">断开 BLE</button>
            </view>

            <scroll-view v-if="bleDevices.length && !bleConnected" class="device-list" scroll-y>
              <view
                v-for="device in bleDevices"
                :key="device.deviceId"
                class="list-row"
                @tap="connectBleDevice(device)"
              >
                <text>{{ device.name || 'RoboDog' }}</text>
                <text>{{ device.RSSI || '--' }} dBm</text>
              </view>
            </scroll-view>

            <view v-if="bleConnected" class="wifi-area">
              <view class="provision-actions">
                <button class="mini-button" :disabled="wifiScanning || wifiProvisioning" @tap="scanProvisionWifi">
                  {{ wifiScanning ? '扫描 Wi-Fi 中' : '扫描 Wi-Fi' }}
                </button>
                <button class="mini-button" :disabled="wifiProvisioning" @tap="clearProvisionWifi">清除配置</button>
              </view>

              <scroll-view v-if="wifiNetworks.length" class="wifi-list" scroll-y>
                <view
                  v-for="network in wifiNetworks"
                  :key="network.ssid"
                  :class="['list-row', selectedWifiSsid === network.ssid ? 'active' : '']"
                  @tap="selectProvisionWifi(network)"
                >
                  <text>{{ network.ssid }}</text>
                  <text>{{ network.secure ? '加密' : '开放' }} {{ network.rssi }} dBm</text>
                </view>
              </scroll-view>

              <view class="field compact-field">
                <text class="field-label">手动输入 Wi-Fi 名称</text>
                <input class="input" :value="manualWifiSsid" @input="updateManualWifiSsid" placeholder="隐藏网络或扫描不到时填写" />
              </view>

              <view class="field compact-field">
                <text class="field-label">Wi-Fi 密码</text>
                <input class="input" password :value="wifiPassword" @input="updateWifiPassword" placeholder="开放网络可留空" />
              </view>

              <view class="provision-actions">
                <button :class="['mini-button', wifiHidden ? 'active' : '']" @tap="toggleWifiHidden">
                  {{ wifiHidden ? '隐藏网络' : '普通网络' }}
                </button>
                <button class="mini-button primary" :disabled="wifiProvisioning" @tap="submitWifiProvisioning">
                  {{ wifiProvisioning ? '等待结果' : '发送配网' }}
                </button>
              </view>
            </view>

            <text class="hint">{{ provisionHint }}</text>
          </view>
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
    connectHint: String,
    bleDevices: { type: Array, default: () => [] },
    bleScanning: Boolean,
    bleConnected: Boolean,
    bleBusy: Boolean,
    bleDeviceName: String,
    provisionHint: String,
    wifiNetworks: { type: Array, default: () => [] },
    wifiScanning: Boolean,
    selectedWifiSsid: String,
    manualWifiSsid: String,
    wifiPassword: String,
    wifiHidden: Boolean,
    wifiProvisioning: Boolean,
    provisionButtonLabel: String
  },
  methods: {
    updateControllerAddress(event) {
      this.$emit('update-controller-address', event.detail.value)
    },
    connect() {
      this.$emit('connect')
    },
    startBleProvisioning() { this.$emit('start-ble-provisioning') },
    stopBleProvisioningScan() { this.$emit('stop-ble-provisioning-scan') },
    connectBleDevice(device) { this.$emit('connect-ble-device', device) },
    disconnectBleProvisioning() { this.$emit('disconnect-ble-provisioning') },
    scanProvisionWifi() { this.$emit('scan-provision-wifi') },
    selectProvisionWifi(network) { this.$emit('select-provision-wifi', network) },
    updateManualWifiSsid(event) { this.$emit('update-manual-wifi-ssid', event.detail.value) },
    updateWifiPassword(event) { this.$emit('update-wifi-password', event.detail.value) },
    toggleWifiHidden() { this.$emit('toggle-wifi-hidden') },
    submitWifiProvisioning() { this.$emit('submit-wifi-provisioning') },
    clearProvisionWifi() { this.$emit('clear-provision-wifi') }
  }
}
</script>

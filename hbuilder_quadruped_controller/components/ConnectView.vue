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
      <view v-if="bleInitializing" class="ble-init-overlay">
        <view class="ble-init-card">
          <text class="ble-init-title">正在初始化连接</text>
          <text class="ble-init-text">蓝牙已连接，系统正在准备通信通道，请稍候</text>
        </view>
      </view>
      <view class="connect-copy">
          <view class="connect-workspace">
          <scroll-view class="provision-box primary-provision" scroll-y :scroll-into-view="scrollTargetId" scroll-with-animation>
            <view class="provision-head">
              <text class="panel-title">蓝牙配网</text>
              <view :class="['pill', bleConnected ? 'ok' : bleScanning || bleAutoConnecting ? 'wait' : 'bad']">
                {{ bleConnected ? 'BLE 已连接' : bleScanning || bleAutoConnecting ? '寻找中' : '待配网' }}
              </view>
            </view>

            <view class="provision-actions">
              <button class="provision-primary-button" :class="bleScanning || bleAutoConnecting ? 'active' : ''" :disabled="bleBusy || wifiProvisioning" @tap="startBleProvisioning">
                {{ provisionButtonLabel }}
              </button>
              <button v-if="bleScanning" class="mini-button" @tap="stopBleProvisioningScan">停止扫描</button>
              <button v-if="bleConnected" class="mini-button" :disabled="wifiProvisioning" @tap="disconnectBleProvisioning">断开 BLE</button>
            </view>

            <view v-if="bleDeviceName || bleDevices.length" class="provision-summary">
              <text>{{ bleConnected ? '已连接 ' + (bleDeviceName || '设备') : '发现 ' + bleDevices.length + ' 台设备，正在自动连接' }}</text>
            </view>

            <view v-if="bleConnected" class="wifi-area">
              <view v-if="deviceWifiConnected" class="device-wifi-card">
                <text class="device-wifi-title">机器狗已连接 Wi-Fi</text>
                <text class="device-wifi-name">{{ deviceWifiSsid }}</text>
                <text class="device-wifi-tip">请确认手机也连接到同一 Wi-Fi</text>
                <view class="provision-actions">
                  <button class="mini-button primary" @tap="continueWithDeviceWifi">我已连接同一 Wi-Fi</button>
                  <button class="mini-button" :disabled="wifiScanning || wifiProvisioning" @tap="reprovisionDeviceWifi">重新配网</button>
                </view>
              </view>

              <view v-else>
              <view class="provision-actions">
                <button class="mini-button" :disabled="wifiScanning || wifiProvisioning" @tap="scanProvisionWifi">
                  {{ wifiScanning ? '扫描 Wi-Fi 中' : '扫描 Wi-Fi' }}
                </button>
              </view>

              <view v-if="wifiNetworks.length" class="wifi-list">
                <view
                  v-for="network in wifiNetworks"
                  :key="network.ssid"
                  :class="['list-row', isWifiRowActive(network) ? 'active' : '']"
                  @tap="armProvisionWifi(network)"
                >
                  <view class="wifi-main">
                    <text>{{ network.ssid }}</text>
                    <text>{{ network.secure ? '加密' : '开放' }} {{ network.rssi }} dBm</text>
                  </view>
                  <button
                    v-if="armedWifiSsid === network.ssid && selectedWifiSsid !== network.ssid"
                    class="wifi-select-button"
                    @tap.stop="confirmProvisionWifi(network)"
                  >
                    选择
                  </button>
                  <text v-else-if="selectedWifiSsid === network.ssid" class="wifi-selected-tag">已选择</text>
                </view>
              </view>

              <view class="field compact-field">
                <text class="field-label">输入 Wi-Fi 名称</text>
                <input class="input" :value="wifiNameInputValue" @input="updateManualWifiSsid" placeholder="隐藏网络或扫描不到时填写" />
              </view>

              <view id="wifi-password-field" class="field compact-field">
                <text class="field-label">Wi-Fi 密码</text>
                <view class="input-with-action">
                  <input class="input input-with-button" :password="!passwordVisible" :focus="passwordFocus" :value="wifiPassword" @input="updateWifiPassword" @blur="passwordFocus = false" placeholder="开放网络可留空" />
                  <button class="input-action-button" @tap="togglePasswordVisible">
                    {{ passwordVisible ? '隐藏' : '显示' }}
                  </button>
                </view>
              </view>

              <view class="provision-actions">
                <button class="mini-button primary" :disabled="wifiProvisioning || !provisionSsid" @tap="submitWifiProvisioning">
                  {{ wifiProvisioning ? '等待结果' : '发送配网' }}
                </button>
              </view>
              </view>
            </view>

            <text class="hint">{{ provisionHint }}</text>
          </scroll-view>

          <view class="manual-connect">
            <view class="manual-head" @tap="toggleManualConnection">
              <text class="panel-title">手动连接网关</text>
              <text class="manual-toggle">{{ manualConnectionOpen ? '收起' : '展开' }}</text>
            </view>

            <view v-if="manualConnectionOpen" class="manual-body">
              <view class="field">
                <text class="field-label">控制器地址</text>
                <input class="input" :value="controllerAddressInput" @input="updateControllerAddress" placeholder="10.0.50.236:9001" />
              </view>

              <view class="provision-actions">
                <button :class="['connect-button', connecting ? 'active' : '']" :disabled="connecting" @tap="connect">
                  {{ connecting ? '连接中' : '连接' }}
                </button>
                <button class="mini-button" :disabled="!bleConnected || wifiProvisioning" @tap="clearProvisionWifi">清除配网</button>
              </view>
            </view>
          </view>
          </view>
      </view>

      <view class="connect-steps">
        <view :class="['step', bleScanning || bleConnected || connecting || connected ? 'active' : '']"><text>1</text><text>发现机器狗</text></view>
        <view :class="['step', bleConnected || connecting || connected ? 'active' : '']"><text>2</text><text>发送 Wi-Fi</text></view>
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
    bleAutoConnecting: Boolean,
    bleInitializing: Boolean,
    bleDeviceName: String,
    provisionHint: String,
    wifiNetworks: { type: Array, default: () => [] },
    wifiScanning: Boolean,
    selectedWifiSsid: String,
    manualWifiSsid: String,
    wifiPassword: String,
    wifiHidden: Boolean,
    wifiProvisioning: Boolean,
    deviceWifiConnected: Boolean,
    deviceWifiSsid: String,
    deviceWifiIp: String,
    provisionButtonLabel: String
  },
  data() {
    return {
      manualConnectionOpen: false,
      armedWifiSsid: '',
      scrollTargetId: '',
      passwordFocus: false,
      passwordVisible: false
    }
  },
  computed: {
    provisionSsid() {
      return String(this.selectedWifiSsid || this.manualWifiSsid || '').trim()
    },
    wifiNameInputValue() {
      return String(this.manualWifiSsid || this.selectedWifiSsid || '')
    }
  },
  methods: {
    isWifiRowActive(network) {
      const ssid = network && network.ssid ? network.ssid : ''
      return this.selectedWifiSsid === ssid || this.armedWifiSsid === ssid
    },
    armProvisionWifi(network) {
      const ssid = network && network.ssid ? network.ssid : ''
      this.armedWifiSsid = this.armedWifiSsid === ssid ? '' : ssid
    },
    confirmProvisionWifi(network) {
      this.armedWifiSsid = network && network.ssid ? network.ssid : ''
      this.$emit('select-provision-wifi', network)
      this.scrollTargetId = ''
      this.passwordFocus = false
      this.$nextTick(() => {
        this.scrollTargetId = 'wifi-password-field'
        this.passwordFocus = true
      })
    },
    updateControllerAddress(event) {
      this.$emit('update-controller-address', event.detail.value)
    },
    connect() {
      this.$emit('connect')
    },
    toggleManualConnection() { this.manualConnectionOpen = !this.manualConnectionOpen },
    startBleProvisioning() { this.$emit('start-ble-provisioning') },
    stopBleProvisioningScan() { this.$emit('stop-ble-provisioning-scan') },
    connectBleDevice(device) { this.$emit('connect-ble-device', device) },
    disconnectBleProvisioning() { this.$emit('disconnect-ble-provisioning') },
    scanProvisionWifi() {
      this.armedWifiSsid = ''
      this.scrollTargetId = ''
      this.passwordFocus = false
      this.$emit('scan-provision-wifi')
    },
    togglePasswordVisible() {
      this.passwordVisible = !this.passwordVisible
    },
    updateManualWifiSsid(event) { this.$emit('update-manual-wifi-ssid', event.detail.value) },
    updateWifiPassword(event) { this.$emit('update-wifi-password', event.detail.value) },
    submitWifiProvisioning() { this.$emit('submit-wifi-provisioning') },
    clearProvisionWifi() { this.$emit('clear-provision-wifi') },
    continueWithDeviceWifi() { this.$emit('continue-with-device-wifi') },
    reprovisionDeviceWifi() { this.$emit('reprovision-device-wifi') }
  }
}
</script>

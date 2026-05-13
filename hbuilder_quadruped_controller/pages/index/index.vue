<template>
  <view class="screen">
    <ConnectView
      v-if="pageMode === 'connect'"
      :page-mode="pageMode"
      :connected="connected"
      :connecting="connecting"
      :connect-label="connectLabel"
      :controller-address-input="controllerAddressInput"
      :connect-hint="connectHint"
      :ble-devices="bleDevices"
      :ble-scanning="bleScanning"
      :ble-connected="bleConnected"
      :ble-busy="bleBusy"
      :ble-device-name="bleDeviceName"
      :provision-hint="provisionHint"
      :wifi-networks="wifiNetworks"
      :wifi-scanning="wifiScanning"
      :selected-wifi-ssid="selectedWifiSsid"
      :manual-wifi-ssid="manualWifiSsid"
      :wifi-password="wifiPassword"
      :wifi-hidden="wifiHidden"
      :wifi-provisioning="wifiProvisioning"
      :provision-button-label="provisionButtonLabel"
      @update-controller-address="controllerAddressInput = $event"
      @connect="connect"
      @start-ble-provisioning="startBleProvisioning"
      @stop-ble-provisioning-scan="stopBleProvisioningScan"
      @connect-ble-device="connectBleProvisionDevice"
      @disconnect-ble-provisioning="disconnectBleProvisioning"
      @scan-provision-wifi="scanProvisionWifi"
      @select-provision-wifi="selectProvisionWifi"
      @update-manual-wifi-ssid="updateManualWifiSsid"
      @update-wifi-password="updateWifiPassword"
      @toggle-wifi-hidden="toggleWifiHidden"
      @submit-wifi-provisioning="submitWifiProvisioning"
      @clear-provision-wifi="clearProvisionWifi"
    />

    <ControlView
      v-else-if="pageMode === 'control'"
      ref="controlView"
      :connected="connected"
      :battery-width="batteryWidth"
      :battery-color="batteryColor"
      :robot-model="selectedRobotModel"
      :speed-percent="speedPercent"
      :speed-slider="speedSlider"
      :turn-percent="turnPercent"
      :turn-slider="turnSlider"
      :motion-text="motionText"
      :battery-text="batteryText"
      :fault-text="faultText"
      :move-knob-transform="moveKnobTransform"
      :turn-knob-transform="turnKnobTransform"
      :active-command="activeCommand"
      :settings-open="settingsOpen"
      :actions-open="actionsOpen"
      :controller-address-input="controllerAddressInput"
      :obstacle="obstacle"
      :video="video"
      :logs="logs"
      @open-vision="openVision"
      @command="handleControlCommand"
      @toggle-settings="settingsOpen = !settingsOpen"
      @set-speed="setSpeed"
      @set-turn-speed="setTurnSpeed"
      @stick-start="startStick"
      @stick-move="moveStick"
      @stick-end="endStick"
      @toggle-actions="actionsOpen = !actionsOpen"
      @update-controller-address="controllerAddressInput = $event"
      @save-and-connect="saveAndConnect"
      @back-to-connect="backToConnect"
      @toggle-obstacle="toggleObstacle"
      @toggle-video="toggleVideo"
    />

    <VisionView
      v-else
      ref="visionView"
      :connected="connected"
      :vision-mode="visionMode"
      :camera-status="cameraStatus"
      :point-cloud-status="pointCloudStatus"
      :camera-frame="cameraFrame"
      :camera-online="cameraOnline"
      :point-cloud-points="pointCloudPoints"
      :point-cloud-online="pointCloudOnline"
      @back-to-control="backToControl"
      @set-vision-mode="setVisionMode"
    />
  </view>
</template>

<script>
import ConnectView from '../../components/ConnectView.vue'
import ControlView from '../../components/ControlView.vue'
import VisionView from '../../components/VisionView.vue'
import gatewayConnection from '../../features/gatewayConnection.js'
import wifiProvisioning from '../../features/wifiProvisioning.js'
import robotControl from '../../features/robotControl.js'
import robotStatus from '../../features/robotStatus.js'
import visionStream from '../../features/visionStream.js'

export default {
  components: {
    ConnectView,
    ControlView,
    VisionView
  },
  mixins: [
    gatewayConnection,
    wifiProvisioning,
    robotStatus,
    robotControl,
    visionStream
  ],
  data() {
    return {
      pageMode: 'connect',
      settingsOpen: false,
      actionsOpen: false,
      logs: []
    }
  },
  onLoad() {
    this.loadStoredAddress()
  },
  onUnload() {
    this.stopCameraCapture({ force: true })
    this.stopPointCloudCapture({ force: true })
    this.stopRobot(false)
    this.stopMoveLoop()
    this.disconnectBleProvisioning()
    this.closeSocket()
  },
  onHide() {
    this.stopCameraCapture({ force: true })
    this.stopPointCloudCapture({ force: true })
  },
  onShow() {
    this.syncVisionCapture()
  },
  methods: {
    openVision() {
      this.stopMoveLoop()
      this.resetDrive()
      this.sendMove(true)
      this.settingsOpen = false
      this.actionsOpen = false
      this.pageMode = 'vision'
      this.syncVisionCapture()
    },
    backToControl() {
      this.stopCameraCapture({ force: true })
      this.stopPointCloudCapture({ force: true })
      this.pageMode = 'control'
    },
    backToConnect(close = true) {
      this.stopCameraCapture({ force: true })
      this.stopPointCloudCapture({ force: true })
      if (close) this.closeSocket()
      this.stopMoveLoop()
      this.connected = false
      this.connecting = false
      this.pageMode = 'connect'
      this.settingsOpen = false
      this.actionsOpen = false
    },
    routeGatewayMessage(message) {
      if (this.handleVisionMessage(message)) return

      if (message.type === 'hello') {
        this.target = message.dog || '--'
        this.updateStatus(message.status || {})
        this.updateImu(message.imu || {})
        this.connected = true
        this.connecting = false
        this.connectHint = '通讯完成'
        this.pageMode = 'control'
        this.syncVisionCapture()
        this.addLog('网关握手完成')
      } else if (message.type === 'status') {
        this.updateStatus(message.status || {})
      } else if (message.type === 'snapshot') {
        this.updateStatus(message.status || {})
        this.updateImu(message.imu || {})
      } else if (message.type === 'imu') {
        this.updateImu(message.imu || {})
      } else if (message.type === 'command_result') {
        this.addLog(`响应 ${JSON.stringify(message.result)}`)
      } else if (message.type === 'sent') {
        this.addLog(`发送 ${JSON.stringify(message.command)}`)
      } else if (message.type === 'error') {
        this.addLog(message.message)
      }
    },
    addLog(message) {
      const time = new Date().toLocaleTimeString()
      this.logs.unshift(`[${time}] ${message}`)
      this.logs = this.logs.slice(0, 80)
    }
  }
}
</script>

<style>
.screen {
  width: 100vw;
  height: 100vh;
  max-width: 100vw;
  max-height: 100vh;
  overflow: hidden;
  position: fixed;
  left: 0;
  top: 0;
  background:
    radial-gradient(circle at 50% 42%, rgba(54, 241, 244, 0.16), transparent 34%),
    linear-gradient(180deg, #020607, #061014);
  color: #ecfbfb;
}

button {
  min-height: 38px;
  padding: 0 10px;
  border: 1px solid rgba(75, 226, 231, 0.34);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(18, 75, 85, 0.92), rgba(7, 22, 29, 0.92));
  color: #ecfbfb;
  font-size: 13px;
  font-weight: 700;
  box-shadow: inset 0 0 18px rgba(54, 241, 244, 0.08), 0 0 18px rgba(54, 241, 244, 0.18);
}

button.active {
  color: #021114;
  background: linear-gradient(180deg, #82ffff, #19d8e0);
}

button[disabled] {
  opacity: 0.78;
}

button.danger {
  border-color: rgba(255, 90, 90, 0.7);
  color: #ff9b9b;
  background: rgba(72, 15, 18, 0.86);
}

.connect-page,
.control-page,
.vision-page {
  width: 100%;
  height: 100%;
}

.connect-header {
  height: 54px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
  border-bottom: 1px solid rgba(54, 241, 244, 0.22);
  background: rgba(0, 0, 0, 0.36);
}

.brand-block {
  display: grid;
  gap: 2px;
}

.brand-title {
  font-size: 21px;
  font-weight: 900;
}

.brand-subtitle {
  color: #94b7bc;
  font-size: 12px;
  font-weight: 650;
}

.connect-center {
  height: calc(100vh - 54px);
  display: grid;
  place-items: center;
  padding: 10px;
}

.connect-panel {
  position: relative;
  width: min(700px, calc(100vw - 20px));
  min-height: 0;
  max-height: calc(100vh - 74px);
  padding: 18px;
  border: 1px solid rgba(54, 241, 244, 0.42);
  border-radius: 8px;
  background: rgba(3, 16, 21, 0.86);
  box-shadow: 0 0 40px rgba(54, 241, 244, 0.16);
  overflow-y: auto;
}

.panel-glow {
  position: absolute;
  right: -120px;
  top: -120px;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(54, 241, 244, 0.22), transparent 68%);
}

.connect-layout {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 180px;
  gap: 18px;
  align-items: center;
}

.connect-copy {
  min-width: 0;
}

.connect-title {
  position: relative;
  display: block;
  font-size: 23px;
  font-weight: 900;
}

.connect-desc {
  position: relative;
  display: block;
  margin-top: 6px;
  color: #94b7bc;
  font-size: 13px;
}

.field {
  position: relative;
  display: grid;
  gap: 5px;
  margin-top: 14px;
}

.field-label {
  color: #94b7bc;
  font-size: 12px;
}

.input {
  width: 100%;
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid rgba(54, 241, 244, 0.28);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.35);
  color: #ecfbfb;
  font-size: 14px;
}

.connect-button {
  position: relative;
  width: 150px;
  height: 42px;
  margin-top: 14px;
  font-size: 15px;
}

.connect-visual {
  position: relative;
  width: 170px;
  height: 170px;
  display: grid;
  place-items: center;
}

.signal-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid rgba(54, 241, 244, 0.26);
  box-shadow: inset 0 0 28px rgba(54, 241, 244, 0.12), 0 0 22px rgba(54, 241, 244, 0.1);
}

.ring-a {
  width: 160px;
  height: 160px;
}

.ring-b {
  width: 104px;
  height: 104px;
  border-color: rgba(54, 241, 244, 0.46);
}

.signal-core {
  width: 68px;
  height: 68px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: linear-gradient(180deg, rgba(72, 255, 255, 0.92), rgba(15, 164, 174, 0.92));
  color: #021114;
  font-size: 12px;
  font-weight: 900;
  box-shadow: 0 0 28px rgba(54, 241, 244, 0.52);
}

.node {
  position: absolute;
  min-width: 54px;
  min-height: 26px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(54, 241, 244, 0.28);
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.34);
  color: #94b7bc;
  font-size: 12px;
}

.node-phone {
  left: 2px;
  bottom: 26px;
}

.node-board {
  right: 0;
  top: 26px;
}

.connect-steps {
  position: relative;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 7px;
  margin-top: 14px;
}

.step {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 8px;
  border: 1px solid rgba(54, 241, 244, 0.16);
  border-radius: 8px;
  color: #64858b;
  background: rgba(0, 0, 0, 0.22);
  font-size: 12px;
}

.step text:first-child {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 1px solid currentColor;
}

.step.active {
  color: #36f1f4;
  border-color: rgba(54, 241, 244, 0.4);
  box-shadow: 0 0 16px rgba(54, 241, 244, 0.12);
}

.hint {
  position: relative;
  display: block;
  margin-top: 8px;
  color: #94b7bc;
  font-size: 12px;
}

.provision-box {
  position: relative;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid rgba(54, 241, 244, 0.18);
}

.provision-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.provision-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 8px;
}

.mini-button {
  min-width: 86px;
  min-height: 34px;
  font-size: 12px;
}

.mini-button.primary {
  min-width: 104px;
}

.device-list,
.wifi-list {
  height: 86px;
  margin-top: 8px;
  border: 1px solid rgba(54, 241, 244, 0.18);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.24);
}

.wifi-list {
  height: 104px;
}

.list-row {
  min-height: 34px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0 9px;
  border-bottom: 1px solid rgba(54, 241, 244, 0.1);
  color: #c8f3f3;
  font-size: 12px;
}

.list-row.active {
  color: #021114;
  background: #36f1f4;
}

.list-row text:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.list-row text:last-child {
  flex-shrink: 0;
  color: inherit;
  opacity: 0.78;
}

.wifi-area {
  margin-top: 8px;
}

.compact-field {
  margin-top: 8px;
}

.topbar {
  height: 54px;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  padding: 6px 12px;
  border-bottom: 1px solid rgba(54, 241, 244, 0.22);
  background: rgba(0, 0, 0, 0.36);
}

.status-left,
.top-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.top-actions {
  justify-content: flex-end;
}

.title {
  display: grid;
  justify-items: center;
  line-height: 1.1;
}

.title-main {
  font-size: 19px;
  font-weight: 800;
}

.title-sub {
  margin-top: 2px;
  color: #94b7bc;
  font-size: 12px;
  font-weight: 650;
}

.pill {
  min-height: 26px;
  display: inline-flex;
  align-items: center;
  padding: 0 9px;
  border-radius: 999px;
  border: 1px solid rgba(54, 241, 244, 0.24);
  background: rgba(6, 20, 26, 0.8);
  color: #94b7bc;
  font-size: 12px;
}

.pill.ok { color: #65f29b; border-color: rgba(101, 242, 155, 0.42); }
.pill.bad { color: #ff5a5a; border-color: rgba(255, 90, 90, 0.46); }
.pill.wait { color: #ffd15b; border-color: rgba(255, 209, 91, 0.46); }

.battery {
  width: 42px;
  height: 19px;
  padding: 3px;
  border: 2px solid #c9ffff;
  border-radius: 5px;
  box-shadow: 0 0 12px rgba(54, 241, 244, 0.45);
}

.battery-fill {
  height: 100%;
  border-radius: 2px;
}

.wifi {
  width: 28px;
  height: 19px;
  position: relative;
  color: #36f1f4;
}

.arc {
  position: absolute;
  left: 50%;
  bottom: 0;
  border: 2px solid #36f1f4;
  border-color: #36f1f4 transparent transparent transparent;
  border-radius: 50%;
  transform: translateX(-50%);
}

.arc1 { width: 28px; height: 28px; }
.arc2 { width: 19px; height: 19px; }
.arc3 { width: 10px; height: 10px; }

.icon-button {
  width: 54px;
}

.tab-button {
  min-width: 78px;
}

.main {
  position: relative;
  height: calc(100vh - 54px);
  overflow: hidden;
  display: grid;
  grid-template-columns: 132px minmax(300px, 1fr) 100px;
  grid-template-rows: 1fr;
  gap: 8px;
  padding: 10px;
}

.sidebar {
  display: grid;
  gap: 7px;
  align-content: start;
}

.sidebar {
  grid-column: 1;
  grid-row: 1;
  padding-top: 6px;
}

.rail {
  grid-column: 3;
  grid-row: 1;
  display: grid;
}

.command-rail {
  gap: 10px;
  align-content: center;
}

.mode-button {
  min-height: 42px;
  display: grid;
  grid-template-columns: 28px 1fr;
  align-items: center;
  text-align: left;
}

.mode-icon {
  color: #36f1f4;
  font-size: 18px;
}

.slider-card {
  min-height: 50px;
  padding: 7px 8px 4px;
  border: 1px solid rgba(54, 241, 244, 0.2);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.28);
  color: #94b7bc;
  font-size: 11px;
}

.center-status {
  grid-column: 2;
  grid-row: 1;
  align-self: start;
  justify-self: center;
  width: min(400px, 62%);
  margin-top: 4px;
  display: grid;
  gap: 7px;
}

.camera-panel {
  grid-column: 2;
  grid-row: 1;
  align-self: center;
  justify-self: center;
  position: relative;
  width: min(720px, 100%);
  height: min(54vh, 430px);
  margin: 84px 0 86px;
  overflow: hidden;
  border: 1px solid rgba(54, 241, 244, 0.26);
  border-radius: 8px;
  background: #071017;
  box-shadow: inset 0 0 34px rgba(54, 241, 244, 0.08), 0 0 22px rgba(0, 0, 0, 0.38);
}

.camera-frame {
  width: 100%;
  height: 100%;
  background: #071017;
}

.camera-empty {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  color: #94b7bc;
  font-size: 14px;
}

.camera-badge,
.pointcloud-badge {
  position: absolute;
  top: 10px;
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  max-width: calc(100% - 20px);
  padding: 0 10px;
  border: 1px solid rgba(54, 241, 244, 0.28);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.6);
  color: #ffd15b;
  font-size: 12px;
  font-weight: 800;
}

.camera-badge { left: 10px; }
.pointcloud-badge { right: 10px; }

.camera-badge.ok,
.pointcloud-badge.ok {
  color: #65f29b;
  border-color: rgba(101, 242, 155, 0.42);
}

.camera-badge.bad,
.pointcloud-badge.bad {
  color: #ff9b9b;
  border-color: rgba(255, 90, 90, 0.46);
}

.status-card {
  min-height: 64px;
  display: grid;
  align-content: center;
  padding: 10px 14px;
  border: 1px solid rgba(54, 241, 244, 0.34);
  border-radius: 8px;
  background:
    radial-gradient(circle at 82% 20%, rgba(54, 241, 244, 0.2), transparent 34%),
    rgba(2, 18, 23, 0.72);
  box-shadow: 0 0 30px rgba(54, 241, 244, 0.14);
}

.status-kicker {
  color: #94b7bc;
  font-size: 11px;
  font-weight: 700;
}

.status-title {
  margin-top: 3px;
  font-size: 24px;
  font-weight: 900;
}

.mini-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.mini-card {
  min-height: 38px;
  display: grid;
  align-content: center;
  gap: 2px;
  padding: 6px 8px;
  border: 1px solid rgba(54, 241, 244, 0.18);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.24);
  color: #94b7bc;
  font-size: 11px;
}

.mini-card text:last-child {
  color: #ecfbfb;
  font-size: 14px;
  font-weight: 800;
}

.stick-area {
  position: absolute;
  bottom: 64px;
  width: min(148px, 34vh);
  height: min(148px, 34vh);
  border-radius: 50%;
  background: radial-gradient(circle, rgba(54, 241, 244, 0.27) 0 18%, rgba(54, 241, 244, 0.09) 20% 52%, rgba(54, 241, 244, 0.02) 72%);
  border: 1px solid rgba(54, 241, 244, 0.16);
  box-shadow: inset 0 0 42px rgba(54, 241, 244, 0.21), 0 0 22px rgba(54, 241, 244, 0.18);
}

.stick-area.left { left: 246px; }
.stick-area.right { right: 126px; }

.knob {
  width: min(48px, 11vh);
  height: min(48px, 11vh);
  border-radius: 50%;
  position: absolute;
  left: 50%;
  top: 50%;
  background: rgba(12, 170, 182, 0.54);
  border: 2px solid rgba(54, 241, 244, 0.74);
  box-shadow: 0 0 22px rgba(54, 241, 244, 0.56);
}

.arrow {
  position: absolute;
  color: #36f1f4;
  font-size: 24px;
  font-weight: 900;
}

.up { left: 50%; top: 8%; transform: translateX(-50%); }
.down { left: 50%; bottom: 6%; transform: translateX(-50%); }
.left-a { left: 11%; top: 50%; transform: translateY(-50%); }
.right-a { right: 11%; top: 50%; transform: translateY(-50%); }

.command-button {
  width: 100%;
  min-width: 0;
  min-height: 40px;
  transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
}

.command-button.active {
  color: #021114;
  border-color: rgba(130, 255, 255, 0.9);
  background: linear-gradient(180deg, #82ffff, #19d8e0);
  box-shadow: inset 0 0 14px rgba(255, 255, 255, 0.18), 0 0 22px rgba(54, 241, 244, 0.42);
}

.button-press {
  transform: scale(0.96);
  box-shadow: inset 0 0 22px rgba(54, 241, 244, 0.24), 0 0 10px rgba(54, 241, 244, 0.22);
}

.drawer {
  position: fixed;
  right: 12px;
  top: 62px;
  width: 312px;
  max-height: calc(100vh - 74px);
  overflow: hidden;
  border: 1px solid rgba(54, 241, 244, 0.42);
  border-radius: 8px;
  background: rgba(3, 13, 17, 0.96);
  box-shadow: 0 0 30px rgba(0, 0, 0, 0.5), 0 0 22px rgba(54, 241, 244, 0.16);
  padding: 10px;
  transform: translateX(340px);
  transition: transform 180ms ease;
  z-index: 5;
}

.drawer.open {
  transform: translateX(0);
}

.panel {
  margin-bottom: 8px;
}

.panel-title {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 800;
}

.panel-actions,
.action-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
  margin-top: 7px;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
}

.metric {
  min-height: 42px;
  padding: 7px;
  border: 1px solid rgba(54, 241, 244, 0.18);
  border-radius: 8px;
  background: rgba(9, 34, 41, 0.66);
  color: #94b7bc;
  font-size: 12px;
}

.metric-value {
  display: block;
  margin-top: 3px;
  color: #ecfbfb;
  font-size: 13px;
  font-weight: 800;
}

.log {
  height: 58px;
  margin-top: 8px;
  padding: 7px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.42);
  color: #c8f3f3;
  font-size: 11px;
  line-height: 1.3;
}

.vision-topbar {
  grid-template-columns: 1fr minmax(180px, auto) 1fr;
}

.vision-main {
  height: calc(100vh - 54px);
  padding: 10px;
  background: #020607;
}

.vision-stage {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border: 1px solid rgba(54, 241, 244, 0.26);
  border-radius: 8px;
  background: #071017;
  box-shadow: inset 0 0 34px rgba(54, 241, 244, 0.08), 0 0 22px rgba(0, 0, 0, 0.38);
}

.vision-rgb,
.pointcloud-canvas {
  width: 100%;
  height: 100%;
  background: #071017;
}

.vision-empty {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  display: grid;
  place-items: center;
  color: #94b7bc;
  font-size: 16px;
  pointer-events: none;
}

.vision-badge {
  position: absolute;
  left: 14px;
  top: 14px;
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  max-width: calc(100% - 28px);
  padding: 0 12px;
  border: 1px solid rgba(54, 241, 244, 0.28);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.62);
  color: #ffd15b;
  font-size: 13px;
  font-weight: 800;
}

.vision-badge.ok {
  color: #65f29b;
  border-color: rgba(101, 242, 155, 0.42);
}

.vision-badge.bad {
  color: #ff9b9b;
  border-color: rgba(255, 90, 90, 0.46);
}

.pointcloud-tools {
  position: absolute;
  right: 14px;
  bottom: 14px;
  display: flex;
  gap: 8px;
}

.pointcloud-tools button {
  min-width: 70px;
}

@media screen and (max-height: 380px) {
  button {
    min-height: 34px;
    font-size: 12px;
  }

  .topbar,
  .connect-header {
    height: 48px;
    padding-top: 4px;
    padding-bottom: 4px;
  }

  .main,
  .vision-main {
    height: calc(100vh - 48px);
    padding: 8px;
  }

  .connect-center {
    height: calc(100vh - 48px);
    padding: 8px;
  }

  .connect-panel {
    padding: 14px;
    max-height: calc(100vh - 64px);
  }

  .connect-layout {
    grid-template-columns: 1fr 150px;
    gap: 12px;
  }

  .connect-visual {
    width: 150px;
    height: 150px;
  }

  .ring-a {
    width: 140px;
    height: 140px;
  }

  .ring-b {
    width: 90px;
    height: 90px;
  }

  .signal-core {
    width: 58px;
    height: 58px;
  }

  .connect-steps {
    margin-top: 10px;
  }

  .hint {
    margin-top: 6px;
  }

  .main {
    grid-template-columns: 122px minmax(280px, 1fr) 92px;
    grid-template-rows: 1fr;
    gap: 6px;
  }

  .title-main {
    font-size: 17px;
  }

  .title-sub,
  .brand-subtitle {
    display: none;
  }

  .mode-button {
    min-height: 38px;
  }

  .slider-card {
    min-height: 44px;
    padding: 5px 7px 2px;
  }

  .center-status {
    width: min(360px, 64%);
    gap: 5px;
  }

  .status-card {
    min-height: 56px;
    padding: 8px 12px;
  }

  .status-title {
    font-size: 21px;
  }

  .mini-card {
    min-height: 34px;
    padding: 5px 7px;
  }

  .stick-area {
    bottom: 56px;
    width: min(132px, 32vh);
    height: min(132px, 32vh);
  }

  .stick-area.left {
    left: 210px;
  }

  .stick-area.right {
    right: 104px;
  }

  .knob {
    width: min(42px, 10vh);
    height: min(42px, 10vh);
  }

  .command-button {
    min-width: 68px;
    min-height: 36px;
  }

  .drawer {
    top: 54px;
    max-height: calc(100vh - 62px);
  }

  .log {
    height: 44px;
  }
}
</style>

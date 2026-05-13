export default {
  data() {
    return {
      battery: null,
      motionMode: '',
      robotModel: 0,
      selectedRobotModel: 0,
      hardwareError: 0,
      imu: { roll: '--', pitch: '--', yaw: '--' }
    }
  },
  computed: {
    batteryText() {
      return this.battery === null ? '--' : `${Math.round(this.battery)}%`
    },
    batteryWidth() {
      const value = this.battery === null ? 8 : Math.max(8, Math.min(100, this.battery))
      return `${value}%`
    },
    batteryColor() {
      if (this.battery === null) return '#65f29b'
      if (this.battery < 25) return '#ff5a5a'
      if (this.battery < 50) return '#ffd15b'
      return '#65f29b'
    },
    faultText() {
      return Number(this.hardwareError) ? '有故障' : '正常'
    },
    motionText() {
      const mode = this.motionMode
      if (mode === undefined || mode === null || mode === '') return '--'
      const number = Number(mode)
      if (!Number.isNaN(number)) return ['未回零', '趴地', '站立', '低身位', '翻倒'][number] || `未知(${mode})`
      const text = String(mode).toLowerCase()
      if (text.indexOf('stand') >= 0) return '站立'
      if (text.indexOf('lying') >= 0 || text.indexOf('lie') >= 0) return '趴地'
      if (text.indexOf('reset') >= 0) return '未回零'
      if (text.indexOf('low') >= 0) return '低身位'
      if (text.indexOf('fall') >= 0) return '翻倒'
      return String(mode)
    },
    activeCommand() {
      if (this.actionsOpen) return 'actions'
      const mode = Number(this.motionMode)
      if (mode === 0) return 'reset'
      if (mode === 1) return 'lie'
      if (mode === 2) return 'stand'
      const text = String(this.motionMode || '').toLowerCase()
      if (text.indexOf('stand') >= 0) return 'stand'
      if (text.indexOf('lying') >= 0 || text.indexOf('lie') >= 0) return 'lie'
      if (text.indexOf('reset') >= 0) return 'reset'
      return ''
    }
  },
  methods: {
    updateStatus(status) {
      const battery = Number(status.battery !== undefined ? status.battery : status.battery_level)
      this.battery = Number.isFinite(battery) ? Math.max(0, Math.min(100, battery)) : this.battery
      this.motionMode = status.motion_mode !== undefined ? status.motion_mode : this.motionMode
      this.hardwareError = status.hardware_error || 0
    },
    updateImu(imu) {
      const euler = imu.euler || imu.rpy || {}
      this.imu = {
        roll: this.angle(euler.roll !== undefined ? euler.roll : imu.roll),
        pitch: this.angle(euler.pitch !== undefined ? euler.pitch : imu.pitch),
        yaw: this.angle(euler.yaw !== undefined ? euler.yaw : imu.yaw)
      }
    },
    angle(input) {
      if (input === undefined || input === null || input === '') return '--'
      const number = Number(input)
      const degree = Math.abs(number) <= Math.PI * 2 ? number * 180 / Math.PI : number
      return `${degree.toFixed(1)}°`
    }
  }
}

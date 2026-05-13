import {
  actionCommand,
  emergencyCommand,
  lieCommand,
  modelCommand,
  moveCommand,
  obstacleCommand,
  resetCommand,
  standCommand,
  stopCommand,
  videoCommand
} from '../services/commands.js'

const MOVE_SEND_INTERVAL_MS = 200

export default {
  data() {
    return {
      speed: 0.35,
      turnSpeed: 0.35,
      speedSlider: 35,
      turnSlider: 35,
      drive: { frontback: 0, leftright: 0, turn: 0 },
      lastMove: 0,
      moveLoopTimer: null,
      movePadRect: null,
      turnPadRect: null,
      moveKnobTransform: 'translate(-50%, -50%)',
      turnKnobTransform: 'translate(-50%, -50%)',
      moveDragging: false,
      turnDragging: false,
      obstacle: true,
      video: false
    }
  },
  computed: {
    speedPercent() {
      return `${Math.round(this.speed * 100)}%`
    },
    turnPercent() {
      return `${Math.round(this.turnSpeed * 100)}%`
    }
  },
  methods: {
    handleControlCommand(command) {
      const name = command && command.name
      const value = command && command.value
      if (name === 'reset') this.sendCommand(resetCommand())
      else if (name === 'stand') this.sendCommand(standCommand())
      else if (name === 'lie') this.sendCommand(lieCommand())
      else if (name === 'emergency') this.sendCommand(emergencyCommand())
      else if (name === 'stop') this.stopRobot()
      else if (name === 'model') {
        this.selectedRobotModel = Number(value) === 1 ? 1 : 0
        this.robotModel = this.selectedRobotModel
        this.sendCommand(modelCommand(this.selectedRobotModel))
      } else if (name === 'action') {
        this.sendCommand(actionCommand(value))
      }
    },
    stopRobot(showLog = true) {
      this.sendCommand(stopCommand(), showLog)
    },
    resetDrive() {
      this.moveDragging = false
      this.turnDragging = false
      this.drive = { frontback: 0, leftright: 0, turn: 0 }
      this.moveKnobTransform = 'translate(-50%, -50%)'
      this.turnKnobTransform = 'translate(-50%, -50%)'
    },
    setSpeed(event) {
      this.speedSlider = Number(event.detail.value)
      this.speed = this.speedSlider / 100
    },
    setTurnSpeed(event) {
      this.turnSlider = Number(event.detail.value)
      this.turnSpeed = this.turnSlider / 100
    },
    startStick(kind, event) {
      if (kind === 'move') this.moveDragging = true
      if (kind === 'turn') this.turnDragging = true
      const touch = this.getTouch(event)
      this.startMoveLoop()
      this.cacheStickRect(kind, rect => {
        this.updateStick(kind, touch, rect)
        this.sendMove(true)
      })
    },
    moveStick(kind, event) {
      if (kind === 'move' && !this.moveDragging) return
      if (kind === 'turn' && !this.turnDragging) return
      const rect = kind === 'move' ? this.movePadRect : this.turnPadRect
      const touch = this.getTouch(event)
      if (rect) {
        this.updateStick(kind, touch, rect)
      } else {
        this.cacheStickRect(kind, cachedRect => this.updateStick(kind, touch, cachedRect))
      }
    },
    endStick(kind) {
      if (kind === 'move') {
        this.moveDragging = false
        this.moveKnobTransform = 'translate(-50%, -50%)'
        this.drive.frontback = 0
        this.drive.leftright = 0
      } else {
        this.turnDragging = false
        this.turnKnobTransform = 'translate(-50%, -50%)'
        this.drive.turn = 0
      }
      this.sendMove(true)
      if (!this.moveDragging && !this.turnDragging) this.stopMoveLoop()
    },
    getTouch(event) {
      const touch = event.touches && event.touches[0]
      if (!touch) return null
      return { clientX: touch.clientX, clientY: touch.clientY }
    },
    cacheStickRect(kind, callback) {
      if (!this.$refs.controlView || !this.$refs.controlView.getStickRect) return
      this.$refs.controlView.getStickRect(kind, rect => {
        if (!rect) return
        if (kind === 'move') this.movePadRect = rect
        else this.turnPadRect = rect
        if (callback) callback(rect)
      })
    },
    updateStick(kind, touch, rect) {
      if (!touch || !rect) return
      const cx = rect.left + rect.width / 2
      const cy = rect.top + rect.height / 2
      const radius = rect.width * 0.34
      let dx = touch.clientX - cx
      let dy = touch.clientY - cy
      const distance = Math.sqrt(dx * dx + dy * dy)
      if (distance > radius) {
        dx = dx / distance * radius
        dy = dy / distance * radius
      }
      const transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`
      if (kind === 'move') {
        this.moveKnobTransform = transform
        this.drive.leftright = Number((-dx / radius * this.speed).toFixed(2))
        this.drive.frontback = Number((-dy / radius * this.speed).toFixed(2))
      } else {
        this.turnKnobTransform = transform
        this.drive.turn = Number((-dx / radius * this.turnSpeed).toFixed(2))
      }
      this.sendMove(false)
    },
    startMoveLoop() {
      if (this.moveLoopTimer) return
      this.moveLoopTimer = setInterval(() => {
        if (!this.moveDragging && !this.turnDragging) {
          this.stopMoveLoop()
          return
        }
        this.sendMove(false)
      }, MOVE_SEND_INTERVAL_MS)
    },
    stopMoveLoop() {
      if (!this.moveLoopTimer) return
      clearInterval(this.moveLoopTimer)
      this.moveLoopTimer = null
    },
    sendMove(force) {
      const now = Date.now()
      if (!force && now - this.lastMove < MOVE_SEND_INTERVAL_MS) return
      this.lastMove = now
      this.sendCommand(moveCommand(this.drive.frontback, this.drive.leftright, this.drive.turn), false)
    },
    toggleObstacle() {
      this.obstacle = !this.obstacle
      this.sendCommand(obstacleCommand(this.obstacle))
    },
    toggleVideo() {
      this.video = !this.video
      this.sendCommand(videoCommand(this.video))
    }
  }
}

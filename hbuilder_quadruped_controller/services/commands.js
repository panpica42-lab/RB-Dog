export function resetCommand() {
  return { type: 'reset' }
}

export function standCommand() {
  return { type: 'stand' }
}

export function lieCommand() {
  return { type: 'lie' }
}

export function emergencyCommand() {
  return { type: 'emergency' }
}

export function stopCommand() {
  return { type: 'stop' }
}

export function moveCommand(frontback, leftright, turn) {
  return { type: 'move', frontback, leftright, turn }
}

export function modelCommand(value) {
  return { type: 'model', value }
}

export function obstacleCommand(enabled) {
  return { type: 'obstacle', enabled }
}

export function videoCommand(enabled) {
  return { type: 'video', enabled }
}

export function cameraCommand(enabled) {
  return { type: 'camera', enabled }
}

export function actionCommand(code) {
  return { type: 'action', code }
}

export function pointcloudCommand(enabled) {
  return { type: 'pointcloud', enabled }
}

export function createGatewayClient({ onOpen, onClose, onError, onMessage } = {}) {
  let task = null
  let token = 0

  function connect(url) {
    close()
    token += 1
    const currentToken = token
    task = uni.connectSocket({ url, complete: () => {} })

    task.onOpen(() => {
      if (currentToken !== token) return
      if (onOpen) onOpen()
    })

    task.onClose(() => {
      if (currentToken !== token) return
      task = null
      if (onClose) onClose()
    })

    task.onError(error => {
      if (currentToken !== token) return
      if (onError) onError(error)
    })

    task.onMessage(event => {
      if (currentToken !== token) return
      if (!onMessage) return
      try {
        const text = normalizeMessageData(event.data)
        onMessage(JSON.parse(text))
      } catch (error) {
        if (isArrayBuffer(event.data)) {
          onMessage({ type: 'binary', data: event.data })
        } else {
          onMessage(null, error)
        }
      }
    })
  }

  function normalizeMessageData(data) {
    if (typeof data === 'string') return data
    if (isArrayBuffer(data)) {
      if (typeof TextDecoder !== 'undefined') {
        return new TextDecoder('utf-8').decode(data)
      }
      const bytes = new Uint8Array(data)
      let binary = ''
      for (let index = 0; index < bytes.length; index += 1) {
        binary += String.fromCharCode(bytes[index])
      }
      return decodeURIComponent(escape(binary))
    }
    if (data && data.data !== undefined) return normalizeMessageData(data.data)
    return String(data || '')
  }

  function isArrayBuffer(data) {
    return typeof ArrayBuffer !== 'undefined' && data instanceof ArrayBuffer
  }

  function send(payload, callbacks = {}) {
    if (!task) {
      if (callbacks.fail) callbacks.fail()
      if (callbacks.complete) callbacks.complete()
      return false
    }
    task.send({
      data: JSON.stringify(payload),
      success: callbacks.success,
      fail: callbacks.fail,
      complete: callbacks.complete
    })
    return true
  }

  function close() {
    token += 1
    if (!task) return
    const closingTask = task
    task = null
    try {
      closingTask.close({})
    } catch (error) {}
  }

  function isOpen() {
    return Boolean(task)
  }

  return {
    connect,
    send,
    close,
    isOpen
  }
}

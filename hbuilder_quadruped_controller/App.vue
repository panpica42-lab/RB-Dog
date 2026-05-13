<script>
export default {
  onLaunch() {
    // #ifdef APP-PLUS
    plus.screen.lockOrientation('landscape-primary')
    this.enterFullscreen()
    // #endif
  },
  onShow() {
    // #ifdef APP-PLUS
    this.enterFullscreen()
    // #endif
  },
  methods: {
    enterFullscreen() {
      plus.navigator.setFullscreen(true)
      const webview = plus.webview.currentWebview()
      if (webview) {
        webview.setStyle({
          bounce: 'none',
          scrollIndicator: 'none'
        })
      }
    }
  }
}
</script>

<style>
page {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: #061014;
  color: #ecfbfb;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

html,
body {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

view,
text,
button,
input {
  box-sizing: border-box;
}

button::after {
  border: none;
}
</style>

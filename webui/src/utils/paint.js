const SIZE = 512

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(`图片加载失败: ${url}`))
    img.src = url
  })
}

// 与 LayerCanvas 的 DOM 显示完全一致：先居中 rotate，再 flip。
// Layer 的 DOM 变换为: translate(x,y) -> translate(cx,cy) rotate(angle) scaleX(flip)
function drawLayer(ctx, layer, img) {
  const w = layer.scale_w
  const h = layer.scale_h
  const cx = layer.x + w / 2
  const cy = layer.y + h / 2
  ctx.save()
  ctx.translate(cx, cy)
  if (layer.angle) ctx.rotate((layer.angle * Math.PI) / 180)
  if (layer.flip) ctx.scale(-1, 1)
  ctx.drawImage(img, -w / 2, -h / 2, w, h)
  ctx.restore()
}

// 渲染当前所见画布为透明底 RGBA，返回 dataURL
async function renderCanvas(layers) {
  const canvas = document.createElement('canvas')
  canvas.width = SIZE
  canvas.height = SIZE
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, SIZE, SIZE)
  for (const layer of layers) {
    const img = await loadImage(layer.url)
    drawLayer(ctx, layer, img)
  }
  return canvas
}

export { renderCanvas, SIZE }
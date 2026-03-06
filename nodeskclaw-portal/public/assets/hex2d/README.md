# Hex 2D 素材规格

放置 2D 工作区地板纹理和家具精灵的目录。装修为逐格模式，每个占用格独立配置。

## 目录结构

```
hex2d/
  floors/
    terrazzo-diamond.png  水磨石（菱形，通过 clipPath 裁切为六边形）
    carpet-warm.svg       暖色地毯（SVG 占位）
    carpet-cool.svg       冷色地毯（SVG 占位）
    carpet-marble.svg     大理石（SVG 占位）
  furniture/
    office-chair.svg      办公椅（SVG 占位）
    office-desk.svg       办公桌（SVG 占位）
    desk-lamp.svg         台灯（SVG 占位）
    stool.svg             凳子（SVG 占位）
```

SVG 占位素材后续可替换为 Figma 导出的 PNG，需同步更新 `src/config/decorationAssets.ts` 中的 URL。

## Hex Cell 尺寸

| 参数 | 值 |
|---|---|
| HEX_SIZE | 1.2 |
| SCALE | 60 |
| HEX_RADIUS | HEX_SIZE * SCALE * 0.85 = 61.2 |

计算公式：

```
cell_width  = sqrt(3) * HEX_RADIUS ≈ 106 px
cell_height = 2 * HEX_RADIUS ≈ 122 px
```

## 素材要求

- 格式：PNG 或 SVG
- 背景：透明（非透明底色会在 hex 裁切区域内可见）
- 尺寸：不小于 106 x 122 px，建议 2x 以获得 Retina 清晰度
- 地板纹理：通过 `preserveAspectRatio="xMidYMid slice"` + `clip-path="url(#hex-clip)"` 裁切填满六边形
- 家具精灵：通过 `preserveAspectRatio="xMidYMid meet"` + `clip-path` 保持比例居中

## 素材注册

所有素材必须在 `nodeskclaw-portal/src/config/decorationAssets.ts` 中注册后才能在装修面板中使用。

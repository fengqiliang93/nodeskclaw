# Hex 2D 素材规格

放置 2D 工作区地板纹理和家具精灵的目录。

## 目录结构

```
hex2d/
  floors/      地板纹理 PNG
  furniture/   家具精灵 PNG
```

## Hex Cell 尺寸

当前参数：

| 参数 | 值 |
|---|---|
| HEX_SIZE | 1.2 |
| SCALE | 60 |
| HEX_RADIUS | HEX_SIZE * SCALE * 0.85 = 61.2 |
| Y_SCALE | 1（默认正六边形，调为 0.5~0.7 得 2.5D） |

计算公式：

```
cell_width  = sqrt(3) * HEX_RADIUS ≈ 106 px
cell_height = 2 * HEX_RADIUS * Y_SCALE
```

| Y_SCALE | cell_width | cell_height |
|---|---|---|
| 1.0 | 106 px | 122 px |
| 0.7 | 106 px | 86 px |
| 0.5 | 106 px | 61 px |

## 素材要求

- 格式：PNG
- 背景：透明
- 尺寸：不小于 cell bounding box（上表），建议 2x 以获得 Retina 清晰度
- 地板纹理：用 `preserveAspectRatio="xMidYMid slice"` 裁切填满 hex cell
- 家具精灵：用 `preserveAspectRatio="xMidYMid meet"` 保持原始比例居中

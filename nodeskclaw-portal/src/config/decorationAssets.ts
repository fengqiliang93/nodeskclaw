export interface DecorationAsset {
  id: string
  nameKey: string
  category: 'floor' | 'furniture'
  url: string
  thumbnailUrl?: string
}

export const FLOOR_ASSETS: DecorationAsset[] = [
  {
    id: 'terrazzo-diamond',
    nameKey: 'decoration.floor.terrazzo_diamond',
    category: 'floor',
    url: '/assets/hex2d/floors/terrazzo-tile.png',
  },
]

export const FURNITURE_ASSETS: DecorationAsset[] = [
  {
    id: 'office-chair',
    nameKey: 'decoration.furniture.office_chair',
    category: 'furniture',
    url: '/assets/hex2d/furniture/office-chair.png',
  },
]

export function findAssetById(id: string): DecorationAsset | undefined {
  return [...FLOOR_ASSETS, ...FURNITURE_ASSETS].find(a => a.id === id)
}

export function findFloorAssetById(id: string): DecorationAsset | undefined {
  return FLOOR_ASSETS.find(a => a.id === id)
}

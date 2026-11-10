// Quality presets. Everything that costs GPU time should read from here.
export const QUALITY_ORDER = ['low', 'medium', 'high'];

export const QUALITY = {
  low:    { pixelRatio: 1,   seaSegments: 40,  shadows: false, shadowMapSize: 0,    rainDrops: 500 },
  medium: { pixelRatio: 1.5, seaSegments: 96,  shadows: true,  shadowMapSize: 1024, rainDrops: 1000 },
  high:   { pixelRatio: 2,   seaSegments: 160, shadows: true,  shadowMapSize: 2048, rainDrops: 1800 },
};

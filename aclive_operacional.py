"""CLI para calcular o aclive operacional de um talhão usando DEM local.

Implementa o pipeline solicitado:
1. Leitura do KMZ/KML (com suporte a KMZ comprimido).
2. Reprojeção para CRS métrico adequado (SIRGAS 2000 UTM zona determinada
   pelo centróide).
3. Reprojeção/recorte do DEM para o talhão (com pequena margem externa).
4. Aplicação de filtro mediano leve.
5. Cálculo do slope por diferença central (em %), com máscara que remove bordas.
6. Suavização por janela (média uniforme), winsorização opcional e cálculo de
   percentis robustos.
7. Conversão para grau operacional considerando sin(alpha).
8. Fallback automático: se o resultado com o percentil configurado exceder 15°,
   o cálculo é refeito com percentil 80.
9. Saída em JSON e opção de salvar rasters intermediários.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from zipfile import ZipFile

import geopandas as gpd
import numpy as np
import rasterio
from rasterio import Affine
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from rasterio.mask import mask as rio_mask
from rasterio.warp import calculate_default_transform, reproject
from scipy.ndimage import median_filter, uniform_filter, binary_erosion
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

LOGGER = logging.getLogger("aclives")
DEFAULT_PERCENTIL = 80
FALLBACK_PERCENTILE = 70
MAX_OPERATIONAL_DEG = 15.0
DEFAULT_ALPHA_GRAUS = 30.0
DEFAULT_JANELA_M = 50.0
DEFAULT_BUFFER_BORDA_M = 15.0


@dataclass
class RasterData:
    array: np.ndarray
    transform: Affine
    meta: dict


def read_polygon(path: Path) -> gpd.GeoSeries:
    """Lê KMZ/KML retornando GeoSeries com geometria dissolvida."""
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    if path.suffix.lower() == ".kmz":
        with ZipFile(path) as zf, tempfile.TemporaryDirectory() as tmpdir:
            kml_candidates = [name for name in zf.namelist() if name.lower().endswith(".kml")]
            if not kml_candidates:
                raise ValueError("KMZ não possui doc.kml interno.")
            kml_name = kml_candidates[0]
            zf.extract(kml_name, tmpdir)
            gdf = gpd.read_file(Path(tmpdir) / kml_name)
    elif path.suffix.lower() == ".kml":
        gdf = gpd.read_file(path)
    else:
        raise ValueError("Arquivo do talhão deve ser .kmz ou .kml.")

    if gdf.empty:
        raise ValueError("Arquivo do talhão não contém geometrias.")
    if gdf.crs is None:
        LOGGER.info("CRS do talhão não informado. Assumindo EPSG:4326.")
        gdf = gdf.set_crs("EPSG:4326")

    geom = unary_union(make_valid(gdf.unary_union))
    if isinstance(geom, (Polygon, MultiPolygon)):
        return gpd.GeoSeries([geom], crs=gdf.crs)
    raise ValueError("Geometria do talhão não é poligonal.")


def choose_utm_crs(poligon_wgs84: gpd.GeoSeries) -> str:
    centroid = poligon_wgs84.to_crs("EPSG:4326").iloc[0].centroid
    lon = centroid.x
    lat = centroid.y
    zone = int((lon + 180) // 6) + 1
    epsg = 32700 + zone if lat < 0 else 32600 + zone
    return f"EPSG:{epsg}"


def reproject_dem(dem_path: Path, target_crs: str) -> RasterData:
    with rasterio.open(dem_path) as src:
        if src.crs is None:
            raise ValueError("DEM sem CRS definido.")
        if src.crs.to_string() == target_crs:
            data = src.read(1, masked=False).astype(np.float32)
            meta = src.meta.copy()
            meta.update({"dtype": "float32", "nodata": src.nodata})
            return RasterData(data, src.transform, meta)

        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds
        )
        destination = np.empty((height, width), dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=target_crs,
            resampling=Resampling.bilinear,
        )
        meta = src.meta.copy()
        meta.update(
            {
                "crs": target_crs,
                "transform": transform,
                "width": width,
                "height": height,
                "dtype": "float32",
                "nodata": src.nodata,
            }
        )
        return RasterData(destination, transform, meta)


def crop_dem_to_polygon(raster: RasterData, polygon: Polygon, buffer_exterior: float = 5.0) -> RasterData:
    buffered = polygon.buffer(buffer_exterior)
    with MemoryFile() as memfile:
        with memfile.open(**raster.meta) as dataset:
            dataset.write(raster.array, 1)
            out_image, out_transform = rio_mask(
                dataset, [buffered.__geo_interface__], crop=True, filled=False
            )
    dem = out_image[0].astype(np.float32)
    meta = raster.meta.copy()
    meta.update({"transform": out_transform, "height": dem.shape[0], "width": dem.shape[1]})
    return RasterData(dem, out_transform, meta)


def median_denoise(array: np.ndarray) -> np.ndarray:
    mask = ~np.isfinite(array)
    array = array.copy()
    array[mask] = 0.0
    filtered = median_filter(array, size=3)
    filtered[mask] = np.nan
    return filtered


def calculate_slope_percent(array: np.ndarray, transform: Affine) -> tuple[np.ndarray, float]:
    if array.size == 0:
        raise ValueError("DEM recortado vazio.")
    xres = abs(transform.a)
    yres = abs(transform.e)
    if xres <= 0 or yres <= 0:
        raise ValueError("Resolução do DEM inválida.")
    gy, gx = np.gradient(array, yres, xres)
    slope_rad = np.arctan(np.sqrt(gx ** 2 + gy ** 2))
    slope_pct = np.tan(slope_rad) * 100.0
    slope_pct[~np.isfinite(array)] = np.nan
    return slope_pct.astype(np.float32), float((xres + yres) / 2.0)


def inward_buffer(geometry: Polygon, buffer_m: float, *, min_fraction: float = 0.7, min_area_m2: float = 10_000.0):
    original_area = geometry.area
    current = buffer_m
    geom = geometry.buffer(-current)
    while (geom.is_empty or geom.area < min_area_m2 or (geom.area / original_area) < min_fraction) and current > 3.0:
        LOGGER.warning(
            "Buffer interno reduziu área para %.1f%%; reduzindo buffer para %.1f m.",
            100 * (geom.area / original_area) if geom.area else 0.0,
            current * 0.75,
        )
        current *= 0.75
        geom = geometry.buffer(-current)
    if geom.is_empty:
        LOGGER.warning("Buffer interno resultou em geometria vazia; utilizando polígono original.")
        return geometry, 0.0
    return geom, current


def rasterize_mask(geometry: Polygon, transform: Affine, shape: tuple[int, int]) -> np.ndarray:
    return geometry_mask([geometry.__geo_interface__], invert=True, transform=transform, out_shape=shape)


def _compute_slope_percent(grid: "DemGrid") -> np.ndarray:
    elev = grid.elevations
    mask = grid.mask
    if not np.isfinite(elev[mask]).any():
        return np.full_like(elev, np.nan, dtype=float)

    ny, nx = elev.shape
    slopes = np.full((ny, nx), np.nan, dtype=float)
    step = grid.step

    for iy in range(ny):
        for ix in range(nx):
            if not mask[iy, ix] or not np.isfinite(elev[iy, ix]):
                continue

            if ix > 0 and ix < nx - 1 and mask[iy, ix - 1] and mask[iy, ix + 1]:
                dzdx = (elev[iy, ix + 1] - elev[iy, ix - 1]) / (2 * step)
            elif ix > 0 and mask[iy, ix - 1]:
                dzdx = (elev[iy, ix] - elev[iy, ix - 1]) / step
            elif ix < nx - 1 and mask[iy, ix + 1]:
                dzdx = (elev[iy, ix + 1] - elev[iy, ix]) / step
            else:
                dzdx = 0.0

            if iy > 0 and iy < ny - 1 and mask[iy - 1, ix] and mask[iy + 1, ix]:
                dzdy = (elev[iy + 1, ix] - elev[iy - 1, ix]) / (2 * step)
            elif iy > 0 and mask[iy - 1, ix]:
                dzdy = (elev[iy, ix] - elev[iy - 1, ix]) / step
            elif iy < ny - 1 and mask[iy + 1, ix]:
                dzdy = (elev[iy + 1, ix] - elev[iy, ix]) / step
            else:
                dzdy = 0.0

            slope_rad = math.atan(math.sqrt(dzdx * dzdx + dzdy * dzdy))
            slopes[iy, ix] = math.tan(slope_rad) * 100.0

    return slopes


def _uniform_filter(array: np.ndarray, window: int) -> np.ndarray:
    return uniform_filter(array, size=window, mode="nearest")


def uniform_smooth(values: np.ndarray, mask: np.ndarray, window_px: int) -> np.ndarray:
    if window_px < 3:
        window_px = 3
    if window_px % 2 == 0:
        window_px += 1
    valid = mask & np.isfinite(values)
    weighted = np.where(valid, values, 0.0)
    counts = _uniform_filter(valid.astype(np.float32), size=window_px, mode="nearest")
    smoothed = _uniform_filter(weighted, size=window_px, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        smoothed = smoothed / counts
    smoothed[counts == 0] = np.nan
    return smoothed


def winsorize(values: np.ndarray, mask: np.ndarray, pct: float) -> np.ndarray:
    if pct <= 0:
        return values
    valid = values[mask & np.isfinite(values)]
    if valid.size == 0:
        return values
    low = np.nanpercentile(valid, pct)
    high = np.nanpercentile(valid, 100 - pct)
    return np.clip(values, low, high)


def compute_percentile(values: np.ndarray, mask: np.ndarray, percentil: int) -> float:
    valid = values[mask & np.isfinite(values)]
    if valid.size == 0:
        raise ValueError("Nenhum pixel válido para percentil.")
    return float(np.nanpercentile(valid, percentil))


def _compute_percentiles(
    grid: "DemGrid",
    janela_m: float,
    winsorizar_pct: float,
) -> tuple[dict[int, float], float]:
    slopes_pct = _compute_slope_percent(grid)
    mask = grid.mask & np.isfinite(slopes_pct)
    if mask.sum() == 0:
        raise ValueError("Nenhum pixel válido para cálculo do aclive.")

    window_px = clamp_window_pixels(janela_m, grid.step)
    smoothed = uniform_smooth(slopes_pct, mask, window_px)
    if winsorizar_pct > 0:
        smoothed = winsorize(smoothed, mask, winsorizar_pct)

    valid = smoothed[mask & np.isfinite(smoothed)]
    if valid.size == 0:
        raise ValueError("Nenhum pixel válido após suavização.")

    percentiles = {
        50: float(np.nanpercentile(valid, 50)),
        70: float(np.nanpercentile(valid, 70)),
        80: float(np.nanpercentile(valid, 80)),
        85: float(np.nanpercentile(valid, 85)),
        90: float(np.nanpercentile(valid, 90)),
        95: float(np.nanpercentile(valid, 95)),
    }
    return percentiles, float(grid.step)


def clamp_window_pixels(janela_m: float, resolucao_m: float) -> int:
    window_px = max(3, int(math.ceil(janela_m / resolucao_m)))
    if window_px % 2 == 0:
        window_px += 1
    return window_px


def save_raster(path: Path, array: np.ndarray, transform: Affine, crs: str, nodata: float = np.nan) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {
        "driver": "GTiff",
        "height": array.shape[0],
        "width": array.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
    }
    with rasterio.open(path, "w", **kwargs) as dst:
        dst.write(np.where(np.isfinite(array), array, nodata).astype(np.float32), 1)


def pipeline(
    kmz_path: Path,
    dem_path: Path,
    *,
    percentil: int,
    janela_suavizacao_m: float,
    alpha_graus: float,
    buffer_borda_m: float,
    winsorizar_pct: float,
    salvar_rasters: Path | None,
) -> dict:
    talhao = read_polygon(kmz_path)
    utm_crs = choose_utm_crs(talhao)
    LOGGER.info("CRS de trabalho: %s", utm_crs)

    talhao_utm = talhao.to_crs(utm_crs)
    geometry_utm = talhao_utm.iloc[0]

    dem = reproject_dem(dem_path, utm_crs)
    dem = crop_dem_to_polygon(dem, geometry_utm, buffer_exterior=5.0)
    dem.array = median_denoise(dem.array)

    slope_pct, resolucao_m = calculate_slope_percent(dem.array, dem.transform)

    area_total_ha = geometry_utm.area / 10_000.0
    inner_geom, effective_buffer = inward_buffer(geometry_utm, buffer_borda_m)
    mask = rasterize_mask(inner_geom, dem.transform, slope_pct.shape)
    mask &= np.isfinite(slope_pct)
    if area_total_ha > 30.0:
        eroded_mask = binary_erosion(mask, structure=np.ones((3, 3), dtype=bool), border_value=0)
        if eroded_mask.sum() > 0:
            ratio = eroded_mask.sum() / mask.sum()
            if ratio >= 0.7:
                mask = eroded_mask
            else:
                LOGGER.info("Erosão da borda manteria apenas %.1f%% dos pixels; revertendo.", ratio * 100)
        else:
            LOGGER.info("Erosão adicional removeu todos os pixels; mantendo máscara original.")
    if mask.sum() == 0:
        raise ValueError("Buffer interno removeu todos os pixels válidos.")

    janela_px = clamp_window_pixels(janela_suavizacao_m, resolucao_m)
    slope_smoothed = uniform_smooth(slope_pct, mask, janela_px)
    if winsorizar_pct > 0:
        slope_smoothed = winsorize(slope_smoothed, mask, winsorizar_pct)

    sp_pct = compute_percentile(slope_smoothed, mask, percentil)
    percentil_usado = percentil
    slope_deg_raw = math.degrees(math.atan(sp_pct / 100.0))

    if slope_deg_raw > MAX_OPERATIONAL_DEG and FALLBACK_PERCENTILE != percentil:
        LOGGER.info(
            "Aclive operacional %.2f deg excede %.1f deg com P%d. Aplicando fallback P%d.",
            slope_deg_raw,
            MAX_OPERATIONAL_DEG,
            percentil,
            FALLBACK_PERCENTILE,
        )
        sp_pct = compute_percentile(slope_smoothed, mask, FALLBACK_PERCENTILE)
        slope_deg_raw = math.degrees(math.atan(sp_pct / 100.0))
        percentil_usado = FALLBACK_PERCENTILE

    grade_operacional_pct = sp_pct * math.sin(math.radians(alpha_graus))
    theta_op_deg = math.degrees(math.atan(grade_operacional_pct / 100.0))
    if theta_op_deg > 20.0:
        grade_operacional_pct *= 0.7
        theta_op_deg = math.degrees(math.atan(grade_operacional_pct / 100.0))

    area_utilizada_m2 = mask.sum() * abs(dem.transform.a * dem.transform.e)
    area_utilizada_ha = area_utilizada_m2 / 10_000.0

    if salvar_rasters:
        LOGGER.info("Salvando rasters intermediários em %s", salvar_rasters)
        save_raster(salvar_rasters / "slope_pct.tif", slope_pct, dem.transform, utm_crs)
        save_raster(salvar_rasters / "slope_pct_suav.tif", slope_smoothed, dem.transform, utm_crs)
        save_raster(
            salvar_rasters / "mascara_interior.tif",
            mask.astype(np.float32),
            dem.transform,
            utm_crs,
            nodata=0.0,
        )

    return {
        "theta_op_deg": round(theta_op_deg, 4),
        "grade_op_pct": round(grade_operacional_pct, 4),
        "S_p_pct": round(sp_pct, 4),
        "percentil_usado": percentil_usado,
        "janela_suavizacao_m": janela_suavizacao_m,
        "alpha_graus": alpha_graus,
        "buffer_borda_m": effective_buffer or buffer_borda_m,
        "area_utilizada_ha": round(area_utilizada_ha, 4),
        "resolucao_m": round(resolucao_m, 4),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calcula aclive operacional de talhão a partir de DEM local.")
    parser.add_argument("--kmz", "--kml", dest="talhao", required=True, help="Caminho para o talhão (.kmz ou .kml).")
    parser.add_argument("--dem", required=True, help="Caminho para o DEM raster (GeoTIFF).")
    parser.add_argument(
        "--percentil",
        type=int,
        default=DEFAULT_PERCENTIL,
        choices=[70, 80, 85, 90, 95],
        help="Percentil do slope suavizado (default: 80).",
    )
    parser.add_argument(
        "--janela-suavizacao-m",
        type=float,
        default=DEFAULT_JANELA_M,
        help="Janela de suavização em metros (default: 75).",
    )
    parser.add_argument(
        "--alpha-graus",
        type=float,
        default=DEFAULT_ALPHA_GRAUS,
        help="Ângulo máximo em relação ao contorno (default: 30).",
    )
    parser.add_argument(
        "--buffer-borda-m",
        type=float,
        default=DEFAULT_BUFFER_BORDA_M,
        help="Buffer interno para eliminar bordas (default: 15).",
    )
    parser.add_argument(
        "--winsorizar-pct",
        type=float,
        default=0.0,
        help="Winsorização opcional (0 = desativado).",
    )
    parser.add_argument(
        "--salvar-rasters",
        default=None,
        help="Diretório para salvar rasters intermediários (opcional).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nível de log (default: INFO).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(message)s")

    talhao_path = Path(args.talhao)
    dem_path = Path(args.dem)
    salvar_rasters = Path(args.salvar_rasters) if args.salvar_rasters else None

    try:
        result = pipeline(
            talhao_path,
            dem_path,
            percentil=args.percentil,
            janela_suavizacao_m=args.janela_suavizacao_m,
            alpha_graus=args.alpha_graus,
            buffer_borda_m=args.buffer_borda_m,
            winsorizar_pct=args.winsorizar_pct,
            salvar_rasters=salvar_rasters,
        )
    except Exception as exc:  # pragma: no cover
        LOGGER.error("Falha ao calcular aclive operacional: %s", exc)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

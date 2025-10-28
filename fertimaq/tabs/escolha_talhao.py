"""Tab responsible for loading field polygons and computing slope metrics."""

from __future__ import annotations

import json
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Sequence
import xml.etree.ElementTree as ET

import numpy as np
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request

import customtkinter as ctk
from tkinter import filedialog
from scipy.ndimage import binary_erosion, uniform_filter
from PIL import Image, ImageTk
from io import BytesIO
from PIL import Image, ImageTk

from ferticalc_ui_blueprint import create_card, primary_button, section_title

from .base import FertiMaqTab, tab_registry

EARTH_RADIUS_M = 6_371_000.0
DEFAULT_OPERATIONAL_PERCENTILE = 80
FALLBACK_OPERATIONAL_PERCENTILE = 70
OPERATIONAL_THRESHOLD_DEG = 15.0
ALPHA_DEGREES = 30.0
SLOPE_CORRECTION_THRESHOLD_DEG = 20.0
SLOPE_CORRECTION_FACTOR = 0.7
MIN_BUFFER_RETENTION = 0.7


@dataclass
class DemGrid:
    elevations: np.ndarray
    mask: np.ndarray
    x_coords: np.ndarray
    y_coords: np.ndarray
    step: float


# --------------------------------------------------------------------------- #
# KMZ / KML helpers                                                           #
# --------------------------------------------------------------------------- #
def _read_kml_from_kmz(path: Path) -> str:
    with zipfile.ZipFile(path) as kmz:
        kml_name = next((name for name in kmz.namelist() if name.lower().endswith(".kml")), None)
        if not kml_name:
            raise ValueError("KMZ sem arquivo KML interno.")
        return kmz.read(kml_name).decode("utf-8")


def _load_polygon(path: Path) -> tuple[list[tuple[float, float, float]], str]:
    if path.suffix.lower() == ".kmz":
        xml_text = _read_kml_from_kmz(path)
    elif path.suffix.lower() == ".kml":
        xml_text = path.read_text(encoding="utf-8")
    else:
        raise ValueError("Arquivo do talhao deve ser .kmz ou .kml.")

    root = ET.fromstring(xml_text)
    namespaces = {"kml": "http://www.opengis.net/kml/2.2"}

    placemark = root.find(".//kml:Placemark", namespaces) or root.find(".//{*}Placemark")
    if placemark is None:
        raise ValueError("Nenhum Placemark encontrado no arquivo.")

    name_elem = placemark.find("kml:name", namespaces) or placemark.find("{*}name")
    name = name_elem.text.strip() if name_elem is not None and name_elem.text else path.stem

    coords_elem = (
        placemark.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", namespaces)
        or placemark.find(".//{*}Polygon/{*}outerBoundaryIs/{*}LinearRing/{*}coordinates")
    )
    if coords_elem is None or not coords_elem.text:
        raise ValueError("Poligono do talhao nao possui coordenadas.")

    raw_chunks = [chunk for chunk in coords_elem.text.replace("\n", " ").split() if chunk.strip()]
    points: list[tuple[float, float, float]] = []
    for chunk in raw_chunks:
        parts = chunk.split(",")
        if len(parts) < 2:
            continue
        lon = float(parts[0])
        lat = float(parts[1])
        alt = float(parts[2]) if len(parts) > 2 and parts[2] else 0.0
        points.append((lon, lat, alt))

    if len(points) < 3:
        raise ValueError("Talhao possui pontos insuficientes.")
    if points[0] == points[-1]:
        points = points[:-1]

    points = _enrich_elevation(points)
    return points, name

def _enrich_elevation(points: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    if not points:
        return points

    altitudes = {round(pt[2], 2) for pt in points}
    if len(altitudes) > 1:
        return points

    coords = [(lon, lat) for lon, lat, _ in points]
    elevations = _fetch_elevations(coords)
    if not elevations:
        return points

    return [(lon, lat, elev) for (lon, lat, _), elev in zip(points, elevations)]


def _fetch_elevations(coords: Sequence[tuple[float, float]], datasets: Sequence[str] | None = None) -> list[float]:
    datasets = datasets or ("srtm30m", "aster30m", "etopo1")
    for dataset in datasets:
        values = _fetch_elevation_dataset(coords, dataset)
        if values:
            return values
    return []


def _fetch_elevation_dataset(
    coords: Sequence[tuple[float, float]],
    dataset: str,
    *,
    chunk_size: int = 100,
) -> list[float]:
    elevations: list[float] = []
    for start in range(0, len(coords), chunk_size):
        subset = coords[start : start + chunk_size]
        query = "|".join(f"{lat:.6f},{lon:.6f}" for lon, lat in subset)
        url = f"https://api.opentopodata.org/v1/{dataset}?locations={urllib.parse.quote(query, safe=',|')}"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return []

        api_results = data.get("results", [])
        if len(api_results) != len(subset):
            return []

        for item in api_results:
            elevation = item.get("elevation")
            if elevation is None:
                return []
            elevations.append(float(elevation))
    return elevations

# --------------------------------------------------------------------------- #
# Projection helpers                                                          #
# --------------------------------------------------------------------------- #

def _project_points(points: Sequence[tuple[float, float, float]]) -> tuple[list[tuple[float, float]], Dict[str, float]]:
    lats_rad = [math.radians(lat) for _, lat, _ in points]
    lons_rad = [math.radians(lon) for lon, _, _ in points]
    lat0 = sum(lats_rad) / len(lats_rad)
    lon0 = sum(lons_rad) / len(lons_rad)
    cos_lat0 = math.cos(lat0) or 1.0

    projected: list[tuple[float, float]] = []
    for lon, lat, _ in points:
        lon_r = math.radians(lon)
        lat_r = math.radians(lat)
        x = EARTH_RADIUS_M * (lon_r - lon0) * cos_lat0
        y = EARTH_RADIUS_M * (lat_r - lat0)
        projected.append((x, y))
    return projected, {"lat0": lat0, "lon0": lon0, "cos_lat0": cos_lat0}


def _inverse_project(x: float, y: float, projection: Dict[str, float]) -> tuple[float, float]:
    lat = projection["lat0"] + (y / EARTH_RADIUS_M)
    lon = projection["lon0"] + (x / (EARTH_RADIUS_M * projection["cos_lat0"]))
    return math.degrees(lon), math.degrees(lat)


def _polygon_area_m2(points: Sequence[tuple[float, float]]) -> float:
    if not points:
        return 0.0
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += (x1 * y2) - (x2 * y1)
    return abs(area) * 0.5


def _point_in_polygon(x: float, y: float, polygon: Sequence[tuple[float, float]]) -> bool:
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
        if intersects:
            inside = not inside
        j = i
    return inside


def _choose_sampling_step(area_m2: float) -> float:
    if area_m2 <= 30_000.0:
        return 10.0
    if area_m2 <= 200_000.0:
        return 20.0
    if area_m2 <= 1_000_000.0:
        return 35.0
    if area_m2 <= 5_000_000.0:
        return 60.0
    return 90.0

def _collect_dem_grid(
    projected: Sequence[tuple[float, float]],
    projection: Dict[str, float],
) -> DemGrid | None:
    area_m2 = _polygon_area_m2(projected)
    if area_m2 <= 0:
        return None

    step = _choose_sampling_step(area_m2)
    min_x = min(px for px, _ in projected)
    max_x = max(px for px, _ in projected)
    min_y = min(py for _, py in projected)
    max_y = max(py for _, py in projected)

    span_x = max_x - min_x
    span_y = max_y - min_y
    approx_count = ((span_x / step) + 1) * ((span_y / step) + 1)
    if approx_count > 4000:
        scale = math.sqrt(approx_count / 4000)
        step *= scale

    x_coords = np.arange(min_x, max_x + step, step, dtype=float)
    y_coords = np.arange(min_y, max_y + step, step, dtype=float)

    for _ in range(3):
        mask = np.zeros((y_coords.size, x_coords.size), dtype=bool)
        coords: list[tuple[float, float]] = []
        for iy, y in enumerate(y_coords):
            for ix, x in enumerate(x_coords):
                if _point_in_polygon(x, y, projected):
                    mask[iy, ix] = True
                    lon, lat = _inverse_project(x, y, projection)
                    coords.append((lon, lat))

        if coords and (area_m2 / 10_000.0) > 30.0:
            eroded = binary_erosion(mask, structure=np.ones((3, 3), dtype=bool), border_value=0)
            if eroded.sum() > 0:
                retention = eroded.sum() / mask.sum()
                if retention >= MIN_BUFFER_RETENTION:
                    mask = eroded
                    coords = []
                    for iy, y in enumerate(y_coords):
                        for ix, x in enumerate(x_coords):
                            if mask[iy, ix]:
                                lon, lat = _inverse_project(x, y, projection)
                                coords.append((lon, lat))

        if mask.sum() >= 3:
            break

        step = max(step / 2.0, 5.0)
        x_coords = np.arange(min_x, max_x + step, step, dtype=float)
        y_coords = np.arange(min_y, max_y + step, step, dtype=float)
    else:
        return None

    elevations = _fetch_elevations(coords)
    if not elevations or len(elevations) != len(coords):
        return None

    elev_matrix = np.full(mask.shape, np.nan, dtype=float)
    idx = 0
    for iy in range(mask.shape[0]):
        for ix in range(mask.shape[1]):
            if mask[iy, ix]:
                elev_matrix[iy, ix] = elevations[idx]
                idx += 1

    return DemGrid(elevations=elev_matrix, mask=mask, x_coords=x_coords, y_coords=y_coords, step=step)


# --------------------------------------------------------------------------- #
# Slope calculations                                                          #
# --------------------------------------------------------------------------- #

def _scale_projected_to_canvas(
    points: Sequence[tuple[float, float]],
    width: int,
    height: int,
    padding: int = 18,
) -> list[float]:
    if not points:
        return []
    xs = [px for px, _ in points]
    ys = [py for _, py in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)

    scale = min((width - 2 * padding) / span_x, (height - 2 * padding) / span_y)
    scale = max(scale, 0.0001)

    draw_w = span_x * scale
    draw_h = span_y * scale
    offset_x = (width - draw_w) / 2.0
    offset_y = (height - draw_h) / 2.0

    coords: list[float] = []
    for x, y in points:
        cx = offset_x + (x - min_x) * scale
        cy = height - (offset_y + (y - min_y) * scale)
        coords.extend((cx, cy))
    return coords


def _scale_latlon_to_canvas(
    points: Sequence[tuple[float, float, float]],
    bounds: tuple[float, float, float, float],
    width: int,
    height: int,
) -> list[float]:
    if not points:
        return []
    lon_min, lon_max, lat_min, lat_max = bounds
    span_lon = max(lon_max - lon_min, 1e-6)
    span_lat = max(lat_max - lat_min, 1e-6)
    coords: list[float] = []
    for lon, lat, _ in points:
        cx = (lon - lon_min) / span_lon * width
        cy = height - ((lat - lat_min) / span_lat * height)
        coords.extend((cx, cy))
    return coords


def _download_satellite_snapshot(
    points: Sequence[tuple[float, float, float]],
    canvas_width: int,
    canvas_height: int,
) -> tuple[ImageTk.PhotoImage | None, tuple[float, float, float, float] | None]:
    if not points:
        return None, None

    lons = [lon for lon, _, _ in points]
    lats = [lat for _, lat, _ in points]
    lon_min, lon_max = min(lons), max(lons)
    lat_min, lat_max = min(lats), max(lats)


    lon_span = max(lon_max - lon_min, 0.0005)
    lat_span = max(lat_max - lat_min, 0.0005)
    base_span = max(lon_span, lat_span)

    center_lon = (lon_min + lon_max) / 2.0
    center_lat = (lat_min + lat_max) / 2.0

    for margin in (0.7, 0.55, 0.4):
        span = max(base_span * (1.0 + margin), 0.002)
        span = min(span, 10.0)
        for size in (650, 600, 550, 500, 450):
            url = (
                "https://static-maps.yandex.ru/1.x/?"
                f"l=sat&ll={center_lon:.6f},{center_lat:.6f}&spn={span:.6f},{span:.6f}&size={size},{size}"
            )
            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    data = response.read()
                image = Image.open(BytesIO(data)).convert("RGB")
            except Exception:
                continue
            resample = Image.LANCZOS if hasattr(Image, "LANCZOS") else Image.BILINEAR
            image = image.resize((canvas_width, canvas_height), resample)
            photo = ImageTk.PhotoImage(image)
            bounds = (
                center_lon - span / 2.0,
                center_lon + span / 2.0,
                center_lat - span / 2.0,
                center_lat + span / 2.0,
            )
            return photo, bounds

    return None, None
def _compute_slope_percent(grid: DemGrid) -> np.ndarray:
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


def _smooth(values: np.ndarray, mask: np.ndarray, window_px: int) -> np.ndarray:
    if window_px < 3:
        window_px = 3
    if window_px % 2 == 0:
        window_px += 1
    valid = mask & np.isfinite(values)
    weighted = np.where(valid, values, 0.0)
    counts = uniform_filter(valid.astype(np.float32), size=window_px, mode="nearest")
    smoothed = uniform_filter(weighted, size=window_px, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        smoothed = smoothed / counts
    smoothed[counts == 0] = np.nan
    return smoothed


def _winsorize(values: np.ndarray, mask: np.ndarray, pct: float) -> np.ndarray:
    if pct <= 0:
        return values
    valid = values[mask & np.isfinite(values)]
    if valid.size == 0:
        return values
    low = np.nanpercentile(valid, pct)
    high = np.nanpercentile(valid, 100 - pct)
    return np.clip(values, low, high)


def _compute_percentiles(
    grid: DemGrid,
    janela_m: float,
    winsorizar_pct: float,
) -> tuple[dict[int, float], float]:
    slopes_pct = _compute_slope_percent(grid)
    mask = grid.mask & np.isfinite(slopes_pct)
    if mask.sum() == 0:
        raise ValueError("Nenhum pixel valido para calcular aclive.")

    window_px = max(3, int(round(janela_m / grid.step)))
    smoothed = _smooth(slopes_pct, mask, window_px)
    if winsorizar_pct > 0:
        smoothed = _winsorize(smoothed, mask, winsorizar_pct)

    valid = smoothed[mask & np.isfinite(smoothed)]
    if valid.size == 0:
        raise ValueError("Nenhum pixel valido apos suavizacao.")

    percentiles = {
        50: float(np.nanmean(valid)),
        70: float(np.nanpercentile(valid, 70)),
        80: float(np.nanpercentile(valid, 80)),
        85: float(np.nanpercentile(valid, 85)),
        90: float(np.nanpercentile(valid, 90)),
        95: float(np.nanpercentile(valid, 95)),
    }
    return percentiles, float(grid.step)


def _pct_to_deg(slope_pct: float) -> float:
    return math.degrees(math.atan(slope_pct / 100.0))

def _apply_correction_pct(slope_pct: float) -> tuple[float, bool]:
    """Apply the operational correction (factor 0.7) for slopes above the threshold."""
    angle_deg = _pct_to_deg(slope_pct)
    if angle_deg > SLOPE_CORRECTION_THRESHOLD_DEG:
        return slope_pct * SLOPE_CORRECTION_FACTOR, True
    return slope_pct, False

def _apply_correction_deg(angle_deg: float) -> tuple[float, bool]:
    """Apply the correction for a slope already expressed in degrees."""
    if angle_deg <= SLOPE_CORRECTION_THRESHOLD_DEG:
        return angle_deg, False
    slope_pct = math.tan(math.radians(angle_deg)) * 100.0
    corrected_pct, applied = _apply_correction_pct(slope_pct)
    return _pct_to_deg(corrected_pct), applied

def _slopes_from_edges(
    projected: Sequence[tuple[float, float]],
    original: Sequence[tuple[float, float, float]],
) -> tuple[float, float, float, int, bool]:
    n = min(len(projected), len(original))
    if n < 2:
        return 0.0, 0.0, 0.0, DEFAULT_OPERATIONAL_PERCENTILE, False

    weighted_sum = 0.0
    total_length = 0.0
    max_deg = 0.0
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = projected[i]
        x2, y2 = projected[j]
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist <= 0.0:
            continue
        z1 = original[i][2]
        z2 = original[j][2]
        rise = abs(z2 - z1)
        slope_rad = math.atan(rise / dist) if dist else 0.0
        weighted_sum += slope_rad * dist
        total_length += dist
        slope_deg = math.degrees(slope_rad)
        if slope_deg > max_deg:
            max_deg = slope_deg

    if total_length == 0.0:
        avg_deg = max_deg = 0.0
    else:
        avg_deg = math.degrees(weighted_sum / total_length)

    avg_deg, avg_corrected = _apply_correction_deg(avg_deg)
    max_deg, max_corrected = _apply_correction_deg(max_deg)
    correction_applied = avg_corrected or max_corrected
    return avg_deg, max_deg, max_deg, DEFAULT_OPERATIONAL_PERCENTILE, correction_applied


def _slopes_from_polygon(
    projected: Sequence[tuple[float, float]],
    original: Sequence[tuple[float, float, float]],
    projection: Dict[str, float],
) -> tuple[float, float, float, int, bool]:
    grid = _collect_dem_grid(projected, projection)
    if grid:
        percentiles, _ = _compute_percentiles(grid, janela_m=50.0, winsorizar_pct=0.0)
        mean_pct = percentiles[50]
        mean_pct, mean_corrected = _apply_correction_pct(mean_pct)
        mean_deg = _pct_to_deg(mean_pct)
        operational_pct = percentiles[DEFAULT_OPERATIONAL_PERCENTILE]
        operational_percentile = DEFAULT_OPERATIONAL_PERCENTILE
        correction_applied = mean_corrected

        operational_deg_raw = _pct_to_deg(operational_pct)
        if (
            operational_deg_raw > OPERATIONAL_THRESHOLD_DEG
            and percentiles.get(FALLBACK_OPERATIONAL_PERCENTILE) is not None
        ):
            operational_pct = percentiles[FALLBACK_OPERATIONAL_PERCENTILE]
            operational_percentile = FALLBACK_OPERATIONAL_PERCENTILE
            operational_deg_raw = _pct_to_deg(operational_pct)

        grade_operacional_pct = operational_pct * math.sin(math.radians(ALPHA_DEGREES))
        grade_operacional_pct, operational_corrected = _apply_correction_pct(grade_operacional_pct)
        operational_deg = _pct_to_deg(grade_operacional_pct)
        correction_applied = correction_applied or operational_corrected

        severe_pct = percentiles[95]
        severe_pct, severe_corrected = _apply_correction_pct(severe_pct)
        severe_deg = _pct_to_deg(severe_pct)
        correction_applied = correction_applied or severe_corrected
        return mean_deg, operational_deg, severe_deg, operational_percentile, correction_applied

    return _slopes_from_edges(projected, original)


# --------------------------------------------------------------------------- #
# UI                                                                         #
# --------------------------------------------------------------------------- #
@tab_registry.register
class EscolhaTalhaoTab(FertiMaqTab):
    tab_id = "escolha_talhao"
    title = "ESCOLHA DO TALHAO"

    def __init__(self, app: "FertiMaqApp") -> None:
        super().__init__(app)
        self._canvas_width = 620
        self._canvas_height = 620

        self._projected_polygon: list[tuple[float, float]] = []
        self._original_polygon: list[tuple[float, float, float]] = []
        self._projection_params: Dict[str, float] | None = None
        self._map_bounds: tuple[float, float, float, float] | None = None
        self._canvas_bg_photo: ImageTk.PhotoImage | None = None
        self._status_var = ctk.StringVar(value="Nenhum talhao carregado.")
        self._file_var = ctk.StringVar(value="")

        self._area_display_var = ctk.StringVar(value="Area (ha): --")
        self._slope_mean_display_var = ctk.StringVar(value="Aclive medio (P50 graus): --")
        self._slope_max_display_var = ctk.StringVar(value="Aclive maximo (P95 graus): --")
        self._slope_selected_display_var = ctk.StringVar(value="Aclive em uso (graus): --")
        self._correction_message_var = ctk.StringVar(value="")

        self._slope_mean_deg: float | None = None
        self._correction_active = False

        self._last_slope_mode = "manual"

        self._canvas: tk.Canvas | None = None
        self._manual_calc_button: ctk.CTkButton | None = None
        self._status_label: ctk.CTkLabel | None = None
        self._radio_buttons: dict[str, ctk.CTkRadioButton] = {}

    # ------------------------------------------------------------------ #
    # UI assembly
    # ------------------------------------------------------------------ #

    def build(self, frame: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        mapa_card = create_card(scroll, row=0, column=0)
        mapa_card.grid_columnconfigure(0, weight=1)
        mapa_card.grid_rowconfigure(5, weight=1)

        section_title(mapa_card, "Selecao do talhao (.kmz)")

        ctk.CTkLabel(
            mapa_card,
            text=(
                "Carregue um arquivo .kmz com o poligono da area de cultivo. "
                "O talhao sera exibido abaixo e os valores de area e aclive serao "
                "preenchidos automaticamente."
            ),
            justify="left",
            wraplength=680,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 14))

        self._status_label = ctk.CTkLabel(
            mapa_card,
            textvariable=self._status_var,
            anchor="w",
            text_color="#666666",
        )
        self._status_label.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))

        primary_button(mapa_card, text="Carregar talhao (.kmz)", command=self._choose_file, row=3)

        ctk.CTkLabel(
            mapa_card,
            textvariable=self._file_var,
            anchor="w",
            text_color="#3d4e8a",
        ).grid(row=4, column=0, sticky="ew", padx=20, pady=(6, 12))

        canvas_frame = ctk.CTkFrame(mapa_card, fg_color="#ffffff", corner_radius=18)
        canvas_frame.grid(row=5, column=0, sticky="nsew", padx=20, pady=(0, 20))
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.configure(width=self._canvas_width, height=self._canvas_height)
        canvas_frame.grid_propagate(False)

        self._canvas = tk.Canvas(
            canvas_frame,
            width=self._canvas_width,
            height=self._canvas_height,
            background="#ffffff",
            highlightthickness=0,
        )
        self._canvas.grid(row=0, column=0, sticky="nsew")

        cards_row = ctk.CTkFrame(scroll, fg_color="transparent")
        cards_row.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        for col in (0, 1):
            cards_row.grid_columnconfigure(col, weight=1, uniform="cards")

        summary_card = create_card(
            cards_row,
            row=0,
            column=0,
            sticky="nsew",
            padding={"padx": (0, 10), "pady": (0, 0)},
        )
        summary_card.configure(fg_color="#343a46")
        section_title(summary_card, "Resumo do talhao")

        summary_body = ctk.CTkFrame(summary_card, fg_color="transparent")
        summary_body.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 12))
        summary_body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            summary_body,
            textvariable=self._area_display_var,
            anchor="w",
            text_color="#eef1fb",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(
            summary_body,
            textvariable=self._slope_mean_display_var,
            anchor="w",
            text_color="#eef1fb",
        ).grid(row=1, column=0, sticky="ew", pady=8)
        ctk.CTkLabel(
            summary_body,
            textvariable=self._slope_max_display_var,
            anchor="w",
            text_color="#eef1fb",
        ).grid(row=2, column=0, sticky="ew", pady=8)
        ctk.CTkLabel(
            summary_body,
            textvariable=self._slope_selected_display_var,
            anchor="w",
            text_color="#d8def4",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=3, column=0, sticky="ew", pady=(8, 0))

        ctk.CTkLabel(
            summary_card,
            textvariable=self._correction_message_var,
            anchor="w",
            text_color="#f4c577",
            font=ctk.CTkFont(size=12, slant="italic"),
        ).grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 16))

        manual_card = create_card(
            cards_row,
            row=0,
            column=1,
            sticky="nsew",
            padding={"padx": (10, 0), "pady": (0, 0)},
        )
        manual_card.configure(fg_color="#343a46")
        manual_card.grid_columnconfigure(0, weight=1)

        section_title(manual_card, "Dados manuais e selecao de aclive")

        ctk.CTkLabel(
            manual_card,
            text=(
                "Caso nao exista um arquivo do talhao, informe manualmente a area (ha) "
                "e o aclive em graus. Voce tambem pode optar pelos valores calculados acima."
            ),
            justify="left",
            wraplength=320,
            anchor="w",
            text_color="#cfd7f2",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(6, 14))

        input_frame = ctk.CTkFrame(manual_card, fg_color="transparent")
        input_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 14))
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_frame, text="Area (ha)", anchor="w", text_color="#eef1fb").grid(
            row=0, column=0, sticky="w", pady=6
        )
        ctk.CTkEntry(
            input_frame,
            textvariable=self.app.manual_area_var,
            placeholder_text="ex: 12.5",
            width=140,
        ).grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=6)

        ctk.CTkLabel(input_frame, text="Aclive manual (graus)", anchor="w", text_color="#eef1fb").grid(
            row=1, column=0, sticky="w", pady=6
        )
        ctk.CTkEntry(
            input_frame,
            textvariable=self.app.manual_slope_deg_var,
            placeholder_text="ex: 12.0",
            width=140,
        ).grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=6)

        self._manual_calc_button = ctk.CTkButton(
            manual_card,
            text="CALCULAR",
            command=self._apply_manual_values,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#4CAF50",
            hover_color="#388E3C",
            text_color="#ffffff",
        )
        self._manual_calc_button.grid(row=3, column=0, sticky="ew", padx=20, pady=(10, 18))

        ctk.CTkLabel(
            manual_card,
            text="Escolha qual aclive utilizar nos calculos seguintes:",
            anchor="w",
            text_color="#eef1fb",
        ).grid(row=4, column=0, sticky="ew", padx=20, pady=(18, 8))

        radio_frame = ctk.CTkFrame(manual_card, fg_color="transparent")
        radio_frame.grid(row=5, column=0, sticky="w", padx=20, pady=(0, 12))

        slope_mode_var = self.app.field_vars["slope_mode"]

        self._radio_buttons["manual"] = ctk.CTkRadioButton(
            radio_frame,
            text="Manual",
            value="manual",
            variable=slope_mode_var,
            text_color="#eef1fb",
            command=lambda: self._on_slope_mode_change("manual"),
        )
        self._radio_buttons["manual"].grid(row=0, column=0, padx=(0, 12), pady=4)

        self._radio_buttons["medio"] = ctk.CTkRadioButton(
            radio_frame,
            text="Medio (P50)",
            value="medio",
            variable=slope_mode_var,
            text_color="#eef1fb",
            command=lambda: self._on_slope_mode_change("medio"),
        )
        self._radio_buttons["medio"].grid(row=0, column=1, padx=(0, 12), pady=4)

        self._radio_buttons["maximo"] = ctk.CTkRadioButton(
            radio_frame,
            text="Maximo (P95)",
            value="maximo",
            variable=slope_mode_var,
            text_color="#eef1fb",
            command=lambda: self._on_slope_mode_change("maximo"),
        )
        self._radio_buttons["maximo"].grid(row=0, column=2, padx=(0, 12), pady=4)

        mapa_card.update_idletasks()
        manual_card.update_idletasks()

        self.app.field_vars["area_hectares"].trace_add("write", lambda *_: self._refresh_info_labels())
        self.app.field_vars["slope_avg_deg"].trace_add("write", lambda *_: self._refresh_info_labels())
        self.app.field_vars["slope_max_deg"].trace_add("write", lambda *_: self._refresh_info_labels())
        self.app.field_vars["slope_selected_deg"].trace_add("write", lambda *_: self._refresh_info_labels())
        slope_mode_var.trace_add("write", lambda *_: self._on_mode_var_update())

        self._update_slope_radios()
        self._refresh_info_labels()

    # ------------------------------------------------------------------ #
    # Rendering helpers                                                  #
    # ------------------------------------------------------------------ #

    def _render_canvas(self) -> None:
        if not self._canvas:
            return
        self._canvas.delete("all")
        if self._canvas_bg_photo:
            self._canvas.create_image(0, 0, image=self._canvas_bg_photo, anchor="nw")
        if not self._projected_polygon:
            self._canvas.create_text(
                self._canvas_width / 2,
                self._canvas_height / 2,
                text="Nenhum talhao carregado.",
                fill="#9aa0ad",
                font=("Calibri", 16, "italic"),
            )
            return

        coords = self._polygon_to_canvas()
        if not coords:
            return

        self._canvas.create_polygon(
            coords,
            fill="#b2c8ff",
            outline="#3450a1",
            width=2,
        )

    def _polygon_to_canvas(self) -> list[float]:
        if self._map_bounds and self._original_polygon:
            return _scale_latlon_to_canvas(
                self._original_polygon, self._map_bounds, self._canvas_width, self._canvas_height
            )
        return _scale_projected_to_canvas(
            self._projected_polygon,
            self._canvas_width,
            self._canvas_height,
            padding=0,
        )

    def _update_canvas_background(self, polygon: Sequence[tuple[float, float, float]]) -> None:
        self._canvas_bg_photo = None
        self._map_bounds = None
        if self._canvas is not None:
            self._canvas.update_idletasks()
            width = max(int(self._canvas.winfo_width() or self._canvas_width), self._canvas_width)
            height = max(int(self._canvas.winfo_height() or self._canvas_height), self._canvas_height)
        else:
            width = self._canvas_width
            height = self._canvas_height
        photo, bounds = _download_satellite_snapshot(polygon, width, height)
        if photo and bounds:
            self._canvas_bg_photo = photo
            self._map_bounds = bounds

    # ------------------------------------------------------------------ #
    # State updates                                                      #
    # ------------------------------------------------------------------ #

    def _refresh_info_labels(self) -> None:
        area_text = self.app.field_vars["area_hectares"].get()
        mean_text_var = self.app.field_vars["slope_avg_deg"].get()
        max_text_var = self.app.field_vars["slope_max_deg"].get()
        selected_text = self.app.field_vars["slope_selected_deg"].get()
        mode = self.app.field_vars["slope_mode"].get()
        mean_fallback = f"{self._slope_mean_deg:.2f}" if self._slope_mean_deg is not None else "--"

        mean_text = mean_text_var or mean_fallback
        max_text = max_text_var or "--"

        self._area_display_var.set(f"Area (ha): {area_text or '--'}")
        self._slope_mean_display_var.set(f"Aclive medio (P50 graus): {mean_text}")
        self._slope_max_display_var.set(f"Aclive maximo (P95 graus): {max_text}")

        if 'medio' in self._radio_buttons:
            self._radio_buttons['medio'].configure(text='Medio (P50)')
        if 'maximo' in self._radio_buttons:
            self._radio_buttons['maximo'].configure(text='Maximo (P95)')

        if selected_text:
            mode_label = {
                'manual': 'Manual',
                'medio': 'Medio (P50)',
                'maximo': 'Maximo (P95)',
            }.get(mode, mode)
            self._slope_selected_display_var.set(f"Aclive em uso ({mode_label}): {selected_text} graus")
        else:
            self._slope_selected_display_var.set('Aclive em uso (graus): --')

        if self._correction_active:
            self._correction_message_var.set('Fator 0.7 aplicado automaticamente (aclive acima de 20 graus).')
        else:
            self._correction_message_var.set('')

        self._render_canvas()

    def _update_slope_radios(self) -> None:
        has_map_slopes = bool(self.app.field_vars["slope_avg_deg"].get() or self.app.field_vars["slope_max_deg"].get())
        state = "normal" if has_map_slopes else "disabled"
        for key in ("medio", "maximo"):
            self._radio_buttons[key].configure(state=state)
        self._radio_buttons["manual"].configure(state="normal")

    def _on_slopes_changed(self) -> None:
        self._update_slope_radios()
        self._refresh_info_labels()

    def _on_mode_var_update(self) -> None:
        self._last_slope_mode = self.app.field_vars["slope_mode"].get()
        self._refresh_info_labels()

    # ------------------------------------------------------------------ #
    # Event handlers                                                     #
    # ------------------------------------------------------------------ #

    def _choose_file(self) -> None:
        filename = filedialog.askopenfilename(
            title="Selecione o arquivo KMZ do talhao",
            filetypes=[("Arquivo KMZ", "*.kmz"), ("Todos os arquivos", "*.*")],
        )
        if not filename:
            return
        self._load_kmz(Path(filename))

    def _load_kmz(self, path: Path) -> None:
        try:
            polygon, placemark_name = _load_polygon(path)
            projected, projection = _project_points(polygon)
            area_m2 = _polygon_area_m2(projected)
            area_ha = area_m2 / 10_000.0
            mean_deg, _, severe_deg, _, correction_applied = _slopes_from_polygon(
                projected, polygon, projection
            )
            slopes_available = max(mean_deg, severe_deg) > 0.05

            self._projected_polygon = projected
            self._original_polygon = polygon
            self._projection_params = projection
            self._update_canvas_background(polygon)
            self.app.field_vars["kmz_path"].set(path.name)
            self.app.set_field_area(area_ha, source="mapa")
            self.app.manual_area_var.set(f"{area_ha:.2f}")
            if self._manual_calc_button is not None:
                self._manual_calc_button.configure(state="disabled")
            if slopes_available:
                self._slope_mean_deg = mean_deg
                self._correction_active = correction_applied
                self.app.set_map_slopes(mean_deg, severe_deg)
                self.app.preset_manual_slope(mean_deg)
            else:
                self._slope_mean_deg = None
                self._correction_active = False
                self.app.clear_map_slopes()
                self.app.clear_manual_slope()

            self._refresh_info_labels()
            self._file_var.set(f"{path.name} - {placemark_name}")

            if slopes_available and self.app.apply_slope_mode("medio"):
                self.app.field_vars["slope_mode"].set("medio")
                self._status_label.configure(text_color="#3f7e2d")
                status_msg = (
                    f"Talhao carregado. Medio (P50): {mean_deg:.2f} graus. Maximo (P95): {severe_deg:.2f} graus."
                )
                self._status_var.set(status_msg)
            else:
                self.app.field_vars["slope_mode"].set("manual")
                self.app.field_vars["slope_selected_deg"].set("")
                self._status_label.configure(text_color="#b36b00")
                self._status_var.set(
                    "Nao foi possivel calcular o aclive automaticamente. Informe o valor manualmente."
                )

            self._update_slope_radios()

        except Exception as exc:
            self._projected_polygon = []
            self._original_polygon = []
            self._projection_params = None
            self._slope_mean_deg = None
            self._correction_active = False
            self._map_bounds = None
            self._canvas_bg_photo = None
            self._render_canvas()
            self.app.field_vars["kmz_path"].set("")
            if self._status_label:
                self._status_label.configure(text_color="#b00020")
            self._status_var.set(f"Falha ao carregar talhao: {exc}")
            self._file_var.set("")
            self.app.clear_map_slopes()
            self.app.clear_manual_slope()
            if self._manual_calc_button is not None:
                self._manual_calc_button.configure(state="normal")
            self._update_slope_radios()
            self._refresh_info_labels()

    def _apply_manual_values(self) -> None:
        area_text = (self.app.manual_area_var.get() or "").strip().replace(",", ".")
        slope_text = (self.app.manual_slope_deg_var.get() or "").strip().replace(",", ".")

        if self._projected_polygon:
            if self._status_label:
                self._status_label.configure(text_color="#b00020")
            self._status_var.set("Para usar o modo manual, remova o talhao carregado.")
            return

        try:
            if not area_text:
                raise ValueError("Informe a area em hectares.")
            if not slope_text:
                raise ValueError("Informe o aclive manual em graus.")

            area = float(area_text)
            slope_deg = float(slope_text)
            if area <= 0:
                raise ValueError("A area deve ser maior que zero.")
            if not (0 <= slope_deg < 90):
                raise ValueError("O aclive deve estar entre 0 e 90 graus.")

            self.app.set_manual_area(area)
            self.app.set_manual_slope(slope_deg)
            self._correction_active = False

            if self._status_label:
                self._status_label.configure(text_color="#3f7e2d")
            self._status_var.set("Valores manuais aplicados ao calculo.")
            self._refresh_info_labels()
            self._update_slope_radios()

        except ValueError as exc:
            if self._status_label:
                self._status_label.configure(text_color="#b00020")
            self._status_var.set(str(exc))

    def _on_slope_mode_change(self, mode: str) -> None:
        if not self.app.apply_slope_mode(mode):
            self.app.field_vars["slope_mode"].set(self._last_slope_mode)
            if self._status_label:
                self._status_label.configure(text_color="#b00020")
            self._status_var.set("Selecao indisponivel: informe o valor correspondente.")
            return

        self._last_slope_mode = mode
        if self._status_label:
            self._status_label.configure(text_color="#3d4e8a")
        self._status_var.set("Aclive atualizado para uso nas proximas abas.")
        if mode != "manual":
            selected_value = self.app.field_vars["slope_selected_deg"].get()
            if selected_value:
                self.app.manual_slope_deg_var.set(selected_value)
        self._refresh_info_labels()

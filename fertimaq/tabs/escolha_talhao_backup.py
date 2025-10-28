"""Tab that loads a field polygon and prepares slope metrics for FertiMaq."""

from __future__ import annotations

import json
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple
import xml.etree.ElementTree as ET

import numpy as np
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request

import customtkinter as ctk
from tkinter import filedialog

from ferticalc_ui_blueprint import create_card, primary_button, section_title

from .base import FertiMaqTab, tab_registry

EARTH_RADIUS_M = 6_371_000.0
DEFAULT_OPERATIONAL_PERCENTILE = 80
FALLBACK_OPERATIONAL_PERCENTILE = 70
OPERATIONAL_THRESHOLD_DEG = 15.0
ALPHA_DEGREES = 30.0


@dataclass
class DemGrid:
    elevations: np.ndarray
    mask: np.ndarray
    x_coords: np.ndarray
    y_coords: np.ndarray
    step: float


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
        raise ValueError("polígono do talhao Não possui coordenadas.")

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


def _project_points(points: Sequence[tuple[float, float, float]]) -> tuple[list[tuple[float, float]], dict[str, float]]:
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


def _inverse_project(x: float, y: float, projection: dict[str, float]) -> tuple[float, float]:
    lat = projection["lat0"] + (y / EARTH_RADIUS_M)
    lon = projection["lon0"] + (x / (EARTH_RADIUS_M * projection["cos_lat0"]))
    return math.degrees(lon), math.degrees(lat)


def _polygon_área_m2(points: Sequence[tuple[float, float]]) -> float:
    if not points:
        return 0.0
    área = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        área += (x1 * y2) - (x2 * y1)
    return abs(área) * 0.5


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


def _choose_sampling_step(área_m2: float) -> float:
    if área_m2 <= 30_000.0:
        return 10.0
    if área_m2 <= 200_000.0:
        return 20.0
    if área_m2 <= 1_000_000.0:
        return 35.0
    if área_m2 <= 5_000_000.0:
        return 60.0
    return 90.0


def _collect_dem_grid(
    projected: Sequence[tuple[float, float]],
    projection: dict[str, float],
) -> DemGrid | None:
    área_m2 = _polygon_área_m2(projected)
    if área_m2 <= 0:
        return None

    step = _choose_sampling_step(área_m2)
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

        if (área_m2 / 10_000.0) > 30:
            from scipy.ndimage import binary_erosion

            eroded = binary_erosion(mask, structure=np.ones((3, 3), dtype=bool), border_value=0)
            if eroded.sum() > 0:
                ratio = eroded.sum() / mask.sum()
                if ratio >= 0.7:
                    mask = eroded
                    coords = []
                    for iy, y in enumerate(y_coords):
                        for ix, x in enumerate(x_coords):
                            if mask[iy, ix]:
                                lon, lat = _inverse_project(x, y, projection)
                                coords.append((lon, lat))
                # caso erosão reduza demais a máscara, mantém original

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


def _uniform_filter(array: np.ndarray, window: int) -> np.ndarray:
    from scipy.ndimage import uniform_filter

    return uniform_filter(array, size=window, mode="nearest")


def _smooth(values: np.ndarray, mask: np.ndarray, window_px: int) -> np.ndarray:
    if window_px < 3:
        window_px = 3
    if window_px % 2 == 0:
        window_px += 1
    valid = mask & np.isfinite(values)
    weighted = np.where(valid, values, 0.0)
    counts = _uniform_filter(valid.astype(np.float32), window_px)
    smoothed = _uniform_filter(weighted, window_px)
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
        slope_rad = math.atan(rise / dist)
        weighted_sum += slope_rad * dist
        total_length += dist
        slope_deg = math.degrees(slope_rad)
        if slope_deg > max_deg:
            max_deg = slope_deg

    if total_length == 0.0:
        return 0.0, max_deg, max_deg, DEFAULT_OPERATIONAL_PERCENTILE

    avg_deg = math.degrees(weighted_sum / total_length)
    return avg_deg, max_deg, max_deg, DEFAULT_OPERATIONAL_PERCENTILE, False


def _slopes_from_polygon(
    projected: Sequence[tuple[float, float]],
    original: Sequence[tuple[float, float, float]],
    projection: dict[str, float],
) -> tuple[float, float, float, int, bool]:
    grid = _collect_dem_grid(projected, projection)
    if grid:
        percentiles, _ = _compute_percentiles(grid, janela_m=50.0, winsorizar_pct=0.0)
        median_deg = _pct_to_deg(percentiles[50])
        operational_pct = percentiles[DEFAULT_OPERATIONAL_PERCENTILE]
        operational_percentile = DEFAULT_OPERATIONAL_PERCENTILE
        operational_deg_raw = _pct_to_deg(operational_pct)
        correction_applied = False
        if (
            operational_deg_raw > OPERATIONAL_THRESHOLD_DEG
            and percentiles.get(FALLBACK_OPERATIONAL_PERCENTILE) is not None
        ):
            operational_pct = percentiles[FALLBACK_OPERATIONAL_PERCENTILE]
            operational_percentile = FALLBACK_OPERATIONAL_PERCENTILE
        grade_operacional_pct = operational_pct * math.sin(math.radians(ALPHA_DEGREES))
        operational_deg = _pct_to_deg(grade_operacional_pct)
        if operational_deg > 20.0:
            grade_operacional_pct *= 0.7
            operational_deg = _pct_to_deg(grade_operacional_pct)
            correction_applied = True
        severe_deg = _pct_to_deg(percentiles[95])
        return median_deg, operational_deg, severe_deg, operational_percentile, correction_applied

    return _slopes_from_edges(projected, original)


@tab_registry.register
class EscolhaTalhaoTab(FertiMaqTab):
    tab_id = "escolha_talhao"
    title = "ESCOLHA DO TALHÃO"

    def __init__(self, app) -> None:
        super().__init__(app)
        self._canvas_width = 680
        self._canvas_height = 420

        self._projected_polygon: list[tuple[float, float]] = []
        self._projection_params: dict[str, float] | None = None
        self._status_var = ctk.StringVar(value="Nenhum talhao carregado.")
        self._file_var = ctk.StringVar(value="")

        self._área_display_var = ctk.StringVar(value="Área (ha): --")
        self._slope_media_display_var = ctk.StringVar(value="Aclive médio (P50 graus): --")
        self._slope_operacional_display_var = ctk.StringVar(value="Aclive operacional (P90 graus): --")
        self._slope_severo_display_var = ctk.StringVar(value="Aclive severo (P95 graus): --")
        self._slope_selected_display_var = ctk.StringVar(value="Aclive em uso (graus): --")
        self._slope_median_deg: float | None = None
        self._operational_percentil: int = DEFAULT_OPERATIONAL_PERCENTILE

        self._last_slope_mode = "manual"

        self._canvas: tk.Canvas | None = None
        self._status_label: ctk.CTkLabel | None = None
        self._radio_buttons: dict[str, ctk.CTkRadioButton] = {}

    def build(self, frame: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        mapa_card = create_card(scroll, row=0, column=0)
        mapa_card.grid_columnconfigure(0, weight=1)

        section_title(mapa_card, "Seleção do talhão (.kmz)")

        ctk.CTkLabel(
            mapa_card,
            text=(
                "Carregue um arquivo .kmz contendo o polígono da área de cultivo. "
                "O talhao Será exibido abaixo e os valores de área e aclive Seráo "
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

        primary_button(mapa_card, text="Carregar talhão (.kmz)", command=self._choose_file, row=3)

        ctk.CTkLabel(
            mapa_card,
            textvariable=self._file_var,
            anchor="w",
            text_color="#3d4e8a",
        ).grid(row=4, column=0, sticky="ew", padx=20, pady=(6, 12))

        info_frame = ctk.CTkFrame(mapa_card, fg_color="#e4e7f5", corner_radius=14)
        info_frame.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 16))
        info_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(info_frame, textvariable=self._área_display_var, anchor="w", text_color="#1f2d4d").grid(
            row=0, column=0, sticky="ew", padx=18, pady=(12, 4)
        )
        ctk.CTkLabel(info_frame, textvariable=self._slope_media_display_var, anchor="w", text_color="#1f2d4d").grid(
            row=1, column=0, sticky="ew", padx=18, pady=4
        )
        ctk.CTkLabel(info_frame, textvariable=self._slope_operacional_display_var, anchor="w", text_color="#1f2d4d").grid(
            row=2, column=0, sticky="ew", padx=18, pady=4
        )
        ctk.CTkLabel(info_frame, textvariable=self._slope_severo_display_var, anchor="w", text_color="#1f2d4d").grid(
            row=3, column=0, sticky="ew", padx=18, pady=4
        )
        ctk.CTkLabel(
            info_frame,
            textvariable=self._slope_selected_display_var,
            anchor="w",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=4, column=0, sticky="ew", padx=18, pady=(4, 12))

        canvas_frame = ctk.CTkFrame(mapa_card, fg_color="#ffffff", corner_radius=18)
        canvas_frame.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 12))

        self._canvas = tk.Canvas(
            canvas_frame,
            width=self._canvas_width,
            height=self._canvas_height,
            bg="#ffffff",
            highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True, padx=10, pady=10)
        self._render_canvas()

        manual_card = create_card(scroll, row=1, column=0)
        manual_card.grid_columnconfigure(0, weight=1)

        section_title(manual_card, "Dados manuais e Seleção de aclive")

        ctk.CTkLabel(
            manual_card,
            text=(
                "Caso Não exista um arquivo do talhao, informe manualmente a área (ha) "
                "e o aclive em graus. Voce tambem pode optar por utilizar o aclive operacional "
                "ou severo calculado a partir do mapa."
            ),
            justify="left",
            wraplength=680,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 12))

        input_frame = ctk.CTkFrame(manual_card, fg_color="transparent")
        input_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 12))
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_frame, text="Área (ha)", anchor="w").grid(row=0, column=0, sticky="w", pady=6)
        ctk.CTkEntry(input_frame, textvariable=self.app.manual_área_var, placeholder_text="ex: 12.5").grid(
            row=0, column=1, sticky="ew", padx=(10, 0), pady=6
        )

        ctk.CTkLabel(input_frame, text="Aclive manual (graus)", anchor="w").grid(row=1, column=0, sticky="w", pady=6)
        ctk.CTkEntry(
            input_frame,
            textvariable=self.app.manual_slope_deg_var,
            placeholder_text="ex: 12.0",
        ).grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=6)

        primary_button(
            manual_card,
            text="Aplicar valores manuais",
            command=self._apply_manual_values,
            row=3,
        )

        ctk.CTkLabel(
            manual_card,
            text="Escolha qual aclive utilizar nos cálculos seguintes:",
            anchor="w",
        ).grid(row=4, column=0, sticky="ew", padx=20, pady=(18, 6))

        radio_frame = ctk.CTkFrame(manual_card, fg_color="transparent")
        radio_frame.grid(row=5, column=0, sticky="w", padx=20, pady=(0, 12))

        slope_mode_var = self.app.field_vars["slope_mode"]

        self._radio_buttons["manual"] = ctk.CTkRadioButton(
            radio_frame,
            text="Manual",
            value="manual",
            variable=slope_mode_var,
            command=lambda: self._on_slope_mode_change("manual"),
        )
        self._radio_buttons["manual"].grid(row=0, column=0, padx=(0, 12), pady=4)

        self._radio_buttons["medio"] = ctk.CTkRadioButton(
            radio_frame,
            text=f"Operacional (P{DEFAULT_OPERATIONAL_PERCENTILE})",
            value="medio",
            variable=slope_mode_var,
            command=lambda: self._on_slope_mode_change("medio"),
        )
        self._radio_buttons["medio"].grid(row=0, column=1, padx=(0, 12), pady=4)

        self._radio_buttons["maximo"] = ctk.CTkRadioButton(
            radio_frame,
            text="Severo (P95)",
            value="maximo",
            variable=slope_mode_var,
            command=lambda: self._on_slope_mode_change("maximo"),
        )
        self._radio_buttons["maximo"].grid(row=0, column=2, padx=(0, 12), pady=4)

        mapa_card.update_idletasks()
        manual_card.update_idletasks()

        self.app.field_vars["área_hectares"].trace_add("write", lambda *_: self._refresh_info_labels())
        self.app.field_vars["slope_avg_deg"].trace_add("write", lambda *_: self._refresh_info_labels())
        self.app.field_vars["slope_max_deg"].trace_add("write", lambda *_: self._refresh_info_labels())
        self.app.field_vars["slope_selected_deg"].trace_add("write", lambda *_: self._refresh_info_labels())
        slope_mode_var.trace_add("write", lambda *_: self._on_mode_var_update())

        self._update_slope_radios()
        self._refresh_info_labels()

    def _render_canvas(self) -> None:
        if not self._canvas:
            return
        self._canvas.delete("all")
        if not self._projected_polygon:
            self._canvas.create_text(
                self._canvas_width / 2,
                self._canvas_height / 2,
                text="Nenhum talhao carregado.",
                fill="#9aa0ad",
                font=("Calibri", 16, "italic"),
            )
            return

        coords = self._scale_to_canvas(self._projected_polygon, self._canvas_width, self._canvas_height)
        if not coords:
            return

        self._canvas.create_polygon(
            coords,
            fill="#b2c8ff",
            outline="#3450a1",
            width=2,
        )

    @staticmethod
    def _scale_to_canvas(
        points: Sequence[tuple[float, float]],
        width: int,
        height: int,
        padding: int = 24,
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

        coords: list[float] = []
        for x, y in points:
            cx = padding + (x - min_x) * scale
            cy = height - (padding + (y - min_y) * scale)
            coords.extend((cx, cy))
        return coords

    def _refresh_info_labels(self) -> None:
        área_text = self.app.field_vars["área_hectares"].get()
        operacional_text = self.app.field_vars["slope_avg_deg"].get()
        severo_text = self.app.field_vars["slope_max_deg"].get()
        selected_text = self.app.field_vars["slope_selected_deg"].get()
        mode = self.app.field_vars["slope_mode"].get()
        median_text = f"{self._slope_median_deg:.2f}" if self._slope_median_deg is not None else "--"

        self._área_display_var.set(f"Área (ha): {área_text or '--'}")
        self._slope_media_display_var.set(f"Aclive médio (P50 graus): {median_text}")
        self._slope_operacional_display_var.set(
            f"Aclive operacional (P{self._operational_percentil} graus): {operacional_text or '--'}"
        )
        self._slope_severo_display_var.set(f"Aclive severo (P95 graus): {severo_text or '--'}")
        if "medio" in self._radio_buttons:
            self._radio_buttons["medio"].configure(text=f"Operacional (P{self._operational_percentil})")

        if selected_text:
            mode_label = {
                "manual": "Manual",
                "medio": f"Operacional (P{self._operational_percentil})",
                "maximo": "Severo (P95)",
            }.get(mode, mode)
            self._slope_selected_display_var.set(f"Aclive em uso ({mode_label}): {selected_text} graus")
        else:
            self._slope_selected_display_var.set("Aclive em uso (graus): --")

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
            área_m2 = _polygon_área_m2(projected)
            área_ha = área_m2 / 10_000.0
            median_deg, operational_deg, severe_deg, operational_percentil = _slopes_from_polygon(
                projected, polygon, projection
            )
            slopes_available = max(operational_deg, severe_deg) > 0.05

            self._projected_polygon = projected
            self._projection_params = projection
            self.app.field_vars["kmz_path"].set(path.name)
            self.app.set_field_área(área_ha, source="mapa")
            self.app.manual_área_var.set(f"{área_ha:.2f}")
            if slopes_available:
                self._slope_median_deg = median_deg
                self._operational_percentil = operational_percentil
                self.app.set_map_slopes(operational_deg, severe_deg)
                self.app.preset_manual_slope(operational_deg)
            else:
                self._slope_median_deg = None
                self._operational_percentil = DEFAULT_OPERATIONAL_PERCENTILE
                self.app.clear_map_slopes()
                self.app.clear_manual_slope()

            self._render_canvas()
            self._refresh_info_labels()
            self._file_var.set(f"{path.name} - {placemark_name}")

            if slopes_available and self.app.apply_slope_mode("medio"):
                self.app.field_vars["slope_mode"].set("medio")
                self._status_label.configure(text_color="#3f7e2d")
                self._status_var.set(
                    f"Talhao carregado. Aclive operacional (P{self._operational_percentil}) aplicado: "
                    f"{operational_deg:.2f} graus."
                )
            else:
                self.app.field_vars["slope_mode"].set("manual")
                self.app.field_vars["slope_selected_deg"].set("")
                self._status_label.configure(text_color="#b36b00")
                self._status_var.set(
                    "Não foi possível calcular o aclive automaticamente. Informe o valor manualmente."
                )

            self._update_slope_radios()

        except Exception as exc:
            self._projected_polygon = []
            self._projection_params = None
            self._slope_median_deg = None
            self._operational_percentil = DEFAULT_OPERATIONAL_PERCENTILE
            self._render_canvas()
            self.app.field_vars["kmz_path"].set("")
            self._status_label.configure(text_color="#b00020")
            self._status_var.set(f"Falha ao carregar talhao: {exc}")
            self._file_var.set("")
            self.app.clear_map_slopes()
            self.app.clear_manual_slope()
            self._update_slope_radios()
            self._refresh_info_labels()

    def _apply_manual_values(self) -> None:
        área_txt = (self.app.manual_área_var.get() or "").strip().replace(",", ".")
        slope_txt = (self.app.manual_slope_deg_var.get() or "").strip().replace(",", ".")

        try:
            if not área_txt:
                raise ValueError("Informe a área em hectares.")
            if not slope_txt:
                raise ValueError("Informe o aclive manual em graus.")

            área = float(área_txt)
            slope_deg = float(slope_txt)
            if área <= 0:
                raise ValueError("A área deve ser maior que zero.")
            if not (0 <= slope_deg < 90):
                raise ValueError("O aclive deve estar entre 0 e 90 graus.")

            self.app.set_manual_área(área)
            self.app.set_manual_slope(slope_deg)

            self._status_label.configure(text_color="#3f7e2d")
            self._status_var.set("Valores manuais aplicados ao cálculo.")
            self._refresh_info_labels()
            self._update_slope_radios()

        except ValueError as exc:
            self._status_label.configure(text_color="#b00020")
            self._status_var.set(str(exc))

    def _on_slope_mode_change(self, mode: str) -> None:
        if not self.app.apply_slope_mode(mode):
            self.app.field_vars["slope_mode"].set(self._last_slope_mode)
            self._status_label.configure(text_color="#b00020")
            self._status_var.set("Seleção indisponivel: informe o valor correspondente.")
            return

        self._last_slope_mode = mode
        self._status_label.configure(text_color="#3d4e8a")
        self._status_var.set("Aclive atualizado para uso nas proximas abas.")
        self._refresh_info_labels()





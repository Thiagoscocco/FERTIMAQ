"""Tab responsible for loading and describing the target field (talhão)."""

from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path
from typing import List, Sequence, Tuple
import xml.etree.ElementTree as ET

import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request

import customtkinter as ctk
from tkinter import filedialog

from ferticalc_ui_blueprint import create_card, primary_button, section_title

from .base import FertiMaqTab, tab_registry

EARTH_RADIUS_M = 6_371_000.0
OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"


def _load_polygon_from_kmz(path: Path) -> Tuple[List[Tuple[float, float, float]], str]:
    with zipfile.ZipFile(path) as kmz:
        kml_name = next((name for name in kmz.namelist() if name.lower().endswith(".kml")), None)
        if not kml_name:
            raise ValueError("Arquivo KMZ não possui nenhum KML interno.")
        xml_data = kmz.read(kml_name)

    root = ET.fromstring(xml_data)
    namespaces = {"kml": "http://www.opengis.net/kml/2.2"}

    placemark = root.find(".//kml:Placemark", namespaces) or root.find(".//{*}Placemark")
    if placemark is None:
        raise ValueError("Nenhum Placemark encontrado no KML.")

    name_elem = placemark.find("kml:name", namespaces) or placemark.find("{*}name")
    placemark_name = name_elem.text.strip() if name_elem is not None and name_elem.text else path.stem

    coords_elem = (
        placemark.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", namespaces)
        or placemark.find(".//{*}Polygon/{*}outerBoundaryIs/{*}LinearRing/{*}coordinates")
    )
    if coords_elem is None or not coords_elem.text:
        raise ValueError("Nenhum polígono com coordenadas foi encontrado no KML.")

    raw_chunks = [chunk for chunk in coords_elem.text.replace("\n", " ").split() if chunk.strip()]
    points: List[Tuple[float, float, float]] = []
    for chunk in raw_chunks:
        parts = chunk.split(",")
        if len(parts) < 2:
            continue
        lon = float(parts[0])
        lat = float(parts[1])
        alt = float(parts[2]) if len(parts) > 2 and parts[2] else 0.0
        points.append((lon, lat, alt))

    if len(points) < 3:
        raise ValueError("O polígono do talhão possui pontos insuficientes.")
    if points[0] == points[-1]:
        points = points[:-1]

    points = _enrich_elevation(points)
    return points, placemark_name


def _enrich_elevation(points: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
    if not points:
        return points

    unique_alts = {round(pt[2], 3) for pt in points}
    if len(unique_alts) > 1:
        return points

    try:
        enriched = _fetch_elevations(points)
    except Exception:
        return points

    if not enriched:
        return points

    return enriched


def _fetch_elevations(points: List[Tuple[float, float, float]], chunk_size: int = 50) -> List[Tuple[float, float, float]]:
    results: List[Tuple[float, float, float]] = []
    for start in range(0, len(points), chunk_size):
        subset = points[start : start + chunk_size]
        query = "|".join(f"{lat:.6f},{lon:.6f}" for lon, lat, _ in subset)
        url = f"{OPEN_ELEVATION_URL}?locations={urllib.parse.quote(query, safe=',|')}"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return []

        api_results = data.get("results", [])
        if len(api_results) != len(subset):
            return []

        for original, item in zip(subset, api_results):
            elevation = item.get("elevation")
            if elevation is None:
                results.append(original)
            else:
                results.append((original[0], original[1], float(elevation)))

    return results


def _project_points(points: Sequence[Tuple[float, float, float]]) -> List[Tuple[float, float]]:
    lats_rad = [math.radians(lat) for _, lat, _ in points]
    lons_rad = [math.radians(lon) for lon, _, _ in points]
    lat0 = sum(lats_rad) / len(lats_rad)
    lon0 = sum(lons_rad) / len(lons_rad)
    cos_lat0 = math.cos(lat0) or 1.0

    projected: List[Tuple[float, float]] = []
    for lon, lat, _ in points:
        lon_r = math.radians(lon)
        lat_r = math.radians(lat)
        x = EARTH_RADIUS_M * (lon_r - lon0) * cos_lat0
        y = EARTH_RADIUS_M * (lat_r - lat0)
        projected.append((x, y))
    return projected


def _polygon_area_m2(points: Sequence[Tuple[float, float]]) -> float:
    if not points:
        return 0.0
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += (x1 * y2) - (x2 * y1)
    return abs(area) * 0.5


def _solve_3x3(a11, a12, a13, a21, a22, a23, a31, a32, a33, b1, b2, b3) -> Tuple[float, float, float] | None:
    det = (
        a11 * (a22 * a33 - a23 * a32)
        - a12 * (a21 * a33 - a23 * a31)
        + a13 * (a21 * a32 - a22 * a31)
    )
    if abs(det) < 1e-9:
        return None

    det_x = (
        b1 * (a22 * a33 - a23 * a32)
        - a12 * (b2 * a33 - a23 * b3)
        + a13 * (b2 * a32 - a22 * b3)
    )
    det_y = (
        a11 * (b2 * a33 - a23 * b3)
        - b1 * (a21 * a33 - a23 * a31)
        + a13 * (a21 * b3 - b2 * a31)
    )
    det_z = (
        a11 * (a22 * b3 - b2 * a32)
        - a12 * (a21 * b3 - b2 * a31)
        + b1 * (a21 * a32 - a22 * a31)
    )

    return det_x / det, det_y / det, det_z / det


def _average_slope_degree(points_xy: Sequence[Tuple[float, float]], points_xyz: Sequence[Tuple[float, float, float]]) -> float:
    n = min(len(points_xy), len(points_xyz))
    if n < 3:
        return 0.0

    sum_x = sum_y = sum_z = 0.0
    sum_xx = sum_yy = sum_xy = sum_xz = sum_yz = 0.0

    for (x, y), (_, _, z) in zip(points_xy[:n], points_xyz[:n]):
        sum_x += x
        sum_y += y
        sum_z += z
        sum_xx += x * x
        sum_yy += y * y
        sum_xy += x * y
        sum_xz += x * z
        sum_yz += y * z

    solution = _solve_3x3(
        sum_xx,
        sum_xy,
        sum_x,
        sum_xy,
        sum_yy,
        sum_y,
        sum_x,
        sum_y,
        n,
        sum_xz,
        sum_yz,
        sum_z,
    )
    if solution is None:
        return 0.0
    a, b, _ = solution
    gradient = math.sqrt(a * a + b * b)
    return math.degrees(math.atan(gradient))


def _max_slope_degree(points_xy: Sequence[Tuple[float, float]], points_xyz: Sequence[Tuple[float, float, float]]) -> float:
    n = min(len(points_xy), len(points_xyz))
    if n < 2:
        return 0.0

    max_slope = 0.0
    for i in range(n):
        x1, y1 = points_xy[i]
        z1 = points_xyz[i][2]
        for j in range(i + 1, n):
            x2, y2 = points_xy[j]
            z2 = points_xyz[j][2]
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist <= 0.0:
                continue
            slope = math.degrees(math.atan(abs(z2 - z1) / dist))
            if slope > max_slope:
                max_slope = slope
    return max_slope


def _slopes_from_polygon(
    projected: Sequence[Tuple[float, float]],
    original: Sequence[Tuple[float, float, float]],
) -> Tuple[float, float]:
    average = _average_slope_degree(projected, original)
    maximum = _max_slope_degree(projected, original)
    return average, maximum


def _scale_to_canvas(points: Sequence[Tuple[float, float]], width: int, height: int, padding: int = 24) -> List[float]:
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

    coords: List[float] = []
    for x, y in points:
        cx = padding + (x - min_x) * scale
        cy = height - (padding + (y - min_y) * scale)
        coords.extend((cx, cy))
    return coords


@tab_registry.register
class EscolhaTalhaoTab(FertiMaqTab):
    tab_id = "escolha_talhao"
    title = "ESCOLHA DO TALHÃO"

    def __init__(self, app) -> None:
        super().__init__(app)
        self._canvas_width = 680
        self._canvas_height = 420

        self._projected_polygon: List[Tuple[float, float]] = []
        self._status_var = ctk.StringVar(value="Nenhum talhão carregado.")
        self._file_var = ctk.StringVar(value="")

        self._area_display_var = ctk.StringVar(value="Área (ha): --")
        self._slope_avg_display_var = ctk.StringVar(value="Aclive médio (º): --")
        self._slope_max_display_var = ctk.StringVar(value="Aclive máximo (º): --")
        self._slope_selected_display_var = ctk.StringVar(value="Aclive em uso (º): --")

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
                "O talhão será exibido abaixo e os valores de área e aclive serão "
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

        info_frame = ctk.CTkFrame(mapa_card, fg_color="#f2f5ff", corner_radius=14)
        info_frame.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 16))
        info_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(info_frame, textvariable=self._area_display_var, anchor="w").grid(
            row=0, column=0, sticky="ew", padx=18, pady=(12, 4)
        )
        ctk.CTkLabel(info_frame, textvariable=self._slope_avg_display_var, anchor="w").grid(
            row=1, column=0, sticky="ew", padx=18, pady=4
        )
        ctk.CTkLabel(info_frame, textvariable=self._slope_max_display_var, anchor="w").grid(
            row=2, column=0, sticky="ew", padx=18, pady=4
        )
        ctk.CTkLabel(
            info_frame,
            textvariable=self._slope_selected_display_var,
            anchor="w",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=3, column=0, sticky="ew", padx=18, pady=(4, 12))

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

        section_title(manual_card, "Dados manuais e seleção de aclive")

        ctk.CTkLabel(
            manual_card,
            text=(
                "Caso não exista um arquivo do talhão, informe manualmente a área (ha) "
                "e o aclive em graus. Você também pode optar por utilizar o aclive médio "
                "ou máximo calculado a partir do mapa."
            ),
            justify="left",
            wraplength=680,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 12))

        input_frame = ctk.CTkFrame(manual_card, fg_color="transparent")
        input_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 12))
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_frame, text="Área (ha)", anchor="w").grid(row=0, column=0, sticky="w", pady=6)
        ctk.CTkEntry(input_frame, textvariable=self.app.manual_area_var, placeholder_text="ex: 12.5").grid(
            row=0, column=1, sticky="ew", padx=(10, 0), pady=6
        )

        ctk.CTkLabel(input_frame, text="Aclive manual (º)", anchor="w").grid(row=1, column=0, sticky="w", pady=6)
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

        manual_radio = ctk.CTkRadioButton(
            radio_frame,
            text="Manual",
            value="manual",
            variable=slope_mode_var,
            command=lambda: self._on_slope_mode_change("manual"),
        )
        manual_radio.grid(row=0, column=0, padx=(0, 12), pady=4)
        self._radio_buttons["manual"] = manual_radio

        medio_radio = ctk.CTkRadioButton(
            radio_frame,
            text="Médio do mapa",
            value="medio",
            variable=slope_mode_var,
            command=lambda: self._on_slope_mode_change("medio"),
        )
        medio_radio.grid(row=0, column=1, padx=(0, 12), pady=4)
        self._radio_buttons["medio"] = medio_radio

        maximo_radio = ctk.CTkRadioButton(
            radio_frame,
            text="Máximo do mapa",
            value="maximo",
            variable=slope_mode_var,
            command=lambda: self._on_slope_mode_change("maximo"),
        )
        maximo_radio.grid(row=0, column=2, padx=(0, 12), pady=4)
        self._radio_buttons["maximo"] = maximo_radio

        mapa_card.update_idletasks()
        manual_card.update_idletasks()

        self.app.field_vars["area_hectares"].trace_add("write", lambda *_: self._refresh_info_labels())
        self.app.field_vars["slope_avg_deg"].trace_add("write", lambda *_: self._on_slopes_changed())
        self.app.field_vars["slope_max_deg"].trace_add("write", lambda *_: self._on_slopes_changed())
        self.app.field_vars["slope_selected_deg"].trace_add("write", lambda *_: self._refresh_info_labels())
        slope_mode_var.trace_add("write", lambda *_: self._on_mode_var_update())

        self._update_slope_radios()
        self._refresh_info_labels()

    # ------------------------------------------------------------------ #
    # Canvas and info updates
    # ------------------------------------------------------------------ #

    def _render_canvas(self) -> None:
        if not self._canvas:
            return
        self._canvas.delete("all")
        if not self._projected_polygon:
            self._canvas.create_text(
                self._canvas_width / 2,
                self._canvas_height / 2,
                text="Nenhum talhão carregado.",
                fill="#9aa0ad",
                font=("Calibri", 16, "italic"),
            )
            return

        coords = _scale_to_canvas(self._projected_polygon, self._canvas_width, self._canvas_height)
        if not coords:
            return

        self._canvas.create_polygon(
            coords,
            fill="#b2c8ff",
            outline="#3450a1",
            width=2,
        )

    def _refresh_info_labels(self) -> None:
        area_text = self.app.field_vars["area_hectares"].get()
        avg_text = self.app.field_vars["slope_avg_deg"].get()
        max_text = self.app.field_vars["slope_max_deg"].get()
        selected_text = self.app.field_vars["slope_selected_deg"].get()
        mode = self.app.field_vars["slope_mode"].get()

        self._area_display_var.set(f"Área (ha): {area_text or '--'}")
        self._slope_avg_display_var.set(f"Aclive médio (º): {avg_text or '--'}")
        self._slope_max_display_var.set(f"Aclive máximo (º): {max_text or '--'}")

        if selected_text:
            mode_label = {
                "manual": "Manual",
                "medio": "Médio do mapa",
                "maximo": "Máximo do mapa",
            }.get(mode, mode)
            self._slope_selected_display_var.set(f"Aclive em uso ({mode_label}): {selected_text}º")
        else:
            self._slope_selected_display_var.set("Aclive em uso (º): --")

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
        current = self.app.field_vars["slope_mode"].get()
        self._last_slope_mode = current
        self._refresh_info_labels()

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def _choose_file(self) -> None:
        filename = filedialog.askopenfilename(
            title="Selecione o arquivo KMZ do talhão",
            filetypes=[("Arquivo KMZ", "*.kmz"), ("Todos os arquivos", "*.*")],
        )
        if not filename:
            return
        self._load_kmz(Path(filename))

    def _load_kmz(self, path: Path) -> None:
        try:
            polygon, placemark_name = _load_polygon_from_kmz(path)
            projected = _project_points(polygon)
            altitudes = [pt[2] for pt in polygon]
            alt_range = max(altitudes) - min(altitudes) if altitudes else 0.0
            area_m2 = _polygon_area_m2(projected)
            area_ha = area_m2 / 10_000.0
            avg_deg, max_deg = _slopes_from_polygon(projected, polygon)
            slopes_available = max(avg_deg, max_deg) > 0.01 and alt_range > 0.5

            self._projected_polygon = projected
            self.app.field_vars["kmz_path"].set(path.name)
            self.app.set_field_area(area_ha, source="mapa")
            self.app.manual_area_var.set(f"{area_ha:.2f}")
            if slopes_available:
                self.app.set_map_slopes(avg_deg, max_deg)
            else:
                self.app.clear_map_slopes()
            if slopes_available:
                self.app.manual_slope_deg_var.set(f"{avg_deg:.2f}")
            else:
                self.app.manual_slope_deg_var.set("")

            self._render_canvas()
            self._refresh_info_labels()
            self._file_var.set(f"{path.name} - {placemark_name}")

            if slopes_available and self.app.apply_slope_mode("medio"):
                self.app.field_vars["slope_mode"].set("medio")
                self._status_label.configure(text_color="#3f7e2d")
                self._status_var.set("Talhão carregado com sucesso. Aclive médio aplicado.")
            else:
                self.app.field_vars["slope_mode"].set("manual")
                self.app.field_vars["slope_selected_deg"].set("")
                self._status_label.configure(text_color="#b36b00")
                motivo = (
                    "Arquivo KMZ não possui dados de altitude para o polígono."
                    if alt_range <= 0.5
                    else "Diferença de altitude insuficiente para calcular o aclive."
                )
                self._status_var.set(f"{motivo} Informe o aclive manualmente.")
                self.app.field_vars["slope_mode"].set("manual")

            self._update_slope_radios()

        except Exception as exc:
            self._projected_polygon = []
            self._render_canvas()
            self.app.field_vars["kmz_path"].set("")
            self._status_label.configure(text_color="#b00020")
            self._status_var.set(f"Falha ao carregar talhão: {exc}")
            self._file_var.set("")
            self.app.clear_map_slopes()
            self._update_slope_radios()
            self._refresh_info_labels()

    def _apply_manual_values(self) -> None:
        area_txt = (self.app.manual_area_var.get() or "").strip().replace(",", ".")
        slope_txt = (self.app.manual_slope_deg_var.get() or "").strip().replace(",", ".")

        try:
            if not area_txt:
                raise ValueError("Informe a área em hectares.")
            if not slope_txt:
                raise ValueError("Informe o aclive manual em graus.")

            area = float(area_txt)
            slope_deg = float(slope_txt)
            if area <= 0:
                raise ValueError("A área deve ser maior que zero.")
            if not (0 <= slope_deg < 90):
                raise ValueError("O aclive deve estar entre 0º e 90º.")

            self.app.set_manual_area(area)
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
            self._status_var.set("Seleção indisponível: informe o valor correspondente.")
            return

        self._last_slope_mode = mode
        self._status_label.configure(text_color="#3d4e8a")
        self._status_var.set("Aclive atualizado para uso nas próximas abas.")
        self._refresh_info_labels()

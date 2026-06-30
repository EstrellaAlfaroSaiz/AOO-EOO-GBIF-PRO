# -*- coding: utf-8 -*-
"""Dialog and UI for the AOO/EOO GBIF plugin."""

from __future__ import annotations

from datetime import datetime
import os
import re

from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qgis.PyQt.QtGui import QDesktopServices
from qgis.gui import QgsMapLayerComboBox
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
    QgsMapLayerProxyModel,
    Qgis,
    QgsPointXY,
    QgsVectorLayer,
    QgsFeature,
    QgsField,
)
try:
    from qgis.PyQt.QtCore import QVariant
except ImportError:  # pragma: no cover
    class QVariant:
        String = str
        Int = int
        Double = float
        Bool = bool


def _qt_item_user_checkable():
    try:
        return Qt.ItemIsUserCheckable
    except AttributeError:
        return Qt.ItemFlag.ItemIsUserCheckable


def _qt_checked():
    try:
        return Qt.Checked
    except AttributeError:
        return Qt.CheckState.Checked


def _qt_unchecked():
    try:
        return Qt.Unchecked
    except AttributeError:
        return Qt.CheckState.Unchecked


def _qt_user_role():
    try:
        return Qt.UserRole
    except AttributeError:
        return Qt.ItemDataRole.UserRole


def _qt_item_is_enabled():
    try:
        return Qt.ItemIsEnabled
    except AttributeError:
        return Qt.ItemFlag.ItemIsEnabled


def _qt_item_is_selectable():
    try:
        return Qt.ItemIsSelectable
    except AttributeError:
        return Qt.ItemFlag.ItemIsSelectable


def _dialog_accepted():
    try:
        return QDialog.Accepted
    except AttributeError:
        return QDialog.DialogCode.Accepted


def _dialog_exec(dialog):
    if hasattr(dialog, "exec"):
        return dialog.exec()
    return dialog.exec_()


def _button_box_ok():
    try:
        return QDialogButtonBox.Ok
    except AttributeError:
        return QDialogButtonBox.StandardButton.Ok


def _button_box_cancel():
    try:
        return QDialogButtonBox.Cancel
    except AttributeError:
        return QDialogButtonBox.StandardButton.Cancel




def _set_form_expanding_fields(form):
    """Set QFormLayout fields to grow in Qt5/Qt6-compatible way."""
    try:
        policy = QFormLayout.ExpandingFieldsGrow
    except AttributeError:
        try:
            policy = QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        except AttributeError:
            return
    form.setFieldGrowthPolicy(policy)



def _messagebox_yes():
    try:
        return QMessageBox.Yes
    except AttributeError:
        return QMessageBox.StandardButton.Yes


def _messagebox_no():
    try:
        return QMessageBox.No
    except AttributeError:
        return QMessageBox.StandardButton.No

def _line_edit_password():
    try:
        return QLineEdit.Password
    except AttributeError:
        return QLineEdit.EchoMode.Password


def _point_layer_filter():
    """QGIS 3.34+ and QGIS 4 moved layer filter enums to Qgis.LayerFilter."""
    try:
        return Qgis.LayerFilter.PointLayer
    except AttributeError:  # QGIS 3.28-3.32
        return QgsMapLayerProxyModel.PointLayer

def _layer_is_usable(layer) -> bool:
    """Return False when a QGIS layer wrapper points to an object already deleted by QGIS."""
    if layer is None:
        return False
    try:
        return layer.isValid()
    except RuntimeError:
        return False


def _layer_name(layer, fallback: str = "") -> str:
    try:
        return layer.name() if layer is not None else fallback
    except RuntimeError:
        return fallback


from .gbif_client import (
    GbifError,
    match_species,
    occurrence_facets,
    search_occurrences,
    slim_record,
    request_occurrence_download_by_gbif_ids,
    get_occurrence_download,
)
from .manual_point_tool import ManualPointTool, ManualRectangleTool
from .processing_logic import (
    add_manual_feature,
    create_manual_layer,
    create_occurrence_layer,
    import_manual_csv,
    run_aoo_eoo,
    create_report_layers,
    create_point_distribution_layer,
    write_point_distribution_csv,
    create_point_distribution_shapefile_layer,
    write_point_distribution_shapefile,
    create_iucn_polygon_field_guide_layer,
    create_gbif_derived_dataset_result_layer,
    create_gbif_occurrence_download_result_layer,
    coordinatecleaner_filter_records,
)


BASIS_OPTIONS = [
    ("HUMAN_OBSERVATION", True, "Integrar: observación humana; revisar identidad y precisión espacial."),
    ("PRESERVED_SPECIMEN", True, "Integrar con control: pliegos o especímenes; revisar fecha y georreferenciación."),
    ("MACHINE_OBSERVATION", False, "Revisar: cámaras, sensores o identificación automática. No se incluye por defecto."),
    ("MATERIAL_SAMPLE", False, "Revisar: muestra física o ambiental."),
    ("MATERIAL_CITATION", False, "Revisar: cita de material; posible duplicado o baja precisión."),
    ("OCCURRENCE", False, "Revisar: categoría genérica."),
    ("OBSERVATION", False, "Revisar: categoría genérica."),
    ("LIVING_SPECIMEN", False, "Excluir por defecto: puede ser ex situ o cultivado."),
    ("FOSSIL_SPECIMEN", False, "Excluir por defecto para distribución actual."),
    ("UNKNOWN", False, "Excluir/Revisar: tipo de registro desconocido."),
]

ESTABLISHMENT_OPTIONS = [
    ("NATIVE", True, "Integrar: población nativa."),
    ("NATIVE_REINTRODUCED", True, "Integrar/Revisar: reintroducción dentro del área nativa."),
    ("INTRODUCED", False, "Excluir por defecto en evaluación de distribución nativa."),
    ("INTRODUCED_ASSISTED_COLONISATION", False, "Excluir/Revisar según objetivo."),
    ("VAGRANT", False, "Excluir: no representa ocupación estable."),
    ("UNCERTAIN", False, "Revisar: origen incierto."),
]


class ManualFeatureDialog(QDialog):
    """Small form for one user-added occurrence."""

    def __init__(self, parent=None, default_name: str = "", show_coordinates: bool = False):
        super().__init__(parent)
        self.show_coordinates = show_coordinates
        title = "Añadir un punto por coordenadas" if show_coordinates else "Añadir un punto propio para AOO/EOO"
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        _set_form_expanding_fields(form)

        self.scientific_name = QLineEdit(default_name)
        self.event_date = QLineEdit(datetime.now().strftime("%Y-%m-%d"))

        self.latitude = None
        self.longitude = None
        if show_coordinates:
            coord_note = QLabel("Introduce coordenadas decimales en WGS84 / EPSG:4326.")
            coord_note.setWordWrap(True)
            layout.addWidget(coord_note)
            self.latitude = QDoubleSpinBox()
            self.latitude.setRange(-90.0, 90.0)
            self.latitude.setDecimals(8)
            self.latitude.setSingleStep(0.0001)
            self.latitude.setValue(0.0)
            self.longitude = QDoubleSpinBox()
            self.longitude.setRange(-180.0, 180.0)
            self.longitude.setDecimals(8)
            self.longitude.setSingleStep(0.0001)
            self.longitude.setValue(0.0)

        self.data_origin_text = QLineEdit()
        self.data_origin_text.setPlaceholderText("Ej.: trabajo de campo, herbario, bibliografía, informe")
        self.data_curator = QLineEdit()
        self.evidence = QComboBox()
        self.evidence.addItems(["pliego/testigo", "observación de campo", "fotografía", "informe", "bibliografía", "otro"])
        self.identifier = QLineEdit()
        self.uncertainty = QDoubleSpinBox()
        self.uncertainty.setRange(0, 1_000_000)
        self.uncertainty.setDecimals(2)
        self.uncertainty.setValue(4)
        self.uncertainty.setSuffix(" m")
        self.review = QComboBox()
        self.review.addItems(["Aceptado", "Revisar antes de usar", "Excluido"])
        self.include = QCheckBox("Usar este punto en el cálculo")
        self.include.setChecked(True)
        self.notes = QLineEdit()

        form.addRow("Taxón", self.scientific_name)
        if show_coordinates:
            form.addRow("Latitud decimal*", self.latitude)
            form.addRow("Longitud decimal*", self.longitude)
        form.addRow("Fecha", self.event_date)
        form.addRow("Origen del dato", self.data_origin_text)
        form.addRow("Curador del dato", self.data_curator)
        form.addRow("Evidencia", self.evidence)
        form.addRow("Identificador (número de pliego, otro ID)", self.identifier)
        form.addRow("Incertidumbre", self.uncertainty)
        form.addRow("Decisión sobre este punto", self.review)
        form.addRow("Cálculo", self.include)
        form.addRow("Notas", self.notes)
        layout.addLayout(form)

        buttons = QDialogButtonBox(_button_box_ok() | _button_box_cancel())
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict:
        review_map = {
            "Revisar antes de usar": "revisar",
            "Aceptado": "aceptado",
            "Excluido": "excluido",
        }
        data_citation = ""
        data_origin = self.data_origin_text.text().strip() or "manual"
        values = {
            "scientificName": self.scientific_name.text().strip(),
            "eventDate": self.event_date.text().strip(),
            "data_citation": data_citation,
            "observer": data_citation,  # compatibility with older temporary layers
            "source_ref": data_citation,
            "data_origin": data_origin,
            "data_curator": self.data_curator.text().strip(),
            "evidence": self.evidence.currentText(),
            "identifier": self.identifier.text().strip(),
            "catalog_no": self.identifier.text().strip(),
            "coordUncM": self.uncertainty.value(),
            "review": review_map.get(self.review.currentText(), "revisar"),
            "include": self.include.isChecked(),
            "notes": self.notes.text().strip(),
        }
        if self.show_coordinates:
            values["decimalLatitude"] = self.latitude.value()
            values["decimalLongitude"] = self.longitude.value()
        return values



class PointDistributionSettingsDialog(QDialog):
    """Form with shared fields for the IUCN Point Distribution CSV."""

    def __init__(self, parent=None, default_name: str = "", default_subspecies: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Datos para CSV Point Distribution")
        self.resize(720, 620)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Estos datos se aplicarán a las filas del CSV Point Distribution. "
            "Las coordenadas dec_lat y dec_long se rellenan automáticamente con los puntos usados en el cálculo. "
            "El archivo seguirá exactamente el esquema de columnas que has facilitado."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        this_year = datetime.now().year
        self.sci_name = QLineEdit(default_name)

        self.presence = QComboBox()
        self.presence.addItem("1 - Extant / presente actualmente", 1)
        self.presence.addItem("3 - Possibly Extant / posible presencia", 3)
        self.presence.addItem("4 - Possibly Extinct / posiblemente extinto localmente", 4)
        self.presence.addItem("5 - Extinct / extinto localmente", 5)
        self.presence.addItem("6 - Presence Uncertain / presencia incierta", 6)
        self.presence.addItem("7 - Extant & Introduced / presente e introducido", 7)

        self.origin = QComboBox()
        self.origin.addItem("1 - Native / nativo", 1)
        self.origin.addItem("2 - Reintroduced / reintroducido", 2)
        self.origin.addItem("3 - Introduced / introducido", 3)
        self.origin.addItem("4 - Vagrant / accidental", 4)
        self.origin.addItem("5 - Origin Uncertain / origen incierto", 5)
        self.origin.addItem("6 - Assisted Colonisation / colonización asistida", 6)
        self.origin.addItem("7 - Origin uncertain or mixed / origen incierto o mixto", 7)

        self.seasonal = QComboBox()
        self.seasonal.addItem("1 - Resident / residente", 1)
        self.seasonal.addItem("2 - Breeding Season / época reproductora", 2)
        self.seasonal.addItem("3 - Non-breeding Season / época no reproductora", 3)
        self.seasonal.addItem("4 - Passage / paso", 4)
        self.seasonal.addItem("5 - Seasonal Occurrence Uncertain / estacionalidad incierta", 5)

        self.compiler = QLineEdit()
        self.yrcompiled = QSpinBox()
        self.yrcompiled.setRange(1900, this_year + 1)
        self.yrcompiled.setValue(this_year)
        self.citation = QLineEdit()
        self.spatialref = QLineEdit("WGS84")
        self.subspecies = QLineEdit(default_subspecies)
        self.subpop = QLineEdit()

        self.data_sens = QComboBox()
        self.data_sens.addItem("0 - No sensible", 0)
        self.data_sens.addItem("1 - Sensible", 1)

        self.sens_comm = QLineEdit()
        self.source = QLineEdit("GBIF.org y datos propios revisados")
        self.basisofrec = QLineEdit()
        self.dist_comm = QLineEdit()
        self.island = QLineEdit()
        self.tax_comm = QLineEdit()

        form.addRow("sci_name *", self.sci_name)
        form.addRow("presence *", self.presence)
        form.addRow("origin *", self.origin)
        form.addRow("seasonal", self.seasonal)
        form.addRow("compiler *", self.compiler)
        form.addRow("yrcompiled *", self.yrcompiled)
        form.addRow("citation *", self.citation)
        form.addRow("spatialref *", self.spatialref)
        form.addRow("subspecies", self.subspecies)
        form.addRow("subpop", self.subpop)
        form.addRow("data_sens", self.data_sens)
        form.addRow("sens_comm", self.sens_comm)
        form.addRow("source", self.source)
        form.addRow("basisofrec", self.basisofrec)
        form.addRow("dist_comm", self.dist_comm)
        form.addRow("island", self.island)
        form.addRow("tax_comm", self.tax_comm)
        layout.addLayout(form)

        note = QLabel(
            "* Campos obligatorios o básicos para Point Distribution según la plantilla IUCN. "
            "Si data_sens = 1, rellena sens_comm. "
            "event_year se completa a partir de la fecha/año del registro cuando existe. "
            "catalog_no se rellena con gbifID en registros GBIF."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(_button_box_ok() | _button_box_cancel())
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self):
        missing = []
        if not self.sci_name.text().strip():
            missing.append("sci_name")
        if not self.compiler.text().strip():
            missing.append("compiler")
        if not self.citation.text().strip():
            missing.append("citation")
        if not self.spatialref.text().strip():
            missing.append("spatialref")
        if self.data_sens.currentData() == 1 and not self.sens_comm.text().strip():
            missing.append("sens_comm porque data_sens=1")
        if missing:
            QMessageBox.warning(self, "Point Distribution", "Faltan campos: " + ", ".join(missing))
            return
        self.accept()

    def values(self) -> dict:
        return {
            "sci_name": self.sci_name.text().strip(),
            "presence": self.presence.currentData(),
            "origin": self.origin.currentData(),
            "seasonal": self.seasonal.currentData(),
            "compiler": self.compiler.text().strip(),
            "yrcompiled": self.yrcompiled.value(),
            "citation": self.citation.text().strip(),
            "spatialref": self.spatialref.text().strip() or "WGS84",
            "subspecies": self.subspecies.text().strip(),
            "subpop": self.subpop.text().strip(),
            "data_sens": self.data_sens.currentData(),
            "sens_comm": self.sens_comm.text().strip(),
            "source": self.source.text().strip(),
            "basisofrec": self.basisofrec.text().strip(),
            "dist_comm": self.dist_comm.text().strip(),
            "island": self.island.text().strip(),
            "tax_comm": self.tax_comm.text().strip(),
        }


POINT_DISTRIBUTION_HELP = [
    ("sci_name", "Nombre científico del taxón. Debe coincidir con el nombre usado en la evaluación."),
    ("presence", "Código IUCN de presencia. Habitualmente 1 = presente actualmente."),
    ("origin", "Código IUCN del origen de la presencia. Habitualmente 1 = nativo."),
    ("seasonal", "Código IUCN de estacionalidad. En flora normalmente 1 = residente, salvo que aplique otro caso."),
    ("compiler", "Persona o institución que compila el archivo de puntos."),
    ("yrcompiled", "Año en que se compila o modifica el archivo."),
    ("citation", "Crédito general del archivo de distribución. Debe mantenerse igual en todo el archivo."),
    ("dec_lat", "Latitud decimal del punto. La rellena el plugin a partir de los puntos usados."),
    ("dec_long", "Longitud decimal del punto. La rellena el plugin a partir de los puntos usados."),
    ("spatialref", "Sistema de referencia de las coordenadas. Por defecto WGS84."),
    ("subspecies", "Epíteto infraespecífico si se evalúa una subespecie o variedad."),
    ("subpop", "Nombre de subpoblación si procede. Se mantiene porque está en la plantilla Point Distribution."),
    ("data_sens", "0 = dato no sensible; 1 = dato sensible."),
    ("sens_comm", "Motivo de sensibilidad. Debe rellenarse si data_sens = 1."),
    ("event_year", "Año de observación o colecta, si existe. El plugin lo intenta recuperar del registro."),
    ("source", "Fuente primaria del punto: GBIF, trabajo de campo, herbario, informe, publicación, etc."),
    ("basisofrec", "Naturaleza del registro, por ejemplo PreservedSpecimen o HumanObservation."),
    ("catalog_no", "Identificador del registro. Para GBIF se rellena con gbifID cuando está disponible."),
    ("dist_comm", "Comentario de distribución asociado al punto."),
    ("island", "Isla, si procede."),
    ("tax_comm", "Comentario taxonómico asociado al punto."),
]


class PointDistributionHelpDialog(QDialog):
    """Scrollable help for the exact Point Distribution CSV schema."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guía de campos Point Distribution")
        self.resize(820, 620)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "La tabla Point Distribution se genera con el esquema exacto facilitado: "
            "21 campos, en el mismo orden, sin añadir columnas adicionales."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setMinimumHeight(480)
        lines = ["Campos exportados, en orden exacto:\n"]
        for idx, (field, definition) in enumerate(POINT_DISTRIBUTION_HELP, start=1):
            lines.append(f"{idx:02d}. {field}\n    {definition}\n")
        lines.append(
            "\nNota: dec_lat y dec_long no se rellenan en el cuadro de diálogo porque el plugin "
            "los toma automáticamente de los puntos usados en el último cálculo. catalog_no se rellena "
            "con gbifID cuando el registro procede de GBIF."
        )
        text.setPlainText("\n".join(lines))
        layout.addWidget(text)

        buttons = QDialogButtonBox(_button_box_ok())
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)



COORDINATECLEANER_CRITERIOS_ES = [
    ("coordenadas ausentes", "Registros sin latitud o longitud usable."),
    ("coordenadas fuera de rango", "Registros con latitud fuera de -90/90 o longitud fuera de -180/180."),
    ("coordenadas 0,0", "Registros situados exactamente en el punto 0,0."),
    ("longitud igual a latitud", "Registros en los que latitud y longitud son exactamente iguales."),
    ("problema GBIF: coordenada cero", "Registros que GBIF ya marca con problema de coordenada cero."),
    ("problema GBIF: posible centroide de país", "Registros que GBIF ya marca como posible centroide de país."),
    ("problema GBIF: coordenada inválida", "Registros que GBIF marca como coordenada inválida."),
    ("problema GBIF: coordenada fuera de rango", "Registros que GBIF marca fuera de rango."),
    ("sede de GBIF", "Coordenadas que coinciden con la sede de GBIF o el área de Copenhague."),
    ("coordenadas de capitales", "Coordenadas que coinciden casi exactamente con algunas capitales."),
    ("centroides de país", "Coordenadas que coinciden casi exactamente con centroides nacionales o valores muy genéricos."),
    ("coordenadas de instituciones", "Coordenadas que coinciden casi exactamente con algunas instituciones botánicas o museos."),
]

COORDINATECLEANER_REASON_TRANSLATION = {
    "coordenadas ausentes": "coordenadas ausentes",
    "coordenadas fuera de rango": "coordenadas fuera de rango",
    "coordenadas 0,0": "coordenadas 0,0",
    "longitud igual a latitud": "longitud igual a latitud",
    "GBIF issue ZERO_COORDINATE": "problema GBIF: coordenada cero",
    "GBIF issue COUNTRY_CENTROID": "problema GBIF: posible centroide de país",
    "GBIF issue COORDINATE_INVALID": "problema GBIF: coordenada inválida",
    "GBIF issue COORDINATE_OUT_OF_RANGE": "problema GBIF: coordenada fuera de rango",
    "gbif_headquarters": "sede de GBIF",
    "capital_coordinates": "coordenadas de capitales",
    "country_centroids": "centroides de país",
    "institution_coordinates": "coordenadas de instituciones",
}

class AooEooDialog(QDialog):
    """Main non-modal plugin dialog."""

    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.manual_layer = None
        self.manual_layer_id = None
        self.gbif_layer = None
        self.gbif_layer_id = None
        self.manual_tool = None
        self.previous_map_tool = None
        self.last_result = None
        self.point_distribution_layer = None
        self.gbif_doi_layer = None
        self.gbif_download_key = ""
        self.gbif_download_response = None
        self.calc_layers_list = None

        self.last_filter_removed = []
        self.setWindowTitle("LRN/GBIF")
        self.resize(900, 740)
        self.setMinimumSize(760, 560)
        self._build_ui()
        try:
            self.tabs.currentChanged.connect(self._on_tab_changed)
        except Exception:
            pass
        try:
            project = QgsProject.instance()
            project.layersAdded.connect(lambda _layers: self.refresh_calc_layers(apply_defaults=False))
            project.layersRemoved.connect(lambda _ids: self.refresh_calc_layers(apply_defaults=False))
        except Exception:
            pass

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        main = QVBoxLayout(self)
        intro = QLabel(
            "Herramienta para calcular AOO y EOO con registros de GBIF y, si hace falta, con puntos propios. "
            "Antes de usar los resultados en una evaluación formal, revise los puntos aislados, la precisión de las coordenadas y la fuente de cada dato."
        )
        intro.setWordWrap(True)
        main.addWidget(intro)

        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.addTab(self._make_gbif_tab(), "1. GBIF y filtros")
        self.tabs.addTab(self._make_data_tab(), "2. Capas y puntos propios")
        self.tabs.addTab(self._make_calc_tab(), "3. Calcular AOO/EOO")
        self.tabs.addTab(self._make_report_tab(), "4. Point Distribution")
        self.tabs.addTab(self._make_gbif_citation_tab(), "5. Cita GBIF / DOI")
        main.addWidget(self.tabs)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(110)
        self.log.setMaximumHeight(160)
        main.addWidget(self.log)

        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.close)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close_button)
        main.addLayout(bottom)

    def _make_gbif_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form_box = QGroupBox("Búsqueda GBIF")
        form = QGridLayout(form_box)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)

        def etiqueta(texto: str, ayuda: str) -> QLabel:
            label = QLabel(texto)
            label.setToolTip(ayuda)
            return label

        self.scientific_name = QLineEdit()
        self.scientific_name.setPlaceholderText("Ej.: Genista sanabrensis; o nombre infraespecífico completo")
        # Al pulsar Enter desde el campo de nombre científico, resolver el taxonKey.
        # Evita que Qt active por defecto otro botón de la pestaña, como la tabla de criterios.
        self.scientific_name.returnPressed.connect(self.resolve_taxon)
        self.assess_infraspecific = QCheckBox("Evaluar como subespecie o variedad")
        self.assess_infraspecific.setChecked(False)
        self.infraspecific_epithet = QLineEdit()
        self.infraspecific_epithet.setPlaceholderText("Epíteto infraespecífico, ej.: brevifolia; opcional")
        self.taxon_key = QLineEdit()
        self.taxon_key.setPlaceholderText("Opcional; se puede resolver desde el nombre")
        self.country_code = QLineEdit()
        self.country_code.setMaxLength(2)
        self.country_code.setPlaceholderText("ES, PT, FR... opcional")

        this_year = datetime.now().year
        self.year_min = QSpinBox()
        self.year_min.setRange(0, this_year + 1)
        self.year_min.setSpecialValueText("sin mínimo")
        self.year_min.setValue(0)
        self.year_max = QSpinBox()
        self.year_max.setRange(0, this_year + 1)
        self.year_max.setSpecialValueText("sin máximo")
        self.year_max.setValue(0)
        self.max_records = QSpinBox()
        self.max_records.setRange(1, 100000)
        self.max_records.setValue(5000)
        self.max_records.setSingleStep(1000)

        self.scientific_name.setToolTip(
            "Nombre científico que se buscará en GBIF. Puede ser especie o nombre infraespecífico completo. "
            "Ejemplo: Genista sanabrensis."
        )
        self.assess_infraspecific.setToolTip(
            "Márcalo cuando la evaluación sea para una subespecie o variedad. El epíteto infraespecífico se usará después en las salidas IUCN/SRedList."
        )
        self.infraspecific_epithet.setToolTip(
            "Epíteto infraespecífico, sin repetir el género ni la especie. Ejemplo: brevifolia."
        )
        self.taxon_key.setToolTip(
            "Identificador numérico de GBIF para el taxón. Es opcional: puedes resolverlo desde el nombre científico con el botón Resolver taxonKey."
        )
        self.country_code.setToolTip(
            "Código ISO de dos letras para limitar la búsqueda por país. Ejemplos: ES, PT, FR. Déjalo vacío para no filtrar por país."
        )
        self.year_min.setToolTip(
            "Año mínimo del registro GBIF. Se eliminarán de la descarga los registros anteriores a este año y quedarán documentados en la tabla de registros eliminados. "
            "Usa 'sin mínimo' para no aplicar este filtro."
        )
        self.year_max.setToolTip(
            "Año máximo del registro GBIF. Se eliminarán de la descarga los registros posteriores a este año y quedarán documentados en la tabla de registros eliminados. "
            "Usa 'sin máximo' para no aplicar este filtro."
        )
        self.max_records.setToolTip(
            "Número máximo de registros que el plugin intentará descargar desde GBIF para el taxón y filtros indicados."
        )

        self.exclude_geospatial_issues = QCheckBox("hasGeospatialIssue = false")
        self.exclude_geospatial_issues.setChecked(True)
        self.exclude_geospatial_issues.setToolTip(
            "Cuando está marcado, GBIF devuelve solo registros sin incidencias geoespaciales generales conocidas. Es recomendable dejarlo activado."
        )
        self.has_coordinate = QCheckBox("hasCoordinate = true")
        self.has_coordinate.setChecked(True)
        self.has_coordinate.setEnabled(False)
        self.has_coordinate.setToolTip(
            "Obliga a que los registros tengan coordenadas. Es necesario para calcular AOO, EOO y generar puntos."
        )

        self.occurrence_status = QComboBox()
        self.occurrence_status.addItems(["PRESENT", "ABSENT", "no filtrar"])
        self.occurrence_status.setCurrentText("PRESENT")
        self.occurrence_status.setToolTip(
            "Estado de ocurrencia en GBIF. Para distribución y evaluación de amenaza normalmente debe ser PRESENT. ABSENT no se usa para AOO/EOO."
        )

        self.synonym_1 = QLineEdit()
        self.synonym_1.setPlaceholderText("Sinónimo 1, opcional")
        self.synonym_2 = QLineEdit()
        self.synonym_2.setPlaceholderText("Sinónimo 2, opcional")
        self.synonym_3 = QLineEdit()
        self.synonym_3.setPlaceholderText("Sinónimo 3, opcional")
        self.synonym_4 = QLineEdit()
        self.synonym_4.setPlaceholderText("Sinónimo 4, opcional")
        for syn_widget in [self.synonym_1, self.synonym_2, self.synonym_3, self.synonym_4]:
            syn_widget.setToolTip(
                "Nombre alternativo o sinónimo que también se consultará en GBIF. Úsalo solo cuando quieras sumar registros publicados bajo otro nombre."
            )

        self.coordinatecleaner_filter = QCheckBox("Aplicar filtro automático tipo CoordinateCleaner")
        self.coordinatecleaner_filter.setChecked(True)
        cc_text = (
            "Marcado por defecto. Filtro inspirado en CoordinateCleaner (Zizka et al. 2019), "
            "como en SRedList: puede desactivarse y señala registros con coordenadas coincidentes "
            "con capitales, centroides de país, la sede de GBIF, algunas instituciones o con "
            "longitud igual a latitud. En este plugin se aplica una versión Python conservadora "
            "antes de crear la capa GBIF."
        )
        self.coordinatecleaner_filter.setToolTip(cc_text)
        self.show_cc_criteria_button = QPushButton("Ver criterios del filtro")
        self.show_cc_criteria_button.setToolTip("Crea una tabla con los motivos concretos que puede aplicar el filtro tipo CoordinateCleaner.")
        self.show_cc_criteria_button.clicked.connect(self.create_coordinatecleaner_criteria_table)
        self.show_cc_criteria_button.setAutoDefault(False)
        self.show_cc_criteria_button.setDefault(False)

        self.gbif_uncertainty_filter = QCheckBox("Filtrar por incertidumbre de coordenadas")
        self.gbif_uncertainty_filter.setChecked(False)
        self.gbif_uncertainty_filter.setToolTip(
            "Activa este filtro si quieres retirar registros de GBIF cuya incertidumbre espacial sea mayor que el umbral indicado. "
            "El umbral se interpreta en metros. Los registros sin valor de incertidumbre se mantienen para revisión."
        )
        self.gbif_uncertainty_combo = QComboBox()
        self.gbif_uncertainty_combo.setEditable(True)
        self.gbif_uncertainty_combo.setToolTip(
            "Selecciona un valor del desplegable o escribe uno propio. No es obligatorio escribir unidades: "
            "7050 se interpreta como 7050 metros. También puedes escribir 7050 m o 7.05 km."
        )
        for label, value in [
            ("100 m", 100),
            ("250 m", 250),
            ("500 m", 500),
            ("1 km", 1000),
            ("2 km", 2000),
            ("5 km", 5000),
            ("10 km", 10000),
            ("Sin límite", None),
        ]:
            self.gbif_uncertainty_combo.addItem(label, value)
        self.gbif_uncertainty_combo.setCurrentText("1 km")

        form.addWidget(etiqueta("Nombre científico", "Nombre del taxón que se buscará en GBIF. Puede ser especie o nombre infraespecífico completo."), 0, 0)
        form.addWidget(self.scientific_name, 0, 1)
        form.addWidget(etiqueta("taxonKey", "Identificador numérico de GBIF. Es opcional y puede resolverse desde el nombre científico."), 0, 2)
        form.addWidget(self.taxon_key, 0, 3)
        form.addWidget(self.assess_infraspecific, 1, 0)
        form.addWidget(self.infraspecific_epithet, 1, 1)
        form.addWidget(etiqueta("País", "Código ISO de dos letras para filtrar por país, por ejemplo ES. Déjalo vacío para no filtrar."), 1, 2)
        form.addWidget(self.country_code, 1, 3)
        form.addWidget(etiqueta("Año mínimo", "Año mínimo del registro GBIF. Los registros anteriores se retirarán y se podrán ver en la tabla de registros eliminados."), 2, 0)
        form.addWidget(self.year_min, 2, 1)
        form.addWidget(etiqueta("Año máximo", "Año máximo del registro GBIF. Los registros posteriores se retirarán y se podrán ver en la tabla de registros eliminados."), 2, 2)
        form.addWidget(self.year_max, 2, 3)
        form.addWidget(etiqueta("Estado de ocurrencia", "PRESENT incluye registros de presencia. ABSENT no debe usarse para calcular AOO/EOO salvo revisión muy específica."), 3, 0)
        form.addWidget(self.occurrence_status, 3, 1)
        form.addWidget(etiqueta("Máx. registros", "Número máximo de registros GBIF que se intentará descargar."), 3, 2)
        form.addWidget(self.max_records, 3, 3)
        form.addWidget(self.has_coordinate, 4, 0)
        form.addWidget(self.exclude_geospatial_issues, 4, 1)
        form.addWidget(self.coordinatecleaner_filter, 5, 0, 1, 2)
        form.addWidget(self.show_cc_criteria_button, 5, 2, 1, 2)
        form.addWidget(self.gbif_uncertainty_filter, 6, 0, 1, 2)
        umbral_incertidumbre_label = QLabel("Umbral incertidumbre (m)")
        umbral_incertidumbre_label.setToolTip(
            "Valor máximo aceptado de incertidumbre de coordenadas. Si escribes solo un número, se interpreta en metros. Ejemplo: 7050 = 7050 m."
        )
        form.addWidget(umbral_incertidumbre_label, 6, 2)
        form.addWidget(self.gbif_uncertainty_combo, 6, 3)
        form.addWidget(etiqueta("Sinónimos opcionales", "Nombres alternativos que también se consultarán en GBIF. Úsalos para incluir registros publicados bajo sinónimos."), 7, 0)
        form.addWidget(self.synonym_1, 7, 1)
        form.addWidget(self.synonym_2, 7, 2)
        form.addWidget(self.synonym_3, 8, 1)
        form.addWidget(self.synonym_4, 8, 2)
        layout.addWidget(form_box)

        filters = QHBoxLayout()
        self.basis_list = self._make_check_list(BASIS_OPTIONS)
        self.basis_list.setToolTip(
            "Tipo de registro en GBIF. Para plantas suelen ser útiles HUMAN_OBSERVATION y PRESERVED_SPECIMEN. MACHINE_OBSERVATION queda desmarcado por defecto."
        )
        basis_box = QGroupBox("basisOfRecord")
        basis_box.setToolTip(
            "Naturaleza del registro: observación humana, pliego conservado, observación de máquina, muestra, etc."
        )
        basis_layout = QVBoxLayout(basis_box)
        basis_layout.addWidget(self.basis_list)
        filters.addWidget(basis_box)

        self.establishment_list = self._make_check_list(ESTABLISHMENT_OPTIONS)
        self.establishment_list.setToolTip(
            "Origen o forma de establecimiento del registro según GBIF: nativo, introducido, reintroducido, incierto, etc."
        )
        est_box = QGroupBox("establishmentMeans")
        est_box.setToolTip(
            "Permite filtrar por origen del taxón. Para evaluaciones de distribución nativa, suele revisarse con cuidado."
        )
        est_layout = QVBoxLayout(est_box)
        est_layout.addWidget(self.establishment_list)
        self.filter_establishment = QCheckBox("Aplicar este filtro")
        self.filter_establishment.setChecked(False)
        self.filter_establishment.setToolTip(
            "Si no está marcado, los valores seleccionados de establishmentMeans no se usan para filtrar. Márcalo solo si quieres restringir los registros por origen."
        )
        est_layout.addWidget(self.filter_establishment)
        filters.addWidget(est_box)
        layout.addLayout(filters)

        buttons = QHBoxLayout()
        self.resolve_button = QPushButton("Resolver taxonKey")
        self.resolve_button.setToolTip("Busca el taxonKey de GBIF a partir del nombre científico indicado.")
        self.resolve_button.clicked.connect(self.resolve_taxon)
        self.preview_button = QPushButton("Previsualizar conteos GBIF")
        self.preview_button.setToolTip("Consulta conteos/facetas de GBIF antes de descargar los registros completos.")
        self.preview_button.clicked.connect(self.preview_facets)
        self.download_button = QPushButton("Descargar ocurrencias GBIF")
        self.download_button.setToolTip("Descarga registros de GBIF usando los filtros indicados en esta pestaña.")
        self.download_button.clicked.connect(self.download_gbif)
        self.reset_gbif_button = QPushButton("Resetear")
        self.reset_gbif_button.setToolTip("Limpia los campos y devuelve los filtros de esta pestaña a sus valores iniciales.")
        self.reset_gbif_button.clicked.connect(self.reset_gbif_tab)
        self.show_filtered_button = QPushButton("Ver registros eliminados")
        self.show_filtered_button.setToolTip("Crea una tabla con los registros retirados por los filtros aplicados en la última descarga GBIF.")
        self.show_filtered_button.clicked.connect(self.create_filtered_records_table)
        for _boton_gbif in [
            self.resolve_button,
            self.preview_button,
            self.download_button,
            self.reset_gbif_button,
            self.show_filtered_button,
        ]:
            _boton_gbif.setAutoDefault(False)
            _boton_gbif.setDefault(False)
        buttons.addWidget(self.resolve_button)
        buttons.addWidget(self.preview_button)
        buttons.addWidget(self.reset_gbif_button)
        buttons.addWidget(self.show_filtered_button)
        buttons.addStretch(1)
        buttons.addWidget(self.download_button)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return tab

    def _make_data_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.layer_combo = None  # compatibilidad interna: la selección de capas se hace en la pestaña 3

        manual_box = QGroupBox("Puntos añadidos por ti")
        manual_layout = QVBoxLayout(manual_box)
        self.manual_status = QLabel("Todavía no has creado una capa para tus puntos propios.")
        manual_layout.addWidget(self.manual_status)
        manual_buttons = QGridLayout()
        self.create_manual_button = QPushButton("Crear capa para mis puntos")
        self.create_manual_button.clicked.connect(self.create_manual_points_layer)
        self.activate_manual_button = QPushButton("Añadir punto haciendo clic en el mapa")
        self.activate_manual_button.clicked.connect(self.activate_manual_point_tool)
        self.add_manual_coordinates_button = QPushButton("Añadir punto introduciendo coordenadas")
        self.add_manual_coordinates_button.clicked.connect(self.add_manual_point_by_coordinates)
        self.stop_manual_button = QPushButton("Dejar de añadir puntos")
        self.stop_manual_button.clicked.connect(self.stop_manual_point_tool)
        self.import_csv_button = QPushButton("Importar mis puntos desde CSV")
        self.import_csv_button.setToolTip("Importa puntos desde un archivo CSV con columnas de latitud y longitud. Los puntos se incorporan a la capa de puntos propios.")
        self.import_csv_button.clicked.connect(self.import_manual_points_csv)
        self.import_shapefile_button = QPushButton("Importar puntos desde shapefile")
        self.import_shapefile_button.setToolTip("Carga un shapefile de puntos en el proyecto de QGIS y lo marca para poder usarlo directamente en el cálculo de la pestaña 3. Se conserva su tabla de atributos original.")
        self.import_shapefile_button.clicked.connect(self.import_point_shapefile)
        self.save_csv_template_button = QPushButton("Guardar plantilla base CSV")
        self.save_csv_template_button.clicked.connect(self.save_manual_csv_template)
        manual_buttons.addWidget(self.create_manual_button, 0, 0)
        manual_buttons.addWidget(self.activate_manual_button, 0, 1)
        manual_buttons.addWidget(self.add_manual_coordinates_button, 1, 0)
        manual_buttons.addWidget(self.import_csv_button, 1, 1)
        manual_buttons.addWidget(self.import_shapefile_button, 2, 0, 1, 2)
        manual_buttons.addWidget(self.save_csv_template_button, 3, 0, 1, 2)
        manual_buttons.addWidget(self.stop_manual_button, 4, 0, 1, 2)
        manual_layout.addLayout(manual_buttons)
        hint = QLabel(
            "Los puntos que añadas haciendo clic, escribiendo coordenadas o importando CSV quedan guardados en una capa separada. "
            "También puedes importar un shapefile de puntos: en ese caso se carga como capa independiente en QGIS, se conserva su tabla de atributos original y puedes marcarlo en la pestaña 3. "
            "Si necesitas borrar o corregir puntos, edita directamente la capa en QGIS y luego usa la pestaña 3 para calcular con las capas marcadas. "
            "Un punto solo entra en AOO/EOO si marcas ‘Usar este punto en el cálculo’. "
            "Si lo dejas como ‘Revisar antes de usar’, el programa lo conserva, pero no lo usa salvo que actives esa opción en la pestaña de cálculo. "
            "Para CSV acepta latitud como decimalLatitude, latitude, lat o dec_lat; y longitud como decimalLongitude, longitude, lon, lng, dec_lon, dec_long o long."
        )
        hint.setWordWrap(True)
        manual_layout.addWidget(hint)
        layout.addWidget(manual_box)
        layout.addStretch(1)
        return tab

    def _make_calc_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        layers_box = QGroupBox("Capas que se usarán para calcular")
        layers_layout = QVBoxLayout(layers_box)
        layers_hint = QLabel(
            "Marca una o varias capas de puntos del proyecto. El cálculo usará solo las capas marcadas. "
            "Esto permite calcular AOO/EOO desde GBIF, CSV importado, puntos propios, cualquier capa de puntos cargada en QGIS o varias capas combinadas."
        )
        layers_hint.setWordWrap(True)
        layers_layout.addWidget(layers_hint)
        self.calc_layers_list = QListWidget()
        self.calc_layers_list.setMinimumHeight(150)
        try:
            self.calc_layers_list.setSelectionMode(QAbstractItemView.MultiSelection)
        except Exception:
            pass
        layers_layout.addWidget(self.calc_layers_list)
        layer_buttons = QGridLayout()
        self.refresh_calc_layers_button = QPushButton("Actualizar lista de capas")
        self.refresh_calc_layers_button.clicked.connect(lambda: self.refresh_calc_layers(apply_defaults=False))
        self.check_current_layer_button = QPushButton("Marcar capa activa")
        self.check_current_layer_button.clicked.connect(self.check_current_calc_layer)
        self.check_all_layers_button = QPushButton("Marcar todas")
        self.check_all_layers_button.clicked.connect(self.check_all_calc_layers)
        self.uncheck_all_layers_button = QPushButton("Desmarcar todas")
        self.uncheck_all_layers_button.clicked.connect(self.uncheck_all_calc_layers)
        layer_buttons.addWidget(self.refresh_calc_layers_button, 0, 0)
        layer_buttons.addWidget(self.check_current_layer_button, 0, 1)
        layer_buttons.addWidget(self.check_all_layers_button, 1, 0)
        layer_buttons.addWidget(self.uncheck_all_layers_button, 1, 1)
        layers_layout.addLayout(layer_buttons)
        layout.addWidget(layers_box)
        self.refresh_calc_layers(apply_defaults=True)

        opts = QGroupBox("Parámetros de cálculo")
        form = QFormLayout(opts)
        _set_form_expanding_fields(form)
        self.analysis_crs = QLineEdit("EPSG:3035")
        self.analysis_crs.setMaximumWidth(220)
        self.cell_size = QDoubleSpinBox()
        self.cell_size.setRange(1, 100000)
        self.cell_size.setValue(2000)
        self.cell_size.setSuffix(" m")
        self.cell_size.setDecimals(0)
        self.cell_size.setMaximumWidth(160)

        self.include_pending = QCheckBox("Usar también puntos marcados como ‘revisar antes de usar’")
        self.include_pending.setChecked(False)
        self.deduplicate = QCheckBox("Eliminar duplicados espaciales exactos")
        self.deduplicate.setChecked(True)
        self.use_uncertainty_filter = QCheckBox("Filtrar por incertidumbre máxima")
        self.use_uncertainty_filter.setChecked(True)
        self.max_uncertainty = QDoubleSpinBox()
        self.max_uncertainty.setRange(0, 1_000_000)
        self.max_uncertainty.setValue(1000)
        self.max_uncertainty.setSuffix(" m")
        self.max_uncertainty.setDecimals(0)
        self.max_uncertainty.setMaximumWidth(160)

        form.addRow("CRS de análisis", self.analysis_crs)
        form.addRow("Celda AOO", self.cell_size)
        form.addRow("Puntos por revisar", self.include_pending)
        form.addRow("Duplicados", self.deduplicate)
        form.addRow(self.use_uncertainty_filter, self.max_uncertainty)
        layout.addWidget(opts)

        iucn_box = QGroupBox("Atributos IUCN obligatorios/condicionales para AOO y EOO")
        iucn_form = QFormLayout(iucn_box)
        _set_form_expanding_fields(iucn_form)
        this_year = datetime.now().year
        self.iucn_presence = QComboBox()
        self.iucn_presence.addItem("1 - Extant / presente", 1)
        self.iucn_presence.addItem("3 - Possibly Extant / posible presencia", 3)
        self.iucn_presence.addItem("4 - Possibly Extinct / posiblemente extinto", 4)
        self.iucn_presence.addItem("5 - Extinct / extinto", 5)
        self.iucn_presence.addItem("6 - Presence Uncertain / presencia incierta", 6)
        self.iucn_presence.addItem("7 - Extant & Introduced / presente e introducido", 7)
        self.iucn_presence.setMaximumWidth(360)

        self.iucn_origin = QComboBox()
        self.iucn_origin.addItem("1 - Native / nativo", 1)
        self.iucn_origin.addItem("2 - Reintroduced / reintroducido", 2)
        self.iucn_origin.addItem("3 - Introduced / introducido", 3)
        self.iucn_origin.addItem("4 - Vagrant / accidental", 4)
        self.iucn_origin.addItem("5 - Origin Uncertain / origen incierto", 5)
        self.iucn_origin.addItem("6 - Assisted Colonisation / colonización asistida", 6)
        self.iucn_origin.addItem("7 - Mixed origin / origen mixto", 7)
        self.iucn_origin.setMaximumWidth(360)

        self.iucn_seasonal = QComboBox()
        self.iucn_seasonal.addItem("1 - Resident / residente", 1)
        self.iucn_seasonal.addItem("2 - Breeding Season / época reproductora", 2)
        self.iucn_seasonal.addItem("3 - Non-breeding Season / época no reproductora", 3)
        self.iucn_seasonal.addItem("4 - Passage / paso", 4)
        self.iucn_seasonal.addItem("5 - Seasonal Occurrence Uncertain / estacionalidad incierta", 5)
        self.iucn_seasonal.setMaximumWidth(360)

        self.iucn_compiler = QLineEdit()
        self.iucn_compiler.setMaximumWidth(420)
        self.iucn_yrcompiled = QSpinBox()
        self.iucn_yrcompiled.setRange(1900, this_year + 1)
        self.iucn_yrcompiled.setValue(this_year)
        self.iucn_yrcompiled.setMaximumWidth(120)
        self.iucn_citation = QLineEdit()
        self.iucn_citation.setMaximumWidth(520)
        self.iucn_subspecies = QLineEdit()
        self.iucn_subspecies.setMaximumWidth(320)
        self.iucn_data_sens = QComboBox()
        self.iucn_data_sens.addItem("0 - No sensible", 0)
        self.iucn_data_sens.addItem("1 - Sensible", 1)
        self.iucn_data_sens.setMaximumWidth(200)
        self.iucn_sens_comm = QLineEdit()
        self.iucn_sens_comm.setMaximumWidth(520)

        iucn_form.addRow("sci_name *", QLabel("se tomará del nombre científico de la pestaña GBIF"))
        iucn_form.addRow("presence *", self.iucn_presence)
        iucn_form.addRow("origin *", self.iucn_origin)
        iucn_form.addRow("seasonal * si aplica", self.iucn_seasonal)
        iucn_form.addRow("compiler *", self.iucn_compiler)
        iucn_form.addRow("yrcompiled *", self.iucn_yrcompiled)
        iucn_form.addRow("citation *", self.iucn_citation)
        iucn_form.addRow("subspecies si aplica", self.iucn_subspecies)
        iucn_form.addRow("data_sens si sensible", self.iucn_data_sens)
        iucn_form.addRow("sens_comm * si data_sens=1", self.iucn_sens_comm)
        note = QLabel(
            "Campos IUCN obligatorios/condicionales para las capas AOO y EOO. "
            "compiler y citation quedan vacíos por defecto. generalisd se añade automáticamente: AOO=0 y EOO=1."
        )
        note.setWordWrap(True)
        iucn_form.addRow("Nota", note)
        self.iucn_fields_help_button = QPushButton("Crear ayuda de atributos IUCN AOO/EOO")
        self.iucn_fields_help_button.clicked.connect(self.create_iucn_polygon_field_guide)
        iucn_form.addRow("Ayuda", self.iucn_fields_help_button)
        layout.addWidget(iucn_box)

        threshold_note = QLabel(
            "El informe añadirá una categoría orientativa según los umbrales espaciales de AOO y EOO del Criterio B. "
            "No sustituye una evaluación formal de la Lista Roja."
        )
        threshold_note.setWordWrap(True)
        layout.addWidget(threshold_note)

        buttons = QHBoxLayout()
        self.calc_button = QPushButton("Calcular AOO/EOO")
        self.calc_button.clicked.connect(self.calculate)
        buttons.addStretch(1)
        buttons.addWidget(self.calc_button)
        layout.addLayout(buttons)
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return tab

    def _make_report_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        info = QLabel(
            "Esta pestaña prepara Point Distribution a partir de los puntos usados en el último cálculo de la pestaña 3. "
            "Si en la pestaña 3 marcaste varias capas, aquí se incluirán los registros seleccionados de todas ellas."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        csv_box = QGroupBox("Point Distribution")
        csv_layout = QVBoxLayout(csv_box)
        csv_hint = QLabel(
            "La tabla y el CSV Point Distribution tendrán exactamente 21 campos, en este orden: "
            "sci_name, presence, origin, seasonal, compiler, yrcompiled, citation, dec_lat, dec_long, spatialref, "
            "subspecies, subpop, data_sens, sens_comm, event_year, source, basisofrec, catalog_no, dist_comm, island, tax_comm. "
            "El shapefile se exporta como capa de puntos en WGS84/EPSG:4326 con esos mismos atributos."
        )
        csv_hint.setWordWrap(True)
        csv_layout.addWidget(csv_hint)
        buttons = QGridLayout()
        self.create_point_distribution_button = QPushButton("Crear tabla Point Distribution en QGIS")
        self.create_point_distribution_button.clicked.connect(self.create_point_distribution_table)
        self.create_point_distribution_shp_layer_button = QPushButton("Crear capa Point Distribution en QGIS")
        self.create_point_distribution_shp_layer_button.clicked.connect(self.create_point_distribution_shapefile_layer)
        self.save_point_distribution_button = QPushButton("Guardar CSV Point Distribution...")
        self.save_point_distribution_button.clicked.connect(self.save_point_distribution_csv)
        self.save_point_distribution_shp_button = QPushButton("Guardar Shapefile Point Distribution...")
        self.save_point_distribution_shp_button.clicked.connect(self.save_point_distribution_shapefile)
        self.point_distribution_help_button = QPushButton("Guía de campos Point Distribution")
        self.point_distribution_help_button.clicked.connect(self.show_point_distribution_help)
        buttons.addWidget(self.create_point_distribution_button, 0, 0)
        buttons.addWidget(self.create_point_distribution_shp_layer_button, 0, 1)
        buttons.addWidget(self.save_point_distribution_button, 1, 0)
        buttons.addWidget(self.save_point_distribution_shp_button, 1, 1)
        buttons.addWidget(self.point_distribution_help_button, 2, 0, 1, 2)
        csv_layout.addLayout(buttons)
        layout.addWidget(csv_box)
        layout.addStretch(1)
        return tab


    def _make_gbif_citation_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        info = QLabel(
            "Esta pestaña crea la cita GBIF correcta para los registros GBIF que han entrado realmente en el cálculo. "
            "El flujo usa solo la vía oficial de descarga de ocurrencias de GBIF: gbifID usados → descarga oficial GBIF → DOI → cita. "
            "No usa Derived Dataset, datasetKey/count ni URL pública externa."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        step1 = QGroupBox("Paso 1. Preparar los gbifID usados")
        step1_layout = QVBoxLayout(step1)
        step1_text = QLabel(
            "Después de calcular AOO/EOO, pulsa el botón para extraer los gbifID de la capa de puntos usados. "
            "La lista incluye solo registros procedentes de GBIF. Los puntos añadidos por ti no tienen DOI GBIF y deben citarse aparte."
        )
        step1_text.setWordWrap(True)
        step1_layout.addWidget(step1_text)
        row1 = QHBoxLayout()
        self.prepare_gbif_ids_button = QPushButton("1. Preparar lista de gbifID usados")
        self.prepare_gbif_ids_button.clicked.connect(self.prepare_gbif_download_ids)
        self.copy_gbif_ids_button = QPushButton("Copiar gbifID")
        self.copy_gbif_ids_button.clicked.connect(self.copy_gbif_ids)
        row1.addWidget(self.prepare_gbif_ids_button)
        row1.addWidget(self.copy_gbif_ids_button)
        row1.addStretch(1)
        step1_layout.addLayout(row1)
        layout.addWidget(step1)

        step2 = QGroupBox("Paso 2. Solicitar una descarga oficial a GBIF")
        step2_layout = QVBoxLayout(step2)
        step2_text = QLabel(
            "Con esta opción no tienes que pegar la lista en ninguna web: el plugin la envía a la API oficial de descargas de GBIF. "
            "GBIF responde primero con una clave de descarga. El DOI aparece cuando la descarga termina. "
            "Necesitas usuario y contraseña de GBIF.org; la contraseña no se guarda."
        )
        step2_text.setWordWrap(True)
        step2_layout.addWidget(step2_text)
        form_box = QWidget()
        form = QFormLayout(form_box)
        _set_form_expanding_fields(form)
        self.gbif_download_user = QLineEdit()
        self.gbif_download_user.setPlaceholderText("Nombre de usuario de GBIF, no correo electrónico")
        self.gbif_download_password = QLineEdit()
        self.gbif_download_password.setEchoMode(_line_edit_password())
        self.gbif_download_email = QLineEdit()
        self.gbif_download_email.setPlaceholderText("Correo de notificación de GBIF")
        self.gbif_download_format = QComboBox()
        self.gbif_download_format.addItem("SIMPLE_CSV", "SIMPLE_CSV")
        self.gbif_download_format.addItem("DWCA", "DWCA")
        form.addRow("Usuario GBIF* (no correo)", self.gbif_download_user)
        form.addRow("Contraseña GBIF*", self.gbif_download_password)
        form.addRow("Correo de notificación", self.gbif_download_email)
        form.addRow("Formato", self.gbif_download_format)
        step2_layout.addWidget(form_box)
        row2 = QHBoxLayout()
        self.request_gbif_download_button = QPushButton("2. Solicitar descarga oficial y DOI")
        self.request_gbif_download_button.clicked.connect(self.request_gbif_occurrence_download)
        self.open_gbif_download_button = QPushButton("Abrir mis descargas GBIF")
        self.open_gbif_download_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.gbif.org/occurrence/download")))
        row2.addWidget(self.request_gbif_download_button)
        row2.addWidget(self.open_gbif_download_button)
        row2.addStretch(1)
        step2_layout.addLayout(row2)
        layout.addWidget(step2)

        step3 = QGroupBox("Paso 3. Comprobar si el DOI está listo")
        step3_layout = QVBoxLayout(step3)
        step3_text = QLabel(
            "La descarga de GBIF es asíncrona. Puede tardar desde unos segundos hasta varios minutos. "
            "Cuando el estado sea SUCCEEDED, GBIF devolverá un DOI citable."
        )
        step3_text.setWordWrap(True)
        step3_layout.addWidget(step3_text)
        key_row = QHBoxLayout()
        self.gbif_download_key_edit = QLineEdit()
        self.gbif_download_key_edit.setPlaceholderText("Clave de descarga GBIF")
        self.check_gbif_download_button = QPushButton("3. Comprobar estado / DOI")
        self.check_gbif_download_button.clicked.connect(self.check_gbif_occurrence_download)
        key_row.addWidget(QLabel("Clave:"))
        key_row.addWidget(self.gbif_download_key_edit, 1)
        key_row.addWidget(self.check_gbif_download_button)
        step3_layout.addLayout(key_row)
        layout.addWidget(step3)

        step4 = QGroupBox("Paso 4. Resultado y cita")
        step4_layout = QVBoxLayout(step4)
        self.gbif_download_result = QTextEdit()
        self.gbif_download_result.setReadOnly(True)
        self.gbif_download_result.setMinimumHeight(220)
        self.gbif_download_result.setPlainText(
            "1) Calcula AOO/EOO en la pestaña 3.\n"
            "2) Pulsa ‘Preparar lista de gbifID usados’.\n"
            "3) Rellena usuario/contraseña GBIF y solicita la descarga oficial.\n"
            "4) Copia la clave de descarga o pulsa ‘Comprobar estado / DOI’ hasta que GBIF devuelva SUCCEEDED.\n"
            "5) Cita el DOI de GBIF que aparecerá aquí.\n\n"
            "Nota: el DOI GBIF cubre únicamente los registros procedentes de GBIF. Los puntos propios deben citarse con su fuente independiente."
        )
        step4_layout.addWidget(self.gbif_download_result)
        row4 = QHBoxLayout()
        self.copy_gbif_citation_button = QPushButton("Copiar cita")
        self.copy_gbif_citation_button.clicked.connect(self.copy_gbif_citation)
        self.open_gbif_citation_button = QPushButton("Abrir guía de cita GBIF")
        self.open_gbif_citation_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.gbif.org/citation-guidelines")))
        row4.addWidget(self.copy_gbif_citation_button)
        row4.addWidget(self.open_gbif_citation_button)
        row4.addStretch(1)
        step4_layout.addLayout(row4)
        layout.addWidget(step4)
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return tab

    def _make_check_list(self, options) -> QListWidget:
        widget = QListWidget()
        for value, checked, tooltip in options:
            item = QListWidgetItem(value)
            item.setFlags(item.flags() | _qt_item_user_checkable())
            item.setCheckState(_qt_checked() if checked else _qt_unchecked())
            item.setToolTip(tooltip)
            widget.addItem(item)
        return widget

    def show_point_distribution_help(self):
        dialog = PointDistributionHelpDialog(self)
        _dialog_exec(dialog)


    def reset_gbif_tab(self):
        """Reset the GBIF search/filter tab to its default values."""
        self.scientific_name.clear()
        self.taxon_key.clear()
        self.country_code.clear()
        self.year_min.setValue(0)
        self.year_max.setValue(0)
        self.max_records.setValue(5000)
        self.occurrence_status.setCurrentText("PRESENT")
        self.exclude_geospatial_issues.setChecked(True)
        self.coordinatecleaner_filter.setChecked(True)
        if hasattr(self, "gbif_uncertainty_filter"):
            self.gbif_uncertainty_filter.setChecked(False)
        if hasattr(self, "gbif_uncertainty_combo"):
            self.gbif_uncertainty_combo.setCurrentText("1 km")
        self.last_filter_removed = []
        self.assess_infraspecific.setChecked(False)
        self.infraspecific_epithet.clear()
        for widget in [self.synonym_1, self.synonym_2, self.synonym_3, self.synonym_4]:
            widget.clear()
        for list_widget, options in [(self.basis_list, BASIS_OPTIONS), (self.establishment_list, ESTABLISHMENT_OPTIONS)]:
            for i, (_value, checked, _tooltip) in enumerate(options):
                item = list_widget.item(i)
                if item is not None:
                    item.setCheckState(_qt_checked() if checked else _qt_unchecked())
        self.filter_establishment.setChecked(False)
        self._log("Filtros GBIF reseteados a valores por defecto.")


    # ------------------------------------------------------------- utilities
    def _log(self, text: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{stamp}] {text}")

    def _checked_values(self, widget: QListWidget) -> list[str]:
        values = []
        for i in range(widget.count()):
            item = widget.item(i)
            if item.checkState() == _qt_checked():
                values.append(item.text())
        return values

    def _synonym_names(self) -> list[str]:
        names = []
        for widget in [self.synonym_1, self.synonym_2, self.synonym_3, self.synonym_4]:
            value = widget.text().strip()
            if value and value not in names:
                names.append(value)
        return names

    def _gbif_uncertainty_threshold_m(self):
        if not hasattr(self, "gbif_uncertainty_combo"):
            return None
        text = (self.gbif_uncertainty_combo.currentText() or "").strip().lower()
        if not text or "sin" in text:
            return None
        match = re.search(r"[-+]?\d+(?:[\.,]\d+)?", text)
        if match:
            try:
                value = float(match.group(0).replace(",", "."))
                if "km" in text:
                    value *= 1000.0
                return value
            except ValueError:
                return None
        data = self.gbif_uncertainty_combo.currentData()
        if data in (None, ""):
            return None
        try:
            return float(data)
        except (TypeError, ValueError):
            return None

    def _gbif_year_bounds(self):
        ymin = self.year_min.value() if hasattr(self, "year_min") and self.year_min.value() else None
        ymax = self.year_max.value() if hasattr(self, "year_max") and self.year_max.value() else None
        return ymin, ymax

    def _apply_local_year_filter(self, records):
        ymin, ymax = self._gbif_year_bounds()
        if ymin is None and ymax is None:
            return records, []
        kept = []
        removed = []
        for rec in records:
            raw_year = rec.get("year")
            try:
                year_value = int(raw_year) if raw_year not in (None, "") else None
            except (TypeError, ValueError):
                year_value = None
            if year_value is None:
                kept.append(rec)
                continue
            if ymin is not None and year_value < ymin:
                removed.append((rec, f"Filtro por año: {year_value} < año mínimo {ymin}"))
            elif ymax is not None and year_value > ymax:
                removed.append((rec, f"Filtro por año: {year_value} > año máximo {ymax}"))
            else:
                kept.append(rec)
        return kept, removed

    def _build_gbif_params(self) -> dict:
        params = {"hasCoordinate": "true"}
        taxon_key = self.taxon_key.text().strip()
        if taxon_key:
            params["taxonKey"] = taxon_key
        else:
            name = self.scientific_name.text().strip()
            if not name:
                raise ValueError("Introduce un nombre científico o un taxonKey.")
            # GBIF can search by scientificName, but taxonKey is more reproducible.
            params["scientificName"] = name

        if self.country_code.text().strip():
            params["country"] = self.country_code.text().strip().upper()

        # El filtro de año se aplica localmente después de descargar los registros,
        # para que los registros descartados puedan auditarse en la tabla
        # “GBIF registros eliminados por filtros”.
        if self.occurrence_status.currentText() != "no filtrar":
            params["occurrenceStatus"] = self.occurrence_status.currentText()

        basis = self._checked_values(self.basis_list)
        if basis:
            params["basisOfRecord"] = basis

        if self.filter_establishment.isChecked():
            est = self._checked_values(self.establishment_list)
            if est:
                params["establishmentMeans"] = est

        if self.exclude_geospatial_issues.isChecked():
            params["hasGeospatialIssue"] = "false"
        return params


    def _motivo_coordinatecleaner_es(self, reason: str) -> str:
        return COORDINATECLEANER_REASON_TRANSLATION.get(str(reason or ""), str(reason or ""))

    def create_coordinatecleaner_criteria_table(self):
        """Crea una tabla en QGIS con los criterios del filtro CoordinateCleaner aplicado."""
        layer = QgsVectorLayer("None", "Criterios del filtro CoordinateCleaner", "memory")
        provider = layer.dataProvider()
        provider.addAttributes([
            QgsField("motivo", QVariant.String),
            QgsField("que_elimina", QVariant.String),
        ])
        layer.updateFields()
        features = []
        for motivo, descripcion in COORDINATECLEANER_CRITERIOS_ES:
            feat = QgsFeature(layer.fields())
            feat.setAttributes([motivo, descripcion])
            features.append(feat)
        provider.addFeatures(features)
        layer.updateFields()
        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)
        self._log("Tabla creada con los criterios del filtro tipo CoordinateCleaner.")
        self.iface.messageBar().pushSuccess("LRN/GBIF", "Tabla de criterios del filtro creada en el proyecto.")

    def create_filtered_records_table(self):
        """Crea una tabla en QGIS con los registros retirados por filtros automáticos."""
        removed = getattr(self, "last_filter_removed", []) or []
        if not removed:
            QMessageBox.information(
                self,
                "Registros eliminados",
                "No hay registros eliminados por los filtros de año, CoordinateCleaner o incertidumbre en la última descarga GBIF."
            )
            return

        layer = QgsVectorLayer("None", "GBIF registros eliminados por filtros", "memory")
        provider = layer.dataProvider()
        fields = [
            ("motivo", QVariant.String),
            ("gbifID", QVariant.String),
            ("nombre_cientifico", QVariant.String),
            ("latitud", QVariant.Double),
            ("longitud", QVariant.Double),
            ("incertidumbre_m", QVariant.Double),
            ("base_registro", QVariant.String),
            ("estado_ocurrencia", QVariant.String),
            ("origen_establecimiento", QVariant.String),
            ("fecha_evento", QVariant.String),
            ("anio", QVariant.Int),
            ("pais", QVariant.String),
            ("datasetKey", QVariant.String),
            ("institucion", QVariant.String),
            ("coleccion", QVariant.String),
            ("incidencias_gbif", QVariant.String),
        ]
        provider.addAttributes([QgsField(name, typ) for name, typ in fields])
        layer.updateFields()

        def safe_float(value):
            try:
                if value in (None, ""):
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        def safe_int(value):
            try:
                if value in (None, ""):
                    return None
                return int(value)
            except (TypeError, ValueError):
                return None

        features = []
        for rec, reason in removed:
            reason_text = str(reason or "")
            if reason_text.startswith("CoordinateCleaner: "):
                raw_reason = reason_text.split(": ", 1)[1]
                reason_text = "CoordinateCleaner: " + self._motivo_coordinatecleaner_es(raw_reason)
            feat = QgsFeature(layer.fields())
            feat.setAttributes([
                reason_text,
                str(rec.get("gbifID", "") or ""),
                str(rec.get("scientificName", "") or ""),
                safe_float(rec.get("decimalLatitude")),
                safe_float(rec.get("decimalLongitude")),
                safe_float(rec.get("coordinateUncertaintyInMeters")),
                str(rec.get("basisOfRecord", "") or ""),
                str(rec.get("occurrenceStatus", "") or ""),
                str(rec.get("establishmentMeans", "") or ""),
                str(rec.get("eventDate", "") or ""),
                safe_int(rec.get("year")),
                str(rec.get("countryCode", "") or ""),
                str(rec.get("datasetKey", "") or ""),
                str(rec.get("institutionCode", "") or ""),
                str(rec.get("collectionCode", "") or ""),
                str(rec.get("issues", "") or ""),
            ])
            features.append(feat)
        provider.addFeatures(features)
        layer.updateFields()
        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)
        self._log(f"Tabla creada con {len(features)} registros eliminados por filtros automáticos.")
        self.iface.messageBar().pushSuccess("LRN/GBIF", "Tabla de registros eliminados creada en el proyecto.")

    # -------------------------------------------------------------- GBIF ops
    def resolve_taxon(self):
        try:
            result = match_species(self.scientific_name.text().strip())
        except GbifError as exc:
            QMessageBox.warning(self, "GBIF", str(exc))
            return

        usage_key = result.get("usageKey") or result.get("acceptedUsageKey")
        if usage_key:
            self.taxon_key.setText(str(usage_key))
        msg = (
            f"Match GBIF: {result.get('scientificName', '')} | "
            f"rank={result.get('rank', '')} | confidence={result.get('confidence', '')} | "
            f"status={result.get('status', '')} | usageKey={usage_key}"
        )
        self._log(msg)

    def preview_facets(self):
        try:
            params = self._build_gbif_params()
            data = occurrence_facets(params)
        except (GbifError, ValueError) as exc:
            QMessageBox.warning(self, "GBIF", str(exc))
            return

        self._log(f"GBIF total aproximado con filtros principales: {data.get('count', 0)}")
        if self._synonym_names():
            self._log("Nota: los sinónimos opcionales se suman durante la descarga; esta previsualización muestra la consulta principal.")
        facets = data.get("facets") or []
        for facet in facets:
            field = facet.get("field", "")
            counts = facet.get("counts") or []
            summary = ", ".join(f"{c.get('name')}={c.get('count')}" for c in counts[:12])
            self._log(f"  {field}: {summary}")

    def download_gbif(self):
        try:
            params = self._build_gbif_params()
            max_records = self.max_records.value()
            self._log(f"Descargando GBIF con parámetros principales: {params}")

            def progress(done, total):
                total_txt = total if total is not None else "?"
                self._log(f"  descargados {done} de {total_txt}")
                QApplication.processEvents()

            raw_records = search_occurrences(params, max_records=max_records, progress_callback=progress)

            # Optional synonyms: GBIF occurrence/search has no single OR widget here,
            # so we query each synonym separately and deduplicate by gbifID.
            synonyms = self._synonym_names()
            if synonyms:
                self._log(f"Buscando también sinónimos: {', '.join(synonyms)}")
                per_synonym_limit = max(1, max_records // (len(synonyms) + 1))
                for syn in synonyms:
                    syn_params = dict(params)
                    syn_params.pop("taxonKey", None)
                    syn_params["scientificName"] = syn
                    self._log(f"  Descargando sinónimo: {syn}")
                    raw_records.extend(search_occurrences(syn_params, max_records=per_synonym_limit, progress_callback=None))

            # Deduplicate GBIF records before creating the QGIS layer.
            seen_gbif_ids = set()
            slim_records = []
            for record in raw_records:
                rec = slim_record(record)
                gbif_id = rec.get("gbifID", "")
                if gbif_id and gbif_id in seen_gbif_ids:
                    continue
                if gbif_id:
                    seen_gbif_ids.add(gbif_id)
                slim_records.append(rec)

            self.last_filter_removed = []
            records = slim_records

            records, removed_year = self._apply_local_year_filter(records)
            if removed_year:
                self.last_filter_removed.extend(removed_year)
                self._log(f"Filtro por año aplicado: {len(removed_year)} registros retirados antes de crear la capa GBIF.")
            elif self.year_min.value() or self.year_max.value():
                self._log("Filtro por año aplicado: ningún registro retirado.")

            if self.coordinatecleaner_filter.isChecked():
                records, flagged = coordinatecleaner_filter_records(records)
                for rec, reason in flagged:
                    self.last_filter_removed.append((rec, f"CoordinateCleaner: {self._motivo_coordinatecleaner_es(reason)}"))
                self._log(f"Filtro tipo CoordinateCleaner aplicado: {len(flagged)} registros retirados antes de crear la capa GBIF.")
                if flagged:
                    reasons = {}
                    for _rec, reason in flagged:
                        reason_es = self._motivo_coordinatecleaner_es(reason)
                        reasons[reason_es] = reasons.get(reason_es, 0) + 1
                    self._log("  Motivos: " + "; ".join(f"{k}={v}" for k, v in sorted(reasons.items())))

            if self.gbif_uncertainty_filter.isChecked():
                threshold = self._gbif_uncertainty_threshold_m()
                if threshold is not None:
                    kept = []
                    removed_uncertainty = []
                    for rec in records:
                        try:
                            uncertainty = rec.get("coordinateUncertaintyInMeters")
                            uncertainty_value = None if uncertainty in (None, "") else float(uncertainty)
                        except (TypeError, ValueError):
                            uncertainty_value = None
                        if uncertainty_value is not None and uncertainty_value > threshold:
                            reason = f"Incertidumbre: {uncertainty_value:g} m > {threshold:g} m"
                            removed_uncertainty.append((rec, reason))
                            self.last_filter_removed.append((rec, reason))
                        else:
                            kept.append(rec)
                    records = kept
                    self._log(f"Filtro de incertidumbre aplicado: {len(removed_uncertainty)} registros retirados con incertidumbre > {threshold:g} m.")
                    # Los registros sin coordinateUncertaintyInMeters se mantienen para no eliminar datos potencialmente válidos sin revisión.

            layer_name = "GBIF occurrences AOO_EOO"
            if self.scientific_name.text().strip():
                layer_name = f"GBIF {self.scientific_name.text().strip()}"
            self.gbif_layer = create_occurrence_layer(records, layer_name)
            self.gbif_layer.setCustomProperty("aoo_eoo_gbif_pro_layer_type", "gbif_points")
            QgsProject.instance().addMapLayer(self.gbif_layer)
            self.gbif_layer_id = self.gbif_layer.id()
            if self.layer_combo is not None:
                self.layer_combo.setLayer(self.gbif_layer)
            self.refresh_calc_layers(apply_defaults=True)
            self._log(f"Capa GBIF creada: {self.gbif_layer.featureCount()} puntos válidos con coordenadas.")
            self.iface.messageBar().pushSuccess("LRN/GBIF", "Descarga GBIF finalizada y añadida al proyecto.")
        except (GbifError, ValueError, Exception) as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Error al descargar GBIF", str(exc))
            self._log(f"ERROR GBIF: {exc}")

    # -------------------------------------------------------------- GBIF layer
    def _get_existing_gbif_layer(self):
        """Return the current GBIF occurrence layer, or None if it was removed."""
        if _layer_is_usable(self.gbif_layer):
            return self.gbif_layer

        self.gbif_layer = None
        project = QgsProject.instance()

        if self.gbif_layer_id:
            layer = project.mapLayer(self.gbif_layer_id)
            if _layer_is_usable(layer):
                self.gbif_layer = layer
                return layer
            self.gbif_layer_id = None

        for layer in project.mapLayers().values():
            try:
                if layer.customProperty("aoo_eoo_gbif_pro_layer_type") == "gbif_points" and _layer_is_usable(layer):
                    self.gbif_layer = layer
                    self.gbif_layer_id = layer.id()
                    return layer
            except RuntimeError:
                continue
        return None


    # ------------------------------------------------------------- layer selection
    def _is_probably_point_layer(self, layer) -> bool:
        if not _layer_is_usable(layer):
            return False
        try:
            wkb_text = str(layer.wkbType()).lower()
            geom_text = str(layer.geometryType()).lower()
            if "point" in wkb_text or "point" in geom_text:
                return True
        except Exception:
            pass
        try:
            # Be permissive for QGIS 4 and CSV layers: run_aoo_eoo validates
            # feature geometries again and ignores non-point geometries safely.
            return hasattr(layer, "getFeatures") and hasattr(layer, "featureCount") and hasattr(layer, "crs")
        except Exception:
            return False

    def refresh_calc_layers(self, apply_defaults=None):
        if self.calc_layers_list is None:
            return
        had_items = self.calc_layers_list.count() > 0
        if apply_defaults is None:
            apply_defaults = not had_items
        current_checked = set()
        for i in range(self.calc_layers_list.count()):
            item = self.calc_layers_list.item(i)
            if item.checkState() == _qt_checked():
                current_checked.add(item.data(_qt_user_role()))
        self.calc_layers_list.clear()
        project = QgsProject.instance()
        default_ids = set(current_checked)
        if apply_defaults:
            try:
                current = self.layer_combo.currentLayer() if self.layer_combo is not None else None
                if _layer_is_usable(current):
                    default_ids.add(current.id())
            except Exception:
                pass
            if self.gbif_layer_id:
                default_ids.add(self.gbif_layer_id)
            if self.manual_layer_id:
                default_ids.add(self.manual_layer_id)

        for layer in project.mapLayers().values():
            if not self._is_probably_point_layer(layer):
                continue
            try:
                label = f"{layer.name()} ({layer.featureCount()} registros)"
                item = QListWidgetItem(label)
                item.setFlags(_qt_item_is_enabled() | _qt_item_is_selectable() | _qt_item_user_checkable())
                item.setData(_qt_user_role(), layer.id())
                item.setToolTip(f"{layer.name()} | {layer.source() if hasattr(layer, 'source') else ''}")
                item.setCheckState(_qt_checked() if layer.id() in default_ids else _qt_unchecked())
                self.calc_layers_list.addItem(item)
            except RuntimeError:
                continue

    def check_current_calc_layer(self):
        if self.calc_layers_list is None:
            return
        self.refresh_calc_layers(apply_defaults=False)
        try:
            fallback = self.layer_combo.currentLayer() if self.layer_combo is not None else None
            current = self.iface.activeLayer() or fallback
            current_id = current.id() if _layer_is_usable(current) else ""
        except Exception:
            current_id = ""
        if not current_id:
            return
        for i in range(self.calc_layers_list.count()):
            item = self.calc_layers_list.item(i)
            if item.data(_qt_user_role()) == current_id:
                item.setCheckState(_qt_checked())

    def check_all_calc_layers(self):
        if self.calc_layers_list is None:
            return
        self.refresh_calc_layers(apply_defaults=False)
        for i in range(self.calc_layers_list.count()):
            self.calc_layers_list.item(i).setCheckState(_qt_checked())

    def uncheck_all_calc_layers(self):
        if self.calc_layers_list is None:
            return
        for i in range(self.calc_layers_list.count()):
            self.calc_layers_list.item(i).setCheckState(_qt_unchecked())

    def _on_tab_changed(self, index):
        try:
            if self.tabs.tabText(index).startswith("3."):
                self.refresh_calc_layers(apply_defaults=False)
        except Exception:
            pass

    def _selected_calc_layers(self):
        layers = []
        project = QgsProject.instance()
        if self.calc_layers_list is not None:
            for i in range(self.calc_layers_list.count()):
                item = self.calc_layers_list.item(i)
                if item.checkState() != _qt_checked():
                    continue
                layer = project.mapLayer(item.data(_qt_user_role()))
                if _layer_is_usable(layer) and layer not in layers:
                    layers.append(layer)
        return layers

    def _iucn_criterion_b_inputs(self):
        # Se conserva por compatibilidad interna, pero la versión actual solo
        # informa la categoría orientativa según umbrales de AOO y EOO.
        return {}

    # ------------------------------------------------------------- manual ops
    def _get_existing_manual_layer(self):
        """Return the current layer for user-added points, or None if it was removed."""
        if _layer_is_usable(self.manual_layer):
            return self.manual_layer

        self.manual_layer = None
        project = QgsProject.instance()

        if self.manual_layer_id:
            layer = project.mapLayer(self.manual_layer_id)
            if _layer_is_usable(layer):
                self.manual_layer = layer
                return layer
            self.manual_layer_id = None

        for layer in project.mapLayers().values():
            try:
                if layer.customProperty("aoo_eoo_gbif_pro_layer_type") == "manual_points" and _layer_is_usable(layer):
                    self.manual_layer = layer
                    self.manual_layer_id = layer.id()
                    return layer
            except RuntimeError:
                continue
        return None

    def _ensure_manual_layer(self):
        layer = self._get_existing_manual_layer()
        if layer is None:
            layer = create_manual_layer()
            layer.setCustomProperty("aoo_eoo_gbif_pro_layer_type", "manual_points")
            QgsProject.instance().addMapLayer(layer)
            self.manual_layer = layer
            self.manual_layer_id = layer.id()
        self.manual_status.setText(f"Capa para tus puntos activa: {_layer_name(layer)}")
        return layer

    def create_manual_points_layer(self):
        layer = self._ensure_manual_layer()
        if self.layer_combo is not None:
            self.layer_combo.setLayer(layer)
        self._log(f"Capa para puntos añadidos preparada: {_layer_name(layer)}")
        self.refresh_calc_layers(apply_defaults=True)

    def activate_manual_point_tool(self):
        layer = self._ensure_manual_layer()
        if not _layer_is_usable(layer):
            QMessageBox.warning(self, "Puntos añadidos", "No se ha podido crear una capa válida para tus puntos.")
            return
        self.previous_map_tool = self.iface.mapCanvas().mapTool()
        self.manual_tool = ManualPointTool(self.iface.mapCanvas(), self._manual_point_clicked)
        self.iface.mapCanvas().setMapTool(self.manual_tool)
        self._log("Haz clic en el mapa para añadir un punto. Se abrirá un formulario antes de guardarlo.")

    def activate_manual_delete_tool(self):
        layer = self._ensure_manual_layer()
        if not _layer_is_usable(layer):
            QMessageBox.warning(self, "Puntos añadidos", "No se ha encontrado una capa válida de puntos propios para borrar.")
            return
        self.previous_map_tool = self.iface.mapCanvas().mapTool()
        self.manual_tool = ManualPointTool(self.iface.mapCanvas(), self._manual_delete_clicked)
        self.iface.mapCanvas().setMapTool(self.manual_tool)
        self._log("Haz clic cerca de un punto propio para eliminarlo de la capa.")

    def activate_manual_delete_area_tool(self):
        layer = self._ensure_manual_layer()
        if not _layer_is_usable(layer):
            QMessageBox.warning(self, "Puntos añadidos", "No se ha encontrado una capa válida de puntos propios para borrar.")
            return
        self.previous_map_tool = self.iface.mapCanvas().mapTool()
        self.manual_tool = ManualRectangleTool(self.iface.mapCanvas(), self._manual_delete_area_selected)
        self.iface.mapCanvas().setMapTool(self.manual_tool)
        self._log("Arrastra un rectángulo en el mapa para eliminar los puntos propios incluidos en esa área.")

    def _manual_delete_area_selected(self, rect):
        layer = self._get_existing_manual_layer()
        if not _layer_is_usable(layer):
            QMessageBox.warning(self, "Puntos añadidos", "La capa de puntos propios no existe.")
            return
        canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        target_crs = layer.crs()
        try:
            selection_geom = QgsGeometry.fromRect(rect)
            if canvas_crs != target_crs:
                selection_geom.transform(QgsCoordinateTransform(canvas_crs, target_crs, QgsProject.instance()))
        except Exception as exc:
            QMessageBox.warning(self, "Eliminar puntos", f"No se pudo transformar el área de selección: {exc}")
            return

        # If the user only clicks, the rectangle can be nearly empty. Expand it
        # slightly so it still behaves like an easier point-deletion tool.
        try:
            bbox = selection_geom.boundingBox()
            if bbox.width() == 0 and bbox.height() == 0:
                center = bbox.center()
                tol = 0.001 if target_crs.isGeographic() else max(20.0, self.iface.mapCanvas().mapUnitsPerPixel() * 20.0)
                selection_geom = QgsGeometry.fromRect(QgsRectangle(center.x() - tol, center.y() - tol, center.x() + tol, center.y() + tol))
        except Exception:
            pass

        fids = []
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            try:
                if selection_geom.intersects(geom):
                    fids.append(feat.id())
            except Exception:
                continue

        if not fids:
            QMessageBox.information(self, "Puntos añadidos", "No hay puntos propios dentro del área seleccionada.")
            return

        reply = QMessageBox.question(
            self,
            "Eliminar puntos",
            f"¿Eliminar {len(fids)} punto(s) propio(s) dentro del área seleccionada?",
            _messagebox_yes() | _messagebox_no(),
            _messagebox_no(),
        )
        if reply != _messagebox_yes():
            return

        was_editing = layer.isEditable()
        if not was_editing:
            layer.startEditing()
        ok = layer.deleteFeatures(fids)
        if not was_editing:
            layer.commitChanges()
        layer.updateExtents()
        layer.triggerRepaint()
        self.iface.mapCanvas().refresh()
        if ok:
            self.refresh_calc_layers(apply_defaults=False)
            self._log(f"Puntos propios eliminados por área: {len(fids)}")
        else:
            QMessageBox.warning(self, "Puntos añadidos", "QGIS no pudo eliminar los puntos seleccionados.")

    def _manual_delete_clicked(self, point, button):
        layer = self._get_existing_manual_layer()
        if not _layer_is_usable(layer):
            QMessageBox.warning(self, "Puntos añadidos", "La capa de puntos propios no existe.")
            return
        canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        target_crs = layer.crs()
        click_point = QgsPointXY(point)
        if canvas_crs != target_crs:
            click_point = QgsCoordinateTransform(canvas_crs, target_crs, QgsProject.instance()).transform(click_point)
        click_geom = QgsGeometry.fromPointXY(click_point)
        best_fid = None
        best_dist = None
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            try:
                dist = geom.distance(click_geom)
            except Exception:
                continue
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_fid = feat.id()
        # Manual layer is EPSG:4326 by default; 0.0005° is roughly 55 m.
        tol = 0.0005 if target_crs.isGeographic() else max(10.0, self.iface.mapCanvas().mapUnitsPerPixel() * 12.0)
        if best_fid is None or best_dist is None or best_dist > tol:
            QMessageBox.information(self, "Puntos añadidos", "No se ha encontrado ningún punto propio suficientemente cerca del clic.")
            return
        reply = QMessageBox.question(
            self,
            "Eliminar punto",
            "¿Eliminar el punto propio más cercano al clic?",
            _messagebox_yes() | _messagebox_no(),
            _messagebox_no(),
        )
        if reply != _messagebox_yes():
            return
        was_editing = layer.isEditable()
        if not was_editing:
            layer.startEditing()
        ok = layer.deleteFeature(best_fid)
        if not was_editing:
            layer.commitChanges()
        layer.updateExtents()
        layer.triggerRepaint()
        if ok:
            self.refresh_calc_layers(apply_defaults=False)
            self._log(f"Punto propio eliminado: feature id {best_fid}")
        else:
            QMessageBox.warning(self, "Puntos añadidos", "QGIS no pudo eliminar el punto seleccionado.")

    def stop_manual_point_tool(self):
        if self.previous_map_tool is not None:
            self.iface.mapCanvas().setMapTool(self.previous_map_tool)
        self.manual_tool = None
        self._log("Modo de añadir puntos finalizado.")

    def _manual_point_clicked(self, point, button):
        layer = self._ensure_manual_layer()
        if not _layer_is_usable(layer):
            QMessageBox.warning(self, "Puntos añadidos", "La capa para tus puntos ya no existe. Vuelve a crearla.")
            return
        dialog = ManualFeatureDialog(self, default_name=self.scientific_name.text().strip())
        if _dialog_exec(dialog) == _dialog_accepted():
            canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            add_manual_feature(layer, point, canvas_crs, dialog.values())
            self._log("Punto añadido a la capa de tus puntos.")
            self.refresh_calc_layers(apply_defaults=True)

    def add_manual_point_by_coordinates(self):
        layer = self._ensure_manual_layer()
        if not _layer_is_usable(layer):
            QMessageBox.warning(self, "Puntos añadidos", "No se ha podido crear una capa válida para tus puntos.")
            return
        dialog = ManualFeatureDialog(self, default_name=self.scientific_name.text().strip(), show_coordinates=True)
        if _dialog_exec(dialog) == _dialog_accepted():
            values = dialog.values()
            lat = values.get("decimalLatitude")
            lon = values.get("decimalLongitude")
            if abs(float(lat)) < 1e-12 and abs(float(lon)) < 1e-12:
                QMessageBox.warning(self, "Coordenadas", "Las coordenadas 0,0 no son válidas para este punto.")
                return
            add_manual_feature(layer, QgsPointXY(float(lon), float(lat)), QgsCoordinateReferenceSystem("EPSG:4326"), values)
            if self.layer_combo is not None:
                self.layer_combo.setLayer(layer)
            self._log("Punto añadido por coordenadas a la capa de tus puntos.")
            self.refresh_calc_layers(apply_defaults=True)

    def import_manual_points_csv(self):
        layer = self._ensure_manual_layer()
        if not _layer_is_usable(layer):
            QMessageBox.warning(self, "Puntos añadidos", "No se ha podido crear una capa válida para importar el CSV.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Importar CSV de puntos", "", "CSV (*.csv);;Todos los archivos (*.*)")
        if not path:
            return
        try:
            count = import_manual_csv(layer, path, default_scientific_name=self.scientific_name.text().strip())
            self._log(f"Puntos importados desde CSV: {count}")
            self.refresh_calc_layers(apply_defaults=True)
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Error al importar CSV", str(exc))
            self._log(f"ERROR CSV: {exc}")

    def import_point_shapefile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar shapefile de puntos",
            "",
            "Shapefile (*.shp);;GeoPackage (*.gpkg);;GeoJSON (*.geojson *.json);;Todos los archivos (*.*)",
        )
        if not path:
            return
        name = os.path.splitext(os.path.basename(path))[0] or "puntos_importados"
        layer = QgsVectorLayer(path, name, "ogr")
        if not _layer_is_usable(layer):
            QMessageBox.critical(self, "Importar shapefile", "No se ha podido abrir la capa vectorial seleccionada.")
            self._log(f"ERROR shapefile: no se pudo abrir {path}")
            return
        if not self._is_probably_point_layer(layer):
            QMessageBox.warning(
                self,
                "Importar shapefile",
                "La capa seleccionada no parece ser una capa de puntos. Solo se importan capas de puntos o multipuntos.",
            )
            return
        try:
            if layer.featureCount() == 0:
                QMessageBox.warning(self, "Importar shapefile", "La capa seleccionada no contiene puntos.")
                return
        except Exception:
            pass
        layer.setCustomProperty("aoo_eoo_gbif_pro_layer_type", "imported_point_file")
        layer.setCustomProperty("aoo_eoo_gbif_pro_import_source", path)
        QgsProject.instance().addMapLayer(layer)
        try:
            self.iface.setActiveLayer(layer)
        except Exception:
            pass
        self.refresh_calc_layers(apply_defaults=False)
        if self.calc_layers_list is not None:
            for i in range(self.calc_layers_list.count()):
                item = self.calc_layers_list.item(i)
                if item.data(_qt_user_role()) == layer.id():
                    item.setCheckState(_qt_checked())
                    break
        self._log(f"Shapefile/capa vectorial de puntos importada: {_layer_name(layer)} ({layer.featureCount()} registros). Marcada para el cálculo en la pestaña 3.")
        try:
            self.iface.messageBar().pushSuccess("Importar shapefile", f"Capa de puntos importada: {_layer_name(layer)}")
        except Exception:
            pass

    def save_manual_csv_template(self):
        default_name = "LRN_GBIF_plantilla_puntos_propios.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Guardar plantilla base CSV", default_name, "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        header = [
            "scientificName", "decimalLatitude", "decimalLongitude", "eventDate",
            "data_citation", "data_origin", "data_curator", "evidence", "identifier",
            "coordinateUncertaintyInMeters", "review_status", "include_for_aoo_eoo", "notes"
        ]
        example = [
            self.scientific_name.text().strip() or "Nombre científico", "42.000000", "-6.000000",
            "2026-01-01", "", "trabajo de campo", "Curador del dato",
            "pliego/testigo", "ID_001", "25", "aceptado", "sí", "comentario opcional"
        ]
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as handle:
                handle.write(",".join(header) + "\n")
                handle.write(",".join(example) + "\n")
            self._log(f"Plantilla base CSV guardada: {path}")
            try:
                self.iface.messageBar().pushSuccess("Plantilla CSV", "Plantilla base guardada.")
            except Exception:
                pass
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Error al guardar plantilla", str(exc))
            self._log(f"ERROR plantilla CSV: {exc}")


    # ----------------------------------------------------------- Point Distribution CSV
    def _ensure_last_result(self):
        if self.last_result is None:
            QMessageBox.warning(self, "Point Distribution", "Primero calcula AOO/EOO. El CSV se genera con los puntos usados en ese cálculo.")
            return None
        return self.last_result

    def _point_distribution_settings(self):
        dialog = PointDistributionSettingsDialog(self, default_name=self.scientific_name.text().strip(), default_subspecies=(self.infraspecific_epithet.text().strip() if self.assess_infraspecific.isChecked() else ""))
        if _dialog_exec(dialog) == _dialog_accepted():
            return dialog.values()
        return None

    def create_iucn_polygon_field_guide(self):
        try:
            layer = create_iucn_polygon_field_guide_layer()
            QgsProject.instance().addMapLayer(layer)
            self._log("Tabla de ayuda añadida: IUCN atributos AOO EOO campos")
            self.iface.messageBar().pushSuccess("AOO/EOO", "Tabla de ayuda de atributos IUCN para AOO/EOO añadida al proyecto.")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "AOO/EOO", str(exc))
            self._log(f"ERROR ayuda IUCN AOO/EOO: {exc}")

    def create_point_distribution_table(self):
        result = self._ensure_last_result()
        if result is None:
            return
        settings = self._point_distribution_settings()
        if settings is None:
            return
        try:
            layer = create_point_distribution_layer(result, settings)
            QgsProject.instance().addMapLayer(layer)
            self.point_distribution_layer = layer
            self._log(f"Tabla Point Distribution añadida al proyecto: {layer.featureCount()} filas.")
            self.iface.messageBar().pushSuccess("Point Distribution", "Tabla Point Distribution añadida al proyecto de QGIS.")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Point Distribution", str(exc))
            self._log(f"ERROR Point Distribution: {exc}")

    def save_point_distribution_csv(self):
        result = self._ensure_last_result()
        if result is None:
            return
        settings = self._point_distribution_settings()
        if settings is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar CSV Point Distribution", "point_distribution.csv", "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            count = write_point_distribution_csv(result, settings, path)
            self._log(f"CSV Point Distribution guardado: {path} ({count} filas)")
            self.iface.messageBar().pushSuccess("Point Distribution", f"CSV guardado con {count} filas.")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Point Distribution", str(exc))
            self._log(f"ERROR al guardar CSV Point Distribution: {exc}")

    def create_point_distribution_shapefile_layer(self):
        result = self._ensure_last_result()
        if result is None:
            return
        settings = self._point_distribution_settings()
        if settings is None:
            return
        try:
            layer = create_point_distribution_shapefile_layer(result, settings)
            QgsProject.instance().addMapLayer(layer)
            self._log(f"Capa Point Distribution añadida al proyecto: {layer.featureCount()} puntos.")
            self.iface.messageBar().pushSuccess("Point Distribution", "Capa Point Distribution añadida al proyecto de QGIS.")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Point Distribution", str(exc))
            self._log(f"ERROR capa Point Distribution: {exc}")

    def save_point_distribution_shapefile(self):
        result = self._ensure_last_result()
        if result is None:
            return
        settings = self._point_distribution_settings()
        if settings is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar Shapefile Point Distribution", "point_distribution.shp", "Shapefile (*.shp)")
        if not path:
            return
        if not path.lower().endswith(".shp"):
            path += ".shp"
        try:
            count = write_point_distribution_shapefile(result, settings, path)
            self._log(f"Shapefile Point Distribution guardado: {path} ({count} puntos)")
            self.iface.messageBar().pushSuccess("Point Distribution", f"Shapefile guardado con {count} puntos.")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Point Distribution", str(exc))
            self._log(f"ERROR al guardar Shapefile Point Distribution: {exc}")

    # ----------------------------------------------------------- GBIF DOI
    def _gbif_ids_from_result(self, result):
        ids = []
        seen = set()
        manual_or_non_gbif = 0
        missing_gbif_id = 0
        for rec in (result or {}).get("used_records", []):
            origin = (rec.get("data_origin") or rec.get("origin") or "").strip().upper()
            gbif_id = str(rec.get("gbifID") or "").strip()
            if gbif_id:
                if gbif_id not in seen:
                    ids.append(gbif_id)
                    seen.add(gbif_id)
            else:
                if origin == "GBIF":
                    missing_gbif_id += 1
                else:
                    manual_or_non_gbif += 1
        return ids, manual_or_non_gbif, missing_gbif_id

    def _gbif_ids_for_download(self):
        result = self._ensure_last_result()
        if result is None:
            return None
        ids, manual_count, missing_count = self._gbif_ids_from_result(result)
        if not ids:
            QMessageBox.warning(
                self,
                "Cita GBIF",
                "No hay gbifID en los puntos usados. El DOI oficial de GBIF solo puede generarse para registros GBIF con gbifID."
            )
            return None
        return ids, manual_count, missing_count

    def _gbif_ids_preview_text(self, result):
        ids, manual_count, missing_count = self._gbif_ids_from_result(result)
        preview_ids = "\n".join(ids[:250])
        if len(ids) > 250:
            preview_ids += f"\n... ({len(ids) - 250} gbifID más)"
        return (
            f"Registros GBIF con gbifID usados en el cálculo: {len(ids)}\n"
            f"Puntos propios/no GBIF usados: {manual_count}\n"
            f"Registros GBIF usados sin gbifID: {missing_count}\n\n"
            "Lista gbifID que se enviará a GBIF para crear la descarga oficial:\n"
            f"{preview_ids if preview_ids else '[sin gbifID]'}\n\n"
            "No tienes que pegar esta lista en ninguna web si usas el botón ‘Solicitar descarga oficial y DOI’. "
            "El plugin la enviará a GBIF mediante la API de descargas. La copia al portapapeles sirve para revisión o archivo."
        )

    def _refresh_gbif_doi_tab(self):
        if self.last_result is not None and hasattr(self, "gbif_download_result"):
            self.gbif_download_result.setPlainText(self._gbif_ids_preview_text(self.last_result))

    def prepare_gbif_download_ids(self):
        result = self._ensure_last_result()
        if result is None:
            return
        ids_info = self._gbif_ids_for_download()
        if ids_info is None:
            return
        self.gbif_download_result.setPlainText(self._gbif_ids_preview_text(result))
        ids, manual_count, missing_count = ids_info
        self._log(f"Preparados {len(ids)} gbifID para descarga oficial GBIF. Puntos no GBIF: {manual_count}; GBIF sin gbifID: {missing_count}.")
        self.iface.messageBar().pushSuccess("Cita GBIF", f"Preparados {len(ids)} gbifID para solicitar DOI oficial a GBIF.")

    def copy_gbif_ids(self):
        ids_info = self._gbif_ids_for_download()
        if ids_info is None:
            return
        ids, _, _ = ids_info
        QApplication.clipboard().setText("\n".join(ids))
        self._log("gbifID usados copiados al portapapeles.")
        self.iface.messageBar().pushSuccess("Cita GBIF", "gbifID copiados al portapapeles.")

    def request_gbif_occurrence_download(self):
        ids_info = self._gbif_ids_for_download()
        if ids_info is None:
            return
        ids, manual_count, missing_count = ids_info
        username = self.gbif_download_user.text().strip()
        password = self.gbif_download_password.text()
        email = self.gbif_download_email.text().strip()
        fmt = self.gbif_download_format.currentData() or "SIMPLE_CSV"
        missing = []
        if not username:
            missing.append("Usuario GBIF")
        if not password:
            missing.append("Contraseña GBIF")
        if missing:
            QMessageBox.warning(self, "Cita GBIF", "Faltan campos: " + ", ".join(missing))
            return
        if "@" in username:
            QMessageBox.warning(
                self,
                "Cita GBIF",
                "En ‘Usuario GBIF’ debes escribir el nombre de usuario de GBIF, no el correo electrónico.\n\n"
                "Ejemplo correcto: nombre_usuario_gbif\n"
                "El correo solo va en ‘Correo de notificación’."
            )
            return

        if manual_count or missing_count:
            note = (
                f"Se solicitará el DOI solo para {len(ids)} registros GBIF con gbifID.\n"
                f"Puntos propios/no GBIF usados: {manual_count}.\n"
                f"Registros GBIF usados sin gbifID: {missing_count}.\n\n"
                "Esos puntos no quedarán cubiertos por el DOI GBIF. ¿Continuar?"
            )
            confirm = QMessageBox.question(self, "Cita GBIF", note)
            try:
                yes_value = QMessageBox.Yes
            except AttributeError:
                yes_value = QMessageBox.StandardButton.Yes
            if confirm != yes_value:
                return

        try:
            key = request_occurrence_download_by_gbif_ids(
                ids,
                username=username,
                password=password,
                notification_email=email or None,
                download_format=fmt,
            )
            self.gbif_download_key = key
            self.gbif_download_key_edit.setText(key)
            self.gbif_download_result.setPlainText(
                "Solicitud enviada a GBIF.\n\n"
                f"Clave de descarga: {key}\n"
                f"Registros GBIF solicitados: {len(ids)}\n"
                f"Formato: {fmt}\n\n"
                "Todavía puede no existir DOI. Pulsa ‘Comprobar estado / DOI’ dentro de unos minutos. "
                "GBIF también enviará un correo si has indicado dirección de notificación."
            )
            self._log(f"Descarga oficial GBIF solicitada. Clave: {key}")
            self.iface.messageBar().pushSuccess("Cita GBIF", f"Solicitud enviada. Clave GBIF: {key}")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Cita GBIF", str(exc))
            self._log(f"ERROR al solicitar descarga GBIF: {exc}")

    def _citation_from_gbif_download(self, response: dict) -> str:
        citation = (response or {}).get("citation") or ""
        if citation:
            return citation
        doi = (response or {}).get("doi") or ""
        if doi:
            doi_text = str(doi).strip()
            doi_url = doi_text if doi_text.startswith("http") else f"https://doi.org/{doi_text}"
            year = datetime.now().year
            return f"GBIF.org ({year}). GBIF Occurrence Download. {doi_url}"
        return ""

    def check_gbif_occurrence_download(self):
        key = self.gbif_download_key_edit.text().strip() or self.gbif_download_key
        if not key:
            QMessageBox.warning(self, "Cita GBIF", "Introduce o solicita primero una clave de descarga GBIF.")
            return
        try:
            response = get_occurrence_download(key)
            self.gbif_download_key = key
            self.gbif_download_response = response
            status = response.get("status", "")
            doi = response.get("doi", "")
            citation = self._citation_from_gbif_download(response)
            download_link = response.get("downloadLink") or response.get("downloadUrl") or ""
            if doi:
                doi_text = str(doi).strip()
                doi_url = doi_text if doi_text.startswith("http") else f"https://doi.org/{doi_text}"
            else:
                doi_url = "[todavía no disponible]"
            result_text = (
                "Estado de la descarga GBIF\n\n"
                f"Clave: {key}\n"
                f"Estado: {status}\n"
                f"DOI: {doi_url}\n"
                f"Registros en la descarga: {response.get('numberRecords', '')}\n"
                f"Enlace de descarga: {download_link}\n\n"
                "Cita recomendada:\n"
                f"{citation if citation else '[todavía no disponible; espera a que el estado sea SUCCEEDED]'}\n\n"
                "Recuerda: esta cita cubre solo los registros GBIF incluidos en la descarga oficial."
            )
            self.gbif_download_result.setPlainText(result_text)
            if status == "SUCCEEDED" or doi:
                layer = create_gbif_occurrence_download_result_layer(response)
                QgsProject.instance().addMapLayer(layer)
                self.gbif_doi_layer = layer
                self.iface.messageBar().pushSuccess("Cita GBIF", "DOI GBIF listo y tabla añadida al proyecto.")
            else:
                self.iface.messageBar().pushMessage("Cita GBIF", f"Estado actual: {status}", level=Qgis.Info, duration=6)
            self._log(f"Estado descarga GBIF {key}: {status}; DOI: {doi}")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Cita GBIF", str(exc))
            self._log(f"ERROR al comprobar descarga GBIF: {exc}")

    def copy_gbif_citation(self):
        text = self.gbif_download_result.toPlainText() if hasattr(self, "gbif_download_result") else ""
        citation = ""
        if self.gbif_download_response:
            citation = self._citation_from_gbif_download(self.gbif_download_response)
        if not citation and "Cita recomendada:" in text:
            citation = text.split("Cita recomendada:", 1)[1].strip().split("\n\n", 1)[0].strip()
        if not citation or citation.startswith("["):
            QMessageBox.warning(self, "Cita GBIF", "Todavía no hay cita disponible. Comprueba el estado hasta que GBIF devuelva el DOI.")
            return
        QApplication.clipboard().setText(citation)
        self.iface.messageBar().pushSuccess("Cita GBIF", "Cita GBIF copiada al portapapeles.")
        self._log("Cita GBIF copiada al portapapeles.")

    def _iucn_polygon_attrs(self) -> dict:
        return {
            "sci_name": self.scientific_name.text().strip(),
            "presence": self.iucn_presence.currentData(),
            "origin": self.iucn_origin.currentData(),
            "seasonal": self.iucn_seasonal.currentData(),
            "compiler": self.iucn_compiler.text().strip(),
            "yrcompiled": self.iucn_yrcompiled.value(),
            "citation": self.iucn_citation.text().strip(),
            "subspecies": self.iucn_subspecies.text().strip() or (self.infraspecific_epithet.text().strip() if self.assess_infraspecific.isChecked() else ""),
            "subpop": "",
            "data_sens": self.iucn_data_sens.currentData(),
            "sens_comm": self.iucn_sens_comm.text().strip(),
        }

    # --------------------------------------------------------------- calculate
    def calculate(self):
        self.refresh_calc_layers(apply_defaults=False)
        layers = self._selected_calc_layers()

        if not layers:
            QMessageBox.warning(self, "Cálculo", "Marca una o varias capas de puntos en la lista de la pestaña 3 antes de calcular.")
            return

        self._log("Capas enviadas al cálculo: " + "; ".join(f"{_layer_name(layer)} ({layer.featureCount()} registros)" for layer in layers))
        max_uncert = self.max_uncertainty.value() if self.use_uncertainty_filter.isChecked() else None
        try:
            result = run_aoo_eoo(
                layers,
                analysis_crs_authid=self.analysis_crs.text().strip(),
                cell_size_m=self.cell_size.value(),
                max_uncertainty_m=max_uncert,
                include_pending_manual=self.include_pending.isChecked(),
                deduplicate=self.deduplicate.isChecked(),
                iucn_polygon_attrs=self._iucn_polygon_attrs(),
                iucn_b_inputs=self._iucn_criterion_b_inputs(),
            )
            QgsProject.instance().addMapLayer(result["used_layer"])
            QgsProject.instance().addMapLayer(result["aoo_layer"])
            if result["eoo_layer"] is not None:
                QgsProject.instance().addMapLayer(result["eoo_layer"])

            result["taxon_name"] = self.scientific_name.text().strip()
            result["taxon_key"] = self.taxon_key.text().strip()
            try:
                result["gbif_query_params"] = self._build_gbif_params()
            except Exception:
                result["gbif_query_params"] = {}
            self.last_result = result
            self._refresh_gbif_doi_tab()
            report_layers = create_report_layers(result)
            for layer in report_layers.values():
                QgsProject.instance().addMapLayer(layer)
            self._log("Cálculo finalizado. Capas y tablas añadidas al proyecto de QGIS.")
            self._log(f"  Registros usados: {result['n_used']}")
            self._log(f"  Registros excluidos: {result['n_excluded']}")
            self._log(f"  Celdas AOO ocupadas: {result['n_cells']}")
            self._log(f"  AOO: {result['aoo_km2']:.2f} km²")
            self._log(f"  EOO: {result['eoo_km2']:.2f} km²")
            iucn_b = result.get("iucn_criterion_b", {})
            if iucn_b:
                self._log(f"  Categoría orientativa por AOO: {iucn_b.get('aoo_category', 'No evaluable')}")
                self._log(f"  Categoría orientativa por EOO: {iucn_b.get('eoo_category', 'No evaluable')}")
            self._log("  Tabla añadida: AOO_EOO informe resumen")
            self._log("  Pestaña 5 actualizada con los gbifID usados para solicitar DOI oficial GBIF")
            self._log("  Tabla añadida: AOO_EOO registros no usados")
            self.iface.messageBar().pushSuccess("AOO/EOO", "Cálculo terminado. Las capas finales y tablas de informe están en el panel de capas.")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Error en cálculo AOO/EOO", str(exc))
            self._log(f"ERROR cálculo: {exc}")

# -*- coding: utf-8 -*-
"""Main QGIS plugin class."""

try:
    from qgis.PyQt.QtGui import QAction  # Qt6 / QGIS 4
except ImportError:  # pragma: no cover - Qt5 / QGIS 3
    from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtCore import Qt


def _qt_non_modal():
    """Return the non-modal enum in both Qt5 and Qt6 bindings."""
    try:
        return Qt.NonModal
    except AttributeError:
        return Qt.WindowModality.NonModal

from .dialog import AooEooDialog


class AooEooGbifPlugin:
    """Plugin controller loaded by QGIS."""

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None
        self.menu_name = "&LRN/GBIF"

    def initGui(self):  # pylint: disable=invalid-name
        self.action = QAction("LRN/GBIF", self.iface.mainWindow())
        self.action.setToolTip("LRN/GBIF: calcular AOO/EOO desde GBIF, capas QGIS y puntos añadidos")
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(self.menu_name, self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginMenu(self.menu_name, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def run(self):
        if self.dialog is None:
            self.dialog = AooEooDialog(self.iface)
            self.dialog.setWindowModality(_qt_non_modal())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

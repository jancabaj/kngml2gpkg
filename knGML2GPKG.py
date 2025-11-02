# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QTimer, QFile, QIODevice
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QApplication
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsVectorFileWriter,
    QgsWkbTypes,
    QgsMessageLog,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsDxfExport,
    Qgis
)

from .resources import *
from .ui.knGML2GPKG_dialog import knGML2GPKGDialog
import os


class knGML2GPKG:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor."""
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'knGML2GPKG_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = self.tr(u'&knGML2GPKG')
        self.first_start = None

    def tr(self, message):
        """Get the translation for a string using Qt translation API."""
        return QCoreApplication.translate('knGML2GPKG', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar."""

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/knGML2GPKG/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'knGML2GPKG'),
            callback=self.run,
            parent=self.iface.mainWindow())

        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&knGML2GPKG'),
                action)
            self.iface.removeToolBarIcon(action)

    def log(self, message, level=Qgis.Info):
        """Log message to QGIS message log"""
        QgsMessageLog.logMessage(message, 'knGML2GPKG', level)
        if hasattr(self, 'dlg') and self.dlg:
            self.dlg.log(message)

    def convert_gml_to_gpkg(self, gml_c, gml_e, output_file, output_format='GPKG'):
        """Convert 2 GML files to GPKG or DXF using QGIS API with custom transformations

        Args:
            gml_c: Path to Register C GML file
            gml_e: Path to Register E GML file
            output_file: Path to output file (.gpkg or .dxf)
            output_format: 'GPKG' or 'DXF'
        """

        # For DXF, we need to export to GPKG first (for styling), then convert to DXF
        if output_format == 'DXF':
            # Create temporary GPKG file
            temp_gpkg = output_file.replace('.dxf', '_temp.gpkg')

            # First convert to GPKG with styles
            success = self._convert_to_gpkg(gml_c, gml_e, temp_gpkg)
            if not success:
                return False

            # Then export GPKG layers to DXF
            success = self._export_gpkg_to_dxf(temp_gpkg, output_file)

            # Clean up temporary GPKG
            try:
                if os.path.exists(temp_gpkg):
                    os.remove(temp_gpkg)
                    self.log("  Removed temporary GPKG")
            except Exception as e:
                self.log(f"  Warning: Could not remove temp GPKG: {e}", Qgis.Warning)

            return success
        else:
            # Direct GPKG export
            return self._convert_to_gpkg(gml_c, gml_e, output_file)

    def _convert_to_gpkg(self, gml_c, gml_e, output_gpkg):
        """Internal method: Convert 2 GML files to 1 GPKG using QGIS API with custom transformations"""

        # Remove existing GPKG if it exists
        if os.path.exists(output_gpkg):
            try:
                os.remove(output_gpkg)
                self.log("Removed existing output file")
            except:
                pass

        target_crs = QgsCoordinateReferenceSystem('EPSG:5514')
        # Use project transform context to get accurate custom transformation
        transform_context = QgsProject.instance().transformContext()

        # Define layers to convert
        layers = [
            {'gml': gml_c, 'source': 'CadastralParcel', 'target': 'ParcelC', 'qml': 'kn_parcelC.qml'},
            {'gml': gml_e, 'source': 'CadastralParcel', 'target': 'ParcelE', 'qml': 'kn_parcelE.qml'},
            {'gml': gml_c, 'source': 'CadastralZoning', 'target': 'CadastralUnit', 'qml': 'kn_cadastralunit.qml'}
        ]

        total = len(layers)
        for idx, layer_info in enumerate(layers):
            self.dlg.set_progress(int((idx / total) * 90))
            self.log(f"Converting {layer_info['target']}...")
            QApplication.processEvents()  # Update UI

            # Load GML layer
            layer_uri = f"{layer_info['gml']}|layername={layer_info['source']}"
            layer = QgsVectorLayer(layer_uri, layer_info['target'], "ogr")

            if not layer.isValid():
                self.log(f"ERROR: Could not load {layer_info['source']}", Qgis.Critical)
                return False

            self.log(f"  Loaded {layer.featureCount()} features")
            QApplication.processEvents()

            # Export options
            save_options = QgsVectorFileWriter.SaveVectorOptions()
            save_options.driverName = 'GPKG'
            save_options.fileEncoding = 'UTF-8'
            save_options.layerName = layer_info['target']
            save_options.layerOptions = ['SPATIAL_INDEX=YES']

            # Determine file action mode (create new file or add layer to existing)
            if idx > 0 and os.path.exists(output_gpkg):
                file_action = QgsVectorFileWriter.CreateOrOverwriteLayer
            else:
                file_action = QgsVectorFileWriter.CreateOrOverwriteFile

            # For ParcelC and ParcelE, fix corrupt parcels with swapped coordinates before transformation
            if layer_info['target'] in ['ParcelC', 'ParcelE']:
                result = self.convert_parcele_with_fixes(
                    layer, output_gpkg, layer_info['target'], target_crs, transform_context, file_action
                )
                if not result:
                    return False
            else:
                # Set CRS transformation using project transform context (custom transformation)
                save_options.ct = QgsCoordinateTransform(
                    layer.crs(),
                    target_crs,
                    transform_context
                )
                save_options.actionOnExistingFile = file_action

                # Write layer
                error = QgsVectorFileWriter.writeAsVectorFormatV3(
                    layer,
                    output_gpkg,
                    transform_context,
                    save_options
                )

                if error[0] != QgsVectorFileWriter.NoError:
                    self.log(f"ERROR: {error[1]}", Qgis.Critical)
                    return False

            self.log(f"  ✓ {layer_info['target']} converted")
            QApplication.processEvents()

            # Apply style
            self.apply_style(output_gpkg, layer_info['target'], layer_info['qml'])

        # Clean up temporary .gfs files created by GDAL (replaces .gml with .gfs)
        for gml_file in [gml_c, gml_e]:
            gfs_file = os.path.splitext(gml_file)[0] + '.gfs'
            if os.path.exists(gfs_file):
                try:
                    os.remove(gfs_file)
                    self.log(f"  Removed {os.path.basename(gfs_file)}")
                except Exception as e:
                    self.log(f"  Warning: Could not remove {os.path.basename(gfs_file)}: {e}", Qgis.Warning)

        return True

    def convert_parcele_with_fixes(self, source_layer, output_gpkg, layer_name, target_crs, transform_context, file_action):
        """Convert Parcel (C or E) with fixes for corrupt parcels with swapped coordinates"""

        # Determine source CRS (some GML files don't have CRS defined)
        source_crs = source_layer.crs()
        if not source_crs.isValid():
            # Default to EPSG:4258 (ETRS89) for Slovak cadastral data
            source_crs = QgsCoordinateReferenceSystem('EPSG:4258')
            self.log(f"  ⚠ Source CRS not defined, assuming EPSG:4258", Qgis.Warning)

        self.log(f"  Source CRS: {source_crs.authid()}")
        self.log(f"  Target CRS: {target_crs.authid()}")

        # Create memory layer with MultiPolygon geometry to handle both Polygon and MultiPolygon
        memory_layer = QgsVectorLayer(
            f"MultiPolygon?crs={target_crs.authid()}",
            "temp",
            "memory"
        )

        # Add fields
        memory_layer.dataProvider().addAttributes(source_layer.fields())
        memory_layer.updateFields()

        # Create coordinate transform
        transform = QgsCoordinateTransform(source_crs, target_crs, transform_context)

        # Process features
        fixed_count = 0
        total_count = 0

        for feature in source_layer.getFeatures():
            total_count += 1
            geom = feature.geometry()

            if geom.isNull():
                new_feature = QgsFeature(memory_layer.fields())
                new_feature.setAttributes(feature.attributes())
                memory_layer.dataProvider().addFeature(new_feature)
                continue

            bbox = geom.boundingBox()

            # Check for swapped coordinates (X > 40 and Y < 40 in EPSG:4258)
            if bbox.xMinimum() > 40 and bbox.yMaximum() < 40:
                # Swap X and Y coordinates
                fixed_count += 1

                if geom.isMultipart():
                    multipolygon = geom.asMultiPolygon()
                    swapped_multipolygon = []

                    for polygon in multipolygon:
                        swapped_polygon = []
                        for ring in polygon:
                            swapped_ring = []
                            for point in ring:
                                swapped_ring.append(QgsPointXY(point.y(), point.x()))
                            swapped_polygon.append(swapped_ring)
                        swapped_multipolygon.append(swapped_polygon)

                    geom = QgsGeometry.fromMultiPolygonXY(swapped_multipolygon)
                else:
                    polygon = geom.asPolygon()
                    swapped_polygon = []
                    for ring in polygon:
                        swapped_ring = []
                        for point in ring:
                            swapped_ring.append(QgsPointXY(point.y(), point.x()))
                        swapped_polygon.append(swapped_ring)
                    geom = QgsGeometry.fromPolygonXY(swapped_polygon)

            # Transform geometry
            success = geom.transform(transform)
            if success != 0:
                self.log(f"  Warning: Transformation failed for feature {total_count}", Qgis.Warning)

            # Create new feature with memory layer's fields and transformed geometry
            new_feature = QgsFeature(memory_layer.fields())
            new_feature.setAttributes(feature.attributes())
            new_feature.setGeometry(geom)
            memory_layer.dataProvider().addFeature(new_feature)

        if fixed_count > 0:
            self.log(f"  ⚠ Fixed {fixed_count} parcels with swapped coordinates", Qgis.Warning)

        # Write memory layer to GPKG
        save_options = QgsVectorFileWriter.SaveVectorOptions()
        save_options.driverName = 'GPKG'
        save_options.fileEncoding = 'UTF-8'
        save_options.layerName = layer_name
        save_options.layerOptions = ['SPATIAL_INDEX=YES']
        save_options.actionOnExistingFile = file_action

        error = QgsVectorFileWriter.writeAsVectorFormatV3(
            memory_layer,
            output_gpkg,
            transform_context,
            save_options
        )

        if error[0] != QgsVectorFileWriter.NoError:
            self.log(f"ERROR: {error[1]}", Qgis.Critical)
            return False

        return True

    def apply_style(self, gpkg_path, layer_name, qml_file):
        """Apply QML style to GPKG layer and set as default"""

        try:
            # Load layer from GPKG
            layer = QgsVectorLayer(f"{gpkg_path}|layername={layer_name}", layer_name, "ogr")
            if not layer.isValid():
                self.log(f"  Warning: Could not load {layer_name} for styling", Qgis.Warning)
                return

            # Load style
            style_path = os.path.join(self.plugin_dir, 'styles', qml_file)
            if os.path.exists(style_path):
                msg, success = layer.loadNamedStyle(style_path)
                if success:
                    # Save to database as DEFAULT style (useAsDefault=True)
                    error_msg = layer.saveStyleToDatabase(
                        "",  # Empty name = default style
                        "",  # Empty description
                        True,  # useAsDefault = True (THIS IS KEY!)
                        ""  # Empty UI file path
                    )
                    if error_msg:
                        self.log(f"  Warning: Style save warning: {error_msg}", Qgis.Warning)
                    else:
                        self.log(f"  ✓ Style saved as default for {layer_name}")
                else:
                    self.log(f"  Warning: Could not load style: {msg}", Qgis.Warning)
        except Exception as e:
            self.log(f"  Warning: Style error: {str(e)}", Qgis.Warning)

    def _export_gpkg_to_dxf(self, gpkg_path, output_dxf):
        """Export styled GPKG layers to DXF format"""

        self.log("Exporting to DXF format...")

        # Layer names to export
        layer_names = ['ParcelC', 'ParcelE', 'CadastralUnit']

        # Load all layers with their styles
        layers = []
        for layer_name in layer_names:
            layer = QgsVectorLayer(f"{gpkg_path}|layername={layer_name}", layer_name, "ogr")
            if layer.isValid():
                layers.append(layer)
                self.log(f"  Loaded {layer_name} ({layer.featureCount()} features)")
            else:
                self.log(f"  Warning: Could not load {layer_name}", Qgis.Warning)

        if not layers:
            self.log("ERROR: No valid layers to export", Qgis.Critical)
            return False

        # DXF export options
        dxf_export = QgsDxfExport()
        dxf_export.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:5514'))
        dxf_export.setSymbologyExport(QgsDxfExport.SymbologyExport.FeatureSymbology)
        # Set scale to 500 (1:500) to ensure labels are visible (labels visible from 1:1 to 1:1000)
        dxf_export.setSymbologyScale(500.0)
        # Use simple TEXT entities instead of MTEXT, and hairline width (0) for polylines
        dxf_export.setFlags(QgsDxfExport.FlagNoMText | QgsDxfExport.FlagHairlineWidthExport)

        # Add layers to export
        dxf_layers = []
        for layer in layers:
            dxf_layers.append(QgsDxfExport.DxfLayer(layer))
        dxf_export.addLayers(dxf_layers)

        # Write DXF file using QFile
        dxf_file = QFile(output_dxf)
        if not dxf_file.open(QIODevice.WriteOnly):
            self.log(f"ERROR: Could not open {output_dxf} for writing", Qgis.Critical)
            return False

        result = dxf_export.writeToFile(dxf_file, "UTF-8")
        dxf_file.close()

        if result == QgsDxfExport.ExportResult.Success:
            self.log(f"  ✓ DXF export successful")
            return True
        else:
            error_messages = {
                QgsDxfExport.ExportResult.InvalidDeviceError: "Invalid device error",
                QgsDxfExport.ExportResult.DeviceNotWritableError: "Device not writable",
                QgsDxfExport.ExportResult.EmptyExtentError: "Empty extent error"
            }
            error_msg = error_messages.get(result, f"Unknown error ({result})")
            self.log(f"ERROR: DXF export failed: {error_msg}", Qgis.Critical)
            return False

    def process(self):
        """Process the conversion"""

        files_c = self.dlg.selected_files_c
        files_e = self.dlg.selected_files_e
        output_folder = self.dlg.lineEdit_gpkg.text()
        output_format = self.dlg.get_output_format()  # Get selected format

        # Validate inputs
        if not files_c:
            QMessageBox.warning(self.dlg, 'Error', 'Please select Register C GML files')
            return

        if not files_e:
            QMessageBox.warning(self.dlg, 'Error', 'Please select Register E GML files')
            return

        if not output_folder:
            QMessageBox.warning(self.dlg, 'Error', 'Please select an output folder')
            return

        # Create dictionaries with basename as key
        c_dict = {os.path.basename(f): f for f in files_c}
        e_dict = {os.path.basename(f): f for f in files_e}

        # Find matching pairs
        pairs = []
        for basename in c_dict.keys():
            if basename in e_dict:
                pairs.append((c_dict[basename], e_dict[basename], basename))
            else:
                self.log(f"⚠ No matching E file for {basename}", Qgis.Warning)

        # Check for E files without C match
        for basename in e_dict.keys():
            if basename not in c_dict:
                self.log(f"⚠ No matching C file for {basename}", Qgis.Warning)

        if not pairs:
            QMessageBox.warning(self.dlg, 'Error', 'No matching GML pairs found!\nFiles must have the same name in both C and E.')
            return

        # Determine file extension
        file_ext = '.gpkg' if output_format == 'GPKG' else '.dxf'

        # Check for existing output files
        existing_files = []
        for c_path, e_path, filename in pairs:
            base_name = os.path.splitext(filename)[0]
            output_file = os.path.join(output_folder, f"{base_name}{file_ext}")
            if os.path.exists(output_file):
                existing_files.append(os.path.basename(output_file))

        # Ask user about overwriting if files exist
        if existing_files:
            file_list = '\n'.join(existing_files[:5])  # Show first 5
            if len(existing_files) > 5:
                file_list += f'\n... and {len(existing_files) - 5} more'

            reply = QMessageBox.question(
                self.dlg,
                'Overwrite existing files?',
                f'{len(existing_files)} file(s) already exist:\n\n{file_list}\n\nOverwrite them?',
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.No:
                return

        # Disable button during processing
        self.dlg.pushButton_process.setEnabled(False)
        self.dlg.set_progress(0)
        self.dlg.textEdit_log.clear()

        self.log(f"Found {len(pairs)} matching GML pairs to process")
        self.log(f"Output format: {output_format}")
        self.log("="*50)

        # Process all pairs
        total_pairs = len(pairs)
        success_count = 0
        failed_count = 0

        for idx, (c_path, e_path, filename) in enumerate(pairs):
            # Determine output path
            base_name = os.path.splitext(filename)[0]
            output_file = os.path.join(output_folder, f"{base_name}{file_ext}")

            # Log progress
            self.log(f"\n[{idx+1}/{total_pairs}] Processing {filename}...")
            self.log(f"  C: {os.path.basename(c_path)}")
            self.log(f"  E: {os.path.basename(e_path)}")
            self.log(f"  Output: {os.path.basename(output_file)}")
            QApplication.processEvents()

            # Update progress
            overall_progress = int((idx / total_pairs) * 100)
            self.dlg.set_progress(overall_progress)

            # Convert
            success = self.convert_gml_to_gpkg(c_path, e_path, output_file, output_format)

            if success:
                success_count += 1
                self.log(f"  ✓ SUCCESS")
            else:
                failed_count += 1
                self.log(f"  ✗ FAILED", Qgis.Critical)

            QApplication.processEvents()

        # Re-enable button
        self.dlg.pushButton_process.setEnabled(True)
        self.dlg.set_progress(100)

        # Summary
        self.log("="*50)
        self.log(f"COMPLETED: {success_count} successful, {failed_count} failed")

        if failed_count > 0:
            QMessageBox.warning(
                self.dlg,
                'Completed with errors',
                f'{success_count} files converted successfully\n{failed_count} files failed'
            )
            return

        # Ask to load (only for single file and GPKG format)
        if total_pairs == 1:
            if output_format == 'GPKG':
                reply = QMessageBox.question(
                    self.dlg,
                    'Success',
                    f'{output_format} created successfully! Add layers to project?',
                    QMessageBox.Yes | QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    for layer_name in ['ParcelC', 'ParcelE', 'CadastralUnit']:
                        layer = QgsVectorLayer(f"{output_file}|layername={layer_name}", layer_name, "ogr")
                        if layer.isValid():
                            QgsProject.instance().addMapLayer(layer)
                            self.log(f"Added {layer_name} to project")
            else:
                QMessageBox.information(
                    self.dlg,
                    'Success',
                    f'{output_format} file created successfully!'
                )
        else:
            QMessageBox.information(
                self.dlg,
                'Success',
                f'All {success_count} {output_format} files created successfully!'
            )

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog
        if self.first_start == True:
            self.first_start = False
            self.dlg = knGML2GPKGDialog()
            # Connect process button
            self.dlg.pushButton_process.clicked.connect(self.process)

        # Reset UI
        self.dlg.set_progress(0)
        self.dlg.textEdit_log.clear()

        # Show dialog (non-modal so it stays open)
        self.dlg.show()

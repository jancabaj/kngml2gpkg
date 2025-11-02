# -*- coding: utf-8 -*-
import os
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt, QSettings
from qgis.PyQt.QtWidgets import QFileDialog

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'knGML2GPKG_dialog_base.ui'))


class knGML2GPKGDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(knGML2GPKGDialog, self).__init__(parent)
        self.setupUi(self)

        # Settings
        self.settings = QSettings('knGML2GPKG', 'paths')

        # Store selected files
        self.selected_files_c = []
        self.selected_files_e = []

        # Connect browse buttons for default folders
        self.pushButton_browseDefaultC.clicked.connect(self.browse_default_c)
        self.pushButton_browseDefaultE.clicked.connect(self.browse_default_e)

        # Connect browse buttons for file selection
        self.pushButton_browseC.clicked.connect(self.browse_gml_c)
        self.pushButton_browseE.clicked.connect(self.browse_gml_e)
        self.pushButton_browseGPKG.clicked.connect(self.browse_gpkg)

        # Connect action buttons
        self.pushButton_close.clicked.connect(self.close)

        # Save settings when default paths change
        self.lineEdit_defaultC.textChanged.connect(self.save_settings)
        self.lineEdit_defaultE.textChanged.connect(self.save_settings)
        self.lineEdit_gpkg.textChanged.connect(self.save_settings)

        # Load settings
        self.load_settings()

        # Make default folder paths read-only (only editable via browse buttons)
        self.lineEdit_defaultC.setReadOnly(True)
        self.lineEdit_defaultE.setReadOnly(True)
        self.lineEdit_gpkg.setReadOnly(True)

        # Style for read-only line edits with matching focus color
        line_edit_style = """
            QLineEdit:read-only:focus {
                border: 1px solid #A8C5DB;
            }
        """
        self.lineEdit_defaultC.setStyleSheet(line_edit_style)
        self.lineEdit_defaultE.setStyleSheet(line_edit_style)
        self.lineEdit_gpkg.setStyleSheet(line_edit_style)

        self.progressBar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 3px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #A8C5DB;
            }
        """)

    def load_settings(self):
        """Load saved settings"""
        downloads_dir = os.path.join(os.path.expanduser("~"), 'Downloads')

        # Load default paths
        default_c = self.settings.value('default_c_folder', os.path.join(downloads_dir, 'SlovenskoC'))
        default_e = self.settings.value('default_e_folder', os.path.join(downloads_dir, 'SlovenskoE'))
        default_gpkg = self.settings.value('default_gpkg_folder', downloads_dir)

        self.lineEdit_defaultC.setText(default_c)
        self.lineEdit_defaultE.setText(default_e)
        self.lineEdit_gpkg.setText(default_gpkg)

        # Create output folder if it doesn't exist
        if not os.path.exists(default_gpkg):
            os.makedirs(default_gpkg)

    def save_settings(self):
        """Save settings"""
        self.settings.setValue('default_c_folder', self.lineEdit_defaultC.text())
        self.settings.setValue('default_e_folder', self.lineEdit_defaultE.text())
        self.settings.setValue('default_gpkg_folder', self.lineEdit_gpkg.text())

    def browse_default_c(self):
        """Browse for default Register C folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Default Register C Folder",
            self.lineEdit_defaultC.text() or os.path.expanduser("~")
        )
        if folder:
            self.lineEdit_defaultC.setText(folder)

    def browse_default_e(self):
        """Browse for default Register E folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Default Register E Folder",
            self.lineEdit_defaultE.text() or os.path.expanduser("~")
        )
        if folder:
            self.lineEdit_defaultE.setText(folder)

    def browse_gml_c(self):
        """Browse for Register C GML files"""
        default_folder = self.lineEdit_defaultC.text()
        if not default_folder or not os.path.exists(default_folder):
            default_folder = os.path.expanduser("~")

        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Register C GML Files (can select multiple)",
            default_folder,
            "GML Files (*.gml);;All Files (*)"
        )
        if filenames:
            self.selected_files_c = sorted(filenames)
            count = len(self.selected_files_c)
            if count == 1:
                self.label_filesC.setText(f"1 file: {os.path.basename(self.selected_files_c[0])}")
            else:
                self.label_filesC.setText(f"{count} files selected")

            # Auto-pick matching files from default Register E folder
            self.auto_pick_register_e_files()

    def auto_pick_register_e_files(self):
        """Auto-pick matching Register E files based on selected Register C files"""
        default_e_folder = self.lineEdit_defaultE.text()

        # Check if default E folder exists
        if not default_e_folder or not os.path.exists(default_e_folder):
            return

        # Find matching E files for selected C files
        matched_files = []
        for c_file in self.selected_files_c:
            basename = os.path.basename(c_file)
            e_file_path = os.path.join(default_e_folder, basename)

            # Check if matching file exists in E folder
            if os.path.exists(e_file_path):
                matched_files.append(e_file_path)

        # Update selected E files and label
        if matched_files:
            self.selected_files_e = sorted(matched_files)
            count = len(matched_files)
            if count == 1:
                self.label_filesE.setText(f"1 file: {os.path.basename(matched_files[0])}")
            else:
                self.label_filesE.setText(f"{count} files selected")
        else:
            # Clear selection if no matches found
            self.selected_files_e = []
            self.label_filesE.setText("No matching files found in default E folder")

    def browse_gml_e(self):
        """Browse for Register E GML files"""
        default_folder = self.lineEdit_defaultE.text()
        if not default_folder or not os.path.exists(default_folder):
            default_folder = os.path.expanduser("~")

        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Register E GML Files (can select multiple)",
            default_folder,
            "GML Files (*.gml);;All Files (*)"
        )
        if filenames:
            self.selected_files_e = sorted(filenames)
            count = len(self.selected_files_e)
            if count == 1:
                self.label_filesE.setText(f"1 file: {os.path.basename(self.selected_files_e[0])}")
            else:
                self.label_filesE.setText(f"{count} files selected")

    def browse_gpkg(self):
        """Browse for output folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.lineEdit_gpkg.text() or os.path.expanduser("~")
        )
        if folder:
            self.lineEdit_gpkg.setText(folder)

    def log(self, message):
        """Add message to log"""
        self.textEdit_log.append(message)

    def set_progress(self, value):
        """Set progress bar value"""
        self.progressBar.setValue(value)

    def get_output_format(self):
        """Get selected output format"""
        if self.radioButton_gpkg.isChecked():
            return 'GPKG'
        elif self.radioButton_dxf.isChecked():
            return 'DXF'
        return 'GPKG'  # Default to GPKG

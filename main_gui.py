import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QCheckBox, QPushButton, QMessageBox, QInputDialog, QLabel, QLineEdit
)
from pathlib import Path
import subprocess
import json

class VCRedistGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Visual C++ Runtime Manager')
        self.setGeometry(100, 100, 300, 400)

        layout = QVBoxLayout()

        self.include_old_versions_cb = QCheckBox('Include Old Versions (-iov)')
        layout.addWidget(self.include_old_versions_cb)

        self.verbose_cb = QCheckBox('Verbose Output (-v)')
        layout.addWidget(self.verbose_cb)

        self.silent_cb = QCheckBox('Silent Mode (-s)')
        layout.addWidget(self.silent_cb)

        self.no_cleanup_cb = QCheckBox('Skip Cleanup (-nc)')
        layout.addWidget(self.no_cleanup_cb)

        self.clean_up_cb = QCheckBox('Perform Cleanup (-c)')
        layout.addWidget(self.clean_up_cb)

        self.remove_vcredist_cb = QCheckBox('Remove vcruntimes Folder (-rv)')
        layout.addWidget(self.remove_vcredist_cb)

        self.version_cb = QCheckBox('Specify Version (-ver)')
        layout.addWidget(self.version_cb)

        self.version_input_label = QLabel('Enter Version Number:')
        layout.addWidget(self.version_input_label)

        self.version_input = QLineEdit()
        self.version_input.setEnabled(False)  # Initially disabled
        layout.addWidget(self.version_input)

        self.run_button = QPushButton('Run')
        self.run_button.clicked.connect(self.run_process)
        layout.addWidget(self.run_button)

        self.version_cb.toggled.connect(self.toggle_version_input)  # Connect checkbox to toggle input

        self.setLayout(layout)

    def toggle_version_input(self, checked):
        self.version_input.setEnabled(checked)  # Enable or disable the input based on checkbox state

    def run_process(self):
        if self.verbose_cb.isChecked() and self.silent_cb.isChecked():
            QMessageBox.warning(self, 'Conflict', 'Cannot use both Verbose and Silent modes at the same time.')
            return

        args = []
        if self.include_old_versions_cb.isChecked():
            args.append('--include-old-versions')
        if self.verbose_cb.isChecked():
            args.append('--verbose')
        if self.silent_cb.isChecked():
            args.append('--silent')
        if self.no_cleanup_cb.isChecked():
            args.append('--no-cleanup')
        if self.clean_up_cb.isChecked():
            args.append('--clean-up')
        if self.remove_vcredist_cb.isChecked():
            args.append('--remove-vcredist')
        if self.version_cb.isChecked():
            version = self.version_input.text()
            if version:
                args.append(f'--version={version}')
                if not self.check_version_exists(version):
                    QMessageBox.warning(self, 'Version Not Found', f'The specified version "{version}" does not exist.')
                    return

        # Run the main_cli.py script with the constructed arguments
        command = ['python', 'main_cli.py'] + args
        subprocess.run(command)

    def check_version_exists(self, version):
        with open('vcredists.json', 'r') as f:
            data = json.load(f)
            for runtime in data['runtimes']['x64']:
                if runtime['version'] == version:
                    return True
        return False

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = VCRedistGUI()
    gui.show()
    sys.exit(app.exec_())
#!/usr/bin/env python3
import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLineEdit, QPushButton, QLabel, 
                            QSpinBox, QDoubleSpinBox, QCheckBox, QProgressBar,
                            QFileDialog, QListWidget, QMessageBox, QScrollArea,
                            QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor, QIcon
import site_scraper

# Theme Colors
LIGHT_THEME = {
    'bg_primary': '#ffffff',
    'bg_secondary': '#f5f5f5',
    'text_primary': '#333333',
    'text_secondary': '#666666',
    'accent': '#4a90e2',
    'accent_hover': '#357abd',
    'accent_pressed': '#2d6da3',
    'border': '#ddd',
    'disabled': '#cccccc'
}

DARK_THEME = {
    'bg_primary': '#1e1e1e',
    'bg_secondary': '#2d2d2d',
    'text_primary': '#ffffff',
    'text_secondary': '#b0b0b0',
    'accent': '#4a90e2',
    'accent_hover': '#357abd',
    'accent_pressed': '#2d6da3',
    'border': '#404040',
    'disabled': '#404040'
}

class ScraperWorker(QThread):
    progress = pyqtSignal(dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, scraper):
        super().__init__()
        self.scraper = scraper

    def run(self):
        try:
            self.scraper.start()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class ModernButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.update_style()

    def update_style(self, theme=LIGHT_THEME):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme['accent']};
                color: {theme['text_primary']};
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {theme['accent_hover']};
            }}
            QPushButton:pressed {{
                background-color: {theme['accent_pressed']};
            }}
            QPushButton:disabled {{
                background-color: {theme['disabled']};
                color: {theme['text_secondary']};
            }}
        """)

class ModernLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.update_style()

    def update_style(self, theme=LIGHT_THEME):
        self.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px;
                border: 2px solid {theme['border']};
                border-radius: 6px;
                background-color: {theme['bg_primary']};
                color: {theme['text_primary']};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 2px solid {theme['accent']};
            }}
            QLineEdit:disabled {{
                background-color: {theme['disabled']};
                color: {theme['text_secondary']};
            }}
        """)

class ScraperGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.scraper = None
        self.worker = None
        self.current_theme = LIGHT_THEME
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Modern Site Scraper')
        self.setMinimumWidth(900)
        self.update_theme()

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Header with theme toggle
        header_layout = QHBoxLayout()
        title_label = QLabel('Site Scraper')
        title_label.setFont(QFont('Segoe UI', 24, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        
        self.theme_button = ModernButton('🌙 Dark Mode' if self.current_theme == LIGHT_THEME else '☀️ Light Mode')
        self.theme_button.clicked.connect(self.toggle_theme)
        header_layout.addWidget(self.theme_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(header_layout)

        # Main content frame
        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(20, 20, 20, 20)

        # URL Input
        url_layout = QHBoxLayout()
        url_label = QLabel('Website URL:')
        url_label.setMinimumWidth(120)
        self.url_input = ModernLineEdit()
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        content_layout.addLayout(url_layout)

        # Output Directory
        output_layout = QHBoxLayout()
        output_label = QLabel('Output Directory:')
        output_label.setMinimumWidth(120)
        self.output_input = ModernLineEdit()
        self.output_input.setText('./scraped_sites')
        browse_button = ModernButton('Browse')
        browse_button.clicked.connect(self.browse_directory)
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_input)
        output_layout.addWidget(browse_button)
        content_layout.addLayout(output_layout)

        # Settings Grid
        settings_layout = QHBoxLayout()
        
        # Left column
        left_column = QVBoxLayout()
        
        # Max Depth
        depth_layout = QHBoxLayout()
        depth_label = QLabel('Maximum Depth:')
        depth_label.setMinimumWidth(120)
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 10)
        self.depth_spin.setValue(3)
        depth_layout.addWidget(depth_label)
        depth_layout.addWidget(self.depth_spin)
        left_column.addLayout(depth_layout)

        # Delay
        delay_layout = QHBoxLayout()
        delay_label = QLabel('Request Delay (s):')
        delay_label.setMinimumWidth(120)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.1, 5.0)
        self.delay_spin.setValue(0.5)
        self.delay_spin.setSingleStep(0.1)
        delay_layout.addWidget(delay_label)
        delay_layout.addWidget(self.delay_spin)
        left_column.addLayout(delay_layout)

        # Threads
        threads_layout = QHBoxLayout()
        threads_label = QLabel('Number of Threads:')
        threads_label.setMinimumWidth(120)
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 20)
        self.threads_spin.setValue(5)
        threads_layout.addWidget(threads_label)
        threads_layout.addWidget(self.threads_spin)
        left_column.addLayout(threads_layout)

        settings_layout.addLayout(left_column)

        # Right column - Checkboxes
        right_column = QVBoxLayout()
        self.follow_external = QCheckBox('Follow External Links')
        self.download_images = QCheckBox('Download Images')
        self.download_css = QCheckBox('Download CSS')
        self.download_js = QCheckBox('Download JavaScript')
        self.verbose_output = QCheckBox('Verbose Output')

        # Set default states
        self.download_images.setChecked(True)
        self.download_css.setChecked(True)
        self.download_js.setChecked(True)

        right_column.addWidget(self.follow_external)
        right_column.addWidget(self.download_images)
        right_column.addWidget(self.download_css)
        right_column.addWidget(self.download_js)
        right_column.addWidget(self.verbose_output)

        settings_layout.addLayout(right_column)
        content_layout.addLayout(settings_layout)

        # File Types Section
        file_types_label = QLabel('Additional File Types')
        file_types_label.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
        content_layout.addWidget(file_types_label)
        
        self.file_types_list = QListWidget()
        self.file_types_list.setMaximumHeight(120)
        content_layout.addWidget(self.file_types_list)

        # File Type Input
        file_type_layout = QHBoxLayout()
        self.file_type_input = ModernLineEdit()
        self.file_type_input.setPlaceholderText('Enter file extension (e.g., .pdf)')
        add_type_button = ModernButton('Add')
        add_type_button.clicked.connect(self.add_file_type)
        remove_type_button = ModernButton('Remove Selected')
        remove_type_button.clicked.connect(self.remove_file_type)
        
        file_type_layout.addWidget(self.file_type_input)
        file_type_layout.addWidget(add_type_button)
        file_type_layout.addWidget(remove_type_button)
        content_layout.addLayout(file_type_layout)

        # Progress Section
        progress_frame = QFrame()
        progress_frame.setObjectName("progressFrame")
        progress_layout = QVBoxLayout(progress_frame)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat('Ready')
        self.progress_bar.setMinimumHeight(30)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel('')
        progress_layout.addWidget(self.status_label)
        
        content_layout.addWidget(progress_frame)

        # Start Button
        self.start_button = ModernButton('Start Scraping')
        self.start_button.setMinimumHeight(40)
        self.start_button.clicked.connect(self.start_scraping)
        content_layout.addWidget(self.start_button)

        layout.addWidget(content_frame)
        self.setGeometry(100, 100, 900, 800)

    def update_theme(self):
        theme = self.current_theme
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {theme['bg_secondary']};
            }}
            QWidget {{
                color: {theme['text_primary']};
            }}
            QFrame#contentFrame {{
                background-color: {theme['bg_primary']};
                border-radius: 10px;
                border: 1px solid {theme['border']};
            }}
            QFrame#progressFrame {{
                background-color: {theme['bg_secondary']};
                border-radius: 8px;
                padding: 10px;
            }}
            QSpinBox, QDoubleSpinBox {{
                padding: 5px;
                border: 2px solid {theme['border']};
                border-radius: 6px;
                background-color: {theme['bg_primary']};
                color: {theme['text_primary']};
            }}
            QListWidget {{
                background-color: {theme['bg_primary']};
                border: 2px solid {theme['border']};
                border-radius: 6px;
                padding: 5px;
            }}
            QCheckBox {{
                spacing: 8px;
                color: {theme['text_primary']};
            }}
            QProgressBar {{
                border: 2px solid {theme['border']};
                border-radius: 6px;
                text-align: center;
                background-color: {theme['bg_primary']};
            }}
            QProgressBar::chunk {{
                background-color: {theme['accent']};
                border-radius: 4px;
            }}
        """)
        
        # Update theme for custom widgets
        for widget in self.findChildren(ModernButton):
            widget.update_style(theme)
        for widget in self.findChildren(ModernLineEdit):
            widget.update_style(theme)

    def toggle_theme(self):
        self.current_theme = DARK_THEME if self.current_theme == LIGHT_THEME else LIGHT_THEME
        self.theme_button.setText('🌙 Dark Mode' if self.current_theme == LIGHT_THEME else '☀️ Light Mode')
        self.update_theme()

    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_input.setText(directory)

    def add_file_type(self):
        file_type = self.file_type_input.text().strip()
        if file_type:
            if not file_type.startswith('.'):
                file_type = '.' + file_type
            if self.file_types_list.findItems(file_type, Qt.MatchFlag.MatchExactly):
                QMessageBox.warning(self, 'Warning', 'This file type is already in the list.')
            else:
                self.file_types_list.addItem(file_type)
            self.file_type_input.clear()

    def remove_file_type(self):
        current_item = self.file_types_list.currentItem()
        if current_item:
            self.file_types_list.takeItem(self.file_types_list.row(current_item))

    def update_progress(self, data):
        total = data.get('total_pages', 0)
        downloaded = data.get('downloaded_pages', 0)
        failed = data.get('failed_pages', 0)
        
        if total > 0:
            progress = (downloaded / total) * 100
            self.progress_bar.setValue(int(progress))
            self.progress_bar.setFormat(f'Progress: {downloaded}/{total} ({failed} failed)')
            
        self.status_label.setText(f'Downloaded: {downloaded}, Failed: {failed}, Total: {total}')

    def start_scraping(self):
        if not self.url_input.text():
            QMessageBox.warning(self, 'Error', 'Please enter a website URL.')
            return

        # Disable UI elements
        self.start_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat('Starting...')

        # Get file types
        file_types = []
        for i in range(self.file_types_list.count()):
            file_types.append(self.file_types_list.item(i).text())

        # Create scraper instance
        self.scraper = site_scraper.WebScraper(
            base_url=self.url_input.text(),
            output_dir=self.output_input.text(),
            max_depth=self.depth_spin.value(),
            follow_external=self.follow_external.isChecked(),
            download_images=self.download_images.isChecked(),
            download_css=self.download_css.isChecked(),
            download_js=self.download_js.isChecked(),
            file_types=file_types,
            delay=self.delay_spin.value(),
            verbose=self.verbose_output.isChecked(),
            num_threads=self.threads_spin.value()
        )

        # Create and start worker thread
        self.worker = ScraperWorker(self.scraper)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.scraping_finished)
        self.worker.error.connect(self.scraping_error)
        self.worker.start()

    def scraping_finished(self):
        self.start_button.setEnabled(True)
        self.progress_bar.setFormat('Complete')
        QMessageBox.information(self, 'Success', 'Scraping completed successfully!')

    def scraping_error(self, error_msg):
        self.start_button.setEnabled(True)
        self.progress_bar.setFormat('Error')
        QMessageBox.critical(self, 'Error', f'An error occurred: {error_msg}')

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for a modern look
    
    # Set application-wide font
    font = QFont('Segoe UI', 9)  # Modern font
    app.setFont(font)
    
    gui = ScraperGUI()
    gui.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 
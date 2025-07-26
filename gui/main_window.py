# In clip_search/gui/main_window.py

import sys
import os
from PyQt5 import QtWidgets, QtGui, QtCore

# Import our custom modules
from .. import config
from ..core.image_engine import ImageEngine

class ImageDropLabel(QtWidgets.QLabel):
    """A custom QLabel that accepts image file drops."""
    # Define a new signal that will emit the path of the dropped file
    image_dropped = QtCore.pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.setText("Drop Query Image Here")
        self.setStyleSheet("""
            ImageDropLabel {
                border: 2px dashed #aaa;
                border-radius: 5px;
                background-color: #f0f0f0;
                color: #888;
            }
            ImageDropLabel[is_active="true"] {
                border-color: #0078d7;
                background-color: #e0eafc;
            }
        """)

    def dragEnterEvent(self, event):
        """Event handler for when a drag enters the widget."""
        # Check if the dragged data contains URLs (file paths)
        if event.mimeData().hasUrls():
            # Get the path of the first file
            file_path = event.mimeData().urls()[0].toLocalFile()
            # Check if the file is a supported image type
            from ..core.image_engine import is_image_file # Local import to avoid circular dependency
            if is_image_file(file_path):
                event.acceptProposedAction()
                self.setProperty("is_active", "true") # Set a property for styling
                self.style().polish(self) # Force a style refresh

    def dragLeaveEvent(self, event):
        """Event handler for when a drag leaves the widget."""
        self.setProperty("is_active", "false")
        self.style().polish(self)

    def dropEvent(self, event):
        """Event handler for when the item is dropped."""
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.setProperty("is_active", "false")
        self.style().polish(self)
        self.image_dropped.emit(file_path) # Emit the signal with the file path

class MainWindow(QtWidgets.QMainWindow):
    """The main application window."""

    # Define a custom signal that will carry the search results
    # This is necessary to pass complex data types (like a list) from the worker thread
    search_results_ready = QtCore.pyqtSignal(list)

    def __init__(self):
        super().__init__()

        # --- Worker Thread Setup ---
        # 1. Create an ImageEngine instance (our worker object)
        self.engine = ImageEngine()
        # 2. Create a QThread to run the worker in the background
        self.worker_thread = QtCore.QThread()
        # 3. Move the engine to the worker thread
        self.engine.moveToThread(self.worker_thread)
        # 4. Connect signals from the engine to slots in this UI thread
        self.engine.progress.connect(self.update_progress)
        self.engine.finished.connect(self.on_task_finished)
        self.engine.error.connect(self.show_error_message)
        # 5. Connect the thread's start signal to a task (e.g., loading the model)
        self.worker_thread.started.connect(self.load_initial_model)
        # 6. Start the thread. It will now run its own event loop.
        self.worker_thread.start()

        # Connect our custom signal for search results
        self.search_results_ready.connect(self.display_results)
        
        # --- UI Initialization ---
        self.current_directory = None
        self._init_ui()
        self.set_ui_enabled(False) # Disable most UI elements until a directory is chosen

    def _init_ui(self):
        """Initializes all widgets and layouts."""
        self.setWindowTitle(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.setGeometry(100, 100, *config.WINDOW_SIZE)
        self.setMinimumSize(800, 600)

        # --- Main Layout ---
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)

        # --- Top Controls Layout ---
        top_controls_layout = QtWidgets.QHBoxLayout()
        self.dir_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("folder"), "Select Image Directory")
        self.dir_button.clicked.connect(self.select_directory)
        top_controls_layout.addWidget(self.dir_button)

        self.model_combo = QtWidgets.QComboBox()
        self._populate_models_combo()
        self.model_combo.currentTextChanged.connect(self.change_model)
        top_controls_layout.addWidget(QtWidgets.QLabel("Model:"))
        top_controls_layout.addWidget(self.model_combo)
        top_controls_layout.addStretch()
        
        self.cancel_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("process-stop"), "Cancel Indexing")
        self.cancel_button.clicked.connect(self.engine.stop_indexing)
        self.cancel_button.setEnabled(False)
        top_controls_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(top_controls_layout)

        # --- Search Controls Layout ---
        search_layout = QtWidgets.QHBoxLayout()
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Enter a text description to search for...")
        self.search_input.returnPressed.connect(self.search_by_text)
        search_layout.addWidget(self.search_input)

        self.search_text_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("edit-find"), "Find by Text")
        self.search_text_button.clicked.connect(self.search_by_text)
        search_layout.addWidget(self.search_text_button)

        self.search_image_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("system-search"), "Find by Image")
        self.search_image_button.clicked.connect(self.select_and_search_by_image)
        search_layout.addWidget(self.search_image_button)
        
        search_layout.addWidget(QtWidgets.QLabel("Results:"))
        self.top_k_spinbox = QtWidgets.QSpinBox()
        self.top_k_spinbox.setRange(1, config.MAX_TOP_K)
        self.top_k_spinbox.setValue(config.DEFAULT_TOP_K)
        search_layout.addWidget(self.top_k_spinbox)
        main_layout.addLayout(search_layout)

        # --- Results Display ---
        self.results_list = QtWidgets.QListWidget()
        self.results_list.setViewMode(QtWidgets.QListWidget.IconMode)
        self.results_list.setIconSize(QtCore.QSize(config.THUMBNAIL_SIZE, config.THUMBNAIL_SIZE))
        self.results_list.setResizeMode(QtWidgets.QListWidget.Adjust)
        self.results_list.setSpacing(config.RESULTS_GRID_SPACING)
        self.results_list.itemDoubleClicked.connect(self.open_image_in_viewer)
        self.results_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.results_list.customContextMenuRequested.connect(self.show_results_context_menu)
        main_layout.addWidget(self.results_list)

        # --- Status Bar ---
        self.status_bar = self.statusBar()
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.progress_bar.hide()

    def _populate_models_combo(self):
        """Fills the model selection dropdown from config."""
        for name, details in config.AVAILABLE_MODELS.items():
            self.model_combo.addItem(name, userData=details['notes'])
        self.model_combo.setCurrentText(config.DEFAULT_MODEL_KEY)
        self.model_combo.setToolTip(config.AVAILABLE_MODELS[config.DEFAULT_MODEL_KEY]['notes'])
        self.model_combo.currentIndexChanged.connect(
            lambda: self.model_combo.setToolTip(self.model_combo.currentData())
        )

    # --- Major Action Slots ---

    @QtCore.pyqtSlot()
    def load_initial_model(self):
        """Slot to load the default model when the thread starts."""
        model_key = self.model_combo.currentText()
        QtCore.QMetaObject.invokeMethod(self.engine, "load_model", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, model_key))

    @QtCore.pyqtSlot()
    def select_directory(self):
        """Opens a dialog to select a directory and starts indexing."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Image Directory")
        if folder:
            self.current_directory = folder
            self.results_list.clear()
            self.setWindowTitle(f"{config.APP_NAME} - {os.path.basename(folder)}")
            self.set_ui_enabled(False, is_indexing=True)
            # Call the 'index_directory' method on the engine object in the worker thread
            QtCore.QMetaObject.invokeMethod(self.engine, "index_directory", QtCore.Qt.QueuedConnection,
                                            QtCore.Q_ARG(str, self.current_directory))

    @QtCore.pyqtSlot(str)
    def change_model(self, model_key):
        """Loads a new model when selected from the dropdown."""
        if not model_key: return
        self.set_ui_enabled(False)
        self.results_list.clear()
        self.engine.image_features = None # Invalidate old index
        QtCore.QMetaObject.invokeMethod(self.engine, "load_model", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, model_key))

    @QtCore.pyqtSlot()
    def search_by_text(self):
        query = self.search_input.text().strip()
        if query and self.current_directory:
            self.status_bar.showMessage(f"Searching for '{query}'...")
            self.set_ui_enabled(False)
            top_k = self.top_k_spinbox.value()
            # We need a separate function to handle the result, because search is on another thread
            self._start_search(query, top_k)

    @QtCore.pyqtSlot()
    def select_and_search_by_image(self):
        if self.current_directory:
            # We use the current directory to start the file dialog
            query, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Select Query Image", self.current_directory,
                f"Images ({' '.join(['*' + ext for ext in config.IMAGE_EXTENSIONS])})"
            )
            if query:
                query = os.path.normpath(query) # Normalize the path from the dialog
                self.status_bar.showMessage(f"Searching for images similar to {os.path.basename(query)}...")
                self.set_ui_enabled(False)
                top_k = self.top_k_spinbox.value()
                self._start_search(query, top_k)

    def _start_search(self, query, top_k):
        """
        Helper to run a search on the worker thread.
        It calls the engine's search method and ensures the result is emitted
        via the search_results_ready signal.
        """
        # This is a cleaner way to invoke a method on a worker thread
        # and have it perform a task. It's more readable than a lambda in a timer.
        QtCore.QMetaObject.invokeMethod(
            self,  # The target object to emit the final signal
            "__emit_search_results", # The method to call on this object
            QtCore.Qt.QueuedConnection, # Ensure it runs in the UI thread
            QtCore.Q_ARG(list, self.engine.search(query, top_k)) # The argument is the *result* of the search
        )

    @QtCore.pyqtSlot(list)
    def __emit_search_results(self, results):
        """Internal slot to safely emit the search results signal."""
        self.search_results_ready.emit(results)

    # --- UI Update Slots (connected to engine signals) ---

    @QtCore.pyqtSlot(list)
    def display_results(self, results):
        self.results_list.clear()
        if not results:
            self.status_bar.showMessage("No results found.", 5000)
            self.set_ui_enabled(True)
            return

        for score, path in results:
            item = QtWidgets.QListWidgetItem()
            pixmap = QtGui.QPixmap(path)
            icon = QtGui.QIcon(pixmap.scaled(config.THUMBNAIL_SIZE, config.THUMBNAIL_SIZE,
                                            QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            item.setIcon(icon)
            item.setText(f"Score: {score:.3f}")
            item.setData(QtCore.Qt.UserRole, path) # Store full path for later use
            item.setToolTip(f"{os.path.basename(path)}\nScore: {score:.3f}")
            self.results_list.addItem(item)
            
        self.status_bar.showMessage(f"Found {len(results)} results.", 5000)
        self.set_ui_enabled(True)
    
    @QtCore.pyqtSlot(QtCore.QPoint)
    def show_results_context_menu(self, pos):
        """Creates and shows a context menu when right-clicking on a result item."""
        # Get the item that was right-clicked. If the click was not on an item, do nothing.
        item = self.results_list.itemAt(pos)
        if item is None:
            return

        # Create the context menu
        context_menu = QtWidgets.QMenu(self)

        # Create the "Find More Like This" action
        find_similar_action = QtWidgets.QAction(QtGui.QIcon.fromTheme("system-search"), "Find More Like This", self)
        
        # Connect the action's 'triggered' signal to a function that will start the search.
        # We use a lambda function here to pass the specific item that was clicked.
        find_similar_action.triggered.connect(lambda: self.search_by_result_item(item))
        
        # Add the action to the menu
        context_menu.addAction(find_similar_action)

        # --- Future actions can be added here ---
        # For example, an action to open the file's containing folder.
        context_menu.addSeparator()
        open_folder_action = QtWidgets.QAction(QtGui.QIcon.fromTheme("folder"), "Open Containing Folder", self)
        open_folder_action.triggered.connect(lambda: self.open_containing_folder(item))
        context_menu.addAction(open_folder_action)


        # Show the menu at the position of the mouse click
        # The mapToGlobal function converts the widget's local coordinates to screen coordinates.
        context_menu.exec_(self.results_list.mapToGlobal(pos))

    def search_by_result_item(self, item):
        """Starts a new search using a result item as the query image."""
        # Retrieve the full file path we stored in the item's UserRole data
        query_path = item.data(QtCore.Qt.UserRole)
        
        if query_path and os.path.exists(query_path):
            self.status_bar.showMessage(f"Finding images similar to {os.path.basename(query_path)}...")
            self.set_ui_enabled(False)
            top_k = self.top_k_spinbox.value()
            
            # Reuse our existing search helper method
            self._start_search(query_path, top_k)
        else:
            self.show_error_message(f"File not found: {query_path}")

    def open_containing_folder(self, item):
        """Opens the system's file explorer to the location of the selected item."""
        path = item.data(QtCore.Qt.UserRole)
        if not path:
            return
            
        # QDesktopServices.openUrl can open local file paths.
        # We use QUrl.fromLocalFile to ensure the path format is correct for the OS.
        # To open the folder and select the file, we need a bit of platform-specific logic.
        
        # This is a more advanced way to show the file in the folder.
        # The simple way is: QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.dirname(path)))
        
        # Let's use a robust method that tries to select the file.
        import subprocess
        import sys
        
        if sys.platform == 'win32':
            subprocess.run(['explorer', '/select,', path])
        elif sys.platform == 'darwin': # macOS
            subprocess.run(['open', '-R', path])
        else: # linux
            subprocess.run(['xdg-open', os.path.dirname(path)])
            
    @QtCore.pyqtSlot(int, int, str)
    def update_progress(self, value, total, msg):
        self.status_bar.showMessage(msg)
        if total > 0:
            self.progress_bar.show()
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(value)

    @QtCore.pyqtSlot(str)
    def on_task_finished(self, msg):
        self.status_bar.showMessage(msg, 5000)
        self.progress_bar.hide()
        # Only enable the search UI if a directory has been successfully indexed
        if self.engine.image_features is not None:
            self.set_ui_enabled(True)
        else: # e.g. model finished loading but no dir indexed yet
            self.dir_button.setEnabled(True)
            self.model_combo.setEnabled(True)

    @QtCore.pyqtSlot(str)
    def show_error_message(self, msg):
        self.progress_bar.hide()
        QtWidgets.QMessageBox.critical(self, "Error", msg)
        self.set_ui_enabled(True) # Re-enable UI after error

    # --- Utility Methods ---

    def set_ui_enabled(self, enabled, is_indexing=False):
        """Enable or disable UI elements to prevent user actions during tasks."""
        self.dir_button.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        self.search_input.setEnabled(enabled)
        self.search_text_button.setEnabled(enabled)
        self.search_image_button.setEnabled(enabled)
        self.top_k_spinbox.setEnabled(enabled)
        
        # Special handling for cancel button
        self.cancel_button.setEnabled(is_indexing)
        if not is_indexing:
             self.dir_button.setEnabled(True)
             self.model_combo.setEnabled(True)


    def open_image_in_viewer(self, item):
        """Opens the selected image using the system's default viewer."""
        path = item.data(QtCore.Qt.UserRole)
        url = QtCore.QUrl.fromLocalFile(path)
        QtGui.QDesktopServices.openUrl(url)

    def closeEvent(self, event):
        """Properly shuts down the worker thread when the window is closed."""
        self.worker_thread.quit()
        self.worker_thread.wait() # Wait for the thread to finish
        event.accept()

# In clip_search/gui/main_window.py

import sys
import os
from PyQt5 import QtWidgets, QtGui, QtCore

# Import our custom modules
from clip_search import config
from clip_search.core.image_engine import ImageEngine

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
            from clip_search.core.image_engine import is_image_file # Local import to avoid circular dependency
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
        
class ThumbnailWorker(QtCore.QObject):
    """A worker that generates QListWidgetItems with thumbnails in the background."""
    finished = QtCore.pyqtSignal(list) # Signal will emit the list of generated items

    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.results = results

    @QtCore.pyqtSlot()
    def run(self):
        """Processes the search results and creates widget items."""
        items = []
        for score, path in self.results:
            try:
                pixmap = QtGui.QPixmap(path)
                icon = QtGui.QIcon(pixmap.scaled(config.THUMBNAIL_SIZE, config.THUMBNAIL_SIZE,
                                                QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                
                # We can't create a QListWidgetItem here because it's a GUI object.
                # Instead, we prepare all the data needed to create it.
                item_data = {
                    'icon': icon,
                    'text': f"Score: {score:.3f}",
                    'tooltip': f"{os.path.basename(path)}\nScore: {score:.3f}",
                    'path': path
                }
                items.append(item_data)
            except Exception as e:
                print(f"Error creating thumbnail for {path}: {e}")
        
        self.finished.emit(items)

class MainWindow(QtWidgets.QMainWindow):
    """The main application window."""

    # Define a custom signal that will carry the search results
    # This is necessary to pass complex data types (like a list) from the worker thread
    search_results_ready = QtCore.pyqtSignal(list)

    def __init__(self):
        super().__init__()
        
        self.is_first_load = True

        self.thumbnail_thread = None
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
        self._load_settings() # Restore previous session's state
        
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
        self.cancel_button.clicked.connect(self.handle_cancel_click)
        self.cancel_button.setEnabled(False)
        top_controls_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(top_controls_layout)

        # --- Search Controls Layout ---
        # --- Search Controls Layout (NEW VERSION) ---
        search_groupbox = QtWidgets.QGroupBox("Search")
        search_layout = QtWidgets.QHBoxLayout(search_groupbox)

        # Left side: Text Search
        text_search_layout = QtWidgets.QVBoxLayout()
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Enter a text description to search for...")
        self.search_input.returnPressed.connect(self.search_by_text)
        text_search_layout.addWidget(self.search_input)
        self.search_text_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("edit-find"), "Find by Text")
        self.search_text_button.clicked.connect(self.search_by_text)
        text_search_layout.addWidget(self.search_text_button)
        search_layout.addLayout(text_search_layout, stretch=3) # Give text search more space

        # Middle: Vertical Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.VLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        search_layout.addWidget(separator)

        # Right side: Image Search
        image_search_layout = QtWidgets.QVBoxLayout()
        # --- OUR NEW WIDGET IS CREATED HERE ---
        self.image_drop_zone = ImageDropLabel()
        self.image_drop_zone.setMinimumHeight(50)
        self.image_drop_zone.image_dropped.connect(self.search_by_dropped_image)
        image_search_layout.addWidget(self.image_drop_zone)

        # We still keep the button for accessibility
        self.search_image_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("system-search"), "... or Find by Clicking")
        self.search_image_button.clicked.connect(self.select_and_search_by_image)
        image_search_layout.addWidget(self.search_image_button)
        search_layout.addLayout(image_search_layout, stretch=2) # Give image search less space

        # Far Right: Results Count
        results_count_layout = QtWidgets.QVBoxLayout()
        results_count_layout.addWidget(QtWidgets.QLabel("Results:"))
        self.top_k_spinbox = QtWidgets.QSpinBox()
        self.top_k_spinbox.setRange(1, config.MAX_TOP_K)
        self.top_k_spinbox.setValue(config.DEFAULT_TOP_K)
        results_count_layout.addWidget(self.top_k_spinbox)
        results_count_layout.addStretch()
        search_layout.addLayout(results_count_layout)

        main_layout.addWidget(search_groupbox)

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
    
    @QtCore.pyqtSlot(str)
    def search_by_dropped_image(self, query_path):
        """
        Starts a search triggered by a file being dropped onto the ImageDropLabel.
        This is a slot connected to the image_dropped signal.
        """
        if not self.current_directory:
            self.show_error_message("Please select an image directory before searching.")
            return

        # We must normalize the path, as it comes from an external source
        query_path = os.path.normpath(query_path)

        if os.path.exists(query_path):
            self.status_bar.showMessage(f"Searching for images similar to {os.path.basename(query_path)}...")
            self.set_ui_enabled(False)
            top_k = self.top_k_spinbox.value()
            
            # Reuse our existing search helper method. It's that simple!
            self._start_search(query_path, top_k)
        else:
            # This case is unlikely with drag-and-drop, but good to have
            self.show_error_message(f"Dropped file not found: {query_path}")

    def _start_search(self, query, top_k):
        """
        Helper to run a search on the worker thread.
        It calls the engine's search method and ensures the result is emitted
        via the search_results_ready signal.
        """
        
        if self.engine._is_indexing:
            self.show_error_message("Please wait for the current indexing task to complete before starting a search.")
            return
    
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
    
    @QtCore.pyqtSlot()
    def handle_cancel_click(self):
        """Handles the user clicking the 'Cancel' button."""
        self.status_bar.showMessage("Cancelling task...")
        # Immediately disable the button to prevent multiple clicks
        self.cancel_button.setEnabled(False) 
        # Tell the engine to stop
        self.engine.stop_indexing()

    # --- UI Update Slots (connected to engine signals) ---

    @QtCore.pyqtSlot(list)
    def display_results(self, results):
        """
        Receives search results and starts a background worker to generate thumbnails.
        """
        self.results_list.clear()
        if not results:
            self.status_bar.showMessage("No results found.", 5000)
            self.set_ui_enabled(True)
            return

        # --- DELEGATE TO WORKER ---
        self.thumbnail_thread = QtCore.QThread()
        self.thumbnail_worker = ThumbnailWorker(results)
        self.thumbnail_worker.moveToThread(self.thumbnail_thread)
        
        # When the worker is done, call a new method to populate the list
        self.thumbnail_worker.finished.connect(self.populate_results_list)
        
        # Clean up the thread and worker when finished
        self.thumbnail_thread.started.connect(self.thumbnail_worker.run)
        self.thumbnail_worker.finished.connect(self.thumbnail_thread.quit)
        self.thumbnail_worker.finished.connect(self.thumbnail_worker.deleteLater)
        self.thumbnail_thread.finished.connect(self.thumbnail_thread.deleteLater)
        
        self.thumbnail_thread.start()
    
    @QtCore.pyqtSlot(list)
    def populate_results_list(self, items_data):
        """
        Receives the prepared thumbnail data from the worker and populates the QListWidget.
        This method runs on the main UI thread.
        """
        for data in items_data:
            item = QtWidgets.QListWidgetItem()
            item.setIcon(data['icon'])
            item.setText(data['text'])
            item.setToolTip(data['tooltip'])
            item.setData(QtCore.Qt.UserRole, data['path'])
            self.results_list.addItem(item)
            
        self.status_bar.showMessage(f"Found {len(items_data)} results.", 5000)
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
        """
        Handles cleanup and next steps after a worker task is finished.
        This is a key control-flow method.
        """
        self.status_bar.showMessage(msg, 5000)
        self.progress_bar.hide()
        self.cancel_button.setEnabled(False) # Always disable cancel on finish

        # Check if the task that just finished was a model load
        if msg == "Model loaded successfully." and self.is_first_load:
            self.is_first_load = False # Prevent this from running again
            
            # Now that the model is loaded, check if we should auto-load a directory
            settings = QtCore.QSettings("MyCompany", config.APP_NAME)
            last_directory = settings.value("last_directory")
            if last_directory and os.path.isdir(last_directory):
                print(f"Auto-indexing last directory: {last_directory}")
                self.current_directory = last_directory
                self.setWindowTitle(f"{config.APP_NAME} - {os.path.basename(last_directory)}")
                self.set_ui_enabled(False, is_indexing=True)
                QtCore.QMetaObject.invokeMethod(self.engine, "index_directory", QtCore.Qt.QueuedConnection,
                                                QtCore.Q_ARG(str, self.current_directory))
                return # Don't fall through to the set_ui_enabled below

        # This part runs after indexing or if no auto-load was needed
        if self.engine.image_features is not None:
            self.set_ui_enabled(True)
        else: # e.g., model finished loading but no dir indexed yet
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
    
    def _load_settings(self):
        """Loads and applies settings from the previous session."""
        settings = QtCore.QSettings("MyCompany", config.APP_NAME)
        
        # Restore window geometry
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event):
        """Saves settings and properly shuts down the worker thread when the window is closed."""
        # --- SAVE SETTINGS ---
        # Create a QSettings object. The arguments are your organization and application name.
        # This ensures settings are stored in a unique, standard location.
        settings = QtCore.QSettings("MyCompany", config.APP_NAME)
        
        # Save window geometry (size and position)
        settings.setValue("geometry", self.saveGeometry())
        
        # Save the last used directory, if one was selected
        if self.current_directory:
            settings.setValue("last_directory", self.current_directory)

        # --- SHUT DOWN THREAD ---
        self.worker_thread.quit()
        self.worker_thread.wait() # Wait for the thread to finish
        event.accept()

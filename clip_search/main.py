# In clip_search/main.py

import sys
from PyQt5 import QtWidgets

# Import the MainWindow class from our gui package
from clip_search.gui.main_window import MainWindow

# Define a dummy stream object for the packaged executable
class DummyStream:
    def write(self, x): pass
    def flush(self): pass

# Redirect stdout/stderr to the dummy stream if running as a bundled app
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    sys.stdout = DummyStream()
    sys.stderr = DummyStream()

def main():
    """
    The main entry point for the application.
    """
    # Create the Qt Application
    app = QtWidgets.QApplication(sys.argv)
    
    # Set a style for a more modern look, if available
    # 'Fusion' is a good cross-platform choice.
    if 'Fusion' in QtWidgets.QStyleFactory.keys():
        app.setStyle(QtWidgets.QStyleFactory.create('Fusion'))

    # Create and show the main window
    main_window = MainWindow()
    main_window.show()

    # Start the Qt event loop
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

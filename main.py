# In clip_search/main.py

import sys
from PyQt5 import QtWidgets

# Import the MainWindow class from our gui package
from .gui.main_window import MainWindow

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

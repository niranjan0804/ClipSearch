# Clip Image Search v1.1.0-rc.1

**Clip Image Search** is a powerful and intuitive desktop application that allows you to search through your local image collection using natural language descriptions and similar images. Powered by OpenAI's CLIP model, it understands the *content* of your photos, so you can find what you're looking for without relying on filenames or tags.

This tool is designed for photographers, designers, meme collectors, researchers, or anyone with a large, unorganized library of images.

---

## ✨ Features

*   **Semantic Search:** Search your images using natural language. Instead of "IMG_2025.jpg", search for "a photo of a dog on a beach at sunset".
*   **Search by Image:** Find visually similar images by providing a query image.
*   **"Find More Like This":** Right-click on any result to instantly start a new search for images like it, allowing for deep, iterative exploration.
*   **Drag-and-Drop:** Quickly use any image as a query by simply dragging and dropping it into the app.
*   **Multiple AI Models:** Choose from several models, from fast and lightweight to high-quality and powerful, to balance speed and accuracy.
*   **Responsive and Fast:** The UI never freezes, thanks to a multi-threaded architecture that performs all heavy processing in the background.
*   **Offline First:** The default search model is bundled with the application, so it works instantly out-of-the-box with no internet connection required.
*   **Smart Caching:** Indexing is fast. The application intelligently caches image features and only re-processes new or modified files.

---

## 🚀 Getting Started

### Installation

1.  Go to the [**Releases Page**](https://github.com/niranjan0804/ClipSearch/releases). <!-- IMPORTANT: Replace with your actual repo URL -->
2.  Download the `CLIP_Image_Search.exe` file from the latest release.
3.  No installation is needed! Just run the `.exe` file.

### How to Use

1.  **Select Directory:** On first launch, click "Select Image Directory" and choose the folder containing the images you want to search.
2.  **Indexing:** The application will perform a one-time indexing of your images. A progress bar will show the status. This may take some time for very large collections.
3.  **Search:** Once indexing is complete, you can:
    *   **Type a description** in the search box and click "Find by Text".
    *   **Drag and drop an image** from your computer onto the "Drop Query Image Here" box.
    *   **Click the "...or Find by Clicking"** button to select a query image using a file dialog.
4.  **Explore:** Right-click on any result to "Find More Like This" or open its location on your computer.

---

## 🛠️ Built With

*   **Python 3**
*   **PyQt5** for the graphical user interface.
*   **PyTorch** for deep learning operations.
*   **OpenCLIP** for the powerful text and image embedding models.
*   **PyInstaller** for packaging the application.

---

## Roadmap

Future versions aim to introduce even more innovative features, including:
*   A "Semantic Atlas" to visualize the entire image collection as an interactive 2D map.
*   AI-powered "Smart Albums" that automatically group photos by event and theme.

---

## License

This project is licensed under the MIT License - see the `LICENSE.txt` file for details. 

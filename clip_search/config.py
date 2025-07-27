# In clip_search/config.py

import os

# --- General Application Settings ---
APP_NAME = "CLIP Image Search"
APP_VERSION = "1.1.0"

# --- Image Processing Settings ---
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
# Batch size for encoding images. Lower this if you run out of VRAM/RAM during indexing.
BATCH_SIZE = 64

# --- Caching Settings ---
# A hidden subdirectory inside the image folder to store cache files.
CACHE_DIR_NAME = ".clip_search_cache"
# The cache filename will be generated based on the model, e.g., "cache_ViT-B-32_laion2b_s34b_b79k.pkl"

# --- Model Configuration ---
# This dictionary defines the models available in the UI.
# 'model_name' & 'pretrained': Required by the open_clip library.
# 'notes': A user-friendly description to guide the user.

AVAILABLE_MODELS = {
    # User-facing Name: {model_details}
    "Fast (ViT-B/32)": {
        "model_name": "ViT-B-32",
        "pretrained": "laion2b_s34b_b79k",
        "notes": "Good balance of speed and quality. Recommended for most users."
    },
    "High Quality (ViT-L/14)": {
        "model_name": "ViT-L-14",
        "pretrained": "laion2b_s32b_b82k",
        "notes": "Excellent quality. Requires a good GPU for reasonable speed."
    },
    "Best Quality (ViT-H/14)": {
        "model_name": "ViT-H-14",
        "pretrained": "laion2b_s32b_b79k",
        "notes": "State-of-the-art. Very slow. Requires a high-end GPU (12GB+ VRAM)."
    }
}

# Set the default model to be used when the application starts
DEFAULT_MODEL_KEY = "Fast (ViT-B/32)"

# --- UI / UX Settings ---
THUMBNAIL_SIZE = 150              # Size of the result thumbnails in pixels (width and height)
WINDOW_SIZE = (1200, 800)         # Default window size (width, height)
DEFAULT_TOP_K = 24                # Default number of search results to show
MAX_TOP_K = 200                   # Maximum number of results the user can request
RESULTS_GRID_SPACING = 10         # Space between thumbnails in the results grid

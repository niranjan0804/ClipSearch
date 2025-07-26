# In clip_search/core/image_engine.py (CORRECTED VERSION)

import os
import hashlib
import pickle
import torch
import open_clip
from PIL import Image
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot # <-- Import pyqtSlot

# Use relative import to access config from a sibling package
from .. import config

# Disable PIL's image size limit to handle large images
Image.MAX_IMAGE_PIXELS = None

def is_image_file(filename):
    """A helper function to check for valid image extensions."""
    return filename.lower().endswith(config.IMAGE_EXTENSIONS)

class ImageEngine(QObject):
    """
    Manages model loading, image indexing, caching, and searching.
    This class is designed to be moved to a separate thread to avoid freezing the UI.
    """
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.preprocess = None
        self.model_key = None
        self._is_indexing = False

        self.image_paths = []
        self.image_features = None
        self.current_directory = None

    @pyqtSlot() # <-- ADDED: Mark as a slot with no arguments
    def stop_indexing(self):
        """Signals the indexing loop to terminate early."""
        self._is_indexing = False

    @pyqtSlot(str) # <-- ADDED: Mark as a slot that takes one string argument
    def load_model(self, model_key):
        """Loads a specified CLIP model from config.py."""
        if self.model is not None and self.model_key == model_key:
            self.finished.emit(f"Model '{model_key}' is already loaded.")
            return

        try:
            self.progress.emit(0, 100, f"Loading model: {model_key}...")
            model_info = config.AVAILABLE_MODELS[model_key]
            
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                model_name=model_info['model_name'],
                pretrained=model_info['pretrained'],
                device=self.device
            )
            self.model.eval()
            self.model_key = model_key
            self.finished.emit("Model loaded successfully.")
            print(f"Model '{model_key}' loaded on {self.device}.")
        except Exception as e:
            self.error.emit(f"Failed to load model '{model_key}'.\nError: {e}")

    def _get_cache_path(self, image_folder):
        """Generates a unique cache file path based on folder and model."""
        if not self.model_key:
            return None
        model_info = config.AVAILABLE_MODELS[self.model_key]
        model_filename = f"{model_info['model_name']}_{model_info['pretrained']}"
        sanitized_filename = model_filename.replace('/', '_').replace('-', '_')
        cache_dir = os.path.join(image_folder, config.CACHE_DIR_NAME)
        return os.path.join(cache_dir, f"cache_{sanitized_filename}.pkl")

    def _get_directory_hash(self, image_folder, all_paths):
        """Computes a hash for the directory based on file names and mod times."""
        hash_obj = hashlib.md5()
        for file_path in sorted(all_paths):
            hash_obj.update(os.path.basename(file_path).encode())
            hash_obj.update(str(os.path.getmtime(file_path)).encode())
        return hash_obj.hexdigest()

    @pyqtSlot(str) # <-- ADDED: Mark as a slot that takes one string argument
    def index_directory(self, image_folder):
        """The main worker function to index all images in a directory."""
        self._is_indexing = True
        try:
            self.current_directory = image_folder
            all_paths = [os.path.join(root, file)
                         for root, _, files in os.walk(image_folder)
                         for file in files if is_image_file(file)]

            if not all_paths:
                self.error.emit("No images found in the selected directory.")
                return

            cache_path = self._get_cache_path(image_folder)
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            cached_data, directory_hash = {}, self._get_directory_hash(image_folder, all_paths)

            if os.path.exists(cache_path):
                try:
                    with open(cache_path, 'rb') as f:
                        data = pickle.load(f)
                        if data.get('directory_hash') == directory_hash:
                            cached_data = data.get('features', {})
                            self.progress.emit(0, 100, f"Loaded {len(cached_data)} features from valid cache.")
                except Exception as e:
                    print(f"Could not read cache file: {e}")

            paths_to_process = [p for p in all_paths if p not in cached_data]
            
            if paths_to_process:
                with torch.no_grad():
                    for i in range(0, len(paths_to_process), config.BATCH_SIZE):
                        if not self._is_indexing:
                            self.finished.emit("Indexing cancelled.")
                            return

                        batch_paths = paths_to_process[i:i + config.BATCH_SIZE]
                        image_tensors, valid_paths = [], []
                        for path in batch_paths:
                            try:
                                image = self.preprocess(Image.open(path).convert("RGB"))
                                image_tensors.append(image)
                                valid_paths.append(path)
                            except Exception as e:
                                print(f"Warning: Skipping corrupted image '{path}': {e}")
                        
                        if not image_tensors: continue

                        batch_features = self.model.encode_image(torch.stack(image_tensors).to(self.device))
                        batch_features /= batch_features.norm(dim=-1, keepdim=True)
                        
                        for path, feature in zip(valid_paths, batch_features.cpu()):
                            cached_data[path] = feature
                        
                        processed_count = len(cached_data)
                        self.progress.emit(processed_count, len(all_paths), f"Indexing: {processed_count}/{len(all_paths)}")

            with open(cache_path, 'wb') as f:
                pickle.dump({'features': cached_data, 'directory_hash': directory_hash}, f)
            
            self.image_paths = all_paths
            ordered_features = [cached_data.get(p) for p in self.image_paths]
            self.image_paths = [p for i, p in enumerate(self.image_paths) if ordered_features[i] is not None]
            self.image_features = torch.stack([f for f in ordered_features if f is not None]).to(self.device)
            
            self.finished.emit(f"Indexing complete. {len(self.image_paths)} images ready.")

        except Exception as e:
            self.error.emit(f"An unexpected error occurred during indexing.\nError: {e}")
        finally:
            self._is_indexing = False

    def search(self, query, top_k):
        if self.image_features is None:
            self.error.emit("Please index a directory before searching.")
            return []
        
        if isinstance(query, str) and os.path.isfile(query):
            return self._search_by_image(query, top_k)
        elif isinstance(query, str):
            return self._search_by_text(query, top_k)
        return []

    def _search_by_text(self, text_query, top_k):
        with torch.no_grad():
            text = open_clip.tokenize([text_query]).to(self.device)
            query_features = self.model.encode_text(text)
            query_features /= query_features.norm(dim=-1, keepdim=True)
            
            similarities = (self.image_features @ query_features.T).squeeze()
            top_results = torch.topk(similarities, k=min(top_k, len(self.image_paths)))
            
            return [(score.item(), self.image_paths[idx]) for score, idx in zip(top_results.values, top_results.indices)]

    def _search_by_image(self, image_path, top_k):
        try:
            query_idx = self.image_paths.index(image_path)
            query_features = self.image_features[query_idx].unsqueeze(0)
        except (ValueError, IndexError):
            self.error.emit(f"Query image '{os.path.basename(image_path)}' not found in index.")
            return []
            
        similarities = (self.image_features @ query_features.T).squeeze()
        similarities[query_idx] = -1.0
        
        top_results = torch.topk(similarities, k=min(top_k, len(self.image_paths) - 1))
        
        return [(score.item(), self.image_paths[idx]) for score, idx in zip(top_results.values, top_results.indices)]

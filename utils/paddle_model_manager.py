"""
PaddleOCR Model Manager
Downloads native Paddle models and converts them to ONNX using paddle2onnx.

All models are downloaded from official PaddleOCR repository and converted locally.
Configuration is loaded from paddle_models.yaml.
"""

import os
import asyncio
import aiohttp
import tarfile
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
from loguru import logger
import threading
import yaml


class ModelType(str, Enum):
    DETECTION = "det"
    RECOGNITION = "rec"
    CLASSIFICATION = "cls"


class DownloadStatus(str, Enum):
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    CONVERTING = "converting"
    DOWNLOADED = "downloaded"
    ERROR = "error"


@dataclass
class ModelInfo:
    """Information about a PaddleOCR model."""

    version: str
    model_type: str
    language: str
    filename: str  # Output ONNX filename
    url: str  # Download URL for .tar file
    size_mb: float  # Approximate download size
    description: str
    paddle_model_name: str  # Name of model directory inside tar
    dict_url: Optional[str] = None
    dict_filename: Optional[str] = None


# Configuration cache
_config_cache: Optional[Dict[str, Any]] = None
_config_lock = threading.Lock()


def _get_config_path() -> Path:
    """Get the path to the configuration file."""
    return Path(__file__).parent / "paddle_models.yaml"


def _load_config() -> Dict[str, Any]:
    """Load configuration from YAML file with caching."""
    global _config_cache
    with _config_lock:
        if _config_cache is not None:
            return _config_cache

        config_path = _get_config_path()
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            loaded_config = yaml.safe_load(f)
            if loaded_config is None:
                loaded_config = {}
            _config_cache = loaded_config

        # At this point _config_cache is guaranteed to be a dict
        assert _config_cache is not None
        return _config_cache


def _resolve_url(url_template: str, base_urls: Dict[str, str]) -> str:
    """Resolve URL template with base URLs."""
    result = url_template
    for key, value in base_urls.items():
        result = result.replace(f"{{{key}}}", value)
    return result


def _build_paddle_models() -> Dict[str, ModelInfo]:
    """Build PADDLE_MODELS dictionary from configuration."""
    config = _load_config()
    base_urls = config.get("base_urls", {})
    models_config = config.get("models", {})

    models: Dict[str, ModelInfo] = {}
    for key, model_data in models_config.items():
        # Resolve URLs
        url = _resolve_url(model_data.get("url", ""), base_urls)
        dict_url = model_data.get("dict_url")
        if dict_url:
            dict_url = _resolve_url(dict_url, base_urls)

        models[key] = ModelInfo(
            version=model_data.get("version", ""),
            model_type=model_data.get("model_type", ""),
            language=model_data.get("language", ""),
            filename=model_data.get("filename", ""),
            url=url,
            size_mb=model_data.get("size_mb", 0.0),
            description=model_data.get("description", ""),
            paddle_model_name=model_data.get("paddle_model_name", ""),
            dict_url=dict_url,
            dict_filename=model_data.get("dict_filename"),
        )

    return models


def _build_model_sets() -> Dict[str, List[str]]:
    """Build MODEL_SETS dictionary from configuration."""
    config = _load_config()
    sets_config = config.get("model_sets", {})

    return {key: data.get("models", []) for key, data in sets_config.items()}


def _build_model_set_info() -> Dict[str, Dict[str, Any]]:
    """Build MODEL_SET_INFO dictionary from configuration."""
    config = _load_config()
    return config.get("model_set_info", {})


def _build_ocr_presets() -> Dict[str, Dict[str, Any]]:
    """Build OCR presets from configuration."""
    config = _load_config()
    return config.get("ocr_presets", {})


# Lazy-loaded module-level references
def get_paddle_models() -> Dict[str, ModelInfo]:
    """Get all available Paddle models."""
    return _build_paddle_models()


def get_model_sets() -> Dict[str, List[str]]:
    """Get model sets for easy selection."""
    return _build_model_sets()


def get_model_set_info() -> Dict[str, Dict[str, Any]]:
    """Get model set metadata for UI."""
    return _build_model_set_info()


# Legacy compatibility - these will be computed on first access
PADDLE_MODELS: Dict[str, ModelInfo] = {}
MODEL_SETS: Dict[str, List[str]] = {}
MODEL_SET_INFO: Dict[str, Dict[str, Any]] = {}


def _ensure_loaded() -> None:
    """Ensure configuration is loaded into module-level variables."""
    global PADDLE_MODELS, MODEL_SETS, MODEL_SET_INFO
    if not PADDLE_MODELS:
        PADDLE_MODELS.update(_build_paddle_models())
    if not MODEL_SETS:
        MODEL_SETS.update(_build_model_sets())
    if not MODEL_SET_INFO:
        MODEL_SET_INFO.update(_build_model_set_info())


class PaddleModelManager:
    """Manager for downloading and converting PaddleOCR models to ONNX."""

    def __init__(self, model_dir: Path = Path("models/paddle-ocr")):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._temp_dir = self.model_dir / "_temp"
        self._download_progress: Dict[str, Dict] = {}
        self._download_lock = threading.Lock()
        # Ensure config is loaded
        _ensure_loaded()

    def get_model_path(self, model_key: str) -> Path:
        """Get the path where a model should be stored."""
        _ensure_loaded()
        if model_key not in PADDLE_MODELS:
            raise ValueError(f"Unknown model: {model_key}")
        return self.model_dir / PADDLE_MODELS[model_key].filename

    def is_model_downloaded(self, model_key: str) -> bool:
        """Check if a model is already downloaded and converted."""
        try:
            model_path = self.get_model_path(model_key)
            if not model_path.exists():
                return False
            return model_path.stat().st_size > 10 * 1024  # At least 10KB
        except ValueError:
            return False

    def get_model_status(self, model_key: str) -> Dict:
        """Get the status of a model."""
        _ensure_loaded()
        if model_key not in PADDLE_MODELS:
            return {"error": f"Unknown model: {model_key}"}

        model_info = PADDLE_MODELS[model_key]
        model_path = self.get_model_path(model_key)

        with self._download_lock:
            if model_key in self._download_progress:
                progress = self._download_progress[model_key]
                return {
                    "model_key": model_key,
                    "status": progress.get("status", DownloadStatus.DOWNLOADING.value),
                    "progress": progress.get("progress", 0),
                    "downloaded_mb": progress.get("downloaded_mb", 0),
                    "total_mb": model_info.size_mb,
                    "info": asdict(model_info),
                }

        if self.is_model_downloaded(model_key):
            actual_size = model_path.stat().st_size / (1024 * 1024)
            return {
                "model_key": model_key,
                "status": DownloadStatus.DOWNLOADED.value,
                "progress": 100,
                "downloaded_mb": actual_size,
                "total_mb": model_info.size_mb,
                "path": str(model_path),
                "info": asdict(model_info),
            }

        return {
            "model_key": model_key,
            "status": DownloadStatus.NOT_DOWNLOADED.value,
            "progress": 0,
            "downloaded_mb": 0,
            "total_mb": model_info.size_mb,
            "info": asdict(model_info),
        }

    def get_all_models_status(self) -> List[Dict]:
        """Get status of all available models."""
        _ensure_loaded()
        return [self.get_model_status(key) for key in PADDLE_MODELS.keys()]

    async def download_model(self, model_key: str) -> Dict:
        """Download and convert a model to ONNX."""
        _ensure_loaded()
        if model_key not in PADDLE_MODELS:
            return {"error": f"Unknown model: {model_key}", "success": False}

        model_info = PADDLE_MODELS[model_key]

        with self._download_lock:
            if model_key in self._download_progress:
                current_status = self._download_progress[model_key].get(
                    "status", "unknown"
                )
                return {
                    "error": f"Already downloading (status: {current_status})",
                    "success": False,
                }
            self._download_progress[model_key] = {
                "status": DownloadStatus.DOWNLOADING.value,
                "progress": 0,
                "downloaded_mb": 0,
            }

        tar_path = None
        try:
            # Create temp directory
            self._temp_dir.mkdir(parents=True, exist_ok=True)
            tar_path = self._temp_dir / f"{model_key}.tar"

            # Download tar file
            logger.info(f"Downloading model: {model_key} from {model_info.url}")
            success = await self._download_file(
                model_info.url, tar_path, model_key, model_info.size_mb
            )

            if not success:
                return {
                    "error": f"Download failed for {model_key} from {model_info.url}",
                    "success": False,
                }

            # Update status to converting
            with self._download_lock:
                self._download_progress[model_key]["status"] = (
                    DownloadStatus.CONVERTING.value
                )
                self._download_progress[model_key]["progress"] = 80

            # Extract and convert
            logger.info(f"Converting model: {model_key}")
            output_path = self.model_dir / model_info.filename
            success = await self._extract_and_convert(
                tar_path, model_info.paddle_model_name, output_path, model_key
            )

            if not success:
                return {"error": "Conversion failed", "success": False}

            # Download dictionary if needed
            if model_info.dict_url and model_info.dict_filename:
                dict_path = self.model_dir / model_info.dict_filename
                if not dict_path.exists():
                    await self._download_file(
                        model_info.dict_url, dict_path, f"{model_key}_dict", 0.1
                    )

            logger.info(f"Successfully downloaded and converted: {model_key}")
            return {
                "success": True,
                "message": f"Downloaded {model_info.filename}",
                "path": str(output_path),
            }

        except Exception as e:
            logger.error(f"Error downloading model {model_key}: {e}")
            return {"error": str(e), "success": False}
        finally:
            with self._download_lock:
                if model_key in self._download_progress:
                    del self._download_progress[model_key]
            # Cleanup temp files
            try:
                if tar_path is not None and tar_path.exists():
                    tar_path.unlink()
            except (NameError, OSError):
                pass

    async def _download_file(
        self, url: str, dest_path: Path, progress_key: str, expected_size_mb: float
    ) -> bool:
        """Download a file with progress tracking."""
        try:
            timeout = aiohttp.ClientTimeout(total=3600, connect=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.info(f"Starting download: {url}")
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(
                            f"HTTP {response.status} for {url}: {response.reason}"
                        )
                        return False

                    total_size = int(response.headers.get("content-length", 0))
                    downloaded = 0
                    logger.info(f"Download size: {total_size / (1024 * 1024):.1f} MB")

                    with open(dest_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded += len(chunk)

                            with self._download_lock:
                                if progress_key in self._download_progress:
                                    downloaded_mb = downloaded / (1024 * 1024)
                                    if total_size > 0:
                                        progress = int((downloaded / total_size) * 70)
                                    else:
                                        progress = int(
                                            (downloaded_mb / expected_size_mb) * 70
                                        )
                                    self._download_progress[progress_key][
                                        "progress"
                                    ] = min(progress, 70)
                                    self._download_progress[progress_key][
                                        "downloaded_mb"
                                    ] = downloaded_mb

                    logger.info(f"Download complete: {dest_path}")
                    return True

        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return False

    async def _extract_and_convert(
        self, tar_path: Path, model_name: str, output_path: Path, progress_key: str
    ) -> bool:
        """Extract tar and convert to ONNX."""
        extract_dir = self._temp_dir / progress_key
        try:
            extract_dir.mkdir(parents=True, exist_ok=True)

            # Extract
            with tarfile.open(tar_path, "r") as tar:
                tar.extractall(extract_dir)

            # Find model directory
            paddle_model_dir = extract_dir / model_name
            if not paddle_model_dir.exists():
                # Try to find it by looking for model files
                for item in extract_dir.rglob("*.pdmodel"):
                    paddle_model_dir = item.parent
                    break
                # Also try to find PaddleX 3.0 format (.json)
                if not paddle_model_dir.exists():
                    for item in extract_dir.rglob("inference.json"):
                        paddle_model_dir = item.parent
                        break

            if not paddle_model_dir.exists():
                logger.error(f"Model directory not found: {model_name}")
                return False

            # Find model files - support both old (.pdmodel) and new (.json) formats
            model_file = None
            params_file = None
            json_file = None

            for f in paddle_model_dir.iterdir():
                if f.suffix == ".pdmodel" or f.name == "inference.pdmodel":
                    model_file = f
                elif f.suffix == ".pdiparams" or f.name == "inference.pdiparams":
                    params_file = f
                elif f.name == "inference.json":
                    json_file = f

            # Determine which format to use
            use_new_format = False
            if not model_file and json_file:
                # PaddleX 3.0 / Paddle 3.0 format - use inference.json
                use_new_format = True
                logger.info(f"Using Paddle 3.0 format (inference.json)")
            elif not model_file:
                logger.error("No .pdmodel or inference.json file found")
                return False

            # Convert using paddle2onnx
            if use_new_format:
                # Paddle 3.0 format: explicitly specify model_filename as inference.json
                cmd = [
                    "paddle2onnx",
                    "--model_dir",
                    str(paddle_model_dir),
                    "--model_filename",
                    "inference.json",
                    "--save_file",
                    str(output_path),
                    "--opset_version",
                    "14",
                    "--enable_onnx_checker",
                    "True",
                ]
                if params_file:
                    cmd.extend(["--params_filename", params_file.name])
            else:
                # Traditional format: specify model_filename as .pdmodel
                assert model_file is not None  # Already checked above
                cmd = [
                    "paddle2onnx",
                    "--model_dir",
                    str(paddle_model_dir),
                    "--model_filename",
                    model_file.name,
                    "--save_file",
                    str(output_path),
                    "--opset_version",
                    "14",
                    "--enable_onnx_checker",
                    "True",
                ]
                if params_file:
                    cmd.extend(["--params_filename", params_file.name])

            logger.info(f"Running paddle2onnx conversion: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                logger.error(f"paddle2onnx failed: {result.stderr}")
                return False

            with self._download_lock:
                if progress_key in self._download_progress:
                    self._download_progress[progress_key]["progress"] = 95

            return output_path.exists() and output_path.stat().st_size > 1000

        except Exception as e:
            logger.error(f"Conversion error: {e}")
            return False
        finally:
            if extract_dir.exists():
                shutil.rmtree(extract_dir, ignore_errors=True)

    async def download_model_set(self, set_name: str) -> Dict:
        """Download a set of models."""
        _ensure_loaded()
        if set_name not in MODEL_SETS:
            return {"error": f"Unknown model set: {set_name}", "success": False}

        results = []
        for model_key in MODEL_SETS[set_name]:
            if not self.is_model_downloaded(model_key):
                result = await self.download_model(model_key)
                results.append({model_key: result})
            else:
                results.append(
                    {model_key: {"success": True, "message": "Already downloaded"}}
                )

        success = all(r[list(r.keys())[0]].get("success", False) for r in results)
        return {"success": success, "results": results}

    def delete_model(self, model_key: str) -> Dict:
        """Delete a downloaded model."""
        _ensure_loaded()
        if model_key not in PADDLE_MODELS:
            return {"error": f"Unknown model: {model_key}", "success": False}

        model_path = self.get_model_path(model_key)
        model_info = PADDLE_MODELS[model_key]

        try:
            if model_path.exists():
                model_path.unlink()

            if model_info.dict_filename:
                dict_path = self.model_dir / model_info.dict_filename
                if dict_path.exists():
                    dict_path.unlink()

            return {"success": True, "message": f"Deleted {model_info.filename}"}
        except Exception as e:
            return {"error": str(e), "success": False}


# Singleton
_manager: Optional[PaddleModelManager] = None


def get_paddle_model_manager(
    model_dir: Path = Path("models/paddle-ocr"),
) -> PaddleModelManager:
    """Get or create the PaddleModelManager instance."""
    global _manager
    if _manager is None:
        _manager = PaddleModelManager(model_dir)
    return _manager


def get_available_models() -> Dict:
    """Get all available models."""
    _ensure_loaded()
    return {
        "models": {key: asdict(info) for key, info in PADDLE_MODELS.items()},
        "model_sets": MODEL_SETS,
    }


def get_model_sets_with_info() -> List[Dict[str, Any]]:
    """Get model sets with metadata for UI."""
    _ensure_loaded()
    result = []
    for set_key, models in MODEL_SETS.items():
        info = MODEL_SET_INFO.get(set_key, {})
        total_size = sum(PADDLE_MODELS[m].size_mb for m in models if m in PADDLE_MODELS)
        result.append(
            {
                "key": set_key,
                "name": info.get("name", set_key),
                "description": info.get("description", ""),
                "models_desc": info.get("models_desc", ""),
                "badge": info.get("badge"),
                "badge_type": info.get("badge_type"),
                "order": info.get("order", 99),
                "models": models,
                "total_size_mb": round(total_size, 1),
            }
        )
    result.sort(key=lambda x: x["order"])
    return result


def get_downloaded_models(
    model_dir: Path = Path("models/paddle-ocr"),
) -> List[Dict[str, Any]]:
    """Get list of downloaded models."""
    _ensure_loaded()
    manager = get_paddle_model_manager(model_dir)
    return [
        manager.get_model_status(key)
        for key in PADDLE_MODELS.keys()
        if manager.is_model_downloaded(key)
    ]


def get_ocr_model_presets() -> Dict[str, Dict[str, Any]]:
    """Get OCR model presets for configuration."""
    return _build_ocr_presets()


def get_rec_model_dict_mapping() -> Dict[str, str]:
    """
    Get mapping from recognition model filename to its associated dictionary filename.
    Returns a dict like: {'en_PP-OCRv3_rec_infer.onnx': 'en_dict.txt', ...}
    """
    _ensure_loaded()
    mapping: Dict[str, str] = {}
    for model_info in PADDLE_MODELS.values():
        if model_info.model_type == "rec" and model_info.dict_filename:
            mapping[model_info.filename] = model_info.dict_filename
    return mapping


def get_available_dictionaries(
    model_dir: Path = Path("models/paddle-ocr"),
) -> List[Dict[str, Any]]:
    """
    Get list of available dictionary files (both downloaded and defined).
    Returns info about each dictionary including whether it exists.
    """
    _ensure_loaded()
    model_dir = Path(model_dir)

    # Collect all unique dictionaries from model definitions
    dict_info: Dict[str, Dict[str, Any]] = {}
    for model_key, model_info in PADDLE_MODELS.items():
        if model_info.model_type == "rec" and model_info.dict_filename:
            if model_info.dict_filename not in dict_info:
                dict_path = model_dir / model_info.dict_filename
                dict_info[model_info.dict_filename] = {
                    "filename": model_info.dict_filename,
                    "exists": dict_path.exists(),
                    "language": model_info.language,
                    "associated_models": [],
                }
            dict_info[model_info.dict_filename]["associated_models"].append(
                model_info.filename
            )

    return list(dict_info.values())


def reload_config() -> None:
    """Reload configuration from YAML file (useful for development)."""
    global _config_cache, PADDLE_MODELS, MODEL_SETS, MODEL_SET_INFO
    with _config_lock:
        _config_cache = None
    PADDLE_MODELS.clear()
    MODEL_SETS.clear()
    MODEL_SET_INFO.clear()
    _ensure_loaded()

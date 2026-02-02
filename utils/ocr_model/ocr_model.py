"""
OCR Model wrapper for PP-OCRv3/v4/v5.
Provides a simplified interface for text detection and recognition.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

import numpy as np
from loguru import logger

from .ppocr_onnx.ppocr_onnx import PaddleOcrONNX


@dataclass
class OCRConfig:
    """OCR configuration with defaults for PP-OCRv3/v4/v5 compatibility."""

    # Model directory
    model_dir: str = "models/paddle-ocr"

    # Detection config (DB algorithm)
    det_model: str = "en_PP-OCRv3_det_infer.onnx"
    det_limit_side_len: int = 960
    det_limit_type: str = "max"
    det_box_type: str = "quad"
    det_db_thresh: float = 0.3
    det_db_box_thresh: float = 0.6
    det_db_unclip_ratio: float = 1.5
    det_db_score_mode: str = "fast"
    use_dilation: bool = False
    max_batch_size: int = 10

    # Recognition config (SVTR_LCNet/CTC)
    rec_model: str = "en_PP-OCRv3_rec_infer.onnx"
    rec_image_shape: str = "3, 48, 320"
    rec_char_dict: str = "en_dict.txt"
    rec_batch_num: int = 6
    use_space_char: bool = True
    drop_score: float = 0.5

    # Classification config (optional)
    cls_enabled: bool = False
    cls_model: str = "ch_ppocr_mobile_v2.0_cls_infer.onnx"
    cls_image_shape: str = "3, 48, 192"
    cls_batch_num: int = 6
    cls_thresh: float = 0.9
    cls_label_list: List[str] = None

    def __post_init__(self):
        if self.cls_label_list is None:
            self.cls_label_list = ["0", "180"]


class _ArgsProxy:
    """
    Proxy class that exposes config as attributes.
    Avoids the complex _DictDotNotation approach.
    """

    def __init__(self, model_root: Path, config: OCRConfig, use_gpu: bool):
        self.use_gpu = use_gpu
        self.use_onnx = True
        self.benchmark = False

        # Detection params
        self.det_algorithm = "DB"
        self.det_model_dir = str(model_root / config.det_model)
        self.det_limit_side_len = config.det_limit_side_len
        self.det_limit_type = config.det_limit_type
        self.det_box_type = config.det_box_type
        self.det_db_thresh = config.det_db_thresh
        self.det_db_box_thresh = config.det_db_box_thresh
        self.det_db_unclip_ratio = config.det_db_unclip_ratio
        self.det_db_score_mode = config.det_db_score_mode
        self.use_dilation = config.use_dilation
        self.max_batch_size = config.max_batch_size

        # Recognition params
        self.rec_algorithm = "SVTR_LCNet"
        self.rec_model_dir = str(model_root / config.rec_model)
        self.rec_image_shape = config.rec_image_shape
        self.rec_batch_num = config.rec_batch_num
        self.rec_char_dict_path = str(model_root / config.rec_char_dict)
        self.use_space_char = config.use_space_char
        self.drop_score = config.drop_score

        # Classification params
        self.use_angle_cls = config.cls_enabled
        self.cls_model_dir = str(model_root / config.cls_model)
        self.cls_image_shape = config.cls_image_shape
        self.cls_batch_num = config.cls_batch_num
        self.cls_thresh = config.cls_thresh
        self.label_list = config.cls_label_list

        # Output params
        self.save_crop_res = False


class OCRModel:
    """
    High-level OCR model interface.

    Compatible with PP-OCRv3, PP-OCRv4, and PP-OCRv5 models.
    All versions use the same DB detection and SVTR_LCNet recognition algorithms.
    """

    def __init__(
        self,
        model_root_dir: Optional[Path] = None,
        device: str = "cuda",
        ocr_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize OCR model.

        Parameters
        ----------
        model_root_dir : Path, optional
            Path to the model directory. Defaults to "models/paddle-ocr".
        device : str, optional
            Device to use ("cuda" or "cpu"). Defaults to "cuda".
        ocr_config : dict, optional
            OCR configuration dictionary. Supports keys:
            - det: Detection config (model, limit_side_len, db_thresh, etc.)
            - rec: Recognition config (model, char_dict, image_shape, etc.)
            - cls: Classification config (enabled, model, etc.)
        """
        # Build config from defaults and user overrides
        self.config = self._build_config(ocr_config or {})

        # Set model root directory
        if model_root_dir is not None:
            self.model_root_dir = Path(model_root_dir)
        else:
            self.model_root_dir = Path(self.config.model_dir)

        self.device = device
        use_gpu = device == "cuda"

        # Create args proxy and initialize OCR engine
        args = _ArgsProxy(self.model_root_dir, self.config, use_gpu)
        self.paddleocr = PaddleOcrONNX(args)

    def _build_config(self, user_config: Dict[str, Any]) -> OCRConfig:
        """Build OCRConfig from user configuration dict."""
        config = OCRConfig()

        # Apply model_dir
        if "model_dir" in user_config:
            config.model_dir = user_config["model_dir"]

        # Apply detection config
        det_cfg = user_config.get("det", {})
        if "model" in det_cfg:
            config.det_model = det_cfg["model"]
        if "limit_side_len" in det_cfg:
            config.det_limit_side_len = det_cfg["limit_side_len"]
        if "limit_type" in det_cfg:
            config.det_limit_type = det_cfg["limit_type"]
        if "box_type" in det_cfg:
            config.det_box_type = det_cfg["box_type"]
        if "db_thresh" in det_cfg:
            config.det_db_thresh = det_cfg["db_thresh"]
        if "db_box_thresh" in det_cfg:
            config.det_db_box_thresh = det_cfg["db_box_thresh"]
        if "db_unclip_ratio" in det_cfg:
            config.det_db_unclip_ratio = det_cfg["db_unclip_ratio"]
        if "db_score_mode" in det_cfg:
            config.det_db_score_mode = det_cfg["db_score_mode"]
        if "use_dilation" in det_cfg:
            config.use_dilation = det_cfg["use_dilation"]
        if "max_batch_size" in det_cfg:
            config.max_batch_size = det_cfg["max_batch_size"]

        # Apply recognition config
        rec_cfg = user_config.get("rec", {})
        logger.info(f"DEBUG: rec_cfg in _build_config: {rec_cfg}")
        if "model" in rec_cfg:
            config.rec_model = rec_cfg["model"]
        if "image_shape" in rec_cfg:
            config.rec_image_shape = rec_cfg["image_shape"]
        if "char_dict" in rec_cfg:
            config.rec_char_dict = rec_cfg["char_dict"]
            logger.info(f"DEBUG: Updated char_dict to {config.rec_char_dict}")
        if "batch_num" in rec_cfg:
            config.rec_batch_num = rec_cfg["batch_num"]
        if "use_space_char" in rec_cfg:
            config.use_space_char = rec_cfg["use_space_char"]
        if "drop_score" in rec_cfg:
            config.drop_score = rec_cfg["drop_score"]

        # Apply classification config
        cls_cfg = user_config.get("cls", {})
        if "enabled" in cls_cfg:
            config.cls_enabled = cls_cfg["enabled"]
        if "model" in cls_cfg:
            config.cls_model = cls_cfg["model"]
        if "image_shape" in cls_cfg:
            config.cls_image_shape = cls_cfg["image_shape"]
        if "batch_num" in cls_cfg:
            config.cls_batch_num = cls_cfg["batch_num"]
        if "thresh" in cls_cfg:
            config.cls_thresh = cls_cfg["thresh"]
        if "label_list" in cls_cfg:
            config.cls_label_list = cls_cfg["label_list"]

        return config

    def __call__(
        self, image: np.ndarray
    ) -> Tuple[Optional[List], Optional[List], Dict[str, float]]:
        """
        Perform OCR on the image.

        Parameters
        ----------
        image : np.ndarray
            Input image (BGR format from cv2.imread)

        Returns
        -------
        Tuple containing:
            - boxes: List of detected text boxes (N, 4, 2) or None
            - texts: List of (text, confidence) tuples or None
            - time_dict: Processing time for each stage
        """
        return self.paddleocr(image)

    def get_current_config(self) -> Dict[str, Any]:
        """Get the current OCR configuration as a dictionary."""
        return {
            "model_dir": str(self.model_root_dir),
            "device": self.device,
            "det": {
                "model": self.config.det_model,
                "limit_side_len": self.config.det_limit_side_len,
                "db_thresh": self.config.det_db_thresh,
                "db_box_thresh": self.config.det_db_box_thresh,
                "db_unclip_ratio": self.config.det_db_unclip_ratio,
            },
            "rec": {
                "model": self.config.rec_model,
                "char_dict": self.config.rec_char_dict,
                "image_shape": self.config.rec_image_shape,
                "drop_score": self.config.drop_score,
            },
            "cls": {
                "enabled": self.config.cls_enabled,
                "model": self.config.cls_model,
            },
        }

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Get the default OCR configuration."""
        default = OCRConfig()
        return {
            "model_dir": default.model_dir,
            "det": {
                "model": default.det_model,
                "limit_side_len": default.det_limit_side_len,
                "limit_type": default.det_limit_type,
                "box_type": default.det_box_type,
                "db_thresh": default.det_db_thresh,
                "db_box_thresh": default.det_db_box_thresh,
                "db_unclip_ratio": default.det_db_unclip_ratio,
                "db_score_mode": default.det_db_score_mode,
                "use_dilation": default.use_dilation,
                "max_batch_size": default.max_batch_size,
            },
            "rec": {
                "model": default.rec_model,
                "image_shape": default.rec_image_shape,
                "char_dict": default.rec_char_dict,
                "batch_num": default.rec_batch_num,
                "use_space_char": default.use_space_char,
                "drop_score": default.drop_score,
            },
            "cls": {
                "enabled": default.cls_enabled,
                "model": default.cls_model,
                "image_shape": default.cls_image_shape,
                "batch_num": default.cls_batch_num,
                "thresh": default.cls_thresh,
                "label_list": default.cls_label_list,
            },
        }
"""
PaddleOCR wrapper for PP-OCRv3/v4/v5.
Provides OCR functionality using ONNX inference.
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from .base import OCRBase
from utils import OCRModel


class PaddleOCR(OCRBase):
    """
    PaddleOCR engine wrapper.
    Compatible with PP-OCRv3, PP-OCRv4, and PP-OCRv5 models.
    """

    def init(self, cfg: dict):
        """
        Initialize PaddleOCR with configuration.

        Parameters
        ----------
        cfg : dict
            OCR configuration dictionary containing:
            - device: 'cuda' or 'cpu'
            - model_dir: path to models directory
            - det: detection model config (model, db_thresh, etc.)
            - rec: recognition model config (model, char_dict, etc.)
            - cls: classification model config (enabled, model, etc.)
        """
        model_dir = cfg.get("model_dir", "models/paddle-ocr")
        device = cfg.get("device", "cuda")

        # Build OCR config from cfg
        ocr_config = {"model_dir": model_dir}

        # Pass through det, rec, cls configs if present
        for key in ["det", "rec", "cls"]:
            if key in cfg:
                ocr_config[key] = cfg[key]

        self.ocr_model = OCRModel(
            model_root_dir=Path(model_dir), device=device, ocr_config=ocr_config
        )
        self.cfg = cfg

    def get_config(self) -> Dict[str, Any]:
        """Get current OCR configuration."""
        return self.ocr_model.get_current_config()

    def reload(self, cfg: dict):
        """Reload OCR model with new configuration."""
        self.init(cfg)

    def get_all_text(self, layout):
        """
        Extract text from all text-like layout elements.

        Parameters
        ----------
        layout : list
            List of layout elements with image and type attributes.

        Returns
        -------
        layout : list
            Updated layout with text and line_cnt attributes.
        """
        for line in layout:
            if line.type in ["text", "list", "title"]:
                image = line.image
                boxes, texts, _ = self.get_text(image)

                if texts is not None and len(texts) > 0:
                    # Extract text strings
                    text_strs = [t[0] for t in texts]
                    text = " ".join(text_strs)
                    clean_text = re.sub(r"\n|\t", " ", text)
                    line.text = clean_text

                    # Count lines based on y-coordinate changes
                    if boxes is not None:
                        lasty = 0
                        cnt = 0
                        for box in boxes:
                            if box[0][1] > lasty:
                                cnt += 1
                                lasty = box[2][1]
                        line.line_cnt = cnt
                    else:
                        line.line_cnt = 1
                else:
                    line.text = ""
                    line.line_cnt = 0

        return layout

    def get_text(
        self, image
    ) -> Tuple[Optional[List], Optional[List], Dict[str, float]]:
        """
        Perform OCR on image.

        Parameters
        ----------
        image : np.ndarray
            Input image (BGR format)

        Returns
        -------
        Tuple containing:
            - boxes: List of detected text boxes or None
            - texts: List of (text, confidence) tuples or None
            - time_dict: Processing time for each stage
        """
        return self.ocr_model(image)

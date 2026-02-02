"""
Simplified PaddleOCR ONNX Inference Engine.
Compatible with PP-OCRv3, PP-OCRv4, and PP-OCRv5 models.

This simplified version removes unused algorithms and only supports:
- Detection: DB algorithm
- Recognition: SVTR_LCNet with CTC decoder
- Classification: Optional text direction classifier
"""

import copy
import time
from typing import List, Tuple, Optional, Dict

import cv2
import numpy as np

from .tools.infer import predict_cls, predict_det, predict_rec
from .tools.infer.utility import get_minarea_rect_crop, get_rotate_crop_image


class PaddleOcrONNX:
    """
    Simplified PaddleOCR ONNX inference class.

    Supports PP-OCRv3, PP-OCRv4, and PP-OCRv5 models with:
    - DB detection algorithm
    - SVTR_LCNet recognition (CTC-based)
    - Optional direction classification
    """

    def __init__(self, args):
        """
        Initialize OCR pipeline.

        Args:
            args: Configuration object with model paths and parameters
        """
        args.use_onnx = True
        args.benchmark = False

        self.text_detector = predict_det.TextDetector(args)
        self.text_recognizer = predict_rec.TextRecognizer(args)
        self.use_angle_cls = args.use_angle_cls
        self.drop_score = args.drop_score

        if self.use_angle_cls:
            self.text_classifier = predict_cls.TextClassifier(args)

        self.args = args
        self.crop_image_res_index = 0

    def __call__(
        self, img: np.ndarray, cls: bool = True
    ) -> Tuple[Optional[List], Optional[List], Dict[str, float]]:
        """
        Perform OCR on image.

        Args:
            img: Input image (BGR format)
            cls: Whether to apply text direction classification

        Returns:
            Tuple of:
                - filter_boxes: Detected text boxes or None
                - filter_rec_res: Recognition results (text, score) or None
                - time_dict: Processing time for each stage
        """
        time_dict = {"det": 0, "rec": 0, "cls": 0, "all": 0}
        start = time.time()
        ori_im = img.copy()

        # Text detection
        dt_boxes, elapse = self.text_detector(img)
        time_dict["det"] = elapse

        if dt_boxes is None or len(dt_boxes) == 0:
            return None, None, time_dict

        # Sort boxes top-to-bottom, left-to-right
        dt_boxes = self.sorted_boxes(dt_boxes)

        # Crop text regions
        img_crop_list = []
        for bno in range(len(dt_boxes)):
            tmp_box = copy.deepcopy(dt_boxes[bno])
            if self.args.det_box_type == "quad":
                img_crop = get_rotate_crop_image(ori_im, tmp_box)
            else:
                img_crop = get_minarea_rect_crop(ori_im, tmp_box)
            img_crop_list.append(img_crop)

        # Optional text direction classification
        if self.use_angle_cls and cls:
            img_crop_list, angle_list, elapse = self.text_classifier(img_crop_list)
            time_dict["cls"] = elapse

        # Text recognition
        rec_res, elapse = self.text_recognizer(img_crop_list)
        time_dict["rec"] = elapse

        # Filter by confidence score
        filter_boxes, filter_rec_res = [], []
        for box, rec_result in zip(dt_boxes, rec_res):
            text, score = rec_result
            if score >= self.drop_score:
                filter_boxes.append(box)
                filter_rec_res.append(rec_result)

        time_dict["all"] = time.time() - start
        return filter_boxes, filter_rec_res, time_dict

    def sorted_boxes(self, dt_boxes: np.ndarray) -> List[np.ndarray]:
        """
        Sort text boxes in reading order (top-to-bottom, left-to-right).

        Args:
            dt_boxes: Detected text boxes with shape (N, 4, 2)

        Returns:
            Sorted list of text boxes
        """
        num_boxes = dt_boxes.shape[0]
        sorted_boxes = sorted(dt_boxes, key=lambda x: (x[0][1], x[0][0]))
        _boxes = list(sorted_boxes)

        # Fine-tune sorting for boxes on the same line
        for i in range(num_boxes - 1):
            for j in range(i, -1, -1):
                # If boxes are roughly on same line (y difference < 10 pixels)
                # and box[j+1] is to the left of box[j], swap them
                if (
                    abs(_boxes[j + 1][0][1] - _boxes[j][0][1]) < 10
                    and _boxes[j + 1][0][0] < _boxes[j][0][0]
                ):
                    _boxes[j], _boxes[j + 1] = _boxes[j + 1], _boxes[j]
                else:
                    break

        return _boxes

    def draw_crop_rec_res(self, output_dir: str, img_crop_list: List, rec_res: List):
        """Save cropped images for debugging (optional)."""
        import os

        os.makedirs(output_dir, exist_ok=True)
        for bno in range(len(img_crop_list)):
            cv2.imwrite(
                os.path.join(
                    output_dir, f"img_crop_{bno + self.crop_image_res_index}.jpg"
                ),
                img_crop_list[bno],
            )
        self.crop_image_res_index += len(img_crop_list)

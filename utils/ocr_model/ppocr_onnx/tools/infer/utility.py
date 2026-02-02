# Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Simplified utility functions for PP-OCRv3/v4/v5.
Removed unused algorithms and parameters.
"""

import argparse
import os
import sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import math
import random
from typing import Tuple, List, Optional


def str2bool(v):
    """Convert string to boolean."""
    return v.lower() in ("true", "t", "1")


def init_args():
    """Initialize arguments for OCR inference."""
    parser = argparse.ArgumentParser()

    # ===== Prediction Engine =====
    parser.add_argument("--use_gpu", type=str2bool, default=True)
    parser.add_argument("--gpu_id", type=int, default=0)

    # ===== Text Detector (DB algorithm only) =====
    parser.add_argument("--image_dir", type=str)
    parser.add_argument("--page_num", type=int, default=0)
    parser.add_argument("--det_algorithm", type=str, default="DB")
    parser.add_argument("--det_model_dir", type=str)
    parser.add_argument("--det_limit_side_len", type=float, default=960)
    parser.add_argument("--det_limit_type", type=str, default="max")
    parser.add_argument("--det_box_type", type=str, default="quad")

    # DB parameters
    parser.add_argument("--det_db_thresh", type=float, default=0.3)
    parser.add_argument("--det_db_box_thresh", type=float, default=0.6)
    parser.add_argument("--det_db_unclip_ratio", type=float, default=1.5)
    parser.add_argument("--max_batch_size", type=int, default=10)
    parser.add_argument("--use_dilation", type=str2bool, default=False)
    parser.add_argument("--det_db_score_mode", type=str, default="fast")

    # ===== Text Recognizer (SVTR_LCNet/CTC only) =====
    parser.add_argument("--rec_algorithm", type=str, default="SVTR_LCNet")
    parser.add_argument("--rec_model_dir", type=str)
    parser.add_argument("--rec_image_shape", type=str, default="3, 48, 320")
    parser.add_argument("--rec_batch_num", type=int, default=6)
    parser.add_argument("--max_text_length", type=int, default=25)
    parser.add_argument(
        "--rec_char_dict_path", type=str, default="./ppocr/utils/ppocr_keys_v1.txt"
    )
    parser.add_argument("--use_space_char", type=str2bool, default=True)
    parser.add_argument("--drop_score", type=float, default=0.5)

    # ===== Text Classifier =====
    parser.add_argument("--use_angle_cls", type=str2bool, default=False)
    parser.add_argument("--cls_model_dir", type=str)
    parser.add_argument("--cls_image_shape", type=str, default="3, 48, 192")
    parser.add_argument("--label_list", type=list, default=["0", "180"])
    parser.add_argument("--cls_batch_num", type=int, default=6)
    parser.add_argument("--cls_thresh", type=float, default=0.9)

    # ===== Output =====
    parser.add_argument("--draw_img_save_dir", type=str, default="./inference_results")
    parser.add_argument("--save_crop_res", type=str2bool, default=False)
    parser.add_argument("--crop_res_save_dir", type=str, default="./output")
    parser.add_argument("--vis_font_path", type=str, default="./doc/fonts/simfang.ttf")

    # ===== Performance =====
    parser.add_argument("--warmup", type=str2bool, default=False)
    parser.add_argument("--benchmark", type=str2bool, default=False)
    parser.add_argument("--use_onnx", type=str2bool, default=False)

    return parser


def parse_args():
    """Parse command line arguments."""
    parser = init_args()
    return parser.parse_args()


def create_predictor(args, mode: str, logger):
    """
    Create ONNX predictor for detection, recognition, or classification.

    Args:
        args: Arguments containing model paths
        mode: One of 'det', 'rec', or 'cls'
        logger: Logger instance

    Returns:
        tuple: (session, input_tensor, output_names, None)
    """
    if mode == "det":
        model_dir = args.det_model_dir
    elif mode == "cls":
        model_dir = args.cls_model_dir
    elif mode == "rec":
        model_dir = args.rec_model_dir
    else:
        raise ValueError(f"Unknown mode: {mode}")

    if model_dir is None:
        logger.info(f"Model path not found for mode: {mode}")
        sys.exit(0)

    if not args.use_onnx:
        raise ValueError("Only ONNX inference is supported in simplified version")

    import onnxruntime as ort

    if not os.path.exists(model_dir):
        raise ValueError(f"Model file not found: {model_dir}")

    # Configure providers
    providers = ["CPUExecutionProvider"]
    if args.use_gpu:
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

    sess = ort.InferenceSession(model_dir, providers=providers)
    input_tensor = sess.get_inputs()[0]
    output_names = [o.name for o in sess.get_outputs()]

    return sess, input_tensor, output_names, None


def draw_text_det_res(dt_boxes, img):
    """Draw detection boxes on image."""
    for box in dt_boxes:
        box = np.array(box).astype(np.int32).reshape(-1, 2)
        cv2.polylines(img, [box], True, color=(255, 255, 0), thickness=2)
    return img


def get_rotate_crop_image(img, points):
    """
    Crop and rotate text region from image.

    Args:
        img: Source image
        points: 4 corner points of text box

    Returns:
        Cropped and rotated text region
    """
    assert len(points) == 4, "shape of points must be 4*2"

    img_crop_width = int(
        max(
            np.linalg.norm(points[0] - points[1]), np.linalg.norm(points[2] - points[3])
        )
    )
    img_crop_height = int(
        max(
            np.linalg.norm(points[0] - points[3]), np.linalg.norm(points[1] - points[2])
        )
    )

    pts_std = np.float32(
        [
            [0, 0],
            [img_crop_width, 0],
            [img_crop_width, img_crop_height],
            [0, img_crop_height],
        ]
    )

    M = cv2.getPerspectiveTransform(points, pts_std)
    dst_img = cv2.warpPerspective(
        img,
        M,
        (img_crop_width, img_crop_height),
        borderMode=cv2.BORDER_REPLICATE,
        flags=cv2.INTER_CUBIC,
    )

    dst_img_height, dst_img_width = dst_img.shape[0:2]
    if dst_img_height * 1.0 / dst_img_width >= 1.5:
        dst_img = np.rot90(dst_img)

    return dst_img


def get_minarea_rect_crop(img, points):
    """
    Crop text region using minimum area rectangle.

    Args:
        img: Source image
        points: Polygon points of text box

    Returns:
        Cropped text region
    """
    bounding_box = cv2.minAreaRect(np.array(points).astype(np.int32))
    points = sorted(list(cv2.boxPoints(bounding_box)), key=lambda x: x[0])

    index_a, index_b, index_c, index_d = 0, 1, 2, 3
    if points[1][1] > points[0][1]:
        index_a = 0
        index_d = 1
    else:
        index_a = 1
        index_d = 0
    if points[3][1] > points[2][1]:
        index_b = 2
        index_c = 3
    else:
        index_b = 3
        index_c = 2

    box = [points[index_a], points[index_b], points[index_c], points[index_d]]
    crop_img = get_rotate_crop_image(img, np.array(box))
    return crop_img


def draw_ocr(
    image,
    boxes,
    txts=None,
    scores=None,
    drop_score=0.5,
    font_path="./doc/fonts/simfang.ttf",
):
    """
    Visualize OCR detection and recognition results.

    Args:
        image: RGB image
        boxes: Detection boxes with shape (N, 4, 2)
        txts: Recognized texts
        scores: Recognition confidence scores
        drop_score: Minimum score threshold for visualization
        font_path: Path to font file

    Returns:
        Visualized image
    """
    if scores is None:
        scores = [1] * len(boxes)

    for i in range(len(boxes)):
        if scores is not None and (scores[i] < drop_score or math.isnan(scores[i])):
            continue
        box = np.reshape(np.array(boxes[i]), [-1, 1, 2]).astype(np.int64)
        image = cv2.polylines(np.array(image), [box], True, (255, 0, 0), 2)

    if txts is not None:
        img = np.array(resize_img(image, input_size=600))
        txt_img = text_visual(
            txts,
            scores,
            img_h=img.shape[0],
            img_w=600,
            threshold=drop_score,
            font_path=font_path,
        )
        img = np.concatenate([np.array(img), np.array(txt_img)], axis=1)
        return img

    return image


def resize_img(img, input_size=600):
    """Resize image while keeping aspect ratio."""
    img = np.array(img)
    im_shape = img.shape
    im_size_max = np.max(im_shape[0:2])
    im_scale = float(input_size) / float(im_size_max)
    img = cv2.resize(img, None, None, fx=im_scale, fy=im_scale)
    return img


def str_count(s):
    """Count characters for text visualization width calculation."""
    import string

    count_zh = count_pu = 0
    s_len = len(s)
    en_dg_count = 0
    for c in s:
        if c in string.ascii_letters or c.isdigit() or c.isspace():
            en_dg_count += 1
        elif c.isalpha():
            count_zh += 1
        else:
            count_pu += 1
    return s_len - math.ceil(en_dg_count / 2)


def text_visual(
    texts, scores, img_h=400, img_w=600, threshold=0.0, font_path="./doc/simfang.ttf"
):
    """Create text visualization panel."""
    if scores is not None:
        assert len(texts) == len(scores), "The number of texts and scores must match"

    def create_blank_img():
        blank_img = np.ones(shape=[img_h, img_w], dtype=np.int8) * 255
        blank_img[:, img_w - 1 :] = 0
        blank_img = Image.fromarray(blank_img).convert("RGB")
        draw_txt = ImageDraw.Draw(blank_img)
        return blank_img, draw_txt

    blank_img, draw_txt = create_blank_img()
    font_size = 20
    txt_color = (0, 0, 0)
    font = ImageFont.truetype(font_path, font_size, encoding="utf-8")
    gap = font_size + 5
    txt_img_list = []
    count, index = 1, 0

    for idx, txt in enumerate(texts):
        index += 1
        if scores[idx] < threshold or math.isnan(scores[idx]):
            index -= 1
            continue

        first_line = True
        while str_count(txt) >= img_w // font_size - 4:
            tmp = txt
            txt = tmp[: img_w // font_size - 4]
            if first_line:
                new_txt = str(index) + ": " + txt
                first_line = False
            else:
                new_txt = "    " + txt
            draw_txt.text((0, gap * count), new_txt, txt_color, font=font)
            txt = tmp[img_w // font_size - 4 :]
            if count >= img_h // gap - 1:
                txt_img_list.append(np.array(blank_img))
                blank_img, draw_txt = create_blank_img()
                count = 0
            count += 1

        if first_line:
            new_txt = str(index) + ": " + txt + "   " + "%.3f" % (scores[idx])
        else:
            new_txt = "  " + txt + "  " + "%.3f" % (scores[idx])
        draw_txt.text((0, gap * count), new_txt, txt_color, font=font)

        if count >= img_h // gap - 1 and idx + 1 < len(texts):
            txt_img_list.append(np.array(blank_img))
            blank_img, draw_txt = create_blank_img()
            count = 0
        count += 1

    txt_img_list.append(np.array(blank_img))
    if len(txt_img_list) == 1:
        blank_img = np.array(txt_img_list[0])
    else:
        blank_img = np.concatenate(txt_img_list, axis=1)

    return np.array(blank_img)


def draw_boxes(image, boxes, scores=None, drop_score=0.5):
    """Draw detection boxes on image."""
    if scores is None:
        scores = [1] * len(boxes)
    for box, score in zip(boxes, scores):
        if score < drop_score:
            continue
        box = np.reshape(np.array(box), [-1, 1, 2]).astype(np.int64)
        image = cv2.polylines(np.array(image), [box], True, (255, 0, 0), 2)
    return image


def base64_to_cv2(b64str):
    """Convert base64 string to OpenCV image."""
    import base64

    data = base64.b64decode(b64str.encode("utf8"))
    data = np.frombuffer(data, np.uint8)
    data = cv2.imdecode(data, cv2.IMREAD_COLOR)
    return data

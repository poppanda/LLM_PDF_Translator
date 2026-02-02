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
Simplified Text Recognizer for PP-OCRv3/v4/v5
Only supports SVTR_LCNet algorithm (CTC-based) which is used by all PP-OCR versions.
"""

import os
import sys

__dir__ = os.path.dirname(os.path.abspath(__file__))
sys.path.append(__dir__)
sys.path.insert(0, os.path.abspath(os.path.join(__dir__, "../..")))

os.environ["FLAGS_allocator_strategy"] = "auto_growth"

import cv2
import numpy as np
import math
import time
import traceback

import tools.infer.utility as utility
from ppocr.postprocess import build_post_process
from ppocr.utils.logging import get_logger

logger = get_logger()


class TextRecognizer:
    """
    Simplified Text Recognizer using SVTR_LCNet/CTC algorithm.
    Compatible with PP-OCRv3, PP-OCRv4, and PP-OCRv5 recognition models.
    """

    def __init__(self, args):
        self.rec_image_shape = [int(v) for v in args.rec_image_shape.split(",")]
        self.rec_batch_num = args.rec_batch_num
        self.use_onnx = args.use_onnx

        # CTC postprocess (same for v3/v4/v5 SVTR_LCNet models)
        postprocess_params = {
            "name": "CTCLabelDecode",
            "character_dict_path": args.rec_char_dict_path,
            "use_space_char": args.use_space_char,
        }

        self.postprocess_op = build_post_process(postprocess_params)
        self.predictor, self.input_tensor, self.output_tensors, _ = (
            utility.create_predictor(args, "rec", logger)
        )

    def resize_norm_img(self, img, max_wh_ratio):
        """
        Resize and normalize image for recognition.
        Standard preprocessing for SVTR_LCNet models.
        """
        imgC, imgH, imgW = self.rec_image_shape

        # Compute width based on aspect ratio
        imgW = int(imgH * max_wh_ratio)

        h, w = img.shape[:2]
        ratio = w / float(h)
        if math.ceil(imgH * ratio) > imgW:
            resized_w = imgW
        else:
            resized_w = int(math.ceil(imgH * ratio))

        resized_image = cv2.resize(img, (resized_w, imgH))
        resized_image = resized_image.astype("float32")

        # Normalize: transpose to CHW, scale to [0,1], then normalize to [-1,1]
        resized_image = resized_image.transpose((2, 0, 1)) / 255
        resized_image -= 0.5
        resized_image /= 0.5

        # Padding to target width
        padding_im = np.zeros((imgC, imgH, imgW), dtype=np.float32)
        padding_im[:, :, 0:resized_w] = resized_image

        return padding_im

    def __call__(self, img_list):
        """
        Recognize text in a list of cropped text images.

        Args:
            img_list: List of cropped text region images (BGR format)

        Returns:
            rec_res: List of (text, confidence) tuples
            elapsed_time: Processing time
        """
        img_num = len(img_list)

        # Calculate aspect ratios for sorting
        width_list = [img.shape[1] / float(img.shape[0]) for img in img_list]

        # Sort by width ratio to batch similar-shaped images
        indices = np.argsort(np.array(width_list))
        rec_res = [["", 0.0]] * img_num
        batch_num = self.rec_batch_num

        st = time.time()

        for beg_img_no in range(0, img_num, batch_num):
            end_img_no = min(img_num, beg_img_no + batch_num)
            norm_img_batch = []

            imgC, imgH, imgW = self.rec_image_shape[:3]
            max_wh_ratio = imgW / imgH

            # Find max width ratio in batch
            for ino in range(beg_img_no, end_img_no):
                h, w = img_list[indices[ino]].shape[0:2]
                wh_ratio = w * 1.0 / h
                max_wh_ratio = max(max_wh_ratio, wh_ratio)

            # Preprocess images in batch
            for ino in range(beg_img_no, end_img_no):
                norm_img = self.resize_norm_img(img_list[indices[ino]], max_wh_ratio)
                norm_img = norm_img[np.newaxis, :]
                norm_img_batch.append(norm_img)

            norm_img_batch = np.concatenate(norm_img_batch)
            norm_img_batch = norm_img_batch.copy()

            # ONNX inference
            if self.use_onnx:
                input_dict = {self.input_tensor.name: norm_img_batch}
                outputs = self.predictor.run(self.output_tensors, input_dict)
                preds = outputs[0]
            else:
                self.input_tensor.copy_from_cpu(norm_img_batch)
                self.predictor.run()
                outputs = [t.copy_to_cpu() for t in self.output_tensors]
                preds = outputs[0] if len(outputs) == 1 else outputs

            # Decode predictions
            rec_result = self.postprocess_op(preds)
            for rno in range(len(rec_result)):
                rec_res[indices[beg_img_no + rno]] = rec_result[rno]

        return rec_res, time.time() - st


if __name__ == "__main__":
    from ppocr.utils.utility import get_image_file_list, check_and_read

    args = utility.parse_args()
    image_file_list = get_image_file_list(args.image_dir)
    text_recognizer = TextRecognizer(args)
    valid_image_file_list = []
    img_list = []

    logger.info("In PP-OCRv3/v4/v5, rec_image_shape parameter defaults to '3, 48, 320'")

    # Warmup
    if args.warmup:
        img = np.random.uniform(0, 255, [48, 320, 3]).astype(np.uint8)
        for _ in range(2):
            _ = text_recognizer([img] * int(args.rec_batch_num))

    for image_file in image_file_list:
        img, flag, _ = check_and_read(image_file)
        if not flag:
            img = cv2.imread(image_file)
        if img is None:
            logger.info(f"error in loading image:{image_file}")
            continue
        valid_image_file_list.append(image_file)
        img_list.append(img)

    try:
        rec_res, _ = text_recognizer(img_list)
    except Exception as e:
        logger.info(traceback.format_exc())
        logger.info(e)
        exit()

    for ino in range(len(img_list)):
        logger.info(f"Predicts of {valid_image_file_list[ino]}:{rec_res[ino]}")

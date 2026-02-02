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
Simplified Text Detector for PP-OCRv3/v4/v5
Only supports DB algorithm which is used by all PP-OCR versions.
"""

import os
import sys

__dir__ = os.path.dirname(os.path.abspath(__file__))
sys.path.append(__dir__)
sys.path.insert(0, os.path.abspath(os.path.join(__dir__, "../..")))

os.environ["FLAGS_allocator_strategy"] = "auto_growth"

import cv2
import numpy as np
import time

import tools.infer.utility as utility
from ppocr.utils.logging import get_logger
from ppocr.data.imaug import transform, create_operators
from ppocr.postprocess import build_post_process

logger = get_logger()


class TextDetector:
    """
    Simplified Text Detector using DB algorithm.
    Compatible with PP-OCRv3, PP-OCRv4, and PP-OCRv5 detection models.
    """

    def __init__(self, args):
        self.args = args
        self.use_onnx = args.use_onnx

        # DB preprocessing pipeline (same for v3/v4/v5)
        pre_process_list = [
            {
                "DetResizeForTest": {
                    "limit_side_len": args.det_limit_side_len,
                    "limit_type": args.det_limit_type,
                }
            },
            {
                "NormalizeImage": {
                    "std": [0.229, 0.224, 0.225],
                    "mean": [0.485, 0.456, 0.406],
                    "scale": "1./255.",
                    "order": "hwc",
                }
            },
            {"ToCHWImage": None},
            {"KeepKeys": {"keep_keys": ["image", "shape"]}},
        ]

        # DB postprocess parameters
        postprocess_params = {
            "name": "DBPostProcess",
            "thresh": args.det_db_thresh,
            "box_thresh": args.det_db_box_thresh,
            "max_candidates": 1000,
            "unclip_ratio": args.det_db_unclip_ratio,
            "use_dilation": args.use_dilation,
            "score_mode": args.det_db_score_mode,
            "box_type": args.det_box_type,
        }

        self.preprocess_op = create_operators(pre_process_list)
        self.postprocess_op = build_post_process(postprocess_params)
        self.predictor, self.input_tensor, self.output_tensors, _ = (
            utility.create_predictor(args, "det", logger)
        )

    def order_points_clockwise(self, pts):
        """Order points in clockwise direction."""
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        tmp = np.delete(pts, (np.argmin(s), np.argmax(s)), axis=0)
        diff = np.diff(np.array(tmp), axis=1)
        rect[1] = tmp[np.argmin(diff)]
        rect[3] = tmp[np.argmax(diff)]
        return rect

    def clip_det_res(self, points, img_height, img_width):
        """Clip detection results to image boundaries."""
        for pno in range(points.shape[0]):
            points[pno, 0] = int(min(max(points[pno, 0], 0), img_width - 1))
            points[pno, 1] = int(min(max(points[pno, 1], 0), img_height - 1))
        return points

    def filter_tag_det_res(self, dt_boxes, image_shape):
        """Filter and process detection boxes."""
        img_height, img_width = image_shape[0:2]
        dt_boxes_new = []
        for box in dt_boxes:
            if isinstance(box, list):
                box = np.array(box)
            box = self.order_points_clockwise(box)
            box = self.clip_det_res(box, img_height, img_width)
            rect_width = int(np.linalg.norm(box[0] - box[1]))
            rect_height = int(np.linalg.norm(box[0] - box[3]))
            if rect_width <= 3 or rect_height <= 3:
                continue
            dt_boxes_new.append(box)
        return np.array(dt_boxes_new)

    def filter_tag_det_res_only_clip(self, dt_boxes, image_shape):
        """Filter boxes with only clipping (for polygon mode)."""
        img_height, img_width = image_shape[0:2]
        dt_boxes_new = []
        for box in dt_boxes:
            if isinstance(box, list):
                box = np.array(box)
            box = self.clip_det_res(box, img_height, img_width)
            dt_boxes_new.append(box)
        return np.array(dt_boxes_new)

    def __call__(self, img):
        """
        Detect text regions in image.

        Args:
            img: Input image (BGR format)

        Returns:
            dt_boxes: Detected text boxes
            elapsed_time: Processing time
        """
        ori_im = img.copy()
        data = {"image": img}
        st = time.time()

        # Preprocess
        data = transform(data, self.preprocess_op)
        img, shape_list = data
        if img is None:
            return None, 0

        img = np.expand_dims(img, axis=0)
        shape_list = np.expand_dims(shape_list, axis=0)
        img = img.copy()

        # ONNX inference
        if self.use_onnx:
            input_dict = {self.input_tensor.name: img}
            outputs = self.predictor.run(self.output_tensors, input_dict)
        else:
            self.input_tensor.copy_from_cpu(img)
            self.predictor.run()
            outputs = [t.copy_to_cpu() for t in self.output_tensors]

        # Postprocess (DB algorithm)
        preds = {"maps": outputs[0]}
        post_result = self.postprocess_op(preds, shape_list)
        dt_boxes = post_result[0]["points"]

        # Filter results
        if self.args.det_box_type == "poly":
            dt_boxes = self.filter_tag_det_res_only_clip(dt_boxes, ori_im.shape)
        else:
            dt_boxes = self.filter_tag_det_res(dt_boxes, ori_im.shape)

        return dt_boxes, time.time() - st


if __name__ == "__main__":
    from ppocr.utils.utility import get_image_file_list, check_and_read
    import json

    args = utility.parse_args()
    image_file_list = get_image_file_list(args.image_dir)
    text_detector = TextDetector(args)
    total_time = 0
    draw_img_save_dir = args.draw_img_save_dir
    os.makedirs(draw_img_save_dir, exist_ok=True)

    save_results = []
    for idx, image_file in enumerate(image_file_list):
        img, flag_gif, flag_pdf = check_and_read(image_file)
        if not flag_gif and not flag_pdf:
            img = cv2.imread(image_file)
        if not flag_pdf:
            if img is None:
                logger.debug(f"error in loading image:{image_file}")
                continue
            imgs = [img]
        else:
            page_num = args.page_num
            if page_num > len(img) or page_num == 0:
                page_num = len(img)
            imgs = img[:page_num]

        for index, img in enumerate(imgs):
            dt_boxes, elapse = text_detector(img)
            total_time += elapse
            if len(imgs) > 1:
                save_pred = (
                    f"{os.path.basename(image_file)}_{index}\t"
                    f"{json.dumps([x.tolist() for x in dt_boxes])}\n"
                )
            else:
                save_pred = (
                    f"{os.path.basename(image_file)}\t"
                    f"{json.dumps([x.tolist() for x in dt_boxes])}\n"
                )
            save_results.append(save_pred)
            logger.info(save_pred)
            logger.info(f"{idx} The predict time of {image_file}: {elapse}")

            src_im = utility.draw_text_det_res(dt_boxes, img)
            save_file = image_file
            if flag_gif:
                save_file = image_file[:-3] + "png"
            elif flag_pdf:
                save_file = image_file.replace(".pdf", f"_{index}.png")

            img_path = os.path.join(
                draw_img_save_dir, f"det_res_{os.path.basename(save_file)}"
            )
            cv2.imwrite(img_path, src_im)
            logger.info(f"The visualized image saved in {img_path}")

    with open(os.path.join(draw_img_save_dir, "det_results.txt"), "w") as f:
        f.writelines(save_results)

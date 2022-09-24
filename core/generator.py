from typing import List
from dto.Obj import PgieObj
import numpy as np
import cv2, os

ALARM_THRES: float = 0.8
IMG_DIR = "./result"
class BaseAlarmGenerator:
    obj_list: List

    def run(self):
        pass


class IntrusionAlarmGenerator(BaseAlarmGenerator):
    """IntrusionAlarmGenerator
    알람 상태리스트를 각 객체마다 업데이트 시킨다.
    업데이트된 객체 상태에 따라 특정 행동(이미지저장)을 실행한다."""

    def __init__(self, obj_list: List[PgieObj], frame):
        self.obj_list = obj_list
        self.frame = frame

    def run(self):
        for obj in self.obj_list:
            if obj.alarm_check_list[0] == False and obj.alarm_check_list[1] == True:
                self.save_alarm_img(IMG_DIR, self.frame, obj.bbox)

    def save_alarm_img(self, img_dir, img, bbox_info):
        img_cvt = cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA)

        # 알람을 일으키는 오브젝트에 대해 crop 한다.
        # TODO 이미지 이름 형식에 대한 정의 필요
        img_crop = img_cvt[bbox_info[1]:bbox_info[3], bbox_info[0]:bbox_info[2]]
        img_path = os.path.join(img_dir, "test.jpg")
        cv2.imwrite(img_path, img_crop)
        raw_img_path = os.path.join(img_dir, "raw.jpg")
        cv2.imwrite(raw_img_path, img_cvt)
from typing import Dict, List
from dto import PgieObj, Event
import numpy as np
import json, cv2, os

class BaseAlarmGenerator:
    obj_list: List

    def run(self):
        pass


class IntrusionAlarmGenerator(BaseAlarmGenerator):
    """IntrusionAlarmGenerator
    알람 상태리스트를 각 객체마다 업데이트 시킨다.
    업데이트된 객체 상태에 따라 특정 행동(이미지저장)을 실행한다.
        - Intrusion IN인 경우와 OUT인 경우를 따로 저장한다."""

    def __init__(self, event: Event, frame, dir_name):
        self.obj_list: List[PgieObj] = event.obj_list
        self.event = event
        self.frame = frame
        self.in_dir_path = os.path.join(dir_name, "in")
        self.out_dir_path = os.path.join(dir_name, "out")

    def run(self):
        for obj in self.obj_list:
            # print("obj.alarm_check_list", obj.alarm_check_list)
            if (
                not obj.alarm_check_list[0] and obj.alarm_check_list[1]
            ):  # ROI 밖에서 안으로 <=> intrusion in event
                print("obj", obj)
                self.save_alarm_img_in(self.in_dir_path, self.event, self.frame, obj)
            elif (
                obj.alarm_check_list[0] and not obj.alarm_check_list[1]
            ):  # ROI 안에서 밖으로 <=> intrusion out event
                print("obj", obj)
                self.save_alarm_img_out(self.out_dir_path, self.event, self.frame, obj)
            # else:
            #     self.event.info["status"] = "none"

    def save_alarm_img_in(self, in_dir, event, img, obj):
        event.info["count_in"] += 1
        event.info["status"] = "in"
        for sgie_id, value in obj.secondary_info.items():
            if value[-1] == 0: # mask wear
                event.info["mask_in"] += 1

        # ---- save re id feature ---- #
        obj_dict:Dict = {}
        obj_dict["source_id"] = event.source_id
        obj_dict["event"] = "in"
        obj_dict["obj_id"] = obj.obj_id
        obj_dict["reid_feature"] = obj.reid_feature
        obj_dict["secondary_info"] = obj.secondary_info
        obj_dict["init_time"] = obj.init_time
        obj_dict["last_time"] = obj.last_time

        json_path = os.path.join(
            in_dir, "%s_%s_%s.json" % (event.source_id, obj.obj_id, event.name + "_in")
        )
        with open(json_path, "w") as json_file:
            json.dump(obj_dict, json_file, indent=4)

        # ---- save image ---- #
        bbox_info = obj.bbox
        img_cvt = cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA)
        event_name = event.name + "_in"
        source_id = event.source_id

        # 알람을 일으키는 오브젝트에 대해 crop 한다.
        # TODO 이미지 이름 형식에 대한 정의 필요
        img_crop = img_cvt[bbox_info[1] : bbox_info[3], bbox_info[0] : bbox_info[2]]
        img_path = os.path.join(
            in_dir, "%s_%s_%s.jpg" % (source_id, obj.obj_id, event_name)
        )
        cv2.imwrite(img_path, img_crop)

        obj.alarm_check_list = [True] * 2

    def save_alarm_img_out(self, out_dir, event, img, obj):
        event.info["count_out"] += 1
        event.info["status"] = "out"
        for sgie_id, value in obj.secondary_info.items():
            if value[-1] == 0: # mask wear
                event.info["mask_out"] += 1

        # ---- save re id feature ---- #
        obj_dict:Dict = {}
        obj_dict["source_id"] = event.source_id
        obj_dict["event"] = "out"
        obj_dict["obj_id"] = obj.obj_id
        obj_dict["reid_feature"] = obj.reid_feature
        obj_dict["secondary_info"] = obj.secondary_info
        obj_dict["init_time"] = obj.init_time
        obj_dict["last_time"] = obj.last_time

        json_path = os.path.join(
            out_dir, "%s_%s_%s.json" % (event.source_id, obj.obj_id, event.name + "_out")
        )

        with open(json_path, "w") as json_file:
            json.dump(obj_dict, json_file, indent=4) 
        
        # ---- save image ---- #
        bbox_info = obj.bbox
        img_cvt = cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA)
        event_name = event.name + "_out"
        source_id = event.source_id

        # 알람을 일으키는 오브젝트에 대해 crop 한다.
        # TODO 이미지 이름 형식에 대한 정의 필요
        img_crop = img_cvt[bbox_info[1] : bbox_info[3], bbox_info[0] : bbox_info[2]]
        img_path = os.path.join(
            out_dir, "%s_%s_%s.jpg" % (source_id, obj.obj_id, event_name)
        )
        cv2.imwrite(img_path, img_crop)

        obj.alarm_check_list = [False] * 2


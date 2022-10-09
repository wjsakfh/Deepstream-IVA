import sys
import gi
import os

from core.generator import IntrusionAlarmGenerator

gi.require_version("Gst", "1.0")
from gi.repository import GObject, Gst
import pyds, ctypes

from time import monotonic
from typing import List, Dict
# from core.utils import __parse_buffer2msg
from dataclasses import dataclass

# from algorithms import point_polygon_test
import cv2, numpy as np
from dto import PgieObj, EventConfig, Event, Source

# AlarmGenerator를 담고 있기엔 이름의 범위가 좁음
# MsgManager가 들고있는 최종 Result는 self.obj_list 여야함.
# 이를 바깥 쪽에서 쓸 수 있으면 좋을 것 같음.
roi1 = [[0, 0], [0, 1080], [960, 1080], [960, 0]]
roi2 = [[960, 0], [960, 1080], [1920, 1080], [1920, 0]]

# TODO 추후에 사용자가 event config를 등록 또는 수정할 수 있어야한다.

event_config1 = EventConfig(0, 1, True, "intrusion", roi1, "person", 0.5)
# event_config2 = EventConfig(0, True, "intrusion_out", roi2, "person", 3)
event_config3 = EventConfig(1, 3, True, "intrusion", roi2, "person", 0.5)
# event_config4 = EventConfig(1, True, "intrusion", roi2, "person", 3)
# print(event_config4.source_id)
# EVENT_CONFIGS = [event_config1, event_config2, event_config3, event_config4]
EVENT_CONFIGS = [event_config1, event_config3]
FCC = cv2.VideoWriter_fourcc('D', 'I', 'V', 'X')

class MsgManager:
    def __init__(self, dir_name):
        self.dir_name = dir_name
        # self.obj_info_list = obj_info_list
        self.sources: Dict = {}
        self.obj_list: List = []
        self.timeout: float = 3.0
        self.all_event_configs: List[EventConfig] = EVENT_CONFIGS
        self.vid_outs: Dict = {"_".join([str(e_c.source_id), str(e_c.event_id)]): cv2.VideoWriter("frames/out/%s.avi"%("_".join([str(e_c.source_id), str(e_c.event_id)])),FCC, 30, (1920, 1080)) for e_c in EVENT_CONFIGS}
        # 정보 Extract
        # 리스트 업데이트

    # TODO async로 pgie object에 대한 msg를 msg broker를 통해
    # Event processing 모듈로 전달하고 거기서 모든 것이 처리되도록 해야함.
    # 그래야지 deepstream과 alarm generator를 분리할 수 있을 것임.
    def tiler_sink_pad_buffer_probe(self, pad, info, u_data):
        # msg manager
        msg: Dict = {}
        gst_buffer = info.get_buffer()
        parsed_msg = self.__parse_buffer2msg(gst_buffer, msg)
        # print(parsed_msg)

        source_msg_list = parsed_msg["frame_list"]  # 각 source들의 msg list
        for source_msg in source_msg_list:
            source_id = source_msg["source_id"]
            # TODO 추후 refactoring 필요. (source event configs를 어디서 업데이트 할 것인지)
            source_event_configs = [
                c for c in self.all_event_configs if c.source_id == source_id
            ]
            if source_id not in self.sources.keys():
                self.sources[source_id] = Source(source_id, source_event_configs)
            source = self.sources[source_id]

            # TODO source의 이벤트에 맞는 object를 관리한다.
            self.__update_event_info(source, source_msg)
            self.__display_event_info(source, source_msg)

        return Gst.PadProbeReturn.OK

    def __display_event_info(self, source, source_msg):
        for e in source.event_list:
            img = source_msg["source_frame"]
            img_cvt = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)

            cnt = 0
            for key, value in e.info.items():
                img_text = cv2.putText(img_cvt, "%s : %s"%(key, value), (10, 30 * (cnt+1)), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2, cv2.LINE_AA)
                cnt += 1
            
            obj_list: List[PgieObj] = e.obj_list
            img_bbox = img_text
            for obj in obj_list:
                bbox_info = obj.bbox
                xmin, ymin, xmax, ymax = bbox_info[0], bbox_info[1], bbox_info[2], bbox_info[3]
                img_bbox = cv2.rectangle(img_text, (xmin, ymin), (xmax, ymax), (0,0,255), 2)

            if e.info["status"] == "in":
                img_poly = cv2.polylines(img_bbox, [np.array(e.roi, np.int32)], True, (255,0,0), 2)
            elif e.info["status"] == "out":
                img_poly = cv2.polylines(img_bbox, [np.array(e.roi, np.int32)], True, (0,0,255), 2)
            else:
                img_poly = cv2.polylines(img_bbox, [np.array(e.roi, np.int32)], True, (0,0,0), 2)
            
            # print("source.id", source.id, type(source.id))
            # print(self.vid_outs[str(source.id)])
            # cv2.imwrite("frames/out/img%s.jpg"%monotonic(), img_text)
            
            self.vid_outs["_".join([str(e.source_id), str(e.event_id)])].write(img_poly)
            

    def __update_event_info(self, source, source_msg):
        for e in source.event_list:
            # event에 맞는 object update.
            # 먼저 특정 roi에 들어와있는 객체에 대해 판별한다.
            # roi에 들어와있으면 우선 객체에 등록한다.
            for obj_info in source_msg["obj_list"]:
                e.obj_list = self._update_obj_list(e, PgieObj(obj_info, e.roi))

            intrusion_alarm_gen = IntrusionAlarmGenerator(
                e, source_msg["source_frame"], self.dir_name
            )
            intrusion_alarm_gen.run()
        
    def _update_obj_list(self, event: Event, pgie_obj: PgieObj):
        # pgie_obj: 현재 등록하려는 obj
        # obj: list에 이미 등록된 obj
        self._register_obj(event.obj_list, pgie_obj)
        for obj in event.obj_list:
            self._remove_obj(event.obj_list, obj)

            if obj.obj_id == pgie_obj.obj_id:
                obj.last_time = monotonic()
                obj.pos = pgie_obj.pos
                obj.bbox = pgie_obj.bbox
                obj.traj.append(pgie_obj.pos)

                for k, v in pgie_obj.secondary_info.items():
                    if k not in obj.secondary_info.keys():  # initialization
                        obj.secondary_info[k] = v
                    else:
                        obj.secondary_info[k].append(v[0])

                obj.update_intrusion_flag()
                obj.update_alarm_state()

        del pgie_obj  # 등록을 마치고 메모리에서 삭제한다.

        return event.obj_list

    def _remove_obj(self, event_obj_list, obj):
        # 일정시간이 지난 obj는 list에서 지운다.
        now = monotonic()
        if obj.last_time + self.timeout < now:
            event_obj_list.remove(obj)

    def _register_obj(self, event_obj_list, pgie_obj):
        # list에 아무 obj가 등록되지 않았거나
        # 새로운 id의 obj가 나타났을 때 등록을 한다.
        obj_id_list = [obj.obj_id for obj in event_obj_list]
        if pgie_obj.obj_id not in obj_id_list:
            event_obj_list.append(pgie_obj)

    def __parse_classifier_meta(self, obj_meta):
        classifier_list: List = list()
        l_classifier = obj_meta.classifier_meta_list
        while l_classifier is not None:
            try:
                class_meta = pyds.NvDsClassifierMeta.cast(l_classifier.data)
            except StopIteration:
                break

            classifier_meta_contents: Dict = dict()
            classifier_meta_contents["classifier_id"] = class_meta.unique_component_id

            l_label_info = class_meta.label_info_list
            label_info: Dict = {}
            while l_label_info is not None:
                try:
                    label_info_meta = pyds.NvDsLabelInfo.cast(l_label_info.data)
                except StopIteration:
                    break
                label_info_contents: Dict = dict()
                label_info_contents["result_prob"] = label_info_meta.result_prob
                label_info_contents["result_label"] = label_info_meta.result_label
                label_info_contents["result_class_id"] = label_info_meta.result_class_id

                label_info = label_info_contents
                try:
                    l_label_info = l_label_info.next
                except StopIteration:
                    break

            classifier_meta_contents["label_info"] = label_info
            classifier_list.append(classifier_meta_contents)
            try:
                l_classifier = l_classifier.next
            except StopIteration:
                break

        return classifier_list


    def __parse_reid_meta(self, obj_meta):
        l_user = obj_meta.obj_user_meta_list
        while l_user is not None:
            try:
                user_meta = pyds.NvDsUserMeta.cast(l_user.data)
            except StopIteration:
                break

            if (
                user_meta.base_meta.meta_type
                != pyds.NvDsMetaType.NVDSINFER_TENSOR_OUTPUT_META
            ):
                continue

            tensor_meta = pyds.NvDsInferTensorMeta.cast(user_meta.user_meta_data)
            layer = pyds.get_nvds_LayerInfo(tensor_meta, 0)
            ptr = ctypes.cast(pyds.get_ptr(layer.buffer), ctypes.POINTER(ctypes.c_float))
            features = np.ctypeslib.as_array(ptr, shape=(512,))

            try:
                l_user = l_user.next
            except StopIteration:
                break

            return features.tolist()


    # TODO osnet user meta에 접근하여 feature data parsing필요.
    # TODO parsing되는 데이터들의 type을 면밀히 정해주어야할 필요 있음 (tracker bbox -> int, re_id_features -> List[int])


    def __parse_buffer2msg(self, buffer, msg):
        frame_number = 0
        num_rects = 0

        gst_buffer = buffer
        if not gst_buffer:
            print("Unable to get GstBuffer ")
            return

        # Retrieve batch metadata from the gst_buffer
        # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
        # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        l_frame = batch_meta.frame_meta_list

        frame_list: List = list()
        while l_frame is not None:
            try:
                frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            except StopIteration:
                break
            l_obj = frame_meta.obj_meta_list

            n_frame = pyds.get_nvds_buf_surface(hash(gst_buffer), frame_meta.batch_id)

            frame_meta_contents = {
                "source_id": frame_meta.source_id,
                "source_frame": n_frame,
                "source_height": frame_meta.source_frame_height,
                "source_width": frame_meta.source_frame_width,
                "source_time": frame_meta.ntp_timestamp,
            }

            l_obj = frame_meta.obj_meta_list

            # Getting Image data using nvbufsurface
            # the input should be address of buffer and batch_id

            obj_list: List = list()
            while l_obj is not None:
                try:
                    obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
                except StopIteration:
                    break

                # ---- parser re-id info ---- #
                reid_features = self.__parse_reid_meta(obj_meta)

                # ---- Stacking object meta data ---- #
                obj_meta_contents: Dict = dict()
                obj_meta_contents["obj_id"] = obj_meta.object_id
                obj_meta_contents["obj_confid"] = obj_meta.confidence
                obj_meta_contents["obj_class_id"] = obj_meta.class_id
                obj_meta_contents["obj_class_label"] = obj_meta.obj_label
                obj_meta_contents["obj_reid_feature"] = reid_features
                bbox_info_contents: Dict = dict()
                bbox_info_contents[
                    "height"
                ] = obj_meta.tracker_bbox_info.org_bbox_coords.height
                bbox_info_contents["left"] = obj_meta.tracker_bbox_info.org_bbox_coords.left
                bbox_info_contents["top"] = obj_meta.tracker_bbox_info.org_bbox_coords.top
                bbox_info_contents[
                    "width"
                ] = obj_meta.tracker_bbox_info.org_bbox_coords.width

                obj_meta_contents["tracker_bbox_info"] = bbox_info_contents

                # ---- parse classifier info ---- #
                classifier_list = self.__parse_classifier_meta(obj_meta)
                obj_meta_contents["classifier_list"] = classifier_list
                obj_list.append(obj_meta_contents)

                try:
                    l_obj = l_obj.next
                except StopIteration:
                    break

            frame_meta_contents["obj_list"] = obj_list
            frame_list.append(frame_meta_contents)

            try:
                l_frame = l_frame.next
            except StopIteration:
                break

        msg["frame_list"] = frame_list

        return msg

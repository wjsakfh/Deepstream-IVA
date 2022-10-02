import sys
import gi
import os

gi.require_version("Gst", "1.0")
from gi.repository import GObject, Gst
import pyds
import ctypes
import numpy as np
import cv2

from typing import Dict, List

# from core.manageDB import retrieve_pgie_obj, PgieObjList

fps_streams = {}
frame_count = {}
saved_count = {}
PGIE_CLASS_ID_PERSON = 0

MAX_DISPLAY_LEN = 64
MUXER_OUTPUT_WIDTH = 1920
MUXER_OUTPUT_HEIGHT = 1080
MUXER_BATCH_TIMEOUT_USEC = 4000000
TILED_OUTPUT_WIDTH = 1920
TILED_OUTPUT_HEIGHT = 1080
GST_CAPS_FEATURES_NVMM = "memory:NVMM"
pgie_classes_str = ["Person"]

MIN_CONFIDENCE = 0.3
MAX_CONFIDENCE = 0.4


MAX_DISPLAY_LEN = 64
PGIE_CLASS_ID_VEHICLE = 0
PGIE_CLASS_ID_BICYCLE = 1
PGIE_CLASS_ID_PERSON = 2
PGIE_CLASS_ID_ROADSIGN = 3
MUXER_OUTPUT_WIDTH = 1920
MUXER_OUTPUT_HEIGHT = 1080
MUXER_BATCH_TIMEOUT_USEC = 4000000
TILED_OUTPUT_WIDTH = 1280
TILED_OUTPUT_HEIGHT = 720
GST_CAPS_FEATURES_NVMM = "memory:NVMM"
OSD_PROCESS_MODE = 0
OSD_DISPLAY_TEXT = 1
pgie_classes_str = ["Vehicle", "TwoWheeler", "Person", "RoadSign"]


class SetSaveDir:
    def __init__(self, dir_name):
        self.dir_name = dir_name
        self.__prepare()

    def __prepare(self):
        dir_path = os.path.join(os.getcwd(), self.dir_name)

        if not os.path.isdir(dir_path):
            os.mkdir(dir_path)
            in_path = os.path.join(dir_path, "in")
            out_path = os.path.join(dir_path, "out")
            
            os.mkdir(in_path)
            print("in event directory made.")
            os.mkdir(out_path)
            print("out event directory made.")


def layer_finder(output_layer_info, name):
    """Return the layer contained in output_layer_info which corresponds
    to the given name.
    """
    for layer in output_layer_info:
        # dataType == 0 <=> dataType == FLOAT
        if layer.dataType == 0 and layer.layerName == name:
            return layer
    return None


def make_elm_or_print_err(factoryname, name, printedname, detail=""):
    """Creates an element with Gst Element Factory make.
    Return the element  if successfully created, otherwise print
    to stderr and return None.
    """
    print("Creating", printedname)
    elm = Gst.ElementFactory.make(factoryname, name)
    if not elm:
        sys.stderr.write("Unable to create " + printedname + " \n")
        if detail:
            sys.stderr.write(detail)
    return elm


def cb_newpad(decodebin, decoder_src_pad, data):
    print("In cb_newpad\n")
    caps = decoder_src_pad.get_current_caps()
    gststruct = caps.get_structure(0)
    gstname = gststruct.get_name()
    source_bin = data
    features = caps.get_features(0)

    # Need to check if the pad created by the decodebin is for video and not
    # audio.
    print("gstname=", gstname)
    if gstname.find("video") != -1:
        # Link the decodebin pad only if decodebin has picked nvidia
        # decoder plugin nvdec_*. We do this by checking if the pad caps contain
        # NVMM memory features.
        print("features=", features)
        if features.contains("memory:NVMM"):
            # Get the source bin ghost pad
            bin_ghost_pad = source_bin.get_static_pad("src")
            if not bin_ghost_pad.set_target(decoder_src_pad):
                sys.stderr.write(
                    "Failed to link decoder src pad to source bin ghost pad\n"
                )
        else:
            sys.stderr.write(" Error: Decodebin did not pick nvidia decoder plugin.\n")


def decodebin_child_added(child_proxy, Object, name, user_data):
    print("Decodebin child added:", name, "\n")
    if name.find("decodebin") != -1:
        Object.connect("child-added", decodebin_child_added, user_data)


def create_source_bin(index, uri):
    print("Creating source bin")

    # Create a source GstBin to abstract this bin's content from the rest of the
    # pipeline
    bin_name = "source-bin-%02d" % index
    print(bin_name)
    nbin = Gst.Bin.new(bin_name)
    if not nbin:
        sys.stderr.write(" Unable to create source bin \n")

    # Source element for reading from the uri.
    # We will use decodebin and let it figure out the container format of the
    # stream and the codec and plug the appropriate demux and decode plugins.
    uri_decode_bin = Gst.ElementFactory.make("uridecodebin", "uri-decode-bin")
    if not uri_decode_bin:
        sys.stderr.write(" Unable to create uri decode bin \n")
    # We set the input uri to the source element
    uri_decode_bin.set_property("uri", uri)
    # Connect to the "pad-added" signal of the decodebin which generates a
    # callback once a new pad for raw data has beed created by the decodebin
    uri_decode_bin.connect("pad-added", cb_newpad, nbin)
    uri_decode_bin.connect("child-added", decodebin_child_added, nbin)

    # We need to create a ghost pad for the source bin which will act as a proxy
    # for the video decoder src pad. The ghost pad will not have a target right
    # now. Once the decode bin creates the video decoder and generates the
    # cb_newpad callback, we will set the ghost pad target to the video decoder
    # src pad.
    Gst.Bin.add(nbin, uri_decode_bin)
    bin_pad = nbin.add_pad(Gst.GhostPad.new_no_target("src", Gst.PadDirection.SRC))
    if not bin_pad:
        sys.stderr.write(" Failed to add ghost pad in source bin \n")
        return None
    return nbin


def parse_classifier_meta(obj_meta):
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
        label_info_list: List = list()
        while l_label_info is not None:
            try:
                label_info_meta = pyds.NvDsLabelInfo.cast(l_label_info.data)
            except StopIteration:
                break
            label_info_contents: Dict = dict()
            label_info_contents["result_prob"] = label_info_meta.result_prob
            label_info_contents["result_label"] = label_info_meta.result_label
            label_info_contents["result_class_id"] = label_info_meta.result_class_id

            label_info_list.append(label_info_contents)
            try:
                l_label_info = l_label_info.next
            except StopIteration:
                break

        classifier_meta_contents["label_info_list"] = label_info_list
        classifier_list.append(classifier_meta_contents)
        try:
            l_classifier = l_classifier.next
        except StopIteration:
            break

    return classifier_list


def parse_reid_meta(obj_meta):
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
        # self.reid_features[obj_meta.object_id].append(features.tolist())

        try:
            l_user = l_user.next
        except StopIteration:
            break

        return features.tolist()


# TODO osnet user meta에 접근하여 feature data parsing필요.
# TODO parsing되는 데이터들의 type을 면밀히 정해주어야할 필요 있음 (tracker bbox -> int, re_id_features -> List[int])


def parse_buffer2msg(buffer, msg):
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
        frame_number = frame_meta.frame_num
        l_obj = frame_meta.obj_meta_list
        num_rects = frame_meta.num_obj_meta
        obj_counter = {
            PGIE_CLASS_ID_VEHICLE: 0,
            PGIE_CLASS_ID_PERSON: 0,
            PGIE_CLASS_ID_BICYCLE: 0,
            PGIE_CLASS_ID_ROADSIGN: 0,
        }

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
            obj_counter[obj_meta.class_id] += 1
            # print("Frame Number=", frame_number, "Number of Objects=",num_rects,"Vehicle_count=",obj_counter[PGIE_CLASS_ID_VEHICLE],"Person_count=",obj_counter[PGIE_CLASS_ID_PERSON])

            # ---- parser re-id info ---- #
            reid_features = parse_reid_meta(obj_meta)

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
            classifier_list = parse_classifier_meta(obj_meta)
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


def draw_bounding_boxes(image, obj_meta, confidence):
    confidence = "{0:.2f}".format(confidence)
    rect_params = obj_meta.rect_params
    top = int(rect_params.top)
    left = int(rect_params.left)
    width = int(rect_params.width)
    height = int(rect_params.height)
    obj_name = pgie_classes_str[obj_meta.class_id]
    # image = cv2.rectangle(image, (left, top), (left + width, top + height), (0, 0, 255, 0), 2, cv2.LINE_4)
    color = (0, 0, 255, 0)
    w_percents = int(width * 0.05) if width > 100 else int(width * 0.1)
    h_percents = int(height * 0.05) if height > 100 else int(height * 0.1)
    linetop_c1 = (left + w_percents, top)
    linetop_c2 = (left + width - w_percents, top)
    image = cv2.line(image, linetop_c1, linetop_c2, color, 6)
    linebot_c1 = (left + w_percents, top + height)
    linebot_c2 = (left + width - w_percents, top + height)
    image = cv2.line(image, linebot_c1, linebot_c2, color, 6)
    lineleft_c1 = (left, top + h_percents)
    lineleft_c2 = (left, top + height - h_percents)
    image = cv2.line(image, lineleft_c1, lineleft_c2, color, 6)
    lineright_c1 = (left + width, top + h_percents)
    lineright_c2 = (left + width, top + height - h_percents)
    image = cv2.line(image, lineright_c1, lineright_c2, color, 6)
    # Note that on some systems cv2.putText erroneously draws horizontal lines across the image
    image = cv2.putText(
        image,
        obj_name + ",C=" + str(confidence),
        (left - 10, top - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 0, 255, 0),
        2,
    )
    return image

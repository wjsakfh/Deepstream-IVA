import sys
import gi

gi.require_version("Gst", "1.0")
from gi.repository import GObject, Gst
import pyds
import ctypes
import numpy as np
import cv2

from typing import Dict, List

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


class inference_parameter:
    def __init__(self):
        self.folder_name: str


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


def tiler_sink_pad_buffer_probe(pad, info, u_data):
    msg: Dict = dict()

    frame_number = 0
    num_rects = 0
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    # Retrieve batch metadata from the gst_buffer
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    # print("batch_meta", dir(batch_meta))
    l_frame = batch_meta.frame_meta_list
    # print("l_frame", dir(l_frame))
    # print("l_frame.data", l_frame.data)
    # print("l_frame.next", l_frame.next)
    frame_list: List = list()
    while l_frame is not None:
        try:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break

        frame_meta_contents = {
            "source_id": frame_meta.source_id,
            "source_height": frame_meta.source_frame_height,
            "source_width": frame_meta.source_frame_width,
            "source_time": frame_meta.ntp_timestamp,
        }
        # print("dir(frame_meta)", dir(frame_meta))
        # print("frame_meta.frame_num", frame_meta.frame_num)
        # print("frame_meta.ntp_timestamp", frame_meta.ntp_timestamp)
        # print("frame_meta.source_frame_height", frame_meta.source_frame_height)
        # print("frame_meta.source_frame_width", frame_meta.source_frame_width)
        # print("frame_meta.source_id", frame_meta.source_id)
        # print("frame_meta.surface_index", frame_meta.surface_index)
        # print("frame_meta.surface_type", frame_meta.surface_type)
        # print("frame_meta.frame_user_meta_list",frame_meta.frame_user_meta_list)
        # print("frame_meta.misc_frame_info",frame_meta.misc_frame_info)
        # print("frame_meta.num_obj_meta",frame_meta.num_obj_meta)
        # print("frame_meta.obj_meta_list",frame_meta.obj_meta_list)
        # print("frame_meta.reserved",frame_meta.reserved)
        """
        frame_user_meta_list', 'misc_frame_info', 'ntp_timestamp', 'num_obj_meta', 'num_surfaces_per_frame', 
        'obj_meta_list', 'pad_index', 'reserved', 'source_frame_height', 'source_frame_width', 'source_id', 
        'surface_index', 'surface_type']
        """
        l_obj = frame_meta.obj_meta_list
        obj_list: List = list()
        while l_obj is not None:
            try:
                obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break

            # ---- Stacking object meta data ---- #
            obj_meta_contents = {
                "obj_id": obj_meta.object_id,
                "obj_confid": obj_meta.confidence,
                "obj_class_id": obj_meta.class_id,
            }
            bbox_info_contents = {
                "height": obj_meta.tracker_bbox_info.org_bbox_coords.height,
                "left": obj_meta.tracker_bbox_info.org_bbox_coords.left,
                "top": obj_meta.tracker_bbox_info.org_bbox_coords.top,
                "width": obj_meta.tracker_bbox_info.org_bbox_coords.width,
            }
            obj_meta_contents["tracker_bbox_info"] = bbox_info_contents
            obj_list.append(obj_meta_contents)
            """
            'base_meta', 'cast', 'class_id', 'classifier_meta_list', 'confidence', 'detector_bbox_info', 'mask_params',
             'misc_obj_info', 'obj_label', 'obj_user_meta_list', 'object_id', 'parent', 'rect_params', 'reserved', 
             'text_params', 'tracker_bbox_info', 'tracker_confidence', 'unique_component_id'
            """
            # print("obj_meta.base_meta", obj_meta.base_meta)
            # print("obj_meta.cast", obj_meta.cast)
            # print("obj_meta.class_id", obj_meta.class_id)
            # print("obj_meta.classifier_meta_list", obj_meta.classifier_meta_list)
            # print("obj_meta.confidence", obj_meta.confidence)
            # print("obj_meta.detector_bbox_info", obj_meta.detector_bbox_info)
            # print("obj_meta.misc_obj_info", obj_meta.misc_obj_info)
            # print("obj_meta.obj_label", obj_meta.obj_label)
            # print("obj_meta.obj_user_meta_list", obj_meta.obj_user_meta_list)
            # print("obj_meta.object_id", obj_meta.object_id)
            # print("obj_meta.parent", obj_meta.parent)
            # print("obj_meta.rect_params", obj_meta.rect_params)
            # print("obj_meta.reserved", obj_meta.reserved)
            # print("obj_meta.text_params", obj_meta.text_params)
            # print("obj_meta.tracker_bbox_info", obj_meta.tracker_bbox_info)
            # print("obj_meta.tracker_confidence", obj_meta.tracker_confidence)
            # print("obj_meta.unique_component_id", obj_meta.unique_component_id)

            # print("dir(obj_meta.detector_bbox_info)", dir(obj_meta.detector_bbox_info))
            # print("dir(obj_meta.rect_params)", dir(obj_meta.rect_params))
            # print("dir(obj_meta.text_params)", dir(obj_meta.text_params))
            # print("dir( obj_meta.base_meta)", dir(obj_meta.base_meta))
            # print("dir(obj_meta.tracker_bbox_info)", dir(obj_meta.tracker_bbox_info))

            # print("obj_meta.tracker_bbox_info.org_bbox_coords", obj_meta.tracker_bbox_info.org_bbox_coords)
            # print("obj_meta.base_meta.batch_meta", obj_meta.base_meta.batch_meta)
            # print("obj_meta.base_meta.meta_type", obj_meta.base_meta.meta_type)
            # print("obj_meta.base_meta.text_params.display_text",obj_meta.text_params.display_text)
            # print("obj_meta.base_meta.text_params.x_offset",obj_meta.text_params.x_offset)
            # print("obj_meta.base_meta.text_params.y_offset",obj_meta.text_params.y_offset)
            # print("obj_meta.base_meta.text_params.text_bg_clr",obj_meta.text_params.text_bg_clr)
            # print("obj_meta.base_meta.text_params.font_params",obj_meta.text_params.font_params)
            # print("obj_meta.detector_bbox_info.org_bbox_coords", obj_meta.detector_bbox_info.org_bbox_coords)

            # print(
            #     "dir(obj_meta.tracker_bbox_info.org_bbox_coords)",
            #     dir(obj_meta.tracker_bbox_info.org_bbox_coords),
            # )
            # print(
            #     "dir(obj_meta.base_meta.batch_meta)", dir(obj_meta.base_meta.batch_meta)
            # )
            # print(
            #     "dir(obj_meta.detector_bbox_info.org_bbox_coords)",
            #     dir(obj_meta.detector_bbox_info.org_bbox_coords),
            # )

            # print(
            #     "obj_meta.tracker_bbox_info.org_bbox_coords.height",
            #     obj_meta.tracker_bbox_info.org_bbox_coords.height,
            # )
            # print(
            #     "obj_meta.detector_bbox_info.org_bbox_coords.height",
            #     obj_meta.detector_bbox_info.org_bbox_coords.height,
            # )
            # print(
            #     "obj_meta.base_meta.batch_meta.max_frames_in_batch",
            #     obj_meta.base_meta.batch_meta.max_frames_in_batch,
            # )
            # print(
            #     "obj_meta.base_meta.batch_meta.num_frames_in_batch",
            #     obj_meta.base_meta.batch_meta.num_frames_in_batch,
            # )

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
    print("msg", msg)
    # for frame in l_frame:
    #     print()

    # while l_frame is not None:
    #     try:
    #         # Note that l_frame.data needs a cast to pyds.NvDsFrameMeta
    #         # The casting is done by pyds.NvDsFrameMeta.cast()
    #         # The casting also keeps ownership of the underlying memory
    #         # in the C code, so the Python garbage collector will leave
    #         # it alone.
    #         frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
    #     except StopIteration:
    #         break

    #     frame_number = frame_meta.frame_num
    #     l_obj = frame_meta.obj_meta_list
    #     num_rects = frame_meta.num_obj_meta
    #     is_first_obj = True
    #     save_image = False
    #     obj_counter = {
    #         PGIE_CLASS_ID_PERSON: 0,
    #     }
    #     while l_obj is not None:
    #         try:
    #             # Casting l_obj.data to pyds.NvDsObjectMeta
    #             obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
    #         except StopIteration:
    #             break

    #         # print("obj_meta.class_id", obj_meta.class_id)
    # print("obj_meta.object_id", obj_meta.object_id)
    #         # print("obj_meta.confidence", obj_meta.confidence)
    #         # print("obj_meta.tracker_confidence", obj_meta.tracker_confidence)
    #         # print("obj_meta.rect_params", obj_meta.rect_params)
    #         # print("obj_meta.detector_bbox_info", obj_meta.detector_bbox_info)
    #         # print("obj_meta.classifier_meta_list", obj_meta.classifier_meta_list)

    #         # obj_counter[obj_meta.class_id] += 1
    #         # Periodically check for objects with borderline confidence value that may be false positive detections.
    #         # If such detections are found, annotate the frame with bboxes and confidence value.
    #         # Save the annotated frame to file.

    #         # if saved_count["stream_{}".format(frame_meta.pad_index)] % 30 == 0 and (
    #         #     MIN_CONFIDENCE < obj_meta.confidence
    #         # ):
    #         #     if is_first_obj:
    #         #         is_first_obj = False
    #         #         # Getting Image data using nvbufsurface
    #         #         # the input should be address of buffer and batch_id
    #         #         n_frame = pyds.get_nvds_buf_surface(
    #         #             hash(gst_buffer), frame_meta.batch_id
    #         #         )
    #         #         n_frame = draw_bounding_boxes(
    #         #             n_frame, obj_meta, obj_meta.confidence
    #         #         )
    #         #         # convert python array into numpy array format in the copy mode.
    #         #         frame_copy = np.array(n_frame, copy=True, order="C")
    #         #         # convert the array into cv2 default color format
    #         #         frame_copy = cv2.cvtColor(frame_copy, cv2.COLOR_RGBA2BGRA)

    #         #     save_image = True

    #         try:
    #             l_obj = l_obj.next
    #         except StopIteration:
    #             break

    #     # print(
    #     #     "Frame Number=",
    #     #     frame_number,
    #     #     "Number of Objects=",
    #     #     num_rects,
    #     #     "Person_count=",
    #     #     obj_counter[PGIE_CLASS_ID_PERSON],
    #     # )
    #     # Get frame rate through this probe
    #     # fps_streams["stream{0}".format(frame_meta.pad_index)].get_fps()
    #     # if save_image:
    #     #     img_path = "{}/stream_{}/frame_{}.jpg".format(
    #     #         inference_parameter.folder_name, frame_meta.pad_index, frame_number
    #     #     )
    #     #     cv2.imwrite(img_path, frame_copy)
    #     # saved_count["stream_{}".format(frame_meta.pad_index)] += 1

    #     try:
    #         l_frame = l_frame.next
    #     except StopIteration:
    #         break

    return Gst.PadProbeReturn.OK


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

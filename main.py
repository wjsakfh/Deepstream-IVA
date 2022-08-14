#!/usr/bin/env python3

################################################################################
# SPDX-FileCopyrightText: Copyright (c) 2019-2021 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
################################################################################
# python3 /opt/nvidia/deepstream/deepstream-6.0/workspace/Works/Project/Hyundai-Spot-Project/main_maro.py file:///opt/nvidia/deepstream/deepstream-6.0/workspace/Works/Project/Hyundai-Spot-Project/source/spot_cam.mp4
import sys
sys.path.append('../')
import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst
from common.is_aarch_64 import is_aarch64
from common.bus_call import bus_call
from common.utils import *
import pyds
import configparser

import ctypes
import numpy as np


PGIE_CLASS_ID_PERSON = 0
PGIE_CLASS_ID_OBJECT = 1
PGIE_CLASS_ID_FIRE = 2

past_tracking_meta=[0]

OUTPUT_VIDEO_NAME = "./out.mp4"

def main(args):
    # Check input arguments
    if len(args) != 2:
        sys.stderr.write("usage: %s <media file or uri>\n" % args[0])
        sys.exit(1)

    number_sources=len(args)-1

    # Standard GStreamer initialization
    GObject.threads_init()
    Gst.init(None)

    # Create gstreamer elements
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()

    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")

    # Source element for reading from the file
    print("Creating Source \n ")
    source = Gst.ElementFactory.make("filesrc", "file-source")
    if not source:
        sys.stderr.write(" Unable to create Source \n")

    # # Since the data format in the input file is elementary h264 stream,
    # # we need a h264parser
    print("Creating H264Parser \n")
    h264parser = Gst.ElementFactory.make("h264parse", "h264-parser")
    if not h264parser:
        sys.stderr.write(" Unable to create h264 parser \n")

    # # Use nvdec_h264 for hardware accelerated decode on GPU
    print("Creating Decoder \n")
    decoder = Gst.ElementFactory.make("nvv4l2decoder", "nvv4l2-decoder")
    if not decoder:
        sys.stderr.write(" Unable to create Nvv4l2 Decoder \n")

    # Create nvstreammux instance to form batches from one or more sources.
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        sys.stderr.write(" Unable to create NvStreamMux \n")

    pipeline.add(streammux)

    for i in range(number_sources):
        print("Creating source_bin ",i," \n ")
        uri_name=args[i+1]
        if uri_name.find("rtsp://") == 0 :
            is_live = True
        else:
            is_live = False
        source_bin=create_source_bin(i, uri_name)
        if not source_bin:
            sys.stderr.write("Unable to create source bin \n")
        pipeline.add(source_bin)
        padname="sink_%u" %i
        sinkpad= streammux.get_request_pad(padname) 
        if not sinkpad:
            sys.stderr.write("Unable to create sink pad bin \n")
        srcpad=source_bin.get_static_pad("src")
        if not srcpad:
            sys.stderr.write("Unable to create src pad bin \n")
        srcpad.link(sinkpad)

    # Use nvinfer to run inferencing on decoder's output,
    # behaviour of inferencing is set through config file
    pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    if not pgie:
        sys.stderr.write(" Unable to create pgie \n")

    tracker = Gst.ElementFactory.make("nvtracker", "tracker")
    if not tracker:
        sys.stderr.write(" Unable to create tracker \n")

    # sgie1 = Gst.ElementFactory.make("nvinfer", "secondary1-nvinference-engine")
    # if not sgie1:
    #     sys.stderr.write(" Unable to make sgie1 \n")

    # sgie2 = Gst.ElementFactory.make("nvinfer", "secondary2-nvinference-engine")
    # if not sgie2:
    #     sys.stderr.write(" Unable to make sgie2 \n")

    # Use convertor to convert from NV12 to RGBA as required by nvosd
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvidconv \n")

    # Create OSD to draw on the converted RGBA buffer
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
    if not nvosd:
        sys.stderr.write(" Unable to create nvosd \n")

    # Finally render the osd output
    if is_aarch64():
        transform = Gst.ElementFactory.make("nvegltransform", "nvegl-transform")

    # Finally encode and save the osd output
    queue = make_elm_or_print_err("queue", "queue", "Queue")

    nvvidconv2 = make_elm_or_print_err("nvvideoconvert", "convertor2", "Converter 2 (nvvidconv2)")

    capsfilter = make_elm_or_print_err("capsfilter", "capsfilter", "capsfilter")

    caps = Gst.Caps.from_string("video/x-raw, format=I420")
    capsfilter.set_property("caps", caps)

    # On Jetson, there is a problem with the encoder failing to initialize
    # due to limitation on TLS usage. To work around this, preload libgomp.
    # Add a reminder here in case the user forgets.
    preload_reminder = "If the following error is encountered:\n" + \
                       "/usr/lib/aarch64-linux-gnu/libgomp.so.1: cannot allocate memory in static TLS block\n" + \
                       "Preload the offending library:\n" + \
                       "export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1\n"
    encoder = make_elm_or_print_err("avenc_mpeg4", "encoder", "Encoder", preload_reminder)

    encoder.set_property("bitrate", 2000000)

    codeparser = make_elm_or_print_err("mpeg4videoparse", "mpeg4-parser", 'Code Parser')

    container = make_elm_or_print_err("qtmux", "qtmux", "Container")

    print("Creating EGLSink \n")
    sink = Gst.ElementFactory.make("nveglglessink", "nvvideo-renderer")
    # sink = make_elm_or_print_err("filesink", "filesink", "Sink")
    if not sink:
        sys.stderr.write(" Unable to create egl sink \n")

    # sink.set_property("location", OUTPUT_VIDEO_NAME)
    # sink.set_property("sync", 0)
    # sink.set_property("async", 0)

    if is_live:
        print("is_live", is_live)
        print("Atleast one of the sources is live")
        streammux.set_property('live-source', 1)

    # print("Playing file %s " %args[1])
    # source.set_property('location', args[1])
    streammux.set_property('width', 1920)
    streammux.set_property('height', 1080)
    streammux.set_property('batch-size', 1)
    streammux.set_property('batched-push-timeout', 100)
    pgie.set_property('config-file-path', "/home/snu-nx2/Works/Deepstream-IVA/inference_source/pgie/personnet/dstest1_pgie_config.txt")
    # sgie1.set_property('config-file-path', "./source/sgie/HardhatNet_v1.0.0-official_archive/infer_nvinfer_config.txt")
    # sgie2.set_property('config-file-path', "./source/sgie/MaskNet_v1.0.0-official_archive/infer_nvinfer_config.txt")

    #Set properties of tracker
    config = configparser.ConfigParser()
    config.read('/home/snu-nx2/Works/Deepstream-IVA/inference_source/tracker/dstest2_tracker_config.txt')
    config.sections()

    for key in config['tracker']:
        if key == 'tracker-width' :
            tracker_width = config.getint('tracker', key)
            tracker.set_property('tracker-width', tracker_width)
        if key == 'tracker-height' :
            tracker_height = config.getint('tracker', key)
            tracker.set_property('tracker-height', tracker_height)
        if key == 'gpu-id' :
            tracker_gpu_id = config.getint('tracker', key)
            tracker.set_property('gpu_id', tracker_gpu_id)
        if key == 'll-lib-file' :
            tracker_ll_lib_file = config.get('tracker', key)
            tracker.set_property('ll-lib-file', tracker_ll_lib_file)
        if key == 'll-config-file' :
            tracker_ll_config_file = config.get('tracker', key)
            tracker.set_property('ll-config-file', tracker_ll_config_file)
        if key == 'enable-batch-process' :
            tracker_enable_batch_process = config.getint('tracker', key)
            tracker.set_property('enable_batch_process', tracker_enable_batch_process)
        if key == 'enable-past-frame' :
            tracker_enable_past_frame = config.getint('tracker', key)
            tracker.set_property('enable_past_frame', tracker_enable_past_frame)

    print("Adding elements to Pipeline \n")
    # pipeline.add(source)
    # pipeline.add(h264parser)
    # pipeline.add(decoder)
    # pipeline.add(streammux)
    pipeline.add(pgie)
    pipeline.add(tracker)
    # pipeline.add(sgie1)
    # pipeline.add(sgie2)
    pipeline.add(nvvidconv)
    pipeline.add(nvosd)
    pipeline.add(queue)
    # "Save to mp4"
    pipeline.add(nvvidconv2)
    pipeline.add(capsfilter)
    pipeline.add(encoder)
    pipeline.add(codeparser)
    pipeline.add(container)
    #
    pipeline.add(sink)
    if is_aarch64():
        pipeline.add(transform)

    # we link the elements together
    # file-source -> h264-parser -> nvh264-decoder ->
    # nvinfer -> nvvidconv -> nvosd -> video-renderer
    print("Linking elements in the Pipeline \n")
    # source.link(h264parser)
    # h264parser.link(decoder)

    # sinkpad = streammux.get_request_pad("sink_0")
    # if not sinkpad:
    #     sys.stderr.write(" Unable to get the sink pad of streammux \n")
    # srcpad = decoder.get_static_pad("src")
    # if not srcpad:
    #     sys.stderr.write(" Unable to get source pad of decoder \n")
    # srcpad.link(sinkpad)
    streammux.link(pgie)
    # pgie.link(nvvidconv)

    pgie.link(tracker)
    tracker.link(nvvidconv)
    # tracker.link(sgie1)
    # sgie1.link(sgie2)
    
    # pgie.link(sgie1)
    # sgie1.link(sgie2)
    # sgie2.link(nvvidconv)

    # pgie.link(nvvidconv)

    nvvidconv.link(nvosd)
    if is_aarch64():
        nvosd.link(transform)
        transform.link(sink)
    else:
        nvosd.link(sink)

    # nvosd.link(queue)
    # queue.link(nvvidconv2)
    # nvvidconv2.link(capsfilter)
    # capsfilter.link(encoder)
    # encoder.link(codeparser)
    # codeparser.link(container)
    # container.link(sink)

    # create an event loop and feed gstreamer bus mesages to it
    loop = GObject.MainLoop()
    bus = pipeline.get_bus()
    print("bus_call", bus_call)
    print("bus", bus)
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    # pgiesrcpad = pgie.get_static_pad("src")
    # if not pgiesrcpad:
    #     sys.stderr.write(" Unable to get src pad of primary infer \n")
    # pgiesrcpad.add_probe(Gst.PadProbeType.BUFFER, pgie_src_pad_buffer_probe, 0)

    # sgiesrcpad = sgie1.get_static_pad("src")
    # if not sgiesrcpad:
    #     sys.stderr.write(" Unable to get src pad of primary infer \n")
    # sgiesrcpad.add_probe(Gst.PadProbeType.BUFFER, sgie_src_pad_buffer_probe, 0)

    osdsinkpad = nvosd.get_static_pad("sink")
    if not osdsinkpad:
        sys.stderr.write(" Unable to get sink pad of nvosd \n")

    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)

    # start play back and listen to events
    print("Starting pipeline \n")
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    sys.exit(main(sys.argv))


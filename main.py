import sys

sys.path.append("../")
import gi

gi.require_version("Gst", "1.0")
from gi.repository import GObject, Gst
from common.is_aarch_64 import is_aarch64
from common.bus_call import bus_call
from common.utils import *
import pyds
import configparser
from common.FPS import GETFPS
asda
import ctypes
import numpy as np
import cv2
from os import path
import os
import math


def main(args):
    # Check input arguments
    if len(args) < 2:
        sys.stderr.write(
            "usage: %s <uri1> [uri2] ... [uriN] <folder to save frames>\n" % args[0]
        )
        sys.exit(1)

    for i in range(0, len(args) - 2):
        fps_streams["stream{0}".format(i)] = GETFPS(i)
    number_sources = len(args) - 2

    global folder_name
    folder_name = args[-1]
    inference_parameter.folder_name = folder_name

    # if path.exists(folder_name):
    #     sys.stderr.write(
    #         "The output folder %s already exists. Please remove it first.\n"
    #         % folder_name
    #     )
    #     sys.exit(1)

    # os.mkdir(folder_name)
    # print("Frames will be saved in ", folder_name)
    # Standard GStreamer initialization
    GObject.threads_init()
    Gst.init(None)

    # Create gstreamer elements */
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()
    is_live = False

    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")
    print("Creating streamux \n ")

    # Create nvstreammux instance to form batches from one or more sources.
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        sys.stderr.write(" Unable to create NvStreamMux \n")

    pipeline.add(streammux)
    for i in range(number_sources):
        # os.mkdir(folder_name + "/stream_" + str(i))
        frame_count["stream_" + str(i)] = 0
        saved_count["stream_" + str(i)] = 0
        print("Creating source_bin ", i, " \n ")
        uri_name = args[i + 1]
        if uri_name.find("rtsp://") == 0:
            is_live = True
        else:
            is_live = False
        source_bin = create_source_bin(i, uri_name)
        if not source_bin:
            sys.stderr.write("Unable to create source bin \n")
        pipeline.add(source_bin)
        padname = "sink_%u" % i
        sinkpad = streammux.get_request_pad(padname)
        if not sinkpad:
            sys.stderr.write("Unable to create sink pad bin \n")
        srcpad = source_bin.get_static_pad("src")
        if not srcpad:
            sys.stderr.write("Unable to create src pad bin \n")
        srcpad.link(sinkpad)
    print("Creating Pgie \n ")
    pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    if not pgie:
        sys.stderr.write(" Unable to create pgie \n")

    tracker = Gst.ElementFactory.make("nvtracker", "tracker")
    if not tracker:
        sys.stderr.write(" Unable to create tracker \n")

    # Add nvvidconv1 and filter1 to convert the frames to RGBA
    # which is easier to work with in Python.
    print("Creating nvvidconv1 \n ")
    nvvidconv1 = Gst.ElementFactory.make("nvvideoconvert", "convertor1")
    if not nvvidconv1:
        sys.stderr.write(" Unable to create nvvidconv1 \n")
    print("Creating filter1 \n ")
    caps1 = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=RGBA")
    filter1 = Gst.ElementFactory.make("capsfilter", "filter1")
    if not filter1:
        sys.stderr.write(" Unable to get the caps filter1 \n")
    filter1.set_property("caps", caps1)
    print("Creating tiler \n ")
    tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
    if not tiler:
        sys.stderr.write(" Unable to create tiler \n")
    print("Creating nvvidconv \n ")
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvidconv \n")
    print("Creating nvosd \n ")
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
    if not nvosd:
        sys.stderr.write(" Unable to create nvosd \n")
    if is_aarch64():
        print("Creating transform \n ")
        transform = Gst.ElementFactory.make("nvegltransform", "nvegl-transform")
        if not transform:
            sys.stderr.write(" Unable to create transform \n")

    print("Creating EGLSink \n")
    sink = Gst.ElementFactory.make("nveglglessink", "nvvideo-renderer")
    if not sink:
        sys.stderr.write(" Unable to create egl sink \n")

    if is_live:
        print("Atleast one of the sources is live")
        streammux.set_property("live-source", 1)

    streammux.set_property("width", 1920)
    streammux.set_property("height", 1080)
    streammux.set_property("batch-size", number_sources)
    streammux.set_property("batched-push-timeout", 4000000)
    pgie.set_property(
        "config-file-path", "./inference_source/pgie/personnet/dstest1_pgie_config.txt"
    )
    pgie_batch_size = pgie.get_property("batch-size")
    if pgie_batch_size != number_sources:
        print(
            "WARNING: Overriding infer-config batch-size",
            pgie_batch_size,
            " with number of sources ",
            number_sources,
            " \n",
        )
        pgie.set_property("batch-size", number_sources)
    tiler_rows = int(math.sqrt(number_sources))
    tiler_columns = int(math.ceil((1.0 * number_sources) / tiler_rows))
    tiler.set_property("rows", tiler_rows)
    tiler.set_property("columns", tiler_columns)
    tiler.set_property("width", TILED_OUTPUT_WIDTH)
    tiler.set_property("height", TILED_OUTPUT_HEIGHT)

    sink.set_property("sync", 0)
    sink.set_property("qos", 0)

    if not is_aarch64():
        # Use CUDA unified memory in the pipeline so frames
        # can be easily accessed on CPU in Python.
        mem_type = int(pyds.NVBUF_MEM_CUDA_UNIFIED)
        streammux.set_property("nvbuf-memory-type", mem_type)
        nvvidconv.set_property("nvbuf-memory-type", mem_type)
        nvvidconv1.set_property("nvbuf-memory-type", mem_type)
        tiler.set_property("nvbuf-memory-type", mem_type)

    # Set properties of tracker
    config = configparser.ConfigParser()
    config.read(
        "/home/snu-nx2/Works/Deepstream-IVA/inference_source/tracker/dstest2_tracker_config.txt"
    )
    config.sections()

    for key in config["tracker"]:
        if key == "tracker-width":
            tracker_width = config.getint("tracker", key)
            tracker.set_property("tracker-width", tracker_width)
        if key == "tracker-height":
            tracker_height = config.getint("tracker", key)
            tracker.set_property("tracker-height", tracker_height)
        if key == "gpu-id":
            tracker_gpu_id = config.getint("tracker", key)
            tracker.set_property("gpu_id", tracker_gpu_id)
        if key == "ll-lib-file":
            tracker_ll_lib_file = config.get("tracker", key)
            tracker.set_property("ll-lib-file", tracker_ll_lib_file)
        if key == "ll-config-file":
            tracker_ll_config_file = config.get("tracker", key)
            tracker.set_property("ll-config-file", tracker_ll_config_file)
        if key == "enable-batch-process":
            tracker_enable_batch_process = config.getint("tracker", key)
            tracker.set_property("enable_batch_process", tracker_enable_batch_process)
        if key == "enable-past-frame":
            tracker_enable_past_frame = config.getint("tracker", key)
            tracker.set_property("enable_past_frame", tracker_enable_past_frame)

    print("Adding elements to Pipeline \n")
    pipeline.add(pgie)
    pipeline.add(tracker)
    pipeline.add(tiler)
    pipeline.add(nvvidconv)
    pipeline.add(filter1)
    pipeline.add(nvvidconv1)
    pipeline.add(nvosd)
    pipeline.add(sink)
    if is_aarch64():
        pipeline.add(transform)

    print("Linking elements in the Pipeline \n")
    streammux.link(pgie)
    pgie.link(tracker)
    tracker.link(nvvidconv1)
    nvvidconv1.link(filter1)
    filter1.link(tiler)
    tiler.link(nvvidconv)
    nvvidconv.link(nvosd)
    if is_aarch64():
        nvosd.link(transform)
        transform.link(sink)
    else:
        nvosd.link(sink)

    # create an event loop and feed gstreamer bus mesages to it
    loop = GObject.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    tiler_sink_pad = tiler.get_static_pad("sink")
    if not tiler_sink_pad:
        sys.stderr.write(" Unable to get src pad \n")
    else:
        tiler_sink_pad.add_probe(
            Gst.PadProbeType.BUFFER, tiler_sink_pad_buffer_probe, 0
        )

    # List the sources
    print("Now playing...")
    for i, source in enumerate(args[:-1]):
        if i != 0:
            print(i, ": ", source)

    print("Starting pipeline \n")
    # start play back and listed to events
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    print("Exiting app\n")
    pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

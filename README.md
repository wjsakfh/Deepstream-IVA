# Specific Area (ROI) In-Out-Person Re-identification System Using Deepstream

# Install Deepstream

## 1. git clone in working directory
`https://github.com/wjsakfh/Deepstream-IVA.git`

## 2. Docker build (in clone repo directory)
`docker build -t ds-iva:1.0 .`

## 3. Docker run
```
docker run \
-it \
--gpus all \
-v ${PWD}:/opt/workspace \
--network host \
-v /tmp/.X11-unix:/tmp/.X11-unix \
-e DISPLAY=$DISPLAY \
ds-iva:1.0 \
bash
```
## 4. pyds install (in docker contatiner)
```
apt install -y python3-gi python3-dev python3-gst-1.0 python-gi-dev git python-dev python3 python3-pip python3.8-dev cmake g++ build-essential libglib2.0-dev libglib2.0-dev-bin libgstreamer1.0-dev libtool m4 autoconf automake libgirepository1.0-dev libcairo2-dev

cd /opt/nvidia/deepstream/deepstream/sources/
git clone https://github.com/NVIDIA-AI-IOT/deepstream_python_apps

cd /opt/nvidia/deepstream/deepstream/sources/deepstream_python_apps/
git submodule update --init
apt-get install -y apt-transport-https ca-certificates -y
update-ca-certificates

cd /opt/nvidia/deepstream/deepstream/sources/deepstream_python_apps/3rdparty/gst-python/
./autogen.sh
make
make install

cd /opt/nvidia/deepstream/deepstream/sources/deepstream_python_apps/bindings
mkdir build
cd build
cmake ..
make

pip3 install ./pyds-1.1.4-py3-none*.whl
pip3 install numpy opencv-python
```

# Run (in docker container)
`python3 main.py file://xxxx.mp4 file://xxxx.mp4 ... output_dir_path`
- re-id feature saved in output_dir_path
- add multiple videos 

# Additional info
## Engine build process
### PGIE (YOLOV7)
- pgie -> model: YoloV7, [engine build guide repo](https://github.com/marcoslucianops/DeepStream-Yolo)
- ....

### Re-id model (OSNET)
- re-identifier -> [osnet](https://github.com/KaiyangZhou/deep-person-reid)
- ....

## Features
- Use deepstream pipeline
    - primary detector - tracker - secondary classifier - reid - ...

- Support multiple sources

- Implement Alarm Generation Algorithm
    - Intrusion algorithm

- Save cropped image when alarmed

- Save reid features

- Compute distance btw reid features

### Reference
- [reid repo](https://github.com/KaiyangZhou/deep-person-reid)
- [reid deepstream repo](https://github.com/ml6team/deepstream-python)
- [Area intrusion algorithm repo](https://github.com/yas-sim/object-tracking-line-crossing-area-intrusion)
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
pip3 install protobuf numpy opencv-python

cd /opt/workspace
git clone https://github.com/marcoslucianops/DeepStream-Yolo.git
cd DeepStream-Yolo
CUDA_VER=11.7 make -C nvdsinfer_custom_impl_Yolo
cp nvdsinfer_custom_impl_Yolo/libnvdsinfer_custom_impl_Yolo.so /opt/workspace/source/inference_source/pgie
# Specific Area (ROI) In-Out-Person Re-identification System Using Deepstream

## 환경 셋팅

1. Docker를 pull합니다. 
    
    `docker pull [nvcr.io/nvidia/deepstream:6.1.1-devel](http://nvcr.io/nvidia/deepstream:6.1.1-devel)` 
    
    - [nvcr.io/nvidia/deepstream은](http://nvcr.io/nvidia/deepstream은) nvidia에서 제공하는 deepstream 도커이미지 이름이며, 6.1.1-devel는 최신 버전의 tag이름입니다.
2. Docker를 Run합니다
    1. (주의) Run하기 전, 현 위치를 클론한 폴더(Deepstream-IVA) 위치로 이동해야합니다.
    
    ```
    docker run \
    -it \
    --gpus all \
    --restart=always \
    -v ${PWD}:/opt/workspace \
    --network host \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e DISPLAY=$DISPLAY \
    nvcr.io/nvidia/deepstream:6.1.1-devel \
    /bin/bash
    ```
    
    - `-it` 옵션: command line을 사용자가 이용할 수 있게 interaction을 지원합니다.
    - `--gpus all` 옵션: 자원의 모든 gpu를 사용합니다.
    - `--restart=always` 옵션: 재부팅을 해도 docker containter는 살아있습니다.
    - `-v` 옵션: docker containter와 로컬 volume을 마운트시켜줍니다.
3. deepstream 컨테이너에서 workspace로 이동 후 구동에 필요한 라이브러리들을 설치합니다.
    
    `cd /opt/workspace`
    
    `sh initial_prepare.sh`
    
4. 다음 명령어로 영상소스에 대한 버스 승하차 분석 결과를 볼 수 있다.
    
    `python3 [main.py](http://main.py) file:///{동영상소스절대경로}/sample.mp4 file:///{동영상소스절대경로}/sample2.mp4 {output디렉토리경로}`
    
- (참고) docker 환경으로 쉽게 개발하기 위해 vscode extension인 `Dev Containers`를 이용하면 좋다.

## 승하차 이벤트 발생 코드 설명

- 코드는 크게 `core` 디렉토리, `dto` 디렉토리, `main.py`로 이루어진다.
- `core` 디렉토리
    - `[algorithms.py](http://algorithms.py)` : roi내외판정 알고리즘을 포함
    - `[generator.py](http://generator.py)` : roi 침입 이벤트를 발생시키는 로직
    - `[manageDB.py](http://manageDB.py)` : inference로부터 메세지를 받고 이를 처리하는 로직
    - `[reidentifier.py](http://reidentifier.py)`  : re id feature 들의 similarity distance 계산 알고리즘
    - `utils.py`
- `dto` 디렉토리
    - `[Sources.py](http://Sources.py)` : 여러개의 소스를 시스템이 받게 되는데, 그 소스에 대한 클래스
    - `[Obj.py](http://Obj.py)` : infernce 결과로부터 추론된 객체가 있는데, 그 객체에 대한 정보와 메소드가 포함된 클래스
    - `[Ev.py](http://Ev.py)` : Event 설정값에 대한 클래스와 실제 Event에 대한 정보를 담고 있는 클래스
- `main.py`
    - 실제 코드를 동작하기 위한 파일로 argurment로 여러 영상소스 (mp4, rtsp 등)을 받으며 마지막 argument는 탑승과 하차에 대한 객체정보와 이미지를 저장할 디렉토리를 지정한다.
    - `python3 [main.py](http://main.py) file:///동영상소스절대경로/sample.mp4 file:///동영상소스절대경로/sample2.mp4 output경로`
        - ex) `python3 [main.py](http://main.py/) file:///opt/workspace/source/C_cam.mp4 out`

## 주요 설정

- 이벤트 설정
    - 이벤트 설정은 `manageDB.py`에서 이루어진다
        - `event_config = EventConfig(0, 2, True, "take", roi, "person", 1)`
            - `0`: 영상소스 아이디
            - `2` : 이벤트 아이디
            - `True` : 이벤트의 enable, disable 결정
            - `"take"`: 이벤트 이름
            - `roi` : roi 포인트 정보로 [x,y] 포인트로 이루어진 리스트이다.
                - ex) `roi = [[960, 0], [960, 1080], [1920, 1080], [1920, 0]]`
            - `“person”` : 이벤트에 대한 객체의 라벨이름이다
        - 하나의 영상 소스에 하나 이상의 이벤트를 설정할 수 있다.
        - `EVENT_CONFIGS`는 event_config를 포함하는 리스트이다.
- parameter조정
    - 조정할 수 있는 parameter는 이벤트를 얼마나 sensitive하게 발생시킬 건지 결정하는 `WIN_SIZE` 와 `ALARM_THRES` 가 있다. `Obj.py`에 있다.
        - `WIN_SIZE` : 이벤트는 이 윈도우 사이즈 중 일정 Threshold가 넘어가면 이벤트를 발생시킨다. default는 30개이다. 클수록 예민하지 않게 이벤트를 발생시킬 수 있다.
        - `ALARM_THRES` : 이벤트를 발생시킬 지 결정하는 Threshold 값이다. 높을수록 예민하지 않게 이벤트를 발생시킨다.

## 모델 학습

- 여기에 사용되는 모델은 passenger detector로 yolov7, mask classifier로 resnet, re-identifier feature extractor로 osnet 모델(https://github.com/KaiyangZhou/deep-person-reid)을 각각 사용했고 Customizing하게 학습시킨 모델은 Detector yolov7이다.
- yolov7 모델 학습은 공식레포(https://github.com/WongKinYiu/yolov7.git)를 이용했으며, 학습 후 yolov7모델을 tensorrt engine파일로 변환하는 작업은 다음 레포(https://github.com/marcoslucianops/DeepStream-Yolo) 를 참고하였다.
    - 데이터 위치: NIPA서버 (IP: 14.49.45.209) - `~/Projects/Bus_passenger_AIHUB/data`
        
        ```
        Bus_passenger_AIHUB
        ├── data
            ├── images
            ├── labels
            └── val
        ```
        

## 구동 결과 저장

- 아래 코드의 결과는 `{output디렉토리경로}`에 `{output디렉토리경로}/in`과 `{output디렉토리경로}/out` 으로 저장된다.
    - `python3 [main.py](http://main.py) file:///{동영상소스절대경로}/sample.mp4 file:///{동영상소스절대경로}/sample2.mp4 {output디렉토리경로}`
- in (or out)에는 roi로 설정한 이벤트 내부 (or 외부) 로 객체(person)이 들어왔을 때 (or 나갔을때) 객체에 대한 meta data와 이미지 데이터가 함께 저장된다.
    - 0_2_take_in.jpg (or 0_2_take_out.jpg) 이름 설명 및 이미지 내용
        - `0` : 영상소스 고유 id
        - `2` : 객체의 고유 id
        - `take` : 설정한 이벤트 이름
        - `in` (or `out`): 내부로 들어온 이벤트임을 명시
        - 이미지 내용 : 이벤트가 발생했을 때의 객체의 bbox crop 이미지
    - 0_2_intrusion_out_in.json (or 0_2_take_out.json) 내용
        - `source_id` : 영상소스 고유 id
        - `event` : in인지 out인지 명시
        - `obj_id` : 객체의 고유 id
        - `reid_feature` : re-id feature extractor로부터 나온 feature array
        - `secondary_info` : classifier 정보
        - `init_time` : 객체가 생성된 시간
        - `last_time` : 객체가 최신 업데이트된 시간

## Reid feature matching

- reid feature는 위에서 사용된 osnet reid feature extractor모델로부터 추출된다.
- 이는 json결과로 저장되며 “reid_feature”키에 포함된다.
- 어느 시점에 정확히 matching 알고리즘이 구동되어야하는지 정해진 것은 없지만 버스 승객 결과가 어느정도 모인 뒤에 구동될 것이라고 생각된다.
- 따라서 matching알고리즘에 대한 test code를 `re-id.ipynb` 파일로 제공한다.
    - 이는 matching알고리즘(euclidian, cosine distance)에 대한 내용과 in폴더와 out폴더에서 저장된 meta 정보의 json파일을 읽어오는 부분과 distance를 구해주는 부분으로 나뉜다.

## Reference
- [reid repo](https://github.com/KaiyangZhou/deep-person-reid)
- [reid deepstream repo](https://github.com/ml6team/deepstream-python)
- [Area intrusion algorithm repo](https://github.com/yas-sim/object-tracking-line-crossing-area-intrusion)

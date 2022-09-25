# Specific Area (ROI) In-Out-Person Re-identification System Using Deepstream

## Background
- 실시간으로 여러 영상에서 특정 공간에 들어오고 나가는 사람에 대해 탐지하며, 들어온 사람과 나간 사람이 동일한 경우에 대해 매칭을 시켜주는 시스템이다.
- 이는 대중교통의 승하차 시스템에 적용되어 특정인의 승차지와 하차지를 인지할 수 있다. 

### Features
- Use deepstream pipeline
    - primary detector - tracker - secondary classifier - reid - ...

- Support multiple sources

- Implement Alarm Generation Algorithm
    - Intrusion algorithm

- Save cropped image when alarmed

- Save reid features

### Limitations

### Known Issues

### Reference
- [reid repo](https://github.com/KaiyangZhou/deep-person-reid)
- [reid deepstream repo](https://github.com/ml6team/deepstream-python)
- [Area intrusion algorithm repo](https://github.com/yas-sim/object-tracking-line-crossing-area-intrusion)
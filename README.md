# Specific Area (ROI) In-Out-Person Re-identification System Using Deepstream

## Background
- It is a system that detects who enters and leaves a specific space from multiple stream sources in real time, and matches the case where the person entering and leaving are the same.
- This can be applied to the boarding and disembarking system of public transportation to recognize a specific person's boarding and disembarking point.

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
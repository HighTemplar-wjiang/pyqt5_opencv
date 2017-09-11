# pyqt5_opencv
Cross-platform object tracking tool using pyqt5 and opencv3

Dependencies:
- Python3
- PyQt5
- OpenCV3

Usage:
- Run "python qtcv.py"
- Open your web camera or load a video file
- (Optional) Calibrate: click-and-drag to select a reference line for real-world measurement, this will tell you the displacement of your tracking point in centimeter
  - Note: the __assumption__ is that the distance between each point of your video surface and the lens is identical
- Click-and-drag to select the object you want to track
- Click *Start* to tracking, you may click *Pause* at any time as well.
-- You may also use *Start* and *Pause* to position the frame in which you trakcing object is

Data:
- In the right-top corner, the real-time pixel coordinate of your tracking point and its measured displacement appear in the first line and the second line respectively
- When the tracking finished, tracking data named after *(current time).csv* will be saved in the ./data folder

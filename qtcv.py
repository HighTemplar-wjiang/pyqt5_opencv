#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Python 2/3 compatibility
from __future__ import print_function

import os
import sys
import datetime
import cv2
import numpy as np
from PyQt5.QtCore import QTimer, QEvent, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QFileDialog, QApplication, QMainWindow, QInputDialog

# local import
import qtcvui

# Python 2/3 compatibility
PY3 = sys.version_info[0] == 3

if PY3:
    xrange = range


class Qtcv(QMainWindow, qtcvui.Ui_MainWindow):
    def __init__(self):
        super(Qtcv, self).__init__()
        self.setupUi(self)

        # init parameters
        self.timer = None
        self.frame = None
        self.capture = None
        self.videoFileName = None
        self.isVideoFileLoaded = False

        # tracking parameters
        self.selection = None
        self.dragStart = None
        self.showBackproj = False
        self.trackWindow = None
        self.timestamps = []
        self.trackPoints = []
        self.movePoints = []  # movement in real world
        self.mouseOffset = (0, 0)

        # calibration
        self.isCalibrating = False
        self.isCalibrated = False
        self.calStart = (0, 0)
        self.calEnd = (0, 0)
        self.referLen = 0
        self.unitPerPixel = 0

        # streaming parameters
        self.fps = 30
        self.frameSize = (self.videoWidget.geometry().width(), self.videoWidget.geometry().height())
        self.frameRatio = 1

        # connect signals
        self.buttonCamera.clicked.connect(self.set_camera)
        self.buttonLoad.clicked.connect(self.load_file)
        self.buttonStart.clicked.connect(self.start_video)
        self.buttonPause.clicked.connect(self.pause_video)
        self.buttonCal.clicked.connect(self.calibrate)

    def closeEvent(self, QCloseEvent):
        self._log_tracking()
        super(Qtcv, self).closeEvent(QCloseEvent)

    def mousePressEvent(self, QMouseEvent):
        x, y = QMouseEvent.pos().x(), QMouseEvent.pos().y()

        if self.isCalibrating:
            self.calStart = (int(x), int(y))
        else:
            self.dragStart = (x, y)
            self.trackWindow = None

    def mouseMoveEvent(self, QMouseEvent):
        x, y = QMouseEvent.pos().x(), QMouseEvent.pos().y()

        if self.isCalibrating:

            self.calEnd = (int(x), int(y))
            vis = self.frame.copy()
            cv2.circle(vis, self.calStart, 2, (0, 255, 0), -1)
            cv2.circle(vis, self.calEnd, 2, (0, 255, 0), -1)
            cv2.polylines(vis, [np.array([self.calStart, self.calEnd])], False, (0, 255, 0))
            self._draw_frame(vis)

        else:

            if self.dragStart:
                xmin = min(x, self.dragStart[0])
                ymin = min(y, self.dragStart[1])
                xmax = max(x, self.dragStart[0])
                ymax = max(y, self.dragStart[1])
                self.selection = (xmin, ymin, xmax, ymax)

                frame = self.frame.copy()
                cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 255, 0))
                self._draw_frame(frame)

    def mouseReleaseEvent(self, QMouseEvent):
        x, y = QMouseEvent.pos().x(), QMouseEvent.pos().y()

        if self.isCalibrating:
            self.calEnd = (int(x), int(y))
            referLen, ok = QInputDialog.getDouble(self, 'Input reference', 'Length (cm)')
            if ok and referLen:
                self.referLen = referLen
                self.unitPerPixel = referLen / float(np.hypot(self.calEnd[0] - self.calStart[0],
                                                              self.calEnd[1] - self.calStart[1]))
                self.isCalibrating = False
                self.isCalibrated = True
        else:
            xmin, ymin, xmax, ymax = self.selection
            self.dragStart = None
            self.trackWindow = (xmin, ymin, xmax - xmin, ymax - ymin)

    def calibrate(self):
        self.pause_video()
        self.isCalibrating = True

    def _pixel2unit(self, pixels):
        if self.isCalibrated:
            return pixels * self.unitPerPixel
        else:
            print('Error: Must calibrate before measuring')

    def _show_hist(self):
        bin_count = self.hist.shape[0]
        bin_w = 24
        img = np.zeros((256, bin_count * bin_w, 3), np.uint8)
        for i in range(bin_count):
            h = int(self.hist[i])
            cv2.rectangle(img, (i * bin_w + 2, 255), ((i + 1) * bin_w - 2, 255 - h),
                          (int(180.0 * i / bin_count), 255, 255), -1)
        img = cv2.cvtColor(img, cv2.COLOR_HSV2BGR)
        #cv2.imshow('hist', img)

    def _log_tracking(self):
        if len(self.timestamps) == 0:
            return

        try:
            if not os.path.exists('./data'):
                os.makedirs('./data')

            # log raw data
            if self.isVideoFileLoaded:
                logName = "./data/" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_video_raw.csv"
            else:
                logName = "./data/" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_raw.csv"
            with open(logName, 'w+') as f:
                for time, item in zip(self.timestamps, self.trackPoints):
                    f.write(str(time) + ',' + str(int(item[0])) + ',' + str(int(item[1])) + '\n')

            # log movement data
            if len(self.movePoints) > 0:
                if self.isVideoFileLoaded:
                    logName = "./data/" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_video_move.csv"
                else:
                    logName = "./data/" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_move.csv"
                with open(logName, 'w+') as f:
                    for time, item in zip(self.timestamps, self.movePoints):
                        f.write(str(time) + ',' + str(item[0]) + ',' + str(item[1]) + '\n')

        except Exception as e:
            print(str(e))

    def _tracking(self, frame):
        vis = frame.copy()
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array((0., 60., 32.)), np.array((180., 255., 255.)))

        cv2.polylines(vis, [np.array([[500, 1056], [600, 1200]], np.int32)], False, (0, 255, 0))

        if self.selection:
            x0, y0, x1, y1 = self.selection
            hsv_roi = hsv[y0:y1, x0:x1]
            mask_roi = mask[y0:y1, x0:x1]
            self.hist = cv2.calcHist([hsv_roi], [0], mask_roi, [16], [0, 180])
            cv2.normalize(self.hist, self.hist, 0, 255, cv2.NORM_MINMAX)
            self.hist = self.hist.reshape(-1)

            vis_roi = vis[y0:y1, x0:x1]
            cv2.bitwise_not(vis_roi, vis_roi)
            # vis[mask == 0] = 0

        if self.trackWindow and self.trackWindow[2] > 0 and self.trackWindow[3] > 0:
            self.selection = None
            prob = cv2.calcBackProject([hsv], [0], self.hist, [0, 180], 1)
            prob &= mask
            term_crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 1)
            track_box, self.trackWindow = cv2.CamShift(prob, self.trackWindow, term_crit)

            if self.showBackproj:
                vis[:] = prob[..., np.newaxis]
            try:
                cv2.ellipse(vis, track_box, (0, 0, 255), 2)
                point_track = track_box[0]

                if (point_track != (0, 0)) and isinstance(point_track, tuple) and (point_track not in self.trackPoints):
                    self.timestamps.append(self.capture.get(0))  # get timestamp
                    self.trackPoints.append(point_track)

                    if self.isCalibrated:
                        point_move = (point_track[0] - self.trackPoints[0][0], point_track[1] - self.trackPoints[0][1])
                        point_move = tuple(map(self._pixel2unit, point_move))
                        self.movePoints.append(point_move)
                        self.labelPos.setText("<font color='red'>({:.1f}ms: {:.4f}cm, {:.4f}cm)</font>".format(
                            self.timestamps[-1], point_move[0], point_move[1]))

                cv2.circle(vis, (int(point_track[0]), int(point_track[1])), 2, (0, 255, 0), -1)
                cv2.polylines(vis, [np.array([np.int32(list(tr)) for tr in self.trackPoints])], False, (0, 255, 0))

                # display tracking point
                self.labelTrack.setText("<font color='red'>({:.1f}ms: {:.0f}, {:.0f})</font>".format(
                    self.timestamps[-1], point_track[0], point_track[1]))

            except Exception as e:
                print("Exception while drawing")
                print(e)
                print(track_box)

        return vis

    def _draw_frame(self, frame):
        # convert to pixel
        cvtFrame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = QImage(cvtFrame, cvtFrame.shape[1], cvtFrame.shape[0], QImage.Format_RGB888)
        pix = QPixmap.fromImage(img)

        self.videoWidget.setPixmap(pix)

    def _next_frame(self):
        try:
            if self.capture is not None:
                _ret, frame = self.capture.read()

                # resize
                if self.isVideoFileLoaded:
                    frame = cv2.resize(frame, (0, 0), fx=self.frameRatio, fy=self.frameRatio)
                self.frame = frame.copy()

                # tracking
                frame = self._tracking(frame)

                self._draw_frame(frame)

                # # convert to pixel
                # frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # img = QImage(frame, frame.shape[1], frame.shape[0], QImage.Format_RGB888)
                # pix = QPixmap.fromImage(img)
                #
                # self.videoWidget.setPixmap(pix)

        except Exception as e:
            self.pause_video()
            print("Error: Exception while reading next frame")
            print(str(e))
            self._log_tracking()

    def set_camera(self):
        try:
            if self.capture is not None:
                self.pause_video()
                self.capture.release()
            self.capture = cv2.VideoCapture(0)

            # get frame ratio to shrink
            width = self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
            self.fps = self.capture.get(cv2.CAP_PROP_FPS)

            # start
            self.start_video()
        except:
            self.pause_video()
            self.capture = None
            print("Error: Cannot open your camera")
        finally:
            self.timestamps = []
            self.trackPoints = []
            self.isVideoFileLoaded = False

    def load_file(self):
        try:
            self.pause_video()

            self.videoFileName = QFileDialog.getOpenFileName(self, 'Select .h264 Video File')[0]
            self.isVideoFileLoaded = True

            if self.capture is not None:
                self.capture.release()
            self.capture = cv2.VideoCapture(self.videoFileName)

            # get frame ratio to shrink
            width = self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
            self.fps = self.capture.get(cv2.CAP_PROP_FPS)
            self.frameRatio = min(self.frameSize[0] / width, self.frameSize[1] / height)

            # get the first frame
            self._next_frame()

        except Exception as e:
            self.capture = None
            self.isVideoFileLoaded = False
            print("Error: Exception while selecting&opening video file")
            print(str(e))

        finally:
            self.timestamps = []
            self.trackPoints = []

    def start_video(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._next_frame)
        self.timer.start(1000.0 / self.fps)

    def pause_video(self):
        try:
            self.timer.stop()
        except Exception as e:
            print("Error: Exception while pausing")
            print(str(e))

    @staticmethod
    def run():
        app = QApplication(sys.argv)  # A new instance of QApplication
        form = Qtcv()  # We set the form to be our ExampleApp (design)
        form.show()  # Show the form
        app.exec_()  # and execute the app


if __name__ == '__main__':
    Qtcv.run()

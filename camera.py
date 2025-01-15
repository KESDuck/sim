import cv2 as cv
from config import CAMERA_MATRIX, DIST_COEFFS

class CameraHandler:
    def __init__(self, cam_num=0):
        self.cap = cv.VideoCapture(cam_num)
        self.spin_angle = 0  # Angle for spinning indicator

    def get_frame(self):
        ret, frame = self.cap.read()
        if ret:
            frame_color = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            frame_undistort = cv.undistort(frame_color, CAMERA_MATRIX, DIST_COEFFS)
            self.add_spinning_indicator(frame_undistort)
            return frame_undistort
        return None

    def add_spinning_indicator(self, frame):
            """
            Adds a spinning indicator to the top-right corner of the frame.
            """
            height, width, _ = frame.shape
            center = (width - 30, 30)  # Top-right corner
            radius = 20
            thickness = 2

            # Increment the spinning angle
            self.spin_angle = (self.spin_angle + 10) % 360

            # Draw the spinning arc
            start_angle = self.spin_angle
            end_angle = (self.spin_angle + 60) % 360  # 60-degree arc

            # Handle cases where the end_angle wraps around 360
            if end_angle < start_angle:
                # Draw two arcs to handle wrapping
                cv.ellipse(frame, center, (radius, radius), 0, start_angle, 360, (255, 0, 0), thickness)
                cv.ellipse(frame, center, (radius, radius), 0, 0, end_angle, (255, 0, 0), thickness)
            else:
                # Draw a single arc
                cv.ellipse(frame, center, (radius, radius), 0, start_angle, end_angle, (255, 0, 0), thickness)



    def release(self):
        self.cap.release()

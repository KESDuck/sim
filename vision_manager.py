import numpy as np
import cv2 as cv

from logger_config import get_logger
from camera import CameraHandler
from config import CAMERA_MATRIX, HOMO_MATRIX
from tools import draw_cross, find_centroids, draw_points, save_image, determine_bound, sort_centroids

logger = get_logger("Vision")

class VisionManager():
    """
    Capture using "Camera" class, apply threshold, apply contour, draw centroids, record centroids location
    TODO: Save image
    """
    def __init__(self):
        self.camera = CameraHandler(cam_type="usb", camera_matrix=None, dist_coeffs=None)
        self.first_frame()

        # image frame and points, (all being saved during process_image)
        self.frame_camera = None # right after undistort
        self.frame_threshold = None # right after threshold
        self.frame_contour = None # with contour
        self.centroids = None # list of cenrtroids

    def first_frame(self):
        frame = self.camera.get_frame()
        logger.info(f"Frame shape: {frame.shape}")

    def capture_and_process(self, process=False):
        """
        Process takes more time, so should not do it unless user told to
        By default it should store frame directly from camera (for displaying live image).
        Does not return anything
        Store the frames in VisionManager instance: frame_camera, frame_threshold, frame_contour
        Centroids location is also stored
        """

        # TODO: add these to param
        threshold_value = 135
        min_area = 500
        max_area = 800
        crop_region = None
        alpha = 0.5

        # get frame (preprocessed)
        self.frame_camera = self.camera.get_frame() # grayscale image
        
        if process:
            # threshold
            _, thres = cv.threshold(self.frame_camera, threshold_value, 255, cv.THRESH_BINARY)

            # contours
            contours, _ = cv.findContours(thres, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

            # Filter Contours
            filtered_contours = [cnt for cnt in contours if min_area < cv.contourArea(cnt) < max_area]

            # Find Centroids
            centroids = []
            for cnt in filtered_contours:
                x, y, w, h = cv.boundingRect(cnt)
                aspect_ratio = w / h
                if 0.8 <= aspect_ratio <= 1.2:
                    M = cv.moments(cnt)
                    if M["m00"] != 0:
                        cX = int(M["m10"] / M["m00"])
                        cY = int(M["m01"] / M["m00"])
                        if determine_bound((cX, cY), crop_region):
                            centroids.append((cX, cY))

            ##### SAVING #####
            # All the converting and returning
            self.frame_threshold = cv.cvtColor(thres, cv.COLOR_GRAY2BGR)

            contour_overlay = self.frame_threshold.copy()
            for cnt in filtered_contours: # Draw the contours
                cv.drawContours(contour_overlay, [cnt], -1, (0, 255, 0), 2)  # Green for contours

            self.frame_contour = contour_overlay
            self.centroids = sort_centroids(centroids)

            logger.info(f"Total centroids found: {len(self.centroids)}")



        # if self.view_state == "live" or self.view_state == "live_clear":
        #     frame = self.camera.get_frame()
        # elif self.view_state == "paused_orig":
        #     frame = self.frame_saved
        # elif self.view_state == "paused_thres":
        #     frame = self.frame_threshold
        # elif self.view_state == "paused_contours":
        #     frame = self.frame_contour

        # if frame is None:
        #     return
        # frame = frame.copy()

        # if self.centroids and self.view_state != "live_clear":
        #     draw_points(frame, self.centroids, self.cell_index.value())
        # draw_cross(frame, self.cam_cross_pos[0], self.cam_cross_pos[1])
        
        # if self.save_next_frame:
        #     save_image(frame)
        #     self.save_next_frame = False

        # return frame


    # def process_image(self):
    #     """
    #     Capture the current frame
    #     Also process the image to find centroids
    #     Reset centroid index
    #     """
    #     self.cell_index.setValue(-1)

    #     image = self.camera.get_frame()
    #     if image is None:
    #         return

    #     # process image
    #     process_dict = find_centroids(image)

    #     self.frame_saved = image
    #     self.frame_threshold = process_dict["threshold"]
    #     self.frame_contour = process_dict["contour_overlay"]
    #     self.centroids = process_dict["centroids"]

    #     self.cell_index.setMaximum(len(self.centroids) - 1)

    #     logger.info(f"Total centroids found: {len(self.centroids)}")
    #     self.next_centroid()

    def next_centroid(self):
        """Point self.cam_cross_pos to the next centroid in self.centroids"""
        # TODO: If finish, return none
        if not self.centroids:
            logger.error("No centroids found")
            return
        
        self.cell_index.setValue(self.cell_index.value() + 1) # increment cell index

        if self.cell_index.value() < len(self.centroids):
            x, y = self.centroids[self.cell_index.value()]
            self.set_cross_position(x, y)
            logger.info(f"Centroid #{self.cell_index.value()}: {x}, {y}")
        else:
            logger.info("No more centroids to go next")

    def close(self):
        # Release the camera
        if hasattr(self.camera, 'release') and callable(self.camera.release):
            self.camera.release()
        
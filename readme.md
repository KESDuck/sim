- [Usage:](#usage)
  - [Ideal operation (happy path)](#ideal-operation-happy-path)
  - [Dependency Tree](#dependency-tree)
  - [UI](#ui)
  - [Main insertion operation](#main-insertion-operation)
  - [Camera Setup](#camera-setup)
  - [Vision cycle](#vision-cycle)
  - [Messaging protocol](#messaging-protocol)
  - [Homography Calibration](#homography-calibration)
  - [Insert ActionLoop routine](#insert-actionloop-routine)
- [Milestones](#milestones)
  - [1 Screw (2024-03-11)](#1-screw-2024-03-11)
  - [10 screws (2024-11-26)](#10-screws-2024-11-26)
  - [100 screws (2025-02-11)](#100-screws-2025-02-11)
  - [1000 screws (TODO)](#1000-screws-todo)
  - [10000 screws (TODO)](#10000-screws-todo)
- [Reflections](#reflections)
    - [1 screw](#1-screw)
    - [10 screws](#10-screws)
    - [100 screws](#100-screws)
- [App manual unit tests:](#app-manual-unit-tests)
    - [window](#window)
    - [cross](#cross)
    - [others](#others)
- [Error Analysis](#error-analysis)


# Usage:
This application is a robot vision system that integrates a camera, robot arm, and user interface for precise operations like screw insertion. It consists of multiple components that communicate through message protocols, and it features a homography-based calibration system to convert camera coordinates to robot coordinates.

## Ideal operation (happy path)
1. Setup
    - Feeder is set to the correct screw diameter using precision stairs. Add screws to the feeder (or vibratory feeder)
    - Insert frame and web plate, secure on conveyor
    - Turn on robot and computers. Make sure all is connected with ethernet: robot controller, python script computer, RC+ computer, camera. Start python script and RC+ program.
3. Press start, robot starts main insertion operation
    a. Robot move camera to position
    b. Camera grab frame
    c. Process image to return list of cell location in robot coordinate
    d. Send each coordinate to robot
    e. Robot returns "taskdone" for each insertion, and loop until all cells are inserted
4. When completed the loaded frame is ejected from the robot ready for pick up


## Dependency Tree
```
main
└── AppUI (User Interface)
    ├── GraphicsView (Handles zoom & display)
    └── AppManager (Controls entire system)
        ├── RobotManager (Controls robot movement)
        │   └── RobotSocket (Handles TCP/IP communication with robot)
        └── VisionManager (Handles camera and image processing)
            ├── CameraHandler (Manages camera operations)
            └── image_processing (Applies image thresholding & contour detection)
```


## UI
Live Camera Mode (Real-time updates)
Paused Original Image (For fine-tuning)
Thresholded Image (Processed for centroids)
Contours Mode (Overlays detected contours)
Crosshair Adjustment (Arrow keys & WASD & Mouse Click)
Robot Commands (Jump, Insert, Echo)
Saving Processed Frames

## Main insertion operation

Buttons: Start, Stop, Num box,

## Camera Setup
Webcam
iPhone
Basler (pylon)
- Use pylon IP configurator or pylon Viewer
acA2500-14gm 16mm
- 15x20 cells, 90 pixel per cell

## Vision cycle
```
Flow of Operations:  
    Camera image (camera.py)  
    -> Modify color channel  
    -> cv.undistort

Process button (process_image):  
    -> save                    [self.frame_saved]  
    -> cv2.threshold and save  [self.frame_threshold]  
    -> cv2.findContours        [self.frame_contour]  
    -> filter contour based on size  
    -> find centroids  
    -> filter centroids based on location and store [self.centroids]  

update_frame:
-> depends on state, shows different frame
-> Overlay, draw cross and points on the image (draw_cross)
-> Convert to QImage so it can be zoomed in and out
```
## Messaging protocol
First connect timeout 60s
Will try to connect every 5s if not connected

Python - Nonblocking messaging setup using qtimer. (Because using QTimer is generally the best practice over QApplication.processEvents() in most scenarios. )
- Send msg "insert X Y Z U" with ack msg "ack"

Robot:
- Received msg and send "ack"
- Perform task based on the command, first word decide which function to perform
- If task completed successfully, send msg "taskdone"

Python:
- wait for confirm msg "taskdone"
- Start next cycle

## Homography Calibration
Teach robot tooling (in Robot Manager) 
1. setup hardware:
    - Have a matrix of known points. The points should be at Z-axis of the insertion plate, plane parallel to the ground. (Place it slightly above the 3x3)
    - Turn gripper: move z up and down to see if it is straight. If not loosen the screws to adjust.
    - Rotate gripper make sure it is centered. If not reteach the tool in RC+.
    - Make sure the calibration grid is stable so it will not move if robot touch it
2. Move camera to correct position. Process image and note their points in image coordinate. Save the image in case needed later.
3. let robot go to those positions and note the positions.
4. Move the camera back to capture position, make sure it is not shifted
5. Feed the data to find_homography.py and make sure error is low (<0.2mm). Put the homography matrix in config.yml



## Insert ActionLoop routine
start if CommandReady == 1 and RobotCommand == "insert"
- On off feeder to drop screw
- Jump to FeederReady position
- Go to FeederReceive
- On gripper (close)
- Go to FeederReady
- Jump to next open cell position
- Off gripper (open)
- Move back (-y) for clearance
- Set CommandReady = 0

# Milestones
## 1 Screw (2024-03-11)
Manual robot alignment using visual inspection
Gantry type system for movement

## 10 screws (2024-11-26)
Vision system to detect cells to insert
One by one insert routine with human intervention
Auto feeder for screw supple
HMI:
- Live camera mode for monitoring
- Display centroid centers

## 100 screws (2025-02-11)
Continuously insert without little human interference
One vision section
Communication protocol and error handling
Capture and process image including moving robot to position
HMI
- Pause and resume
- Able to start from any cell

## 1000 screws (TODO)
Multiple vision sections for large-area processing
Conveyor tracking
Insert the 1 whole plate
Very little error
Automatic calibration

## 10000 screws (TODO)
End-to-end automation
Adaptive error handling

# Reflections
### 1 screw
- Gantry too complex to maintain

### 10 screws
- Parallex error is bad, need to capture image in sections
- Careful homography calibration is critical
- Not all setup requires camera calibration

### 100 screws
- HMI system can get buggy easily
- 

# App manual unit tests:
### window
- Resize the window so nothing weird happen

### cross
- When clicked, the cross is at right position and shows the robot coordinate
- Arrow keys moves the cross, WASD moves the cross 10px
- When zoomed in, the mouse click to the right position
- Press R Key to record current cross position

### others
- Image is actually saved
- TCPIP sends in the right format: (str(message).encode()) + b"\r\n"
- When sending message and while waiting for 'taskdone', UI is still responsive

# Error Analysis
1. Parallex Error due to variation in height
    - WD 600mm
    - V_Err = 5mm
    - H_Err = 0.1mm (@10mm), 0.4 (50), 0.8 (100), 1.3 (500)
2. Homography calibration error (~0.1mm)
3. Camera calibration error (camera matrix, distortion vector)
4. Robot tool calibration error (including end effector hardware)
5. Camera resolution error
6. Screw bending
7. Plate shifted after capture image


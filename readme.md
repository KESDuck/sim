# Usage:
This application is a robot vision system that integrates a camera, robot arm, and user interface for precise operations like screw insertion. It consists of multiple components that communicate through message protocols, and it features a homography-based calibration system to convert camera coordinates to robot coordinates.

## Ideal operation (happy path)
1. hardware setup: feeder is set to the correct screw diameter using precision stairs. Add screws to the feeder (or vibratory feeder)
2. Insert frame and web plate, secure on conveyor
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
    - known points
2. take picture and note their points in image coordinate
3. let robot go to those positions


1. 
1. Start both the robot script and vision app
2. 

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
## 1 Screw (Date: )
Manual robot alignment with eye

## 10 screws (Date: )
Camera and robot to find all positions
One by one insert
Human nearby to make sure its accurate

## 100 screws (current)
Continuously insert
Error handling for communication
Start and resume functionality
Automatic calibration

## 1000 screws
Conveyor tracking
Insert the 1 whole plate
Very little error

## 10000 screws
Fully automate

# App manual unit tests:
## window
- Resize the window so nothing weird happen

## cross
- When clicked, the cross is at right position and shows the robot coordinate
- Arrow keys moves the cross, WASD moves the cross 10px
- When zoomed in, the mouse click to the right position
- Press R Key to record current cross position

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

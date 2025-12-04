- [Usage:](#usage)
  - [Ideal operation (happy path)](#ideal-operation-happy-path)
  - [Dependency Tree](#dependency-tree)
  - [UI Features](#ui-features)
  - [Using the HMI](#using-the-hmi)
  - [Camera Setup](#camera-setup)
  - [Vision cycle](#vision-cycle)
  - [Robot Messaging Protocol (old, 100 screws)](#robot-messaging-protocol-old-100-screws)
  - [Dual Process Robot Protocol (1000 screws)](#dual-process-robot-protocol-1000-screws)
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
- [Error Analysis](#error-analysis)
- [Tasks](#tasks)


# Usage:
This app is a robot vision system that integrates camera (pylon), robot (TCPIP), and UI for screw insertion. It consists of multiple components that communicate through message protocols, and it features a homography-based calibration system to convert camera coordinates to robot coordinates.

## Namings

- Cell coordinate: contours center, centroids, screw locations
- Insertion region: capture id, batch insert section, vision section
- Template: 模型版
- Web plate: tray盤
- 3x3: rack, 九宮格
- Grabber: retriver
- Feeder:  
- Pickup station

## Ideal operation (happy path)
1. Setup  
    - Feeder: set to the correct screw diameter using precision stairs. Add screws to the feeder (or vibratory feeder)  
    - Insert frame and web plate, secured on conveyor  
    - Components connected with ethernet and turned on: robot controller, python script computer, RC+ computer, camera. Start python script and RC+ program.  
3. Press start, robot starts main insertion operation. Do a batch insert for each insertion region:  
    a. Robot move camera to position  
    b. Camera grab frame  
    c. Process image to return list of cell locations in robot coordinate. And for each cell:  
        d. Send each coordinate to robot  
        e. Robot returns "taskdone" for each insertion, and loop until all cells are inserted  
4. When completed the loaded frame is ejected from the robot ready for pick up  

## UI
Operator mode: Start, Stop, Insertion region spin box  
Engineer mode: 
    - Live Camera Mode (Real-time updates)  
    - Paused Original Image (For fine-tuning)  
    - Thresholded Image (Processed for centroids)  
    - Contours Mode (Overlays detected contours)  
    - Crosshair Adjustment (Arrow keys & WASD & Mouse Click)  
    - Robot Commands (Jump, Insert, Echo)  
    - Saving Processed Frames  

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

capture_process_frame:
-> depends on state, shows different frame
-> Overlay, draw cross and points on the image (draw_cross)
-> Convert to QImage so it can be zoomed in and out
```

## Messaging Protocol

### Robot States
- State 0: **DISCONNECTED** - No TCP client connected
- State 1: **IDLE** - Waiting for command
- State 2: **MOVING** - Move to X/Y/Z/U
- State 3: **INSERTING** - Insert operation using queued coordinates
- State 4: **TESTING** - Test operation using queued coordinates
- State 5: **EMERGENCY** - Stop requested or error

### Robot Status Updates
- Robot sends status every 1 second: `STATUS {state}, {x}, {y}, {z}, {u}, {index}, {queue_size}`
- Example: `STATUS 1, 120.1, 203.3, 50.0, 90.0, 0, 0`
- App synchronizes with robot state every second
- App displays error if its state differs from robot state

### Commands

1. **Move**: `move x y z u`
   - Moves robot to target position (only if IDLE)
   - Expects: `POSITION_REACHED` (Timeout: 10s)

2. **Queue**: `queue x1 y1 x2 y2 ... xN yN`
   - Appends XY coordinate pairs to queue (max 300 coordinates)
   - Only XY pairs are sent (Z and U are not included in queue)
   - Expects: `QUEUE_APPENDED` (Timeout: 3s)

3. **Clear Queue**: `clearqueue`
   - Clears all queued coordinates
   - Expects: `QUEUE_CLEARED` (Timeout: 3s)

4. **Insert**: `insert`
   - Begins INSERTING mode using queued coordinates
   - Expects: `INSERT_DONE` (Timeout: 60s)

5. **Test**: `test`
   - Begins TESTING mode using queued coordinates
   - Expects: `TEST_DONE` (Timeout: 60s)

6. **Stop**: `stop`
   - Stops current insert/test operation and queue processing
   - Resets state to IDLE
   - Expects: `STOPPED` (Timeout: 1s)

7. **Motor**: `motor on` or `motor off`
   - Turns robot servos on or off
   - Expects: `MOTOR_ON` or `MOTOR_OFF` (Timeout: 5s)

8. **Speed**: `speed <1-100>`
   - Sets robot speed factor
   - Expects: `SPEED_SET <value>` (Timeout: 5s)

9. **Load Magazine**: `loadmagazine count`
   - Moves robot to load position and waits for operator
   - Expects: `MAGAZINE_LOADED` (Timeout: 60s)

### Error Handling
- If command times out: Custom timeout handlers are called, otherwise warning is logged
- If error response is received (`error` or `taskfailed`): Logged and error signal emitted
- Commands can only be sent when robot is in appropriate state (e.g., `move` and `queue` require IDLE state)

### Protocol Notes
- Commands end with `\r\n` over TCP/IP
- Socket connection maintained throughout operation
- App uses expectation-based response handling with optional success/timeout callbacks
- Queue supports up to 300 coordinate pairs
- Status updates are sent automatically by robot every 1 second

## Calibration
Teach robot tooling (in Robot Manager) 
1. setup hardware:
    - Have a matrix of known points. The points should be at Z-axis of the insertion plate, plane parallel to the ground. (Place it slightly above the 3x3)
    - Tune gripper: move z up and down to see if it is straight. If not loosen the screws to adjust.
    - Calibrate robot tool (TCP) BEFORE homography! Rotate gripper around tool center make sure it is centered. If not reteach the tool in RC+.
    - 
    - Make sure the calibration grid is stable so it will not move if robot touch it. Make sure to secure all points (with doubly sticky) because paper will deform due to humidity and temperature change.
    - Make sure camera is focused
2. Move camera to correct position. Process image and note their points in image coordinate. Save the image in case needed later.
3. Let robot go to those positions and note the positions (all units in mm).
4. Move the camera back to capture position, make sure it is not shifted
5. Feed the data to vision_homography_mapper.py and make sure error is low (<0.2mm, best to keep all below 0.1mm.). Put the homography matrix in config.yml

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

**Reflections**
- Gantry setup too complex to maintain

## 10 screws (2024-11-26)
Vision system to detect cells to insert
One by one insert routine with human intervention
Auto feeder for screw supple
HMI:
- Live camera mode for monitoring
- Display centroid centers

**Reflections**
- Parallex error is bad, need to capture image in sections
- Careful homography calibration is critical
- Not all setup requires camera calibration

## 100 screws (2025-02-11)
Continuously insert without little human interference
One vision section
Communication protocol and error handling
Capture and process image including moving robot to position
HMI
- Pause and resume
- Able to start from any cell

**Reflections**
- HMI system can get buggy easily - need testing
- TCP/IP transmission takes time - feed all data to robot or dual process 
- Robot moving fast can be shacky  

## 500 screws - added 2025-09-16
- Metal construction to handle large amount of steel screw rubbing
- Magazine feeder to speed up insertion per second

**Reflections**
- Screw can get intercepted by screw on the rail.
- Need longer vertical stroke
- 

## 1000 screws (TODO)  
Insert the 1 whole plate with high accuracy  
Multiple insertion region for large-area processing  
Send all cell location to robot and robot send insertion status back to app
Force sensor on grabber to skip insertion for bad cells  
Automatic (one click) homography calibration  
Hardware to force web plate onto the 3x3 rack  
Compliance mechanism on the 3x3 rack?
40% robot speed  
Conveyor system  

## 10000 screws (TODO)  
End-to-end automation  
Adaptive error handling  
Non-stop movement when grabbing screw from feeder      

# Insertion source of error
1. Parallex Error due to variation in height
    - WD 600mm
    - V_Err = 5mm
    - H_Err = 0.1mm (@10mm), 0.4 (@50), 0.8 (@100), 1.3 (@500)
    - Higher WD will reduce parallex error
2. Camera calibration (camera matrix, distortion vector) error (0.4mm w/out calibration)
    - Calibrate if have time
3. Homography calibration error (~0.1mm)
    - Usually will have to manually adjust after testing
    - Dangled wires! Make sure to secure the wire and use high flexible ethernet cable!
    - Deformed camera mount caused by camera heating (e=1.5mm)
4. Robot tool calibration error (including end effector hardware)
5. Compliance mechanism deformed
5. Camera resolution error
    - Choose higher resolution (~10px/mm)
6. Tooling error
    - Screw not straight - grab at lower end
7. Plate shifted after capture image

# Tasks
- SPEL extension for VScode
- Send cell coordinates while robot is inserting  
- CI for the app
- Robot simulator (to use the app without robot)

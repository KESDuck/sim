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
- [App manual unit tests:](#app-manual-unit-tests)
    - [window](#window)
    - [cross](#cross)
    - [others](#others)
- [Error Analysis](#error-analysis)
- [Tasks](#tasks)


# Usage:
This app is a robot vision system that integrates camera (pylon), robot (TCPIP), and UI for screw insertion. It consists of multiple components that communicate through message protocols, and it features a homography-based calibration system to convert camera coordinates to robot coordinates.

## Namings

- Cell coordinate: contours center, centroids, screw locations
- Insertion region: capture id, batch insert section, vision section
- Template: 模型版
- Web plate
- 3x3: rack, 九宮格
- Grabber: retriver
- Feeder:  

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


## Camera Setup
Webcam  
iPhone  
Basler (pylon)  
- Use pylon IP configurator or pylon Viewer  

acA2500-14gm (2592x1944)
- z=580mm (robot -18mm), 16mm:
    - FOV: 190x140, 15x20 cells
    - cell 90x90 pixel 
- z=580mm (robot -18mm), 8mm:
    - FOV: 290X380
    - max distortion 0.5mm
    - 6.7 pixel/mm
    - each cell 45x45 pixel
- z=480mm (robot -118mm), 8mm:
    - max distortion 4px
    - 10.9pixel/mm
    - each cell 55x55 pixel
- z= (robot -18mm), 12mm:
    - FOV: 260x190
    - max distortion: 0.3mm
    - 10.0 pixel/mm
Taobao acA2500-14gm (2592x1944)
- z= (robot -18mm), 12mm:
    - FOV: 260x190
    - max distortion: 0.3mm
    - 10.0 pixel/mm

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

## Messaging Protocol

### States
- State 0: Idle
- State 1: Imaging
- State 2: Inserting

### Robot Status Updates
- Robot sends status every 1 second: `status {state #}, {x}, {y}, {z}, {u}, {index}, {queue size}`
- App synchronizes with robot state every second
- App displays error if its state differs from robot state

### Commands
1. **Capture**: `capture x, y, z, u`
   - Changes app state 0 → 1 (only allowed if current state is 0)
   - Expects: `task position_reached` (Timeout: 10s)

2. **Queue**: `queue x1,y1,z1,u1,...,xN,yN,zN,uN`
   - Changes app state 0 → 2
   - Expects: `task queue_set` (Timeout: 3s)
   - Expects: `task queue_completed` (Timeout: 300s)

3. **Stop**: `stop`
   - Changes app state 2 → 0
   - Expects: `task queue_stopped` (Timeout: 1s)
   - Unexpects: `task queue_completed`

### Error Handling
- If command times out:
  - Position-reached timeout: App state → 0
  - Queue-set or queue-completed timeout: App state → 0
- If error response is received (`error` or `taskfailed`): Logged but no state change

### Protocol Notes
- App state changes immediately after command is sent, preventing multiple commands
- Status check runs every 1 second to verify state synchronization
- Commands end with `\r\n` over TCPIP
- Socket connection maintained throughout operation

### Future Tasks
- Set expectation for second status update
- Status update include timestamp

## Homography Calibration
Teach robot tooling (in Robot Manager) 
1. setup hardware:
    - Have a matrix of known points. The points should be at Z-axis of the insertion plate, plane parallel to the ground. (Place it slightly above the 3x3)
    - Tune gripper: move z up and down to see if it is straight. If not loosen the screws to adjust.
    - Rotate gripper around tool center make sure it is centered. If not reteach the tool in RC+.
    - Make sure the calibration grid is stable so it will not move if robot touch it
2. Move camera to correct position. Process image and note their points in image coordinate. Save the image in case needed later.
3. Let robot go to those positions and note the positions (all units in mm).
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
  
## 1000 screws (TODO)  
Insert the 1 whole plate with high accuracy  
Multiple insertion region for large-area processing  
Send all cell location to robot and robot send insertion status back to app
Force sensor on grabber to skip insertion for bad cells  
Automatic (one click) homography calibration  
Hardware to force web plate onto the 3x3 rack  
40% robot speed  
Conveyor system  

## 10000 screws (TODO)  
End-to-end automation  
Adaptive error handling  
Non-stop movement when grabbing screw from feeder      

# App manual tests:
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

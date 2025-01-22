# Usage:

## Ideal operation
1. hardware setup: feeder is set to the correct screw diameter using precision staris. Add screws to the feeder (or vibratory feeder)
2. Insert frame and web plate, secure on conveyor
3. Press start, robot starts main insertion operation
4. When completed the loaded frame is ejected from the robot ready for pick up

## UI
- Camera View
    - Can zoom in and out for precise calibration
    - Click to show coordinate
    - Arrow key and WASD to adjust location
    - If image processed:
- Control panel
    - Process
    - Cycle filters
    - Save Frame
    - Cell number box
- Robot command panel
    - Jump
    - Insert
    - Echo


## Main insertion operation

Buttons: Start, Stop, Num box,

## Camera Setup
Webcam
iPhone
Basler (pylon)
- Use pylon IP configurator



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
1. Teach robot tooling (in Robot Manager)
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


# App Design Requirments: 




# App manual unit tests:
- When clicked, the cross is at right position and shows the robot coordinate
- When zoomed in, the mouse click to the right position
- Resize the window so nothing weird happen
- Arrow keys moves the cross, WASD moves the cross 10px
- Image is actually saved
- TCPIP sends in the right format: (str(message).encode()) + b"\r\n"
- Press R Key to record current cross position
- When sending message and while waiting for 'taskdone', UI is still responsive

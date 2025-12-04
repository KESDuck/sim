# **TCP CONTROL V3.2 – System Documentation**

*(Robot TCP/IP Control Program for Screw Insertion & Testing)*

## **Overview**

`TCP CONTROL V3.2` is a multi-task robot control program enabling TCP/IP communication, state-machine-based robot operations, and coordinated queue processing for screw insertion and testing workflows.

The system manages **network communication**, **robot motion**, **task scheduling**, **IO operations**, and **queue management** for up to **300 coordinate jobs**.

---

# **System Architecture**

The program runs **three concurrent tasks**:

### **1. NetworkManager**

Handles:

* TCP server connection (port 8501)
* Message receiving + decoding
* Sending responses back to client
* Immediate handling of emergency commands (`stop`)

---

### **2. StatusReporter**

Runs every 1 second:

* Sends `STATUS` packet including:

  * Robot state
  * Current XYZU coordinates
  * Current queue index
  * Total queue size

---

### **3. OperationProcessor**

Triggered by `Signal 10` based on robot state:

* MOVING → DoMove()
* INSERTING → Iterate queue → DoInsert()
* TESTING → Iterate queue → DoTest()

---

# **Robot States**

| State Value | Name             | Description                               |
| ----------- | ---------------- | ----------------------------------------- |
| 0           | **DISCONNECTED** | No TCP client connected                   |
| 1           | **IDLE**         | Waiting for command                       |
| 2           | **MOVING**       | Move to X/Y/Z/U                           |
| 3           | **INSERTING**    | Insert operation using queued coordinates |
| 4           | **TESTING**      | Test operation using queued coordinates   |
| 5           | **EMERGENCY**    | Stop requested or error                   |

State transitions are handled through `SetRobotState()`.

---

# **Message Protocol**

Client messages follow the format:

```
<command> [arg1 arg2 arg3 ...]
```

## **Supported Commands**

### **1. move x y z u**

Moves robot to target position if IDLE.

Program: `Jump XY(MoveX, MoveY, MoveZ, MoveU) /L`

Response: `POSITION_REACHED`

---

### **2. queue x1 y1 x2 y2 ... xN yN**

Appends coordinates to queue.
Max queue size = 300.



Response: `QUEUE_APPENDED`

---

### **3. clearqueue**

Clears all queued coordinates.

Response: `QUEUE_CLEARED`

---

### **4. insert**

Begins INSERTING mode using queued coordinates.

Program: `DoInsert(CurrentIndex)`

Response (when complete): `INSERT_DONE`

---

### **5. test**

Begins TESTING mode using queued coordinates.

Program: `DoTest(CurrentIndex)`

Response (when complete): `TEST_DONE`

---

### **6. loadmagazine count**

Moves robot to load position and waits for operator.

Program: `Jump XY(0, 435, -2, 0) /L LimZ -2`

Response: `MAGAZINE_LOADED`

---

### **7. speed <1–100>**

Sets robot speed factor.

Program: `SpeedFactor RobotSpeed`

Response: `SPEED_SET <value>`

---

### **8. motor on/off**

Turns the robot servos on or off.

Response:

* `MOTOR_ON` when powered
* `MOTOR_OFF` when disabled
* `INVALID_MOTOR` if the argument is missing/unknown

---

### **9. stop**

Stops:

* current insert/test
* queue processing
  Resets state to IDLE.

Response: `STOPPED`

---

# **Status Response Format**

Sent automatically every 1 second.

```
STATUS <state>, <X>, <Y>, <Z>, <U>, <currentIndex>, <queueSize>
```

Example:

```
STATUS 1, 120.1, 203.3, 50.0, 90.0, 0, 0
```

---

# **Queue Management**

* Stores up to **300** XY coordinate pairs.
* Stored in global: `CoordinateQueue$(300, 2)`
* Indexes:

  * `QueueSize` = total items
  * `CurrentIndex` = current job index

`ClearQueue()` wipes both columns for all rows.

---

# **Operation Logic**

## **Movement (State = 2)**

Triggered by `move` command.

Executes:

```
Jump XY(X,Y,Z,U) /L
```

Then:

```
POSITION_REACHED
```

Robot returns to IDLE after movement.

---

## **Insert Operation (State = 3)**

Process per coordinate:

1. Jump to XY
2. Close gripper
3. Extend feeder
4. Open gripper
5. Retract feeder
6. Retreat a small offset

At completion:

```
INSERT_DONE
```

---

## **Test Operation (State = 4)**

Process:

1. Jump to XY
2. Extend feeder
3. Retract feeder

At completion:

```
TEST_DONE
```

---

# **Emergency Stop**

`DoStopTask()` performs:

* `StopRequested = True`
* Clears queue
* Resets index
* Returns to IDLE
* Sends: `STOPPED`

This is triggered by:

* receiving `"stop"` from socket
* pressing stop on physical robot

---

# **Function Breakdown**

## **SetRobotState(state)**

Updates global state & prints state.

## **ProcessReceivedMessage()**

Parses received TCP messages into commands and parameters.

## **SendResponse(message$)**

Queues outgoing TCP message.

## **NetworkManager()**

Main loop for connection, receiving, sending.

## **StatusReporter()**

Outputs robot state & position every second.

## **OperationProcessor()**

Executes tasks depending on current robot state.

## **DoInsert(index)**

Runs IO sequence for screw insertion.

## **DoTest(index)**

Runs IO sequence for feeder testing.

## **DoStopTask()**

Clears queue, resets state, sends stop notification.

---

# **Initialization Sequence**

`Main()` performs:

1. Motor ON
2. Power HIGH
3. SpeedFactor=20
4. Safety IO OFF
5. Sets MAX_QUEUE_SIZE
6. Sets robot IDLE
7. Starts concurrent tasks:

   * NetworkManager
   * OperationProcessor

StatusReporter currently commented out.

---

# **Error Handling**

`NetworkManager` includes:

```
OnErr GoTo ErrHandle
```

On any network error:

* Print error code + message
* Resume at connection loop
* Reset state to DISCONNECTED

---

# **Future Extension Points**

### Potential improvements:

* Enable Z/U in queue
* Add auto tool-checking
* Add feeder jam detection
* Integrate force-sensing feedback
* Improve stop behavior for mid-motion halts
* Loadmagazine timer/sensor

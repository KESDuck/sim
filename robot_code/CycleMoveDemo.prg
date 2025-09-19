Function CycleMoveDemo
    ' Initialize robot
    Motor On
    Power High
    SpeedFactor 30
    Speed 50
    SpeedS 50
    
    Real pos1X, pos1Y, pos2X, pos2Y, safeZ, workZ
    pos1X = 0
    pos1Y = 500
    pos2X = 100
    pos2Y = 500
    safeZ = 0      ' Safe Z height for travel
    workZ = -150   ' Working Z height
    
    ' Torque variables
    Real zTorque, maxTorque
    maxTorque = 30.0  ' Set your maximum torque threshold here
    Integer zAxis
    zAxis = 3  ' Z-axis joint number (typically 3)
    
    ' Initialize torque monitoring
    PTCLR zAxis  ' Clear peak torque for Z axis
    
    Print "Starting cycle movement"
    
    Do  ' Infinite loop
        ' Position 1
        Go Here :Z(safeZ)
        Go XY(pos1X, pos1Y, safeZ, 0) /L
        
        ' Clear peak torque before moving down
        PTCLR zAxis
        
        ' Method 1: Move slowly while monitoring torque
        Print "Moving down at position 1"
        SpeedS 10  ' Slow speed for controlled descent
        
        ' Start with safe Z and move incrementally down
        Real currentZ
        currentZ = safeZ
        Boolean contactDetected
        contactDetected = False
        
        ' Move down incrementally while checking torque
        Do While currentZ > workZ
            ' Move down 5mm at a time
            currentZ = currentZ - 5
            If currentZ < workZ Then currentZ = workZ
            
            ' Move to next Z position
            Move XY(pos1X, pos1Y, currentZ, 0) /L
            
            ' Check torque after movement
            zTorque = PTRQ(zAxis)
            Print "Z=", currentZ, " Torque=", zTorque
            
            ' If torque exceeds threshold, stop
            If zTorque > maxTorque Then
                Print "Torque limit reached at position 1: ", zTorque
                contactDetected = True
                Exit Do
            EndIf
        Loop
        
        ' Return to safe Z height
        Go Here :Z(safeZ)
        
        ' Position 2
        Go XY(pos2X, pos2Y, safeZ, 0) /L
        
        ' Clear peak torque before moving down
        PTCLR zAxis
        
        ' Method 2: Using Till (if till works with MemSw)
        Print "Moving down at position 2"
        
        ' Set up a MemSw that we'll turn on in our torque monitoring task
        MemOff 1
        
        ' Start separate task to monitor torque
        Xqt TorqueMonitor
        
        ' Move down with Till condition to stop when MemSw(1) turns on
        Move XY(pos2X, pos2Y, workZ, 0) /L Till MemSw(1) = On
        
        ' Terminate the monitoring task
        Quit TorqueMonitor
        
        ' Check if we stopped due to torque
        If MemSw(1) = On Then
            zTorque = PTRQ(zAxis)
            Print "Torque limit reached at position 2: ", zTorque
        Else
            Print "Reached target depth at position 2 without exceeding torque limit"
        EndIf
        
        ' Return to safe Z height
        Go Here :Z(safeZ)
    Loop
Fend

' Separate task to monitor torque and set a memory switch when threshold is exceeded
Function TorqueMonitor
    Real currentTorque
    
    Do
        currentTorque = PTRQ(3)  ' Z-axis joint
        
        ' If torque exceeds limit, set memory switch and exit task
        If currentTorque > 30.0 Then  ' Same threshold as in main function
            MemOn 1
            Exit Function
        EndIf
        
        Wait 0.01  ' Check frequently but don't overload CPU
    Loop
Fend 
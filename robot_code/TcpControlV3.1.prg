'====================================================================
' TCP CONTROL V3.1
'====================================================================

' Global variables for state machine
Global Integer RobotMode    ' 0=INIT, 1=INSERT, 2=TEST, 3=MOVE
Global Integer RobotState   ' 0=DISCONNECT, 1=IDLE, 2=BUSY, 3=EMERGENCY
Global Real RobotSpeed      ' Speed factor (1-100)
Global Boolean StopRequested

' Movement parameters
Global Real MoveX, MoveY, MoveZ, MoveU
Global Real JumpHeight

' Queue management
Global String CoordinateQueue$(500, 3)  ' Store up to 500 coordinates (X,Y,Z)
Global Integer QueueSize, CurrentIndex

' Message handling
Global String RecvMsg$, SendMsg$
Global Boolean MessageReceived
Global String ReceivedMessage$
Global Boolean NewMessage
Global String MessageToSend$
Global Integer NumTokens

'====================================================================
' State Management Functions
'====================================================================
Function SetRobotMode(ByVal mode As Integer)
    RobotMode = mode
    Select RobotMode
        Case 0
            Print "[SetRobotMode] Mode set to INIT"
        Case 1
            Print "[SetRobotMode] Mode set to INSERT"
        Case 2
            Print "[SetRobotMode] Mode set to TEST"
        Case 3
            Print "[SetRobotMode] Mode set to MOVE"
    Send
Fend

Function SetRobotState(ByVal state As Integer)
    RobotState = state
    Select RobotState
        Case 0
            Print "[SetRobotState] State set to DISCONNECT"
        Case 1
            Print "[SetRobotState] State set to IDLE"
        Case 2
            Print "[SetRobotState] State set to BUSY"
        Case 3
            Print "[SetRobotState] State set to EMERGENCY"
    Send
Fend

'--- ENTRY POINT ---------------------------------------------------
Function Main
    ' Initialize robot
    Motor On
    Power High
    SpeedFactor 10
    Speed 100; Accel 50, 50
    SpeedS 100; AccelS 50, 50
    Off ioGripper
    Off ioFeeder
 
    ' Initialize variables
    SetRobotMode 0      ' INIT mode
    SetRobotState 1     ' IDLE state
    RobotSpeed = 100   ' Default speed
    QueueSize = 0
    CurrentIndex = 0
    JumpHeight = 0    ' Default jump height
    NewMessage = False
    MessageReceived = False
    
    ' Start our comms + status + operation tasks
    Xqt NetworkManager
    Xqt StatusReporter
    Xqt OperationProcessor
Fend

'====================================================================
' Task 1: NetworkManager – single TCP port for both Rx & Tx
'====================================================================
Function NetworkManager
    OnErr GoTo ErrHandle
    SetNet #201, "192.168.0.1", 8501, CRLF

Connect:
    SetRobotState 0  ' DISCONNECT
    OpenNet #201 As Server
    WaitNet #201, 10  ' Wait for client connection (timeout)
    If TW Then Print "[NetworkManager] Connection Timeout. Retrying..."; GoTo Connect
    Print "[NetworkManager] Client Connected"
    SetRobotState 1  ' IDLE

    Do
        ' RECEIVING: Check for incoming messages
        If ChkNet(201) > 0 Then
            Input #201, ReceivedMessage$
            If ReceivedMessage$ <> "" Then
                Print "[NetworkManager] Received: ", ReceivedMessage$
                
                ' Process urgent commands directly
                If ReceivedMessage$ = "stop" Then
                    Print "[NetworkManager] Stop requested"
                    DoStopTask
                Else
                    ' Process message immediately
                    ProcessReceivedMessage
                EndIf
            EndIf
        EndIf
        
        ' SENDING: Check and send any pending messages
        If NewMessage Then
            Print #201, MessageToSend$
            Print "[NetworkManager] Sent: ", MessageToSend$
            NewMessage = False  ' Reset flag after sending
        EndIf
        
        Wait 0.05  ' Short wait to avoid CPU hogging
    Loop

ErrHandle:
    Print "[NetworkManager] ERROR: Error number ", Err, ". Error Message: ", ErrMsg$(Err)
    Print "[NetworkManager] Reconnecting..."
    SetRobotState 0  ' DISCONNECT
    EResume Connect
Fend

'====================================================================
' Task 2: StatusReporter – Periodically reports robot status
'====================================================================
Function StatusReporter
    Do
        SendMsg$ = "STATUS " + Str$(RobotState) + ", " + Str$(CX(CurPos)) + ", " + Str$(CY(CurPos)) + ", " + Str$(CZ(CurPos)) + ", " + Str$(CU(CurPos))

        If QueueSize > 0 Then
            SendMsg$ = SendMsg$ + ", " + Str$(CurrentIndex + 1) + ", " + Str$(QueueSize)
        Else
            SendMsg$ = SendMsg$ + ", 0, 0"
        EndIf
        
        SendResponse SendMsg$
        Wait 1  ' Report status every seconds
    Loop
Fend

'====================================================================
' Task 3: OperationProcessor – Handles all robot operations (move, test, insert)
'====================================================================
Function OperationProcessor
    Do
        ' Wait for signal that there's work to do
        WaitSig 10
        
        ' Process operation based on mode
        If RobotState = 1 Then
            Print "[OperationProcessor] Starting operation in mode ", RobotMode
            SetRobotState 2  ' BUSY

            Select RobotMode
                Case 3  ' MOVE mode
                    Print "[OperationProcessor] Moving to position: (", MoveX, ", ", MoveY, ", ", MoveZ, ")"
                    Jump XY(MoveX, MoveY, MoveZ, CU(CurPos)) /L
                    SendResponse "POSITION_REACHED"
                    SendResponse "MOVE_DONE"
                    SetRobotMode 0  ' Return to INIT mode
                
                Case 1  ' INSERT mode
                    ' Process queue until it's empty or stopped
                    Do While CurrentIndex < QueueSize
                        ' Extract coordinate from queue
                        MoveX = Val(CoordinateQueue$(CurrentIndex, 0))
                        MoveY = Val(CoordinateQueue$(CurrentIndex, 1))
                        
                        Print "[OperationProcessor] Processing item ", CurrentIndex + 1, "/", QueueSize
                        
                        DoInsertOperation(CurrentIndex)
                        
                        ' Increment index
                        CurrentIndex = CurrentIndex + 1

                        If StopRequested Then
                            Print "[OperationProcessor] Stop requested"
                            Exit Do
                        EndIf
                    Loop
                    
                    If StopRequested Then
                        SendResponse "STOPPED"
                    Else
                        ' Queue is complete
                        Print "[OperationProcessor] Queue completed"
                        
                        ' Reset queue
                        QueueSize = 0
                        CurrentIndex = 0
                        SendResponse "INSERT_DONE"
                        SetRobotMode 0  ' Return to INIT mode
                    EndIf
                
                Case 2  ' TEST mode
                    ' Process queue until it's empty or stopped
                    Do While CurrentIndex < QueueSize
                        ' Extract coordinate from queue
                        MoveX = Val(CoordinateQueue$(CurrentIndex, 0))
                        MoveY = Val(CoordinateQueue$(CurrentIndex, 1))
                        
                        Print "[OperationProcessor] Processing item ", CurrentIndex + 1, "/", QueueSize
                        
                        DoTestOperation(CurrentIndex)
                        
                        ' Increment index
                        CurrentIndex = CurrentIndex + 1

                        If StopRequested Then
                            Print "[OperationProcessor] Stop requested"
                            Exit Do
                        EndIf
                    Loop
                    
                    If StopRequested Then
                        SendResponse "STOPPED"
                    Else
                        ' Queue is complete
                        Print "[OperationProcessor] Queue completed"
                        
                        ' Reset queue
                        QueueSize = 0
                        CurrentIndex = 0
                        SendResponse "TEST_DONE"
                        SetRobotMode 0  ' Return to INIT mode
                    EndIf
            Send
            
            SetRobotState 1  ' IDLE
        EndIf
    Loop
Fend

'====================================================================
' Helper Functions
'====================================================================
Function SendResponse(ByVal message$ As String)
    ' Wait if there's already a message waiting to be sent
    Do While NewMessage
        Wait 0.01
    Loop
    
    ' Now it's safe to set a new message
    NewMessage = True
    MessageToSend$ = message$
Fend

Function ProcessReceivedMessage
    RecvMsg$ = ReceivedMessage$
    MessageReceived = False
    
    If RecvMsg$ <> "" Then
        String Tokens$(0)
        NumTokens = ParseStr(RecvMsg$, Tokens$(), " ")
        
        If NumTokens >= 1 Then
            String cmd$
            cmd$ = Tokens$(0)
            
            Select cmd$
                Case "move"
                    ' Format: move x y z
                    If NumTokens = 4 And RobotState = 1 Then
                        MoveX = Val(Tokens$(1))
                        MoveY = Val(Tokens$(2))
                        MoveZ = Val(Tokens$(3))
                        SetRobotMode 3  ' MOVE mode
                        Signal 10  ' Signal OperationProcessor to start working
                        SendResponse "MOVE_STARTED"
                    Else
                        SendResponse "ERROR move failed"
                    EndIf
                
                Case "queue"
                    ' Format: queue x1 y1 x2 y2 ... xN yN
                    If RobotState = 1 And (NumTokens - 1) Mod 2 = 0 Then
                        QueueSize = (NumTokens - 1) / 2
                        If QueueSize > 500 Then QueueSize = 500  ' Limit to 500 points
                        
                        Integer i, j
                        j = 0
                        For i = 0 To QueueSize - 1
                            CoordinateQueue$(i, 0) = Tokens$(j + 1)  ' X
                            CoordinateQueue$(i, 1) = Tokens$(j + 2)  ' Y
                            j = j + 2
                        Next i
                        
                        CurrentIndex = 0
                        SendResponse "QUEUE_SET"
                        Print "[ProcessReceivedMessage] Queued ", QueueSize, " coordinates"
                    Else
                        SendResponse "ERROR queue failed"
                    EndIf
                
                Case "insert"
                    If RobotState = 1 Then
                        SetRobotMode 1  ' INSERT mode
                        Signal 10  ' Signal OperationProcessor to start working
                    Else
                        SendResponse "ERROR robot busy"
                    EndIf
                
                Case "test"
                    If RobotState = 1 Then
                        SetRobotMode 2  ' TEST mode
                        Pause
                        Signal 10  ' Signal OperationProcessor to start working
                    Else
                        SendResponse "ERROR robot busy"
                    EndIf
                
                Case "speed"
                    If NumTokens = 2 And RobotState = 1 Then
                        Real newSpeed
                        newSpeed = Val(Tokens$(1))
                        If newSpeed >= 1 And newSpeed <= 100 Then
                            RobotSpeed = newSpeed
                            SpeedFactor RobotSpeed
                            SendResponse "SPEED_SET " + Str$(RobotSpeed)
                            Print "[ProcessReceivedMessage] Speed changed to ", RobotSpeed
                        Else
                            SendResponse "ERROR invalid_speed_value"
                        EndIf
                    Else
                        SendResponse "ERROR speed failed"
                    EndIf
                
                Case "stop"
                    DoStopTask
                
                Default
                    SendResponse "ERROR unknown_command"
                    Print "[ProcessReceivedMessage] Unknown Command: ", cmd$
            Send
        Else
            SendResponse "ERROR empty_command"
        EndIf
    EndIf
    CheckReceivedMessage
Fend

'====================================================================
' Operation Functions
'====================================================================
Function DoMoveTask
    Print "[DoMoveTask] Moving to position: (", MoveX, ", ", MoveY, ", ", MoveZ, ")"
    Jump XY(MoveX, MoveY, MoveZ, CU(CurPos)) /L
    
    SendResponse "POSITION_REACHED"
    SetRobotState 1  ' IDLE
Fend

Function DoInsertOperation(ByVal index As Integer)
    Print "[DoInsertOperation] Inserting at: (", MoveX, ", ", MoveY, ")"
    
    ' Move to position
    ' Jump XY(MoveX, MoveY, MoveZ, CU(CurPos)) /L LimZ JumpHeight
Fend

Function DoTestOperation(ByVal index As Integer)
    Print "[DoTestOperation] Testing at: (", MoveX, ", ", MoveY, ")"
    
    ' Move to position
    ' Jump XY(MoveX, MoveY, MoveZ, CU(CurPos)) /L LimZ JumpHeight
Fend

Function DoStopTask
    StopRequested = True
    SetRobotState 1  ' IDLE
    QueueSize = 0
    CurrentIndex = 0
    
    ' Emergency stop to turn motor off and on if needed
    
    SendResponse "STOPPED"
    Print "[DoStopTask] Robot stopped"
Fend

Function CheckReceivedMessage
    If MessageReceived Then
        ProcessReceivedMessage
    EndIf
Fend

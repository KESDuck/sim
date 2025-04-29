'====================================================================
' TCP CONTROL V3.1
'====================================================================

' Global variables for state machine
Global Integer RobotMode    ' 0=NORMAL, 1=INSERT, 2=TEST, 3=CAPTURE
Global Integer RobotState   ' 0=DISCONNECT, 1=IDLE, 2=BUSY, 3=EMERGENCY
Global Real RobotSpeed      ' Speed factor (1-100)

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
    RobotMode = 0      ' NORMAL mode
    RobotState = 1     ' IDLE state
    RobotSpeed = 100   ' Default speed
    QueueSize = 0
    CurrentIndex = 0
    JumpHeight = 0    ' Default jump height
    NewMessage = False
    MessageReceived = False
    
    ' Start our comms + status + inserter tasks
    Xqt NetworkManager
    Xqt StatusReporter
    Xqt QueueProcessor
Fend

'====================================================================
' Task 1: NetworkManager – single TCP port for both Rx & Tx
'====================================================================
Function NetworkManager
    OnErr GoTo ErrHandle
    SetNet #201, "192.168.0.1", 8501, CRLF

Connect:
    RobotState = 0  ' DISCONNECT
    OpenNet #201 As Server
    WaitNet #201, 10  ' Wait for client connection (timeout)
    If TW Then Print "[NetworkManager] Connection Timeout. Retrying..."; GoTo Connect
    Print "[NetworkManager] Client Connected"
    RobotState = 1  ' IDLE

    Do
        ' RECEIVING: Check for incoming messages
        If ChkNet(201) > 0 Then
            Input #201, ReceivedMessage$
            If ReceivedMessage$ <> "" Then
                Print "[NetworkManager] Received: ", ReceivedMessage$
                
                ' Process urgent commands directly
                If ReceivedMessage$ = "stop" Then
                    Print "[NetworkManager] Stop requested"
                    Call DoStopTask
                Else
                    ' Process non-urgent messages through normal flow
                    MessageReceived = True
                    ' Wait for message to be processed (with timeout)
                    TmReset 0
                    Do While MessageReceived And (Tmr(0) < 2.0)
                        Wait 0.01
                    Loop
                    ' Timeout safety - don't wait forever
                    If MessageReceived Then
                        Print "[NetworkManager] Message processing timeout"
                        MessageReceived = False
                    EndIf
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
    RobotState = 0  ' DISCONNECT
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
        
        Call SendResponse(SendMsg$)
        Wait 0.5  ' Report status every 0.5 seconds
    Loop
Fend

'====================================================================
' Task 3: QueueProcessor – Processes queued coordinates
'====================================================================
Function QueueProcessor
    Do
        ' Only process queue in INSERT or TEST mode with IDLE state
        If (RobotMode = 1 Or RobotMode = 2) And RobotState = 1 And QueueSize > 0 And CurrentIndex < QueueSize Then
            RobotState = 2  ' BUSY
            
            ' Extract coordinate from queue
            MoveX = Val(CoordinateQueue$(CurrentIndex, 0))
            MoveY = Val(CoordinateQueue$(CurrentIndex, 1))
            
            Print "[QueueProcessor] Processing item ", CurrentIndex + 1, "/", QueueSize, ": (", MoveX, ", ", MoveY, ")"
            
            ' Execute based on mode
            If RobotMode = 1 Then  ' INSERT mode
                Call DoInsertOperation
            ElseIf RobotMode = 2 Then  ' TEST mode
                Call DoTestOperation
            EndIf
            
            ' Increment index
            CurrentIndex = CurrentIndex + 1
            
            ' Check if queue is complete
            If CurrentIndex >= QueueSize Then
                ' Reset queue
                QueueSize = 0
                CurrentIndex = 0
                
                If RobotMode = 1 Then
                    Call SendResponse("INSERT_DONE")
                ElseIf RobotMode = 2 Then
                    Call SendResponse("TEST_DONE")
                Else
                    Call SendResponse("ERORR unknown mode")
                EndIf
                
                Print "[QueueProcessor] Queue completed"
            EndIf
            
            RobotState = 1  ' IDLE
        EndIf
        
        Wait 0.1  ' Short wait to avoid CPU hogging
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
                        RobotState = 2  ' BUSY
                        Call DoMoveTask
                    Else
                        Call SendResponse("ERROR invalid_move_command")
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
                        Call SendResponse("QUEUE_SET")
                        Print "[ProcessReceivedMessage] Queued ", QueueSize, " coordinates"
                    Else
                        Call SendResponse("ERROR invalid_queue_format")
                    EndIf
                
                Case "insert"
                    If RobotState = 1 Then
                        RobotMode = 1  ' INSERT mode
                        Print "[ProcessReceivedMessage] Mode changed to INSERT"
                    Else
                        Call SendResponse("ERROR robot_busy")
                    EndIf
                
                Case "test"
                    If RobotState = 1 Then
                        RobotMode = 2  ' TEST mode
                        Print "[ProcessReceivedMessage] Mode changed to TEST"
                    Else
                        Call SendResponse("ERROR robot_busy")
                    EndIf
                
                Case "speed"
                    If NumTokens = 2 Then
                        Real newSpeed
                        newSpeed = Val(Tokens$(1))
                        If newSpeed >= 1 And newSpeed <= 100 Then
                            RobotSpeed = newSpeed
                            SpeedFactor RobotSpeed
                            Call SendResponse("SPEED_SET " + Str$(RobotSpeed))
                            Print "[ProcessReceivedMessage] Speed changed to ", RobotSpeed
                        Else
                            Call SendResponse("ERROR invalid_speed_value")
                        EndIf
                    Else
                        Call SendResponse("ERROR invalid_speed_command")
                    EndIf
                
                Case "stop"
                    Call DoStopTask
                
                Default
                    Call SendResponse("ERROR unknown_command")
                    Print "[ProcessReceivedMessage] Unknown Command: ", cmd$
            Send
        Else
            Call SendResponse("ERROR empty_command")
        EndIf
    EndIf
    Call CheckReceivedMessage
Fend

'====================================================================
' Operation Functions
'====================================================================
Function DoMoveTask
    Print "[DoMoveTask] Moving to position: (", MoveX, ", ", MoveY, ", ", MoveZ, ")"
    Jump XY(MoveX, MoveY, MoveZ, CU(CurPos)) /L
    
    Call SendResponse("POSITION_REACHED")
    RobotState = 1  ' IDLE
Fend

Function DoInsertOperation
    Print "[DoInsertOperation] Inserting at: (", MoveX, ", ", MoveY, ")"
    
    ' Move to position
    ' Jump XY(MoveX, MoveY, MoveZ, CU(CurPos)) /L LimZ JumpHeight
    
Fend

Function DoTestOperation
    Print "[DoTestOperation] Testing at: (", MoveX, ", ", MoveY, ")"
    
    ' Move to position
    ' Jump XY(MoveX, MoveY, MoveZ, CU(CurPos)) /L LimZ JumpHeight
    
Fend

Function DoStopTask
    RobotState = 1  ' IDLE
    QueueSize = 0
    CurrentIndex = 0
    
    ' Emergency stop (if needed)
    ' Motor Off
    ' Wait 0.5
    ' Motor On
    
    Call SendResponse("STOPPED")
    Print "[DoStopTask] Robot stopped"
Fend

Function CheckReceivedMessage
    If MessageReceived Then
        Call ProcessReceivedMessage
    EndIf
Fend

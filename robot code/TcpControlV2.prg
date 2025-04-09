' Server-Side Program for Advanced Robot Control with Queue and Status Reporting
' 2025-02-11

Global Integer NumTokens
Global String RecvMsg$, SendMsg$
Global Real MoveX, MoveY, MoveZ, MoveU, JumpZ

' State machine variables
Global Integer RobotState  ' 0=IDLE, 1=IMAGING, 2=INSERTING, 3=STOPPING, 4=EMERGENCY_STOP
Global String RobotCommand$
Global String CoordinateQueue$(100, 4)  ' Store up to 100 coordinates (X,Y,Z,U)
Global Integer QueueSize, CurrentIndex

' Message handling variables
Global String MessageToSend$
Global Boolean NewMessage
Global String ReceivedMessage$
Global Boolean MessageReceived

Function main
    ' Initialize
    RobotState = 0  ' IDLE
    QueueSize = 0
    CurrentIndex = 0
    NewMessage = False
    MessageReceived = False
    
    Motor On
    Power High
    SpeedFactor 20
    Speed 100; Accel 100, 100
    SpeedS 100; AccelS 100, 100
    Off ioGripper
    Off ioFeeder

    ' Start network communication task
    Xqt NetworkManager
    ' Start status reporting task
    Xqt StatusReporter
    
    Do
        ' Check for received messages
        If MessageReceived Then
            Call ProcessReceivedMessage
            MessageReceived = False
        EndIf
        
        ' Check if we need to process queue
        If QueueSize > 0 Then
            Call ProcessQueueItem
        EndIf
        Wait 0.1
    Loop
Fend

Function ProcessReceivedMessage
    RecvMsg$ = ReceivedMessage$
    
    If RecvMsg$ <> "" Then
        String Tokens$(0)
        NumTokens = ParseStr(RecvMsg$, Tokens$(), " ")
        
        If NumTokens >= 1 Then
            RobotCommand$ = Tokens$(0)
            
            Select RobotCommand$
                Case "capture"
                    If RobotState = 0 And NumTokens = 5 Then
                        RobotState = 1  ' IMAGING
                        MoveX = Val(Tokens$(1))
                        MoveY = Val(Tokens$(2))
                        MoveZ = Val(Tokens$(3))
                        MoveU = Val(Tokens$(4))
                        Print "[ProcessReceivedMessage] Moving to: (", MoveX, ", ", MoveY, ", ", MoveZ, ", ", MoveU, ")"
                        Call DoCaptureTask
                    Else
                        Print "[ProcessReceivedMessage] Invalid format or robot state not IDLE"
                    EndIf
                
                Case "queue"
                    ' Format: queue x1 y1 z1 u1 x2 y2 z2 u2 ... xN yN zN uN
                    If RobotState = 0 And (NumTokens - 1) Mod 4 = 0 Then
                        RobotState = 2  ' INSERTING

                        QueueSize = (NumTokens - 1) / 4
                        If QueueSize > 100 Then QueueSize = 100
                        Integer i
                        For i = 0 To QueueSize - 1
                            CoordinateQueue$(i, 0) = Tokens$(i * 4 + 1)  ' X
                            CoordinateQueue$(i, 1) = Tokens$(i * 4 + 2)  ' Y
                            CoordinateQueue$(i, 2) = Tokens$(i * 4 + 3)  ' Z
                            CoordinateQueue$(i, 3) = Tokens$(i * 4 + 4)  ' U
                        Next i
                        
                        CurrentIndex = 0
                        
                        Print "[ProcessReceivedMessage] Queued ", QueueSize, " coordinates"

                    Else
                        Print "[ProcessReceivedMessage] Invalid queue format or robot state not ready, tokens count: ", NumTokens
                    EndIf
                
                Case "stop"
                    If RobotState = 2 Then
                        RobotState = 0  ' STOPPING
                        CurrentIndex = 0
                        QueueSize = 0
                        
                        Print "[ProcessReceivedMessage] Stop requested"
                    Else
                        Print "[ProcessReceivedMessage] Robot is not in INSERTING state to stop"
                    EndIf
                
                Case "where"
                    If RobotState = 0 Then
                        Print "[ProcessReceivedMessage] Where requested"
                        Call DoWhereTask
                    Else
                        Print "[ProcessReceivedMessage] Robot is not in IDLE state to get position"
                    EndIf
                    
                Default
                    Print "[ProcessReceivedMessage] Unknown Command: ", RobotCommand$
            Send
        Else
            Print "[ProcessReceivedMessage] Empty or Invalid Message"
        EndIf
    EndIf
Fend

Function NetworkManager
    OnErr GoTo ErrHandle
    SetNet #201, "192.168.0.1", 8501, CRLF

Connect:
    OpenNet #201 As Server
    WaitNet #201, 10  ' Wait for client connection (timeout)
    If TW Then Print "[NetworkManager] Connection Timeout. Retrying..."; GoTo Connect
    Print "[NetworkManager] Client Connected"

    Do
        ' RECEIVING: Check for incoming messages
        If ChkNet(201) > 0 Then
            Input #201, ReceivedMessage$
            If ReceivedMessage$ <> "" Then
                Print "[NetworkManager] Received: ", ReceivedMessage$
                MessageReceived = True
                ' Wait for message to be processed
                Real startTime
                TmReset 0
                Do While MessageReceived And (Tmr(0) - startTime < 2.0)
                    Wait 0.01
                Loop
                ' Timeout safety - don't wait forever
                If MessageReceived Then
                    Print "[NetworkManager] Message processing timeout"
                    MessageReceived = False
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
    Print "[NetworkManager] ERROR: Error number ", Err, ". Error Message is ", ErrMsg$(Err)
    Print "[NetworkManager] Reconnecting..."
    EResume Connect
Fend

Function SendResponse(ByVal message$ As String)
    ' Wait if there's already a message waiting to be sent
    Do While NewMessage
        Wait 0.01
    Loop
    
    ' Now it's safe to set a new message
    MessageToSend$ = message$
    NewMessage = True
    
    ' Wait until message is sent
    Do While NewMessage
        Wait 0.01
    Loop
Fend

Function TaskSuccess
    Call SendResponse("taskdone")
Fend

Function TaskFailure
    Call SendResponse("taskfailed")
Fend

Function StatusReporter
    Do
        Select RobotState
            Case 0  ' IDLE
                SendMsg$ = "status idle"
            Case 1  ' IMAGING
                SendMsg$ = "status imaging"
            Case 2  ' INSERTING
                If QueueSize > 0 Then
                    SendMsg$ = "status inserting " + Str$(CurrentIndex) + "/" + Str$(QueueSize)
                Else
                    SendMsg$ = "status inserting"
                EndIf
            Case 4  ' EMERGENCY_STOP
                SendMsg$ = "status emergency"
        Send
        Call SendResponse(SendMsg$)
        Wait 1  ' Report status every second
    Loop
Fend

Function DoCaptureTask
    ' Go to imaging position
    Print "[DoCaptureTask] Moving to capture position"
    Jump XY(MoveX, MoveY, MoveZ, MoveU) /L LimZ 0
    
    Call SendResponse("position_reached")
    
    RobotState = 0  ' IDLE
Fend

Function ProcessQueueItem
	' Add this to improve error detection
	OnErr GoTo ErrorHandler

    If RobotState = 0 Then
        Print "[ProcessQueueItem] Robot is in IDLE state"
    ElseIf CurrentIndex >= QueueSize Then ' If done with queue
        RobotState = 0  ' IDLE
        Print "[ProcessQueueItem] Queue completed"
        Call SendResponse("queue_completed")
    ElseIf RobotState = 2 Then
        ' Extract coordinate from queue
        MoveX = Val(CoordinateQueue$(CurrentIndex, 0))
        MoveY = Val(CoordinateQueue$(CurrentIndex, 1))
        MoveZ = Val(CoordinateQueue$(CurrentIndex, 2))
        MoveU = Val(CoordinateQueue$(CurrentIndex, 3))
        
        Print "[ProcessQueueItem] Processing item ", CurrentIndex + 1, "/", QueueSize, ": (", MoveX, ", ", MoveY, ", ", MoveZ, ", ", MoveU, ")"
        
        ' Do insertion
        Jump pFeederReceive -Y(12) LimZ -18
        Go pFeederReceive
        On ioGripper
        Go pFeederReceive -Y(12)
        On ioFeeder
        Wait 0.1
        Off ioFeeder
        Jump XY(MoveX, MoveY, -150, 0) /L LimZ -18
        Off ioGripper
        Wait 0.2
        Go XY(MoveX, MoveY, -150, 0) /L -Y(40)
        
        Wait 0.1
        
        ' Increment index
        CurrentIndex = CurrentIndex + 1
    Else
        Print "[ProcessQueueItem] Error: Robot is in a bad state"
    EndIf
    Return

ErrorHandler:
    Print "Error occurred, number: ", Err
    RobotState = 4  ' EMERGENCY_STOP
    ' Safe recovery actions
    Off ioGripper  ' Release gripper
    Motor Off      ' Safety stop
Fend

Function DoWhereTask
    Print "[DoWhereTask]"
    String sX$, sY$, sZ$, sU$
    sX$ = Str$(CX(Here))
    sY$ = Str$(CY(Here))
    sZ$ = Str$(CZ(Here))
    sU$ = Str$(CU(Here))
    SendMsg$ = "position X:" + sX$ + " Y:" + sY$ + " Z:" + sZ$ + " U:" + sU$
    Call SendResponse(SendMsg$)
Fend
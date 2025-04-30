'====================================================================
' TCP CONTROL V3.1
'====================================================================

' Global variables for state machine
Global Integer RobotState   ' 0=DISCONNECTED, 1=IDLE, 2=MOVING, 3=INSERTING, 4=TESTING, 5=EMERGENCY
Global Real RobotSpeed      ' Speed factor (1-100)
Global Boolean StopRequested

' Movement parameters
Global Real MoveX, MoveY, MoveZ
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
' State Management Function
'====================================================================
Function SetRobotState(ByVal state As Integer)
    RobotState = state
    Select RobotState
        Case 0
            Print "[SetRobotState] State set to DISCONNECTED"
        Case 1
            Print "[SetRobotState] State set to IDLE"
        Case 2
            Print "[SetRobotState] State set to MOVING"
        Case 3
            Print "[SetRobotState] State set to INSERTING"
        Case 4
            Print "[SetRobotState] State set to TESTING"
        Case 5
            Print "[SetRobotState] State set to EMERGENCY"
    Send
Fend

'--- ENTRY POINT ---------------------------------------------------
Function Main
    ' Initialize robot
    Motor On
    Power High
    SpeedFactor 10
    Speed 20; Accel 50, 50
    SpeedS 20; AccelS 50, 50
    Off ioGripper
    Off ioFeeder
 
    ' Initialize variables
    SetRobotState 1      ' IDLE state
    RobotSpeed = 20    ' Default speed
    QueueSize = 0
    CurrentIndex = 0
    JumpHeight = 0     ' Default jump height
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
    SetRobotState 0  ' DISCONNECTED
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
    SetRobotState 0  ' DISCONNECTED
    EResume Connect
Fend

'====================================================================
' NetworkManager Functions
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
                    If RobotState = 1 Then  ' Only if IDLE
                        ' Format: move x y z
                        If NumTokens = 4 Then  ' Only if IDLE
                            MoveX = Val(Tokens$(1))
                            MoveY = Val(Tokens$(2))
                            MoveZ = Val(Tokens$(3))
                            SetRobotState 2  ' MOVING
                            Signal 10  ' Signal OperationProcessor to start working
                        Else
                            Print "ERROR bad NumTokens"
                        EndIf
                    Else
                        Print "[ProcessReceivedMessage] WARNING robot busy" + Str$(RobotState)
                    EndIf
                
                Case "queue"
                    ClearQueue
                    ' Format: queue x1 y1 x2 y2 ... xN yN
                    If RobotState = 1 And (NumTokens - 1) Mod 2 = 0 Then  ' Only if IDLE
                        QueueSize = (NumTokens - 1) / 2
                        If QueueSize > 300 Then QueueSize = 300  ' Limit to 300 points
                        
                        Integer i
                        For i = 0 To QueueSize - 1
                            CoordinateQueue$(i, 0) = Tokens$(i*2 + 1)  ' X
                            CoordinateQueue$(i, 1) = Tokens$(i*2 + 2)  ' Y
                        Next i
                        
                        CurrentIndex = 0
                        SendResponse "QUEUE_SET"
                        Print "[ProcessReceivedMessage] Queued ", QueueSize, " coordinates"
                    Else
                        Print "[ProcessReceivedMessage] WARNING robot busy" + Str$(RobotState)
                    EndIf
                
                Case "insert"
                    If RobotState = 1 Then  ' Only if IDLE
                        SetRobotState 3  ' INSERTING
                        Signal 10  ' Signal OperationProcessor to start working
                    Else
                        Print "[ProcessReceivedMessage] WARNING robot busy" + Str$(RobotState)
                    EndIf
                
                Case "test"
                    If RobotState = 1 Then  ' Only if IDLE
                        SetRobotState 4  ' TESTING
                        Pause
                        Signal 10  ' Signal OperationProcessor to start working
                    Else
                        Print "[ProcessReceivedMessage] WARNING robot busy" + Str$(RobotState)
                    EndIf
                
                Case "speed"
                    If NumTokens = 2 And RobotState = 1 Then  ' Only if IDLE
                        Real newSpeed
                        newSpeed = Val(Tokens$(1))
                        If newSpeed >= 1 And newSpeed <= 100 Then
                            RobotSpeed = newSpeed
                            SpeedFactor RobotSpeed
                            SendResponse "SPEED_SET " + Str$(RobotSpeed)
                            Print "[ProcessReceivedMessage] Speed changed to ", RobotSpeed
                        Else
                            Print "ERROR invalid_speed_value"
                        EndIf
                    Else
                        Print "ERROR speed failed"
                    EndIf
                
                Case "stop"
                    DoStopTask
                
                Default
                    Print "ERROR unknown_command"
                    Print "[ProcessReceivedMessage] Unknown Command: ", cmd$
            Send
        Else
            Print "ERROR empty_command"
        EndIf
    EndIf
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
        
        ' Process operation based on state
        Print "[OperationProcessor] Processing state ", RobotState
        
        Select RobotState
            Case 2  ' MOVING
                Print "[OperationProcessor] Moving to position: (", MoveX, ", ", MoveY, ", ", MoveZ, ")"
                Jump XY(MoveX, MoveY, MoveZ, CU(CurPos)) /L
                SendResponse "POSITION_REACHED"
                SetRobotState 1  ' Return to IDLE
            
            Case 3  ' INSERTING
                ' Process queue until it's empty or stopped
                Do While CurrentIndex < QueueSize
                    Print "[OperationProcessor] Processing item ", CurrentIndex + 1, "/", QueueSize
                    
                    DoInsert(CurrentIndex)
                    
                    ' Increment index
                    CurrentIndex = CurrentIndex + 1

                    If StopRequested Then
                        Print "[OperationProcessor] Stop requested"
                        Exit Do
                    EndIf
                Loop
                
                If StopRequested Then
                    Print "robot stopped"
                Else
                    ' Queue is complete
                    Print "[OperationProcessor] Queue completed"
                    
                    ' Reset queue
                    QueueSize = 0
                    CurrentIndex = 0
                    SendResponse "INSERT_DONE"
                EndIf
                SetRobotState 1  ' Return to IDLE
            
            Case 4  ' TESTING
                ' Process queue until it's empty or stopped
                Do While CurrentIndex < QueueSize
                    Print "[OperationProcessor] Processing item ", CurrentIndex + 1, "/", QueueSize
                    
                    DoTest(CurrentIndex)
                    
                    ' Increment index
                    CurrentIndex = CurrentIndex + 1

                    If StopRequested Then
                        Print "[OperationProcessor] Stop requested"
                        Exit Do
                    EndIf
                Loop
                
                If StopRequested Then
                    Print "robot stopped"
                Else
                    ' Queue is complete
                    Print "[OperationProcessor] Queue completed"
                    
                    ' Reset queue
                    QueueSize = 0
                    CurrentIndex = 0
                    SendResponse "TEST_DONE"
                EndIf
                SetRobotState 1  ' Return to IDLE
        Send
    Loop
Fend

'====================================================================
' Operation Functions
'====================================================================
Function DoInsert(ByVal index As Integer)
    Pause
    MoveX = Val(CoordinateQueue$(index, 0))
    MoveY = Val(CoordinateQueue$(index, 1))
    Print "[DoInsert] Inserting at: (", MoveX, ", ", MoveY, ")"

    Jump pFeederReceive -Y(12) LimZ -18
    Go pFeederReceive
    On ioGripper
    Go pFeederReceive -Y(12)
    On ioFeeder
    Wait 0.1
    Off ioFeeder
    Jump XY(MoveX, MoveY, -150, 0) /L LimZ -18
    Off ioGripper
    ' Wait 0.2
    ' Go XY(MoveX, MoveY, -150, 0) /L -Y(40)
Fend

Function DoTest(ByVal index As Integer)
    Pause
    MoveX = Val(CoordinateQueue$(index, 0))
    MoveY = Val(CoordinateQueue$(index, 1))
    Print "[DoTest] Testing at: (", MoveX, ", ", MoveY, ")"

    ' Move to position
    Jump XY(MoveX, MoveY, -100, 0) /L LimZ -50
Fend

Function DoStopTask
    StopRequested = True
    SetRobotState 1  ' IDLE
    QueueSize = 0
    CurrentIndex = 0
    
    ' Emergency stop turn motor off and on if needed
    
    SendResponse "STOPPED"
    Print "[DoStopTask] Robot stopped"
Fend

Function ClearQueue
    ' Clear queue data
    QueueSize = 0
    CurrentIndex = 0

    Integer i
    For i = 0 To 499
        CoordinateQueue$(i, 0) = ""
        CoordinateQueue$(i, 1) = ""
        CoordinateQueue$(i, 2) = ""
    Next i
Fend

' Server-Side Program for Non-blocking Messaging and Task Execution
' 2025-02-11

Global Preserve Integer CommandReady  ' Flag to indicate if a command is ready
Global Integer NumTokens
Global String RecvMsg$, SendMsg$
Global Real MoveX, MoveY, MoveZ, MoveU, JumpZ
Global String RobotCommand$

Function main
    ' Initialize TCP server
    Call TcpIpServer
Fend

Function TcpIpServer
    OnErr GoTo ErrHandle
    SetNet #201, "192.168.0.1", 8501, CRLF

   	Motor On
	Power High
	SpeedFactor 20
	Speed 100; Accel 100, 100
	SpeedS 100; AccelS 100, 100
	Off ioGripper
	Off ioFeeder

Connect:
    OpenNet #201 As Server
    WaitNet #201, 10  ' Wait for client connection (timeout)
    If TW Then Print "[TcpIpServer] Connection Timeout. Retrying..."; GoTo Connect
    Print "[TcpIpServer] Client Connected"
    
    Do
        Call RecvCommand
        If CommandReady Then
            Call ProcessCommand
        EndIf
        Wait 0.1
    Loop

ErrHandle:
	Print "[TcpIpServer] ERROR: Error number ", Err, ". Error Message is ", ErrMsg$(Err)
    Print "[TcpIpServer] Reconnecting..."
    EResume Connect
Fend

Function RecvCommand
    Input #201, RecvMsg$
    If RecvMsg$ <> "" Then
    
        ' Print "[RecvCommand] Received: ", RecvMsg$
        String Tokens$(0)
        
        NumTokens = ParseStr(RecvMsg$, Tokens$(), " ")
        
        If NumTokens >= 1 Then
            RobotCommand$ = Tokens$(0)
            If NumTokens = 1 Then
            	CommandReady = 1
            	Print "[RecvCommand] Command Parsed: ", RobotCommand$
            	SendMsg$ = "ack"
    			Call SendResponse
    			
            ElseIf NumTokens = 5 Then
                MoveX = Val(Tokens$(1))
                MoveY = Val(Tokens$(2))
                MoveZ = Val(Tokens$(3))
                MoveU = Val(Tokens$(4))
                CommandReady = 1
                Print "[RecvCommand] Command Parsed: ", RobotCommand$, "(", MoveX, ", ", MoveY, ", ", MoveZ, ", ", MoveU, ")"
                SendMsg$ = "ack"
    			Call SendResponse
	
            ElseIf NumTokens = 6 Then
                MoveX = Val(Tokens$(1))
                MoveY = Val(Tokens$(2))
                MoveZ = Val(Tokens$(3))
                MoveU = Val(Tokens$(4))
                JumpZ = Val(Tokens$(5))
                CommandReady = 1
                Print "[RecvCommand] Command Parsed: ", RobotCommand$, "(", MoveX, ", ", MoveY, ", ", MoveZ, ", ", MoveU, "), LimZ: ", JumpZ
                SendMsg$ = "ack"
    			Call SendResponse
    			
            Else
                Print "[RecvCommand] Invalid Command Format"
                SendMsg$ = "Invalid format"
    			Call SendResponse
            EndIf
        Else
            Print "[RecvCommand] Empty or Invalid Message"
            SendMsg$ = "Invalid msg"
    		Call SendResponse
        EndIf
    EndIf
Fend

Function ProcessCommand
    ' Print "[ProcessCommand] Acknowledged Command: ", RobotCommand$

    Select Case RobotCommand$
    	' TODO: add move
    	Case "insert"
    		Call DoInsertTask
    	Case "move"
    		Call DoMoveTask
    	Case "jump"
    		If NumTokens = 5 Then
	    		Call DoJumpTask
	    	ElseIf NumTokens = 6 Then
	    		Call DoJumpZTask
	    	EndIf
        Case "echo"
        	Call DoEchoTask
        Case "where"
        	Call DoWhereTask
        Default
        	Call TaskFailure
            Print "[ProcessCommand] Unknown Command: ", RobotCommand$
    Send

Fend

Function SendResponse
    Print #201, SendMsg$
    Print "[SendResponse] Sent: ", SendMsg$
    Wait 0.1
Fend

Function TaskSuccess
    SendMsg$ = "taskdone"
    Call SendResponse
    CommandReady = 0
Fend

Function TaskFailure
    SendMsg$ = "taskfailed"
    Call SendResponse
    ' CommandReady = 0
Fend

Function DoInsertTask
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
    Call TaskSuccess
Fend

Function DoMoveTask
	' TODO: not needed for now
    Wait 2
    Call TaskFailure
Fend

Function DoJumpTask
	Print "[DoJumpTask] Jump XY(", MoveX, ", ", MoveY, ", ", MoveZ, ", ", MoveU, ") /L LimZ 0"
	Jump XY(MoveX, MoveY, MoveZ, MoveU) /L LimZ 0
	Wait 0.2
	Call TaskSuccess
Fend

Function DoJumpZTask
	Print "[DoJumpTask] Jump XY(", MoveX, ", ", MoveY, ", ", MoveZ, ", ", MoveU, ") /L LimZ ", JumpZ
	Jump XY(MoveX, MoveY, MoveZ, MoveU) /L LimZ JumpZ
	Wait 0.2
	Call TaskSuccess
Fend

Function DoEchoTask
	Print "[DoEchoTask]"
    SendMsg$ = RecvMsg$
    Call SendResponse
    Call TaskSuccess
Fend

Function DoWhereTask
	Print "[DoWhereTask]"
	String sX$, sY$, sZ$, sU$, sPoint$
	sX$ = Str$(CX(Here))
	sY$ = Str$(CY(Here))
	sZ$ = Str$(CZ(Here))
	sU$ = Str$(CU(Here))
	SendMsg$ = "X: " + sX$ + ", Y: " + sY$ + ", Z: " + sZ$ + ", U: " + sU$
	Call SendResponse
	Call TaskSuccess
Fend
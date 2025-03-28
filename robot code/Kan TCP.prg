#define IPAddress$ "192.168.1.111"
#define IPPortNum 8501
#define ConnectingTimeOut 10

Global String RecvPLC$, SendPLC$, Tokens$(0)
Global Integer NumChar
Global Real OffsetX, OffsetY, OffsetZ, OffsetU, OffsetV, OffsetW, Result

Function main

	Print "======================================"
	Print "Project Name:TCPIP Program"
	Print "Robot Programmer:Kan Chen"
	Print "Version:V1.0"
	Print "======================================"
	Print ""
	
	If Motor = Off Then Motor On
	Power High
	SpeedFactor 100
	Speed 30; Accel 30, 30
	SpeedS 100; AccelS 100, 100
	Print "motor and speed setting finish"
	Print ""
	
	Xqt PLCCommunication, NoEmgAbort
	
Do

StartPLC:
	If Result <> 1 Then GoTo StartPLC
	Move Here + XY(OffsetX, OffsetY, OffsetZ, OffsetU, OffsetV, OffsetW)
	Print Here
	Result = 0
	
Loop

Fend
Function PLCCommunication
	
	OnErr GoTo ErrHandle
	
	SetNet #201, IPAddress$, IPPortNum, CRLF
	
Connect:
	OpenNet #201 As Server
'	OpenNet #201 As Client
	WaitNet #201, ConnectingTimeOut
		If TW Then Print "Net Connection Error, Reset Connection"; GoTo Connect
	Print "Net Connection Successfully"
	Print ""
	
Do
	
StartPLC:

	Call RecvCommand
	ParseStr RecvPLC$, Tokens$(), Space$(1)
WaitRecvClean:
	If Result = 1 Then GoTo WaitRecvClean
	
	Call CreatCommand
	Call SendCommand

Loop

ErrHandle:
	EResume StartPLC
	
Fend
Function CreatCommand
	
	SendPLC$ = "X:" + Str$(CX(Here)) + ",Y:" + Str$(CY(Here)) + ",Z:" + Str$(CZ(Here)) + ",U:" + Str$(CU(Here)) + ",V:" + Str$(CV(Here)) + ",W:" + Str$(CW(Here))
	
Fend
Function SendCommand
	
	Print #201, SendPLC$
	NumChar = 0
	
	Do
		NumChar = ChkNet(201)
		Wait 0.01
	Loop While NumChar < ChkNet(201) Or NumChar = 0
	
Fend
Function RecvCommand
	
	Input #201, RecvPLC$
	
	If Left$(RecvPLC$, 1) = "E1" Then
		Error 8000
	EndIf
	
	ParseStr RecvPLC$, Tokens$(), "//" 'Space$(1)
	OffsetX = Val(Tokens$(0))
	OffsetY = Val(Tokens$(1))
	OffsetZ = Val(Tokens$(2))
	OffsetU = Val(Tokens$(3))
	OffsetV = Val(Tokens$(4))
	OffsetW = Val(Tokens$(5))
	Result = Val(Tokens$(6))
	Print "OffsetX:", OffsetX, ", OffsetY:", OffsetY, ", OffsetZ:", OffsetZ, ", OffsetU:", OffsetU, ", OffsetV:", OffsetV, ", OffsetW:", OffsetW, ", Result:", Result
	
Fend
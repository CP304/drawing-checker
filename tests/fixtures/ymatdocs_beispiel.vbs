If Not IsObject(application) Then
   Set SapGuiAuto  = GetObject("SAPGUI")
   Set application = SapGuiAuto.GetScriptingEngine
End If
If Not IsObject(connection) Then
   Set connection = application.Children(0)
End If
If Not IsObject(session) Then
   Set session    = connection.Children(0)
End If
If IsObject(WScript) Then
   WScript.ConnectObject session,     "on"
   WScript.ConnectObject application, "on"
End If
session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nYMATDOCS"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/ctxtS_MATNR-LOW").text = "10473215"
session.findById("wnd[0]/usr/ctxtS_MATNR-HIGH").text = "10473215"
session.findById("wnd[0]/usr/ctxtP_WERKS").text = "1000"
session.findById("wnd[0]/usr/chkP_STEP").selected = true
session.findById("wnd[0]/usr/ctxtS_MATNR-LOW").caretPosition = 8
session.findById("wnd[0]").sendVKey 8
session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").pressToolbarButton "DOWNLOAD"
session.findById("wnd[1]/usr/ctxtDY_PATH").text = "C:\temp\ymatdocs"
session.findById("wnd[1]/usr/ctxtDY_FILENAME").text = "10473215.zip"
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/tbar[0]/btn[15]").press

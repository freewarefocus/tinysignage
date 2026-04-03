' TinySignage BrightSign Autorun
' Loads the TinySignage player in an HTML widget.
' Place this file and config.json on the SD card root.
'
' config.json format:
' {
'   "server_url": "http://YOUR_SERVER_IP:8080",
'   "display_name": "Lobby Display"
' }

sub Main()
    ' Read configuration from SD card
    configPath = "SD:/config.json"
    serverUrl = "http://localhost:8080"
    displayName = "BrightSign Player"

    if CreateObject("roFilesystem").Exists(configPath) then
        configFile = CreateObject("roReadFile", configPath)
        configJson = ""
        while not configFile.AtEof()
            configJson = configJson + configFile.ReadLine()
        end while
        configFile.Close()

        config = ParseJson(configJson)
        if config <> invalid then
            if config.server_url <> invalid then serverUrl = config.server_url
            if config.display_name <> invalid then displayName = config.display_name
        end if
    end if

    ' Strip trailing slash from server URL
    if Right(serverUrl, 1) = "/" then
        serverUrl = Left(serverUrl, Len(serverUrl) - 1)
    end if

    ' Set up video mode — auto-detect display resolution
    videoMode = CreateObject("roVideoMode")
    videoMode.SetMode("auto")

    ' Create message port for event handling
    msgPort = CreateObject("roMessagePort")

    ' Create full-screen HTML widget pointing at TinySignage player
    rect = CreateObject("roRectangle", 0, 0, videoMode.GetResX(), videoMode.GetResY())
    widgetConfig = {
        hwz: "on",
        url: serverUrl + "/player?name=" + displayName,
        security_params: {
            websecurity: "off",
            camera_enabled: false,
            insecure_https_enabled: true
        },
        mouse_enabled: false,
        storage_path: "SD:/tinysignage-cache/",
        storage_quota: 512 * 1024 * 1024
    }

    htmlWidget = CreateObject("roHtmlWidget", rect, widgetConfig)
    htmlWidget.SetPort(msgPort)

    ' Enable hardware-accelerated video playback
    htmlWidget.EnableMouseEvents(false)
    htmlWidget.SetAlpha(255)

    ' Event loop — keep the player running
    while true
        msg = Wait(0, msgPort)
        if type(msg) = "roHtmlWidgetEvent" then
            eventData = msg.GetData()
            ' Handle page load failures — retry after delay
            if type(eventData) = "roAssociativeArray" then
                if eventData.reason <> invalid then
                    ' Network error or page load failure — wait and reload
                    Sleep(10000)
                    htmlWidget.SetUrl(serverUrl + "/player?name=" + displayName)
                end if
            end if
        end if
    end while
end sub

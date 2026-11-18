' Entry point. Launched with the `test` param (e.g. `rce launch <device> --param test=run1`),
' the app prints the test log lines described in the README, each tagged with that value.
' Launched with `stop=1`, it breaks into the BrightScript debugger when OK is pressed on a
' tile (README "Debugging").
sub Main(args as Object)
    screen = CreateObject("roSGScreen")
    port = CreateObject("roMessagePort")
    screen.SetMessagePort(port)

    testTag = ""
    if args.test <> invalid then testTag = args.test
    stopOnSelect = false
    if args.stop <> invalid then stopOnSelect = (args.stop = "1")
    screen.GetGlobalNode().AddFields({ testTag: testTag, stopOnSelect: stopOnSelect })

    screen.CreateScene("MainScene")
    screen.Show()

    while true
        msg = Wait(0, port)
        if type(msg) = "roSGScreenEvent" and msg.IsScreenClosed() then return
    end while
end sub

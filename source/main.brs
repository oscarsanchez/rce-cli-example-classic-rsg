' Entry point. Launched with the `test` param (e.g. `rce launch <device> --param test=run1`),
' the app prints the test log lines described in the README, each tagged with that value.
sub Main(args as Object)
    screen = CreateObject("roSGScreen")
    port = CreateObject("roMessagePort")
    screen.SetMessagePort(port)

    testTag = ""
    if args.test <> invalid then testTag = args.test
    screen.GetGlobalNode().AddFields({ testTag: testTag })

    screen.CreateScene("MainScene")
    screen.Show()

    while true
        msg = Wait(0, port)
        if type(msg) = "roSGScreenEvent" and msg.IsScreenClosed() then return
    end while
end sub

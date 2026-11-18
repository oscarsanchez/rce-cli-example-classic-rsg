sub init()
    m.top.backgroundColor = "0x101820FF"
    m.top.backgroundURI = ""
    m.testTag = m.global.testTag
    m.home = m.top.findNode("home")
    m.details = m.top.findNode("details")
    m.player = m.top.findNode("player")

    catalog = ParseCatalog(ReadAsciiFile("pkg:/data/catalog.json"))
    if catalog = invalid
        print "sample: pkg:/data/catalog.json is not a valid catalog"
        return
    end if
    m.home.content = GridContent(catalog)
    m.item = m.home.content.GetChild(0).GetChild(0)

    m.home.observeField("rowItemFocused", "onGridFocused")
    m.home.observeField("rowItemSelected", "onGridSelected")
    m.details.observeField("playSelected", "onPlaySelected")
    m.player.observeField("state", "onPlayerState")

    showScreen("home")
    print ReadyLine(m.testTag)
end sub

' The RowList's content: one row node per catalog row, one item node per item.
function GridContent(catalog as Object) as Object
    root = CreateObject("roSGNode", "ContentNode")
    for each row in catalog.rows
        rowNode = root.CreateChild("ContentNode")
        rowNode.title = row.title
        for each item in row.items
            itemNode = rowNode.CreateChild("ContentNode")
            itemNode.id = item.id
            itemNode.title = item.title
            itemNode.description = item.description
            itemNode.length = item.durationSeconds
            itemNode.url = catalog.stream.url
            itemNode.streamFormat = catalog.stream.format
            itemNode.AddFields({ color: row.color })
        end for
    end for
    return root
end function

sub showScreen(name as String)
    m.screen = name
    m.lastFocusLine = ""
    m.home.visible = (name = "home")
    m.details.visible = (name = "details")
    m.player.visible = (name = "player")
    ' The open line comes before any focus line the new focus causes.
    testLog(OpenLine(m.testTag, name, m.item.id))
    if name = "home" then m.home.setFocus(true)
    if name = "details" then m.details.setFocus(true)
    if name = "player" then m.player.setFocus(true)
    if name = "home" then logGridFocus()
end sub

sub onGridFocused()
    if m.screen <> "home" then return
    m.item = focusedGridItem()
    logGridFocus()
end sub

sub onGridSelected()
    m.item = focusedGridItem()
    m.details.content = m.item
    showScreen("details")
end sub

sub onPlaySelected()
    video = CreateObject("roSGNode", "ContentNode")
    video.title = m.item.title
    video.url = m.item.url
    video.streamFormat = m.item.streamFormat
    m.player.content = video
    showScreen("player")
    m.player.control = "play"
end sub

sub onPlayerState()
    state = m.player.state
    testLog(PlaybackLine(m.testTag, state, m.item.id))
    if (state = "finished" or state = "error") and m.screen = "player" then closePlayer()
end sub

sub closePlayer()
    m.player.control = "stop"
    showScreen("details")
end sub

function focusedGridItem() as Object
    rc = gridFocus()
    return m.home.content.GetChild(rc[0]).GetChild(rc[1])
end function

' [row, col] of the focused tile; [0, 0] before the RowList has reported one.
function gridFocus() as Object
    rc = m.home.rowItemFocused
    if rc = invalid or rc.Count() < 2 or rc[0] < 0 or rc[1] < 0 then return [0, 0]
    return rc
end function

' One focus line per change: the RowList can report the same position more than once.
sub logGridFocus()
    rc = gridFocus()
    line = FocusLine(m.testTag, "home", rc[0], rc[1], focusedGridItem().id)
    if line = m.lastFocusLine then return
    m.lastFocusLine = line
    testLog(line)
end sub

sub testLog(line as String)
    if m.testTag <> "" then print line
end sub

function onKeyEvent(key as String, press as Boolean) as Boolean
    if not press or key <> "back" then return false
    if m.screen = "player"
        closePlayer()
        return true
    end if
    if m.screen = "details"
        showScreen("home")
        return true
    end if
    return false
end function

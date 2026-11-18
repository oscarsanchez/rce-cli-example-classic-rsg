sub init()
    m.buttons = m.top.findNode("buttons")
    m.buttons.buttons = ["Play"]
    m.buttons.observeField("buttonSelected", "onButtonSelected")
    m.top.observeField("focusedChild", "onFocusedChild")
end sub

sub onContent()
    item = m.top.content
    m.top.findNode("art").color = item.color
    m.top.findNode("title").text = item.title
    m.top.findNode("duration").text = FormatDuration(item.length)
    m.top.findNode("description").text = item.description
end sub

sub onButtonSelected()
    m.top.playSelected = true
end sub

' Focus given to the screen goes to the Play button.
sub onFocusedChild()
    if m.top.hasFocus() then m.buttons.setFocus(true)
end sub

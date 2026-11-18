sub init()
    m.grid = m.top.findNode("grid")
    m.top.observeField("focusedChild", "onFocusedChild")
end sub

' Focus given to the screen goes to the grid, which keeps its own position.
sub onFocusedChild()
    if m.top.hasFocus() then m.grid.setFocus(true)
end sub

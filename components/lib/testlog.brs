' The console lines the app prints, as plain functions that build the text.
' The format is a contract with the UI tests: see "Console log lines" in the README.
' tag is the value of the `test` launch param ("" when the app was launched without it).

function ReadyLine(tag as String) as String
    if tag = "" then return "sample: ready"
    return lineStart("ready", tag)
end function

function OpenLine(tag as String, screen as String, itemId as String) as String
    return lineStart("open", tag) + " screen=" + screen + " item=" + itemId
end function

function FocusLine(tag as String, screen as String, row as Integer, col as Integer, itemId as String) as String
    return lineStart("focus", tag) + " screen=" + screen + " row=" + row.ToStr() + " col=" + col.ToStr() + " item=" + itemId
end function

function PlaybackLine(tag as String, state as String, itemId as String) as String
    return lineStart("playback", tag) + " state=" + state + " item=" + itemId
end function

' Every tagged line starts "sample: <event> test=<tag>".
function lineStart(event as String, tag as String) as String
    return "sample: " + event + " test=" + tag
end function

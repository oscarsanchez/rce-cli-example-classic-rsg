' Catalog parsing and formatting: plain functions, no nodes and no globals,
' so unit tests can call them directly.

' Parses the catalog JSON text (see data/catalog.json). Returns
'   { stream: { url, format }, rows: [ { title, color, items: [ { id, title, description, durationSeconds } ] } ] }
' or invalid when the text is not JSON or has no stream URL or rows.
' Items without an id or a title are left out, and so are rows left with no items.
function ParseCatalog(text as String) as Object
    data = ParseJson(text)
    if type(data) <> "roAssociativeArray" then return invalid
    if type(data.stream) <> "roAssociativeArray" or not IsNonEmptyString(data.stream.url) then return invalid
    if type(data.rows) <> "roArray" then return invalid

    format = "hls"
    if IsNonEmptyString(data.stream.format) then format = data.stream.format

    rows = []
    for each row in data.rows
        if type(row) = "roAssociativeArray" and type(row.items) = "roArray"
            items = []
            for each item in row.items
                if type(item) = "roAssociativeArray" and IsNonEmptyString(item.id) and IsNonEmptyString(item.title)
                    items.Push({
                        id: item.id,
                        title: item.title,
                        description: StringOr(item.description, ""),
                        durationSeconds: SecondsOr(item.durationSeconds, 0)
                    })
                end if
            end for
            if items.Count() > 0
                rows.Push({ title: StringOr(row.title, ""), color: StringOr(row.color, "0x404040FF"), items: items })
            end if
        end if
    end for
    if rows.Count() = 0 then return invalid
    return { stream: { url: data.stream.url, format: format }, rows: rows }
end function

' 596 -> "9:56", 3725 -> "1:02:05", 0 or less -> "0:00".
function FormatDuration(seconds as Integer) as String
    if seconds < 0 then seconds = 0
    hours = seconds \ 3600
    minutes = (seconds mod 3600) \ 60
    secs = Right("0" + (seconds mod 60).ToStr(), 2)
    if hours > 0 then return hours.ToStr() + ":" + Right("0" + minutes.ToStr(), 2) + ":" + secs
    return minutes.ToStr() + ":" + secs
end function

function IsNonEmptyString(value as Dynamic) as Boolean
    return (type(value) = "roString" or type(value) = "String") and value <> ""
end function

function StringOr(value as Dynamic, fallback as String) as String
    if type(value) = "roString" or type(value) = "String" then return value
    return fallback
end function

' A JSON number as whole seconds, or the fallback for anything else.
function SecondsOr(value as Dynamic, fallback as Integer) as Integer
    t = type(value)
    if t = "Integer" or t = "roInt" or t = "roInteger" or t = "LongInteger" or t = "roLongInteger" then return value
    if t = "Float" or t = "roFloat" or t = "Double" or t = "roDouble" then return Int(value)
    return fallback
end function

sub onItemContent()
    item = m.top.itemContent
    m.top.findNode("tile").color = item.color
    m.top.findNode("title").text = item.title
end sub

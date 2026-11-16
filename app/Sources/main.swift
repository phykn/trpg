import AppKit

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)

let menu = NSMenu()
for (title, items) in [
    ("TRPG", [("Hide TRPG", #selector(NSApplication.hide(_:)), "h"), ("Quit TRPG", #selector(NSApplication.terminate(_:)), "q")]),
    ("Window", [("Minimize", #selector(NSWindow.performMiniaturize(_:)), "m"), ("Close", #selector(NSWindow.performClose(_:)), "w")]),
] {
    let item = NSMenuItem(), sub = NSMenu(title: title)
    for (name, action, key) in items { sub.addItem(withTitle: name, action: action, keyEquivalent: key) }
    item.submenu = sub
    menu.addItem(item)
}
app.mainMenu = menu
app.run()

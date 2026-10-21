import AppKit

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)

let menu = NSMenu()
func submenu(_ title: String, _ items: [(String, Selector, String)]) {
    let item = NSMenuItem(), sub = NSMenu(title: title)
    for (name, action, key) in items { sub.addItem(withTitle: name, action: action, keyEquivalent: key) }
    item.submenu = sub
    menu.addItem(item)
}
submenu("TRPG", [
    ("Hide TRPG", #selector(NSApplication.hide(_:)), "h"),
    ("Quit TRPG", #selector(NSApplication.terminate(_:)), "q"),
])
submenu("Window", [
    ("Minimize", #selector(NSWindow.performMiniaturize(_:)), "m"),
    ("Close", #selector(NSWindow.performClose(_:)), "w"),
])
app.mainMenu = menu
app.run()
